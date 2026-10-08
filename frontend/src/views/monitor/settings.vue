<template>
  <n-result v-if="!isAdmin" class="access-denied" status="403" title="无访问权限" description="仅系统管理员可以维护监控检查频率。" />
  <section v-else class="monitor-settings">
    <header class="page-header">
      <div><h2>监控设置</h2><p>统一设置监控目标与服务监控的后台检查频率。</p></div>
      <n-button :loading="running" @click="runNow">立即执行一次</n-button>
    </header>

    <n-spin :show="loading">
      <div class="settings-panel">
        <div class="setting-row">
          <div class="setting-copy">
            <strong>监控目标检查频率</strong>
            <p>平台按此频率查询 Prometheus 指标，并判断 CPU、内存、磁盘和主机状态告警。</p>
            <span>最近检查：{{ formatTime(form.last_target_check_at) }}</span>
          </div>
          <n-select v-model:value="form.target_check_interval_seconds" class="interval-select" :options="intervalOptions" />
        </div>
        <div class="setting-row">
          <div class="setting-copy">
            <strong>服务监控检查频率</strong>
            <p>平台按此频率执行 HTTP、TCP 和 Docker 服务检查，并处理异常与恢复通知。</p>
            <span>最近检查：{{ formatTime(form.last_service_check_at) }}</span>
          </div>
          <n-select v-model:value="form.service_check_interval_seconds" class="interval-select" :options="intervalOptions" />
        </div>
        <div class="settings-note">
          <strong>后台独立运行</strong>
          <span>保存后由任务 Worker 按频率执行，无需保持监控台页面打开。测试环境暂不使用时，可将对应检查设置为关闭。</span>
        </div>
        <footer class="panel-footer">
          <span v-if="form.updated_at">最近更新：{{ formatTime(form.updated_at) }}<template v-if="form.updated_by_name"> · {{ form.updated_by_name }}</template></span>
          <n-button type="primary" :loading="saving" @click="save">保存设置</n-button>
        </footer>
      </div>
    </n-spin>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useMessage } from 'naive-ui';
import { MonitorAPI, type MonitorCheckSettings } from '@/api/monitor/http';
import { useUserStore } from '@/store/modules/user';
import { formatDateTime } from '@/utils/time';

const message = useMessage();
const userStore = useUserStore();
const isAdmin = computed(() => Boolean((userStore.info as any)?.is_admin));
const loading = ref(false);
const saving = ref(false);
const running = ref(false);
const form = reactive<MonitorCheckSettings>({ target_check_interval_seconds: 60, service_check_interval_seconds: 60 });
const intervalOptions = [
  { label: '不检查', value: 0 },
  { label: '每 1 分钟', value: 60 },
  { label: '每 2 分钟', value: 120 },
  { label: '每 5 分钟', value: 300 },
  { label: '每 10 分钟', value: 600 },
  { label: '每 15 分钟', value: 900 },
  { label: '每 30 分钟', value: 1800 },
  { label: '每 1 小时', value: 3600 },
];
const formatTime = (value?: string | null) => formatDateTime(value, { empty: '尚未执行' });
const load = async () => { loading.value = true; try { Object.assign(form, await MonitorAPI.checkSettings()); } catch (error: any) { message.error(error?.message || '监控设置加载失败'); } finally { loading.value = false; } };
const save = async () => { saving.value = true; try { Object.assign(form, await MonitorAPI.updateCheckSettings({ ...form })); message.success('监控检查频率已保存'); } catch (error: any) { message.error(error?.message || '保存失败'); } finally { saving.value = false; } };
const runNow = async () => { running.value = true; try { await MonitorAPI.runChecksNow(); message.success('监控检查已执行'); await load(); } catch (error: any) { message.error(error?.message || '执行检查失败'); } finally { running.value = false; } };
onMounted(() => { if (isAdmin.value) void load(); });
</script>

<style scoped lang="less">
.access-denied{display:flex;min-height:calc(100vh - 150px);flex-direction:column;justify-content:center;padding:24px;box-sizing:border-box}
.monitor-settings{padding:24px 28px}.page-header{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:22px}.page-header h2{margin:0;color:#1e293b;font-size:24px}.page-header p{margin:8px 0 0;color:#7b8ba3}.settings-panel{overflow:hidden;border:1px solid #e1e7ef;border-radius:12px;background:#fff}.setting-row{display:flex;align-items:center;justify-content:space-between;gap:40px;min-height:138px;padding:26px 30px;border-bottom:1px solid #e8edf3}.setting-copy strong{color:#263449;font-size:17px}.setting-copy p{max-width:720px;margin:9px 0;color:#718098;line-height:1.7}.setting-copy span{color:#97a3b4;font-size:13px}.interval-select{width:220px;flex:0 0 220px}.settings-note{display:flex;align-items:center;gap:14px;margin:20px 30px;padding:16px 18px;border-radius:8px;background:#f2f6ff;color:#53647d}.settings-note strong{color:#315fd5;white-space:nowrap}.panel-footer{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:0 30px 24px}.panel-footer>span{color:#8a97a9;font-size:13px}@media(max-width:760px){.monitor-settings{padding:18px}.setting-row{align-items:stretch;flex-direction:column;gap:18px}.interval-select{width:100%;flex-basis:auto}.settings-note{align-items:flex-start;flex-direction:column}.panel-footer{align-items:stretch;flex-direction:column}}
</style>
