<template>
  <n-result v-if="!isAdmin" class="access-denied" status="403" title="无访问权限" description="仅系统管理员可以维护系统配置。" />
  <section v-else class="configuration-page">
    <header class="page-header">
      <div><h2>系统配置</h2><p>集中管理平台品牌、执行能力与全局保留规则</p></div>
      <n-button type="primary" :loading="saving" @click="save">保存配置</n-button>
    </header>

    <div class="configuration-notice">
      <span class="notice-mark">i</span>
      <div><strong>全局配置</strong><small>本页修改将影响整个平台，仅系统管理员可以保存</small></div>
    </div>

    <n-spin :show="loading">
      <div class="configuration-grid">
        <article class="config-card brand-card">
          <header class="card-header">
            <div class="card-index">01</div>
            <div><h3>平台 Logo</h3><p>分别配置浅色和深色背景版本，平台会跟随主题自动切换。</p></div>
          </header>
          <div class="brand-variant-list">
            <div class="brand-control">
              <div class="image-preview image-preview--light">
                <img v-if="platformLogoLightPreview" :src="platformLogoLightPreview" alt="浅色背景 Logo 预览" />
                <span v-else>TP</span>
              </div>
              <div class="brand-detail">
                <strong>浅色背景 Logo</strong>
                <span>{{ platformLogoLightFile?.name || (platformLogoLightPreview ? '当前已配置' : '未配置，使用系统默认图标') }}；建议上传深色或彩色透明图标</span>
              </div>
              <div class="card-actions">
                <input ref="platformLogoLightInput" type="file" accept="image/png,image/jpeg,image/webp,image/gif" @change="selectImage($event, 'light')" />
                <n-button @click="platformLogoLightInput?.click()">选择图片</n-button>
                <n-button v-if="platformLogoLightPreview" quaternary type="error" @click="restoreDefault('light')">清除</n-button>
              </div>
            </div>
            <div class="brand-control">
              <div class="image-preview image-preview--dark">
                <img v-if="platformLogoDarkPreview" :src="platformLogoDarkPreview" alt="深色背景 Logo 预览" />
                <img v-else-if="platformLogoLightPreview" class="fallback-preview" :src="platformLogoLightPreview" alt="深色背景 Logo 自动兜底预览" />
                <span v-else>TP</span>
              </div>
              <div class="brand-detail">
                <strong>深色背景 Logo</strong>
                <span>{{ platformLogoDarkFile?.name || (platformLogoDarkPreview ? '当前已配置' : '未配置时自动使用浅色承载底兜底') }}；建议上传白色或亮色透明图标</span>
              </div>
              <div class="card-actions">
                <input ref="platformLogoDarkInput" type="file" accept="image/png,image/jpeg,image/webp,image/gif" @change="selectImage($event, 'dark')" />
                <n-button @click="platformLogoDarkInput?.click()">选择图片</n-button>
                <n-button v-if="platformLogoDarkPreview" quaternary type="error" @click="restoreDefault('dark')">清除</n-button>
              </div>
            </div>
          </div>
          <footer class="card-note"><span class="note-dot" />PNG、JPG、WebP 或 GIF，单张最大 2 MB，建议使用正方形透明图片</footer>
        </article>

        <article class="config-card retention-card">
          <header class="card-header">
            <div class="card-index">02</div>
            <div><h3>执行报告保留</h3><p>统一控制接口执行文件、性能报告、指标明细、通知记录和运行产物的保留周期。</p></div>
          </header>
          <div class="retention-control">
            <label for="retention-days">保留时长</label>
            <div class="retention-input">
              <n-input-number id="retention-days" v-model:value="form.report_retention_days" :min="1" :max="3650" :precision="0" />
              <span>天</span>
            </div>
          </div>
          <footer class="card-note"><span class="note-dot" />每日 03:30 自动清理，执行中的任务不会被删除</footer>
        </article>

        <article class="config-card worker-card">
          <header class="card-header">
            <div class="card-index">03</div>
            <div><h3>最大 Worker 数</h3><p>控制 API、UI 和 App 自动化任务可同时使用的平台工作进程数。</p></div>
          </header>
          <div class="retention-control">
            <label for="max-worker-count">Worker 上限</label>
            <div class="retention-input">
              <n-input-number id="max-worker-count" v-model:value="form.max_worker_count" :min="1" :max="64" :precision="0" />
              <span>个</span>
            </div>
          </div>
          <footer class="card-note"><span class="note-dot" />调小后立即限制新任务；工作进程将在当前任务结束后自动调整</footer>
        </article>

        <article class="config-card worker-card">
          <header class="card-header">
            <div class="card-index">04</div>
            <div><h3>性能 Worker 数</h3><p>控制性能测试可同时启动的 k6 任务数，与 API、UI 和 App Worker 独立计算。</p></div>
          </header>
          <div class="retention-control">
            <label for="max-performance-worker-count">性能 Worker 上限</label>
            <div class="retention-input">
              <n-input-number id="max-performance-worker-count" v-model:value="form.max_performance_worker_count" :min="1" :max="32" :precision="0" />
              <span>个</span>
            </div>
          </div>
          <footer class="card-note"><span class="note-dot" />保存后对后续排队任务立即生效，已在执行的 k6 任务不受影响</footer>
        </article>
      </div>
      <div class="update-meta">
        <span v-if="form.updated_at">最近更新：{{ formatTime(form.updated_at) }}<template v-if="form.updated_by_name"> · {{ form.updated_by_name }}</template></span>
        <span v-else>尚未记录配置更新时间</span>
      </div>
    </n-spin>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import { useMessage } from 'naive-ui';
import { SystemConfigurationAPI, type SystemConfiguration } from '@/api/system/configuration';
import { useUserStore } from '@/store/modules/user';
import { initializeBranding } from '@/config/website.config';
import { formatDateTime as formatTime } from '@/utils/time';

const message = useMessage();
const userStore = useUserStore();
const isAdmin = computed(() => Boolean((userStore.info as any)?.is_admin));
const loading = ref(false);
const saving = ref(false);
const form = reactive<SystemConfiguration>({
  report_retention_days: 15,
  max_worker_count: 2,
  max_performance_worker_count: 1,
});
type LogoVariant = 'light' | 'dark';
const platformLogoLightInput = ref<HTMLInputElement | null>(null);
const platformLogoDarkInput = ref<HTMLInputElement | null>(null);
const platformLogoLightFile = ref<File | null>(null);
const platformLogoDarkFile = ref<File | null>(null);
const platformLogoLightPreview = ref('');
const platformLogoDarkPreview = ref('');
const removePlatformLogoLight = ref(false);
const removePlatformLogoDark = ref(false);
const objectUrls = new Set<string>();

function selectImage(event: Event, variant: LogoVariant) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  const allowedTypes = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'];
  if (!allowedTypes.includes(file.type)) {
    input.value = '';
    return message.warning('仅支持 PNG、JPG、WebP 或 GIF 图片');
  }
  if (file.size > 2 * 1024 * 1024) {
    input.value = '';
    return message.warning('图片大小不能超过 2 MB');
  }
  const previewUrl = URL.createObjectURL(file);
  objectUrls.add(previewUrl);
  if (variant === 'light') {
    platformLogoLightPreview.value = previewUrl;
    platformLogoLightFile.value = file;
    removePlatformLogoLight.value = false;
  } else {
    platformLogoDarkPreview.value = previewUrl;
    platformLogoDarkFile.value = file;
    removePlatformLogoDark.value = false;
  }
}

function restoreDefault(variant: LogoVariant) {
  if (variant === 'light') {
    platformLogoLightPreview.value = '';
    platformLogoLightFile.value = null;
    removePlatformLogoLight.value = true;
    if (platformLogoLightInput.value) platformLogoLightInput.value.value = '';
  } else {
    platformLogoDarkPreview.value = '';
    platformLogoDarkFile.value = null;
    removePlatformLogoDark.value = true;
    if (platformLogoDarkInput.value) platformLogoDarkInput.value.value = '';
  }
}

async function load() {
  loading.value = true;
  try {
    Object.assign(form, await SystemConfigurationAPI.detail());
    platformLogoLightPreview.value = form.platform_logo_light_url || '';
    platformLogoDarkPreview.value = form.platform_logo_dark_url || '';
  } catch (error: any) {
    message.error(error?.message || '系统配置加载失败');
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (!Number.isInteger(form.report_retention_days) || form.report_retention_days < 1 || form.report_retention_days > 3650) {
    return message.warning('保留天数必须在 1 至 3650 天之间');
  }
  if (!Number.isInteger(form.max_worker_count) || form.max_worker_count < 1 || form.max_worker_count > 64) {
    return message.warning('Worker 数必须在 1 至 64 之间');
  }
  if (!Number.isInteger(form.max_performance_worker_count) || form.max_performance_worker_count < 1 || form.max_performance_worker_count > 32) {
    return message.warning('性能 Worker 数必须在 1 至 32 之间');
  }
  saving.value = true;
  try {
    const data = new FormData();
    data.append('report_retention_days', String(form.report_retention_days));
    data.append('max_worker_count', String(form.max_worker_count));
    data.append('max_performance_worker_count', String(form.max_performance_worker_count));
    if (platformLogoLightFile.value) data.append('platform_icon', platformLogoLightFile.value);
    if (platformLogoDarkFile.value) data.append('platform_icon_dark', platformLogoDarkFile.value);
    if (removePlatformLogoLight.value) data.append('remove_platform_icon', 'true');
    if (removePlatformLogoDark.value) data.append('remove_platform_icon_dark', 'true');
    Object.assign(form, await SystemConfigurationAPI.update(data));
    platformLogoLightFile.value = null;
    platformLogoDarkFile.value = null;
    removePlatformLogoLight.value = false;
    removePlatformLogoDark.value = false;
    platformLogoLightPreview.value = form.platform_logo_light_url || '';
    platformLogoDarkPreview.value = form.platform_logo_dark_url || '';
    if (platformLogoLightInput.value) platformLogoLightInput.value.value = '';
    if (platformLogoDarkInput.value) platformLogoDarkInput.value.value = '';
    await initializeBranding();
    message.success('系统配置已保存');
  } catch (error: any) {
    message.error(error?.message || '保存失败');
  } finally {
    saving.value = false;
  }
}

onMounted(() => { if (isAdmin.value) void load(); });
onBeforeUnmount(() => objectUrls.forEach((url) => URL.revokeObjectURL(url)));
</script>

<style scoped lang="less">
.access-denied{display:flex;min-height:calc(100vh - 150px);box-sizing:border-box;flex-direction:column;justify-content:center;padding:24px}
.configuration-page{max-width:1440px;margin:0 auto;padding:22px 28px 40px;color:#263449}
.page-header{display:flex;min-height:58px;align-items:center;justify-content:space-between;gap:24px;margin-bottom:16px}.page-header h2{margin:0;color:#162033;font-size:26px;font-weight:750;line-height:1.2;letter-spacing:-.03em}.page-header p{margin:7px 0 0;color:#7b8ba3;font-size:13px}.page-header>.n-button{min-width:112px;height:38px;border-radius:7px}
.configuration-notice{display:flex;align-items:center;gap:12px;margin-bottom:16px;padding:13px 16px;border:1px solid #dbe5f3;border-left:3px solid #4f78dc;border-radius:8px;background:#f8faff}.notice-mark{display:grid;width:26px;height:26px;flex:0 0 26px;place-items:center;border-radius:7px;color:#3565d8;background:#e9f0ff;font-size:13px;font-weight:700}.configuration-notice div{display:grid;gap:3px}.configuration-notice strong{color:#344258;font-size:13px}.configuration-notice small{color:#7d8ba0;font-size:12px}
.configuration-grid{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(360px,.92fr);gap:18px}
.config-card{display:flex;min-height:282px;overflow:hidden;flex-direction:column;border:1px solid #dfe6ef;border-radius:10px;background:#fff;box-shadow:0 3px 12px rgba(36,54,84,.035);transition:border-color .2s ease,transform .2s ease,box-shadow .2s ease}.config-card:hover{border-color:#bdcce0;box-shadow:0 9px 24px rgba(36,54,84,.065);transform:translateY(-1px)}
.brand-card{min-height:424px}.brand-variant-list{display:grid;flex:1}.brand-control+.brand-control{border-top:1px solid #edf1f5}
.card-header{display:flex;align-items:flex-start;gap:14px;padding:21px 24px 18px;border-bottom:1px solid #edf1f5}.card-index{display:grid;width:36px;height:36px;flex:none;place-items:center;border-radius:8px;color:#2563eb;background:#eff6ff;font-size:11px;font-weight:700;letter-spacing:.06em}.card-header h3{margin:1px 0 0;color:#223047;font-size:17px;font-weight:650}.card-header p{max-width:620px;margin:6px 0 0;color:#7b8ba3;font-size:12px;line-height:1.65;text-wrap:pretty}
.brand-control{display:grid;grid-template-columns:72px minmax(0,1fr) auto;align-items:center;gap:18px;flex:1;padding:22px 24px}.image-preview{display:grid;width:68px;height:68px;place-items:center;overflow:hidden;border:1px solid #d9e2ef;border-radius:14px;background:#f7f9fc}.image-preview img{width:50px;height:50px;object-fit:contain}.image-preview span{display:grid;width:46px;height:46px;place-items:center;border-radius:11px;color:#fff;background:#3478e5;font-size:15px;font-weight:700}.brand-detail{display:flex;min-width:0;flex-direction:column;gap:7px}.brand-detail strong{overflow:hidden;color:#2b3950;font-size:14px;text-overflow:ellipsis;white-space:nowrap}.brand-detail span{max-width:420px;color:#8a97a9;font-size:12px;line-height:1.55}.card-actions{display:flex;align-items:center;gap:7px}.card-actions input{display:none}.card-actions :deep(.n-button){border-radius:6px}
.image-preview--dark{border-color:#34383e;background:#181818}.image-preview--dark .fallback-preview{box-sizing:border-box;padding:6px;border:1px solid #cfd5dc;border-radius:10px;background:#eef1f3}
.retention-control{display:flex;align-items:center;justify-content:space-between;gap:28px;flex:1;padding:28px 24px}.retention-control>label{color:#526177;font-size:13px;font-weight:600}.retention-input{display:flex;align-items:center;gap:10px;color:#526177}.retention-input :deep(.n-input-number){width:190px}.retention-input :deep(.n-input){min-height:44px;border-radius:7px}.retention-input :deep(input){font-variant-numeric:tabular-nums;font-size:20px;font-weight:650}
.card-note{display:flex;align-items:center;gap:9px;padding:13px 24px;border-top:1px solid #edf1f5;color:#8290a4;background:#f8fafc;font-size:12px}.note-dot{width:6px;height:6px;flex:none;border-radius:50%;background:#3b82f6}
.update-meta{margin-top:16px;color:#8a97a9;font-size:12px;text-align:right}
@media(max-width:1000px){.configuration-grid{grid-template-columns:1fr}.config-card{min-height:260px}}
@media(max-width:640px){.configuration-page{padding:18px}.page-header{align-items:flex-start}.page-header .n-button{flex:none}.brand-control{grid-template-columns:64px minmax(0,1fr);padding:22px 20px}.image-preview{width:60px;height:60px;border-radius:15px}.image-preview img{width:44px;height:44px}.image-preview span{width:42px;height:42px}.card-actions{grid-column:1/-1;justify-content:flex-end}.card-header{padding:21px 20px 18px}.retention-control{align-items:stretch;flex-direction:column;gap:16px;padding:24px 20px}.retention-input :deep(.n-input-number){width:100%}.card-note{padding:14px 20px}.update-meta{text-align:left}}
</style>
