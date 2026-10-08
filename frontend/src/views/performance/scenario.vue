<template>
  <section class="performance-page">
    <header class="page-header">
      <div><h2>性能场景</h2><p>复用接口场景和项目环境，配置并发模型、性能阈值及服务器监控。</p></div>
      <n-button type="primary" @click="openForm()">新建性能场景</n-button>
    </header>
    <div class="filters">
      <n-input v-model:value="filters.name" clearable placeholder="请输入场景名称" @keyup.enter="load" />
      <n-select v-model:value="filters.project" clearable :options="projectOptions" placeholder="全部项目" @update:value="load" />
      <n-button class="query-button" type="primary" @click="load">查询</n-button>
    </div>
    <n-data-table :loading="loading" :columns="columns" :data="rows" :row-key="(row) => row.id" />

    <n-modal v-model:show="visible" preset="card" :title="editing?.id ? '编辑性能场景' : '新建性能场景'" :mask-closable="false" :close-on-esc="!saving" class="platform-form-modal performance-form-modal">
      <n-form :model="form" label-placement="top" class="scenario-form">
        <div class="form-overview">
          <div><span>01</span><strong>基础配置</strong></div>
          <div><span>02</span><strong>数据与流量</strong></div>
          <div><span>03</span><strong>负载模型</strong></div>
          <div><span>04</span><strong>验收规则</strong></div>
        </div>

        <div class="section-heading section-heading--numbered"><div><i>01</i><strong>基础配置</strong><span>定义场景归属、执行环境和压测对象</span></div></div>
        <n-grid responsive="screen" cols="1 s:2" :x-gap="18" class="basic-grid">
          <n-gi><n-form-item label="场景名称"><n-input v-model:value="form.name" placeholder="例如：用户中心稳定负载" /></n-form-item></n-gi>
          <n-gi><n-form-item label="所属项目"><n-select v-model:value="form.project" filterable :options="projectOptions" @update:value="onProjectChange" /></n-form-item></n-gi>
          <n-gi><n-form-item label="执行环境"><n-select v-model:value="form.environment" :options="environmentOptions" placeholder="选择当前项目环境" /></n-form-item></n-gi>
          <n-gi><n-form-item label="负载模式"><n-radio-group v-model:value="form.load_mode" @update:value="onLoadModeChange"><n-space><n-radio value="stages">阶段模式</n-radio><n-radio value="thread_group">线程组模式</n-radio></n-space></n-radio-group></n-form-item></n-gi>
          <n-gi v-if="form.load_mode === 'stages'"><n-form-item label="业务模式"><n-radio-group v-model:value="form.source_mode" @update:value="onSourceModeChange"><n-space><n-radio value="single">单一业务</n-radio><n-radio value="mixed">多业务混合</n-radio></n-space></n-radio-group></n-form-item></n-gi>
          <n-gi v-if="form.load_mode === 'stages' && form.source_mode === 'single'"><n-form-item label="压测对象"><n-radio-group v-model:value="form.source_type" @update:value="onSourceTypeChange"><n-space><n-radio value="endpoint">单接口</n-radio><n-radio value="scenario">接口场景</n-radio></n-space></n-radio-group></n-form-item></n-gi>
          <n-gi v-if="form.load_mode === 'stages' && form.source_mode === 'single' && form.source_type === 'endpoint'"><n-form-item label="选择接口"><n-select v-model:value="form.source_endpoint" filterable :options="endpointOptions" placeholder="选择当前项目接口" /></n-form-item></n-gi>
          <n-gi v-if="form.load_mode === 'stages' && form.source_mode === 'single' && form.source_type === 'scenario'"><n-form-item label="选择接口场景"><n-select v-model:value="form.source_scenario" filterable :options="sourceScenarioOptions" placeholder="首次保存时复制场景配置" /></n-form-item></n-gi>
          <n-gi v-if="form.load_mode === 'stages'"><n-form-item label="负载模板"><n-select v-model:value="form.load_type" :options="loadTypeOptions" @update:value="applyTemplate" /></n-form-item></n-gi>
          <n-gi><n-form-item label="关联监控目标"><n-select v-model:value="form.monitor_target" clearable :options="monitorTargetOptions" placeholder="可选，用于关联服务器指标" /></n-form-item></n-gi>
          <n-gi><n-form-item label="通知渠道"><n-select v-model:value="form.notification_channels" multiple clearable :options="notificationOptions" placeholder="任务结束后通知，可选" /></n-form-item></n-gi>
        </n-grid>
        <template v-if="form.source_mode === 'mixed'">
          <div class="section-heading"><div><strong>{{ form.load_mode === 'thread_group' ? '接口流量分配' : '业务流量配比' }}</strong><span>{{ form.load_mode === 'thread_group' ? `按比例轮询执行，当前合计 ${businessWeightTotal}%（必须为 100%）` : '每次事务按权重随机选择一个业务，权重无需合计为 100' }}</span></div><n-button secondary type="primary" size="small" @click="addBusiness">添加业务</n-button></div>
          <div class="business-list">
            <div class="business-header"><span>业务类型</span><span>压测对象</span><span>权重</span><span>操作</span></div>
            <div v-for="(item, index) in form.business_mix" :key="index" class="business-row">
              <span v-if="form.load_mode === 'thread_group'" class="stage-index">单接口</span>
              <n-select v-else v-model:value="item.source_type" :options="sourceTypeOptions" @update:value="resetBusiness(item)" />
              <n-select v-if="form.load_mode === 'thread_group' || item.source_type === 'endpoint'" v-model:value="item.source_endpoint" filterable :options="endpointOptions" placeholder="选择接口" />
              <n-select v-else v-model:value="item.source_scenario" filterable :options="sourceScenarioOptions" placeholder="选择接口场景" />
              <n-input-number v-model:value="item.weight" :min="1" :max="100" />
              <n-button text type="error" :disabled="form.business_mix.length <= 2" @click="form.business_mix.splice(index, 1)">删除</n-button>
            </div>
          </div>
        </template>
        <div class="section-heading section-heading--numbered"><div><i>02</i><strong>参数化数据</strong><span>列名可通过 ${列名} 引用到 URL、请求参数、请求头和请求体</span></div></div>
        <div class="parameter-panel">
          <n-upload :default-upload="false" accept=".csv,.json" :max="1" :show-file-list="false" @change="handleParameterUpload">
            <n-button :loading="parameterLoading">选择 CSV / JSON 文件</n-button>
          </n-upload>
          <n-select v-model:value="form.parameter_strategy" :options="parameterStrategyOptions" :disabled="!form.parameter_data.length" />
          <div v-if="form.parameter_data.length" class="parameter-summary">
            <strong>{{ form.parameter_filename }}</strong>
            <span>{{ parameterColumns.length }} 列 · {{ form.parameter_data.length }} 行</span>
            <n-button text type="error" @click="clearParameters">移除</n-button>
          </div>
          <small v-else>支持 CSV，或对象数组 / { "data": [...] } 格式的 JSON；最大 5MB、最多 10000 行</small>
        </div>
        <div v-if="form.load_mode === 'thread_group'" class="thread-group-panel">
          <div class="section-heading section-heading--numbered"><div><i>03</i><strong>线程组设置</strong><span>在持续时间内维持固定线程数，启动时间为 0 时立即达到目标并发</span></div></div>
          <n-grid responsive="screen" cols="1 s:2" :x-gap="16">
            <n-gi><n-form-item label="线程数"><n-input-number v-model:value="form.thread_count" :min="1" :max="10000" /></n-form-item></n-gi>
            <n-gi><n-form-item label="持续时间（秒）"><n-input-number v-model:value="form.duration_seconds" :min="1" :max="86400" /></n-form-item></n-gi>
            <n-gi><n-form-item label="启动时间（秒）"><n-input-number v-model:value="form.ramp_up_seconds" :min="0" :max="86400" /></n-form-item></n-gi>
            <n-gi><n-form-item label="停止等待时间（秒）"><n-input-number v-model:value="form.graceful_stop_seconds" :min="0" :max="3600" /></n-form-item></n-gi>
          </n-grid>
        </div>
        <div v-else class="section-heading section-heading--numbered"><div><i>03</i><strong>负载阶段</strong><span>k6 会在持续时间内，将并发用户数逐步调整到目标值</span></div><n-button secondary type="primary" size="small" @click="addStage">添加阶段</n-button></div>
        <div v-if="form.load_mode === 'stages'" class="stage-list">
          <div class="stage-header">
            <span>阶段</span>
            <span>持续时间 <small>ms / s / m / h</small></span>
            <span>目标并发 <small>VUs，0 表示停止</small></span>
            <span>操作</span>
          </div>
          <div v-for="(stage, index) in form.stages" :key="index" class="stage-row">
            <span class="stage-index"><b>{{ index + 1 }}</b><em>阶段</em></span>
            <div class="stage-field">
              <n-input v-model:value="stage.duration" placeholder="例如 30s、5m、1h" @update:value="markStagesCustom" />
            </div>
            <div class="stage-field">
              <n-input-number v-model:value="stage.target" :min="0" :max="10000" placeholder="例如 50" @update:value="markStagesCustom" />
            </div>
            <n-button text type="error" :disabled="form.stages.length === 1" @click="removeStage(index)">删除</n-button>
          </div>
        </div>
        <div class="section-heading section-heading--numbered"><div><i>04</i><strong>通过阈值</strong><span>超过阈值时，任务判定为未通过</span></div></div>
        <n-grid responsive="screen" cols="1 s:3" :x-gap="16" class="threshold-grid">
          <n-gi><n-form-item label="P95 小于 (ms)"><n-input-number v-model:value="form.thresholds.p95_ms" :min="1" /></n-form-item></n-gi>
          <n-gi><n-form-item label="错误率小于 (%)"><n-input-number v-model:value="form.thresholds.error_rate" :min="0.01" :max="100" :step="0.1" /></n-form-item></n-gi>
          <n-gi><n-form-item label="最低 RPS"><n-input-number v-model:value="form.thresholds.minimum_rps" :min="0" /></n-form-item></n-gi>
        </n-grid>
        <div class="finishing-grid">
          <n-form-item label="场景说明"><n-input v-model:value="form.description" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="可选，记录压测目标、数据准备或注意事项" /></n-form-item>
          <div class="enable-control"><div><strong>启用场景</strong><span>停用后不可发起执行</span></div><n-switch v-model:value="form.enabled" /></div>
        </div>
      </n-form>
      <template #footer><div class="modal-footer"><span>所有配置会保存到当前项目</span><n-space justify="end"><n-button :disabled="saving" @click="visible = false">取消</n-button><n-button type="primary" :loading="saving" @click="save">保存场景</n-button></n-space></div></template>
    </n-modal>
  </section>
</template>

<script setup lang="ts">
import { asList } from '@/utils/list';

import { computed, h, onMounted, reactive, ref } from 'vue';
import { NButton, NSpace, NTag, useDialog, useMessage } from 'naive-ui';
import { useRouter } from 'vue-router';
import { http } from '@/utils/http/axios';
import { MonitorAPI, type MonitorTarget } from '@/api/monitor/http';
import { PerformanceAPI, type PerformanceBusinessMixItem, type PerformanceScenario } from '@/api/performance/http';

const message = useMessage(); const dialog = useDialog();
const router = useRouter();
const loading = ref(false); const saving = ref(false); const visible = ref(false); const parameterLoading = ref(false);
const rows = ref<PerformanceScenario[]>([]); const projects = ref<any[]>([]); const environments = ref<any[]>([]); const endpoints = ref<any[]>([]); const sourceScenarios = ref<any[]>([]); const targets = ref<MonitorTarget[]>([]); const notifications = ref<any[]>([]);
const filters = reactive({ name: '', project: null as number | null });
const editing = ref<PerformanceScenario>();
const emptyBusiness = (sourceType: 'endpoint' | 'scenario' = 'scenario'): PerformanceBusinessMixItem => ({ source_type: sourceType, source_endpoint: null, source_scenario: null, weight: 50 });
const emptyForm = (): PerformanceScenario => ({ project: null, environment: null, source_mode: 'single', source_type: 'scenario', source_endpoint: null, source_scenario: null, business_mix: [emptyBusiness(), emptyBusiness()], parameter_filename: '', parameter_strategy: 'sequential', parameter_data: [], monitor_target: null, notification_channels: [], name: '', description: '', load_type: 'load', load_mode: 'stages', thread_count: 10, duration_seconds: 60, ramp_up_seconds: 0, graceful_stop_seconds: 5, stages: [{ duration: '1m', target: 10 }, { duration: '5m', target: 50 }, { duration: '1m', target: 0 }], thresholds: { p95_ms: 500, error_rate: 1, minimum_rps: 0 }, enabled: true });
const form = reactive<PerformanceScenario>(emptyForm());

const projectOptions = computed(() => projects.value.map((item) => ({ label: item.name, value: Number(item.id) })));
const environmentOptions = computed(() => environments.value.filter((item) => Number(item.project) === Number(form.project)).map((item) => ({ label: `${item.name} · ${item.base_url}`, value: Number(item.id) })));
const endpointOptions = computed(() => endpoints.value.filter((item) => Number(item.project) === Number(form.project)).map((item) => ({ label: `${item.name} · ${item.method} ${item.url}`, value: Number(item.id) })));
const sourceScenarioOptions = computed(() => sourceScenarios.value.filter((item) => Number(item.project) === Number(form.project) || (item.projects || []).map(Number).includes(Number(form.project))).map((item) => ({ label: item.name, value: Number(item.id) })));
const monitorTargetOptions = computed(() => targets.value.filter((item) => Number(item.project) === Number(form.project)).map((item) => ({ label: `${item.name} · ${item.instance_label}`, value: Number(item.id) })));
const notificationOptions = computed(() => notifications.value.filter((item) => (item.projects || []).map(Number).includes(Number(form.project))).map((item) => ({ label: item.name, value: Number(item.id) })));
const parameterColumns = computed(() => form.parameter_data.length ? Object.keys(form.parameter_data[0]) : []);
const businessWeightTotal = computed(() => form.business_mix.reduce((sum, item) => sum + Number(item.weight || 0), 0));
const sourceTypeOptions = [{ label: '单接口', value: 'endpoint' }, { label: '接口场景', value: 'scenario' }];
const parameterStrategyOptions = [{ label: '顺序循环', value: 'sequential' }, { label: '随机取值', value: 'random' }, { label: '全局唯一（耗尽后失败）', value: 'unique' }];
const loadTypeOptions = [{ label: '冒烟测试', value: 'smoke' }, { label: '负载测试', value: 'load' }, { label: '压力测试', value: 'stress' }, { label: '峰值测试', value: 'spike' }, { label: '稳定性测试', value: 'soak' }, { label: '自定义', value: 'custom' }];
const templates: Record<string, any[]> = { smoke: [{ duration: '30s', target: 1 }], load: [{ duration: '1m', target: 10 }, { duration: '5m', target: 50 }, { duration: '1m', target: 0 }], stress: [{ duration: '2m', target: 50 }, { duration: '3m', target: 100 }, { duration: '3m', target: 200 }, { duration: '1m', target: 0 }], spike: [{ duration: '30s', target: 10 }, { duration: '30s', target: 300 }, { duration: '2m', target: 300 }, { duration: '30s', target: 0 }], soak: [{ duration: '5m', target: 50 }, { duration: '30m', target: 50 }, { duration: '2m', target: 0 }] };
const statusTag = (enabled: boolean) => h(NTag, { type: enabled ? 'success' : 'default', size: 'small' }, { default: () => enabled ? '启用' : '停用' });
const columns: any[] = [
  { title: '场景名称', key: 'name' }, { title: '所属项目', key: 'project_name' }, { title: '执行环境', key: 'environment_name' },
  { title: '压测对象', key: 'source', render: (row: PerformanceScenario) => row.source_mode === 'mixed' ? `多业务混合 · ${row.business_mix.length} 个业务` : row.source_type === 'endpoint' ? `单接口 · ${row.source_endpoint_name || '-'}` : `接口场景 · ${row.source_scenario_name || '-'}` },
  { title: '负载配置', key: 'load_mode', render: (row: PerformanceScenario) => row.load_mode === 'thread_group' ? `线程组 · ${row.thread_count} 线程 / ${row.duration_seconds} 秒` : `${loadTypeOptions.find((item) => item.value === row.load_type)?.label || row.load_type} · ${row.stages.length} 阶段` },
  { title: '状态', key: 'enabled', render: (row: PerformanceScenario) => statusTag(row.enabled) },
  { title: '操作', key: 'actions', width: 300, render: (row: PerformanceScenario) => h(NSpace, { size: 14, wrap: false }, { default: () => [
    h(NButton, { text: true, type: 'primary', onClick: () => start(row) }, { default: () => '执行' }),
    h(NButton, { text: true, type: 'primary', onClick: () => openForm(row) }, { default: () => '编辑' }),
    h(NButton, { text: true, type: 'primary', onClick: () => refreshSnapshot(row) }, { default: () => '更新接口快照' }),
    h(NButton, { text: true, type: 'error', onClick: () => remove(row) }, { default: () => '删除' }),
  ] }) },
];
function onProjectChange() { form.environment = null; form.source_endpoint = null; form.source_scenario = null; const sourceType = form.load_mode === 'thread_group' ? 'endpoint' : 'scenario'; form.business_mix = [emptyBusiness(sourceType), emptyBusiness(sourceType)]; form.monitor_target = null; form.notification_channels = []; clearParameters(); }
function onSourceModeChange() { form.source_endpoint = null; form.source_scenario = null; if (form.business_mix.length < 2) form.business_mix = [emptyBusiness(), emptyBusiness()]; }
function onLoadModeChange(value: 'stages' | 'thread_group') { if (value === 'thread_group') { form.source_mode = 'mixed'; form.source_endpoint = null; form.source_scenario = null; form.business_mix = [emptyBusiness('endpoint'), emptyBusiness('endpoint')]; } else if (!form.stages.length) { form.load_type = 'load'; applyTemplate('load'); } }
function onSourceTypeChange() { form.source_endpoint = null; form.source_scenario = null; }
function addBusiness() { form.business_mix.push(emptyBusiness(form.load_mode === 'thread_group' ? 'endpoint' : 'scenario')); }
function resetBusiness(item: PerformanceBusinessMixItem) { item.source_endpoint = null; item.source_scenario = null; }
function clearParameters() { form.parameter_filename = ''; form.parameter_data = []; }
async function handleParameterUpload(options: any) { const file = options.file?.file as File | undefined; if (!file || !form.project) return message.warning('请先选择所属项目'); parameterLoading.value = true; try { const result = await PerformanceAPI.parseParameters(form.project, file); form.parameter_filename = result.filename; form.parameter_data = result.rows; message.success(`已读取 ${result.row_count} 行参数数据`); } catch (error: any) { clearParameters(); message.error(error?.message || '参数文件解析失败'); } finally { parameterLoading.value = false; } }
function applyTemplate(value: string) { if (templates[value]) form.stages = templates[value].map((item) => ({ ...item })); }
function markStagesCustom() { form.load_type = 'custom'; }
function addStage() { form.stages.push({ duration: '1m', target: 10 }); markStagesCustom(); }
function removeStage(index: number) { form.stages.splice(index, 1); markStagesCustom(); }
function openForm(row?: PerformanceScenario) { editing.value = row; Object.assign(form, emptyForm(), row ? JSON.parse(JSON.stringify(row)) : { project: filters.project }); visible.value = true; }
async function load() { loading.value = true; try { rows.value = asList(await PerformanceAPI.scenarios({ project: filters.project || undefined, name: filters.name || undefined, _t: Date.now() })); } catch (error: any) { message.error(error?.message || '性能场景加载失败'); } finally { loading.value = false; } }
async function save() { const sourceSelected = form.source_mode === 'mixed' ? form.business_mix.length >= 2 : (form.source_type === 'endpoint' ? form.source_endpoint : form.source_scenario); if (!form.name || !form.project || !form.environment || !sourceSelected) return message.warning('请填写名称并选择项目、环境和压测对象'); if (form.load_mode === 'thread_group' && businessWeightTotal.value !== 100) return message.warning('接口比例合计必须等于 100%'); if (form.load_mode === 'thread_group' && form.business_mix.some((item) => !item.source_endpoint)) return message.warning('请选择所有需要分配比例的接口'); const payload: PerformanceScenario = JSON.parse(JSON.stringify(form)); if (payload.load_mode === 'thread_group') { payload.stages = []; payload.load_type = 'custom'; } else { payload.thread_count = 10; payload.duration_seconds = 60; payload.ramp_up_seconds = 0; payload.graceful_stop_seconds = 5; } saving.value = true; try { if (editing.value?.id) await PerformanceAPI.updateScenario(editing.value.id, payload); else await PerformanceAPI.createScenario(payload); visible.value = false; message.success('性能场景已保存'); await load(); } catch (error: any) { message.error(error?.message || '保存失败'); } finally { saving.value = false; } }
async function submitRun(row: PerformanceScenario, confirmProduction = false) { try { const run = await PerformanceAPI.start(row.id!, confirmProduction); message.success(`任务已提交，执行编号：${run.execution_no}`); router.push({ name: 'execution_report', params: { sourceType: 'performance', id: run.id } }); } catch (error: any) { message.error(error?.message || '提交失败'); } }
async function start(row: PerformanceScenario) { if (String(row.environment_name || '').toLowerCase() !== 'prod') return submitRun(row); dialog.warning({ title: '生产环境压测确认', content: `即将在生产环境执行性能场景「${row.name}」，请确认已评估并发量和持续时间。`, positiveText: '确认执行', negativeText: '取消', onPositiveClick: () => submitRun(row, true) }); }
async function refreshSnapshot(row: PerformanceScenario) { try { await PerformanceAPI.refreshSnapshot(row.id!); message.success('已重新继承接口场景配置'); await load(); } catch (error: any) { message.error(error?.message || '更新失败'); } }
async function remove(row: PerformanceScenario) { try { await PerformanceAPI.deleteScenario(row.id!); rows.value = rows.value.filter((item) => item.id !== row.id); message.success('已删除'); } catch (error: any) { message.error(error?.message || '删除失败'); } }
onMounted(async () => { const [p, e, a, s, t, n] = await Promise.all([http.request({ url: '/project/project/', method: 'get', params: { pageSize: 1000 } }), http.request({ url: '/project/environment/', method: 'get', params: { pageSize: 1000 } }), http.request({ url: '/case_api/endpoint/', method: 'get', params: { pageSize: 1000 } }), http.request({ url: '/case_api/scenario/', method: 'get', params: { pageSize: 1000 } }), MonitorAPI.targetList(), http.request({ url: '/suite/notification-channel/', method: 'get', params: { pageSize: 1000 } })]); projects.value = asList(p); environments.value = asList(e); endpoints.value = asList(a); sourceScenarios.value = asList(s); targets.value = asList(t); notifications.value = asList(n); await load(); });
</script>

<style scoped lang="less">
.performance-page {
  padding: 24px 28px;
}
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}
.page-header h2 {
  margin: 0;
  color: #172033;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: -0.02em;
}
.page-header p {
  margin: 7px 0 22px;
  color: #718096;
}
.filters {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(180px, 220px) max-content;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}
.query-button {
  min-width: 80px;
  padding-inline: 20px;
}

:global(.performance-form-modal) {
  width: min(1080px, calc(100vw - 40px));
  height: min(900px, calc(100dvh - 40px));
  max-height: calc(100dvh - 40px);
  overflow: hidden;
}
:global(.performance-form-modal .n-card-header) {
  flex: 0 0 auto;
  padding: 20px 26px 16px;
  border-bottom: 1px solid #edf0f5;
}
:global(.performance-form-modal .n-card-header__main) {
  color: #172033;
  font-size: 19px;
  font-weight: 650;
  letter-spacing: -0.015em;
}
:global(.performance-form-modal .n-card-content) {
  flex: 1 1 auto;
  min-height: 0;
  max-height: none;
  padding: 18px 26px 30px;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}
:global(.performance-form-modal .n-card__footer) {
  flex: 0 0 auto;
  padding: 14px 26px;
  border-top: 1px solid #e8ecf2;
  background: rgba(255, 255, 255, 0.96);
}
.scenario-form :deep(.n-form-item) {
  margin-bottom: 2px;
}
.scenario-form :deep(.n-form-item-label) {
  color: #344054;
  font-size: 13px;
  font-weight: 600;
}
.scenario-form :deep(.n-input),
.scenario-form :deep(.n-base-selection),
.scenario-form :deep(.n-input-number) {
  transition: border-color 180ms ease, box-shadow 180ms ease;
}
.scenario-form :deep(.n-input:focus-within),
.scenario-form :deep(.n-base-selection--active) {
  box-shadow: 0 0 0 3px rgba(47, 102, 224, 0.09);
}
.form-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  margin: 0 0 22px;
  padding: 12px 14px;
  border: 1px solid #e8edf5;
  border-radius: 10px;
  background: #f7f9fc;
}
.form-overview div {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  color: #526177;
  font-size: 12px;
}
.form-overview div + div {
  border-left: 1px solid #e2e7ef;
}
.form-overview span {
  color: #2f66e0;
  font: 600 11px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
}
.form-overview strong {
  font-weight: 600;
}
.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin: 18px 0 10px;
  color: #28364b;
}
.section-heading > div {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 9px;
}
.section-heading strong {
  white-space: nowrap;
  font-size: 14px;
  font-weight: 650;
}
.section-heading span {
  overflow: hidden;
  color: #8190a5;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.section-heading--numbered {
  margin-top: 22px;
}
.section-heading--numbered:first-of-type {
  margin-top: 0;
}
.section-heading--numbered i {
  display: inline-grid;
  width: 25px;
  height: 25px;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 6px;
  background: #edf3ff;
  color: #2f66e0;
  font: normal 650 10px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
}
.basic-grid,
.threshold-grid,
.finishing-grid {
  padding: 16px 18px 4px;
  border: 1px solid #e6ebf2;
  border-radius: 10px;
  background: #fff;
}
.stage-list,
.business-list {
  margin-bottom: 18px;
  overflow: hidden;
  border: 1px solid #dfe5ee;
  border-radius: 10px;
  background: #fff;
}
.stage-header,
.stage-row {
  display: grid;
  grid-template-columns: 78px minmax(180px, 1fr) minmax(210px, 1fr) 52px;
  align-items: center;
  gap: 14px;
  padding: 10px 16px;
}
.stage-header,
.business-header {
  background: #f5f7fa;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}
.stage-header small {
  margin-left: 5px;
  color: #98a3b3;
  font-size: 10px;
  font-weight: 400;
}
.stage-row {
  min-height: 56px;
  border-top: 1px solid #e8ecf2;
  transition: background-color 180ms ease;
}
.stage-row:hover,
.business-row:hover {
  background: #fafcff;
}
.stage-index {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6d7c91;
  font-size: 12px;
}
.stage-index b {
  display: inline-grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border: 1px solid #dce4f0;
  border-radius: 7px;
  background: #f8fafc;
  color: #2f66e0;
  font: 650 12px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
}
.stage-index em {
  display: none;
  font-style: normal;
}
.stage-field :deep(.n-input-number) {
  width: 100%;
}
.business-header,
.business-row {
  display: grid;
  grid-template-columns: 130px minmax(240px, 1fr) 120px 52px;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
}
.business-row {
  border-top: 1px solid #e8ecf2;
  transition: background-color 180ms ease;
}
.business-row :deep(.n-input-number) {
  width: 100%;
}
.parameter-panel {
  display: grid;
  grid-template-columns: auto 220px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
  padding: 16px 18px;
  border: 1px dashed #ccd6e5;
  border-radius: 10px;
  background: #f8fafc;
}
.parameter-panel > small {
  grid-column: 1 / -1;
  color: #8795a8;
  line-height: 1.6;
}
.parameter-summary {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 10px;
}
.parameter-summary strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.parameter-summary span {
  color: #758399;
  font-size: 12px;
  white-space: nowrap;
}
.thread-group-panel {
  margin-bottom: 18px;
  padding: 1px 18px 6px;
  border: 1px solid #e6ebf2;
  border-radius: 10px;
  background: #fff;
}
.threshold-grid {
  padding-bottom: 2px;
  background: #f8fafc;
}
.threshold-grid :deep(.n-input-number) {
  width: 100%;
  font-variant-numeric: tabular-nums;
}
.finishing-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  align-items: stretch;
  gap: 18px;
  margin-top: 14px;
  padding-bottom: 14px;
}
.enable-control {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 14px;
  border-radius: 8px;
  background: #f5f7fa;
}
.enable-control div {
  display: grid;
  gap: 3px;
}
.enable-control strong {
  color: #344054;
  font-size: 13px;
}
.enable-control span {
  color: #8795a8;
  font-size: 11px;
}
.modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}
.modal-footer > span {
  color: #8a97a9;
  font-size: 12px;
}

@media (max-width: 760px) {
  .filters {
    grid-template-columns: minmax(0, 1fr) minmax(160px, 220px) max-content;
  }
  :global(.performance-form-modal) {
    width: min(100vw - 20px, 1080px);
    height: calc(100dvh - 20px);
    max-height: calc(100dvh - 20px);
  }
  :global(.performance-form-modal .n-card-content) {
    padding-inline: 18px;
  }
  :global(.performance-form-modal .n-card-header),
  :global(.performance-form-modal .n-card__footer) {
    padding-inline: 18px;
  }
  .form-overview {
    grid-template-columns: repeat(2, 1fr);
    row-gap: 10px;
  }
  .form-overview div:nth-child(3) {
    border-left: 0;
  }
  .finishing-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 640px) {
  .performance-page {
    padding: 16px;
  }
  .page-header {
    align-items: stretch;
    flex-direction: column;
  }
  .filters {
    grid-template-columns: 1fr;
  }
  .query-button {
    justify-self: start;
  }
  .form-overview {
    display: none;
  }
  .section-heading {
    align-items: flex-start;
  }
  .section-heading > div {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .section-heading span {
    width: 100%;
    padding-left: 34px;
    overflow: visible;
    line-height: 1.5;
    white-space: normal;
  }
  .stage-header,
  .business-header {
    display: none;
  }
  .stage-row {
    grid-template-columns: 60px 1fr;
    padding-block: 14px;
  }
  .stage-index {
    align-self: start;
  }
  .stage-index em {
    display: inline;
  }
  .stage-row > .n-button {
    grid-column: 2;
    justify-self: end;
  }
  .business-row,
  .parameter-panel {
    grid-template-columns: 1fr;
  }
  .business-row > .n-button {
    justify-self: end;
  }
  .parameter-summary {
    flex-wrap: wrap;
  }
  .modal-footer > span {
    display: none;
  }
  .modal-footer {
    justify-content: flex-end;
  }
}
</style>
