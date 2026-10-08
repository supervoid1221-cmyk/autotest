<template>
  <section class="control-page">
    <header class="page-header">
      <div class="refresh-frequency">
        <span>自动刷新</span>
        <n-select
          v-model:value="refreshInterval"
          :options="refreshIntervalOptions"
          size="small"
          aria-label="选择自动刷新频率"
        />
      </div>
      <n-button :loading="loading" @click="loadAll">刷新状态</n-button>
    </header>

    <div class="summary-grid">
      <div class="summary-card"><span>任务总数</span><strong>{{ overview.total || 0 }}</strong><small>当前可见项目</small></div>
      <div class="summary-card active"><span>运行中</span><strong>{{ overview.active || 0 }}</strong><small>含等待与汇总报告</small></div>
      <div class="summary-card" :class="{ danger: overview.abnormal }"><span>需要处理</span><strong>{{ overview.abnormal || 0 }}</strong><small>{{ abnormalSummary }}</small></div>
      <div class="summary-card"><span>在线服务</span><strong>{{ onlineServices }}/{{ configuredServices.length }}</strong><small>未配置服务不计入异常</small></div>
    </div>

    <div class="service-panel">
      <div class="section-title"><div><strong>执行服务</strong><span>心跳超时会自动标记离线</span></div></div>
      <div class="service-list">
        <div v-for="service in overview.services || []" :key="service.key" class="service-item">
          <i :class="service.status" />
          <div><strong>{{ service.name }}</strong><span>{{ service.message }}</span><small>最近心跳：{{ formatServiceHeartbeat(service.last_heartbeat_at) }}</small></div>
          <n-tag size="small" :type="serviceTagType(service.status)">{{ serviceStatusLabel(service.status) }}</n-tag>
        </div>
      </div>
    </div>

    <div class="task-panel">
      <div class="filters">
        <n-input v-model:value="filters.keyword" clearable placeholder="搜索执行编号或任务名称" @keyup.enter="queryTasks" />
        <n-select v-model:value="filters.project" clearable :options="projectOptions" placeholder="全部项目" />
        <n-select v-model:value="filters.source_type" clearable :options="typeOptions" placeholder="全部类型" />
        <n-select v-model:value="filters.status" clearable :options="statusOptions" placeholder="全部状态" />
        <n-button type="primary" @click="queryTasks">查询</n-button>
        <n-button :disabled="checkedRowKeys.length < 2 || checkedRowKeys.length > 5" @click="compareReports">
          对比性能报告{{ checkedRowKeys.length ? `（${checkedRowKeys.length}）` : '' }}
        </n-button>
      </div>
      <n-data-table
        v-model:checked-row-keys="checkedRowKeys"
        remote
        :loading="loading || tasksLoading"
        :columns="columns"
        :data="rows"
        :row-key="row => row.id"
        :scroll-x="1984"
        :pagination="false"
      />
      <div class="task-pagination">
        <PaginationFooter
          :total="pagination.itemCount"
          :page="pagination.page"
          :page-size="pagination.pageSize"
          @update:page="handlePageChange"
          @update:page-size="handlePageSizeChange"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { usePolling } from '@/hooks/web/usePolling';
import { asList } from '@/utils/list';
import { formatDateTime, formatElapsedDuration } from '@/utils/time';

import { computed, h, onActivated, onMounted, reactive, ref, watch } from 'vue';
import { NButton, NProgress, NSpace, NTag, useDialog, useMessage } from 'naive-ui';
import { useRouter } from 'vue-router';
import { http } from '@/utils/http/axios';
import { ExecutionControlAPI, type ExecutionOverview, type ExecutionTask } from '@/api/execution_control/http';
import PaginationFooter from '@/components/PaginationFooter/index.vue';

const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const loading = ref(false);
const tasksLoading = ref(false);
const rows = ref<ExecutionTask[]>([]);
const checkedRowKeys = ref<number[]>([]);
const projects = ref<any[]>([]);
const overview = reactive<ExecutionOverview>({ total: 0, active: 0, abnormal: 0, abnormal_tasks: 0, abnormal_services: 0, status_counts: {}, services: [] });
const filters = reactive({ keyword: '', project: null as number | null, source_type: null as string | null, status: null as string | null });
const pagination = reactive({
  page: 1,
  pageSize: 10,
  itemCount: 0,
});
const poller = usePolling();
const refreshInterval = ref(60_000);
const refreshIntervalOptions = [
  { label: '3 秒', value: 3_000 },
  { label: '10 秒', value: 10_000 },
  { label: '30 秒', value: 30_000 },
  { label: '1 分钟', value: 60_000 },
  { label: '10 分钟', value: 600_000 },
];
let taskRequestVersion = 0;

const onlineServices = computed(() => (overview.services || []).filter(item => item.status === 'online').length);
const configuredServices = computed(() => (overview.services || []).filter(item => item.status !== 'not_configured'));
const abnormalSummary = computed(() => {
  const details = [];
  if (overview.abnormal_services) details.push(`${overview.abnormal_services} 个服务异常`);
  if (overview.abnormal_tasks) details.push(`${overview.abnormal_tasks} 个任务异常`);
  return details.length ? details.join(' · ') : '暂无执行异常';
});
const projectOptions = computed(() => projects.value.map(item => ({ label: item.name, value: Number(item.id) })));
const typeOptions = [
  { label: '测试计划', value: 'suite' }, { label: 'App 测试', value: 'app' }, { label: '性能测试', value: 'performance' },
];
const statusMeta: Record<string, { label: string; type: any; color: string }> = {
  queued: { label: '等待调度', type: 'default', color: '#64748b' }, preparing: { label: '准备环境', type: 'info', color: '#2563eb' },
  running: { label: '执行中', type: 'info', color: '#2563eb' }, paused: { label: '已暂停', type: 'warning', color: '#d97706' },
  reporting: { label: '汇总报告', type: 'warning', color: '#7c3aed' }, succeeded: { label: '执行成功', type: 'success', color: '#16a34a' },
  failed: { label: '执行失败', type: 'error', color: '#dc2626' }, error: { label: '执行异常', type: 'error', color: '#dc2626' },
  canceled: { label: '已取消', type: 'default', color: '#94a3b8' }, stopped: { label: '已停止', type: 'default', color: '#94a3b8' },
};
const statusOptions = Object.entries(statusMeta).map(([value, item]) => ({ value, label: item.label }));
const formatServiceHeartbeat = (value?: string | null) => formatDateTime(value, { empty: '暂无' });
const serviceStatusLabel = (status: string) => ({
  online: '正常', degraded: '异常', offline: '离线', not_configured: '未配置',
}[status] || status);
const serviceTagType = (status: string) => ({
  online: 'success', degraded: 'warning', offline: 'error', not_configured: 'default',
}[status] || 'default') as any;
// 终态：任务已经不会再产生 finished_at，此时用「—」表示无结束时间；未终态用「进行中」，与「耗时」列的实时计时保持一致
const TERMINAL_STATUS = ['succeeded', 'failed', 'error', 'canceled', 'stopped'];
const endTimeText = (row: ExecutionTask) => {
  if (row.finished_at) return formatDateTime(row.finished_at, { empty: '—' });
  return TERMINAL_STATUS.includes(row.status) ? '—' : '进行中';
};
const formatDuration = (row: ExecutionTask) => {
  if (!row.started_at) return '-';
  return formatElapsedDuration(row.started_at, row.finished_at || Date.now(), {
    showMilliseconds: false,
  });
};

const columns: any[] = [
  { type: 'selection', width: 46, disabled: (row: ExecutionTask) => row.source_type !== 'performance' || ['queued', 'preparing', 'running', 'paused', 'reporting'].includes(row.status) },
  { title: '执行编号', key: 'execution_no', width: 132, ellipsis: { tooltip: true } },
  { title: '任务', key: 'name', width: 240, render: (row: ExecutionTask) => h('div', { class: 'task-name', title: `${row.name} · ${row.engine}` }, [h('strong', `${row.name} · ${row.engine}`)]) },
  { title: '所属项目', key: 'project_name', width: 130, ellipsis: { tooltip: true } },
  // 执行人由后端从源任务（套件执行记录的 executor_name / App、性能任务的 created_by）
  // 写入快照。补字段之前的历史任务没有这个信息，接口返回空串，这里显示「-」。
  { title: '执行人', key: 'executor_name', width: 120, ellipsis: { tooltip: true }, render: (row: ExecutionTask) => row.executor_name || '-' },
  { title: '状态', key: 'status', width: 112, render: (row: ExecutionTask) => h(NTag, { size: 'small', type: statusMeta[row.status]?.type || 'default' }, { default: () => row.status_name }) },
  { title: '当前阶段', key: 'stage', width: 180, render: (row: ExecutionTask) => row.status === 'queued'
    ? h('div', { class: 'queue-stage' }, [
      h('strong', `排队中${row.queue_position ? ` · 第 ${row.queue_position} 位` : ''}`),
      h('span', row.waiting_reason || '等待调度器分配资源'),
    ])
    : h('span', row.stage) },
  { title: '进度', key: 'progress', width: 170, render: (row: ExecutionTask) => h('div', { class: 'task-progress' }, [
    h(NProgress, { type: 'line', percentage: row.progress, height: 6, borderRadius: 4, showIndicator: false, color: statusMeta[row.status]?.color || '#2563eb', railColor: '#e8edf4' }),
    h('span', `${row.progress}%`),
  ]) },
  { title: '运行诊断', key: 'diagnostic_message', width: 280, render: (row: ExecutionTask) => row.diagnostic_message
    ? h('div', { class: 'diagnostic danger-text' }, [h('strong', row.diagnostic_code), h('span', row.diagnostic_message)])
    : h('span', { class: 'healthy-text' }, '未发现异常') },
  { title: '执行时间', key: 'started_at', width: 232, render: (row: ExecutionTask) => {
    const start = formatDateTime(row.started_at || row.queued_at, { empty: '—' });
    const end = endTimeText(row);
    return h('div', { class: 'run-time' }, [
      h('div', { class: 'run-time-row' }, [
        h('span', { class: 'run-time-tag is-start' }, '开始'),
        h('span', { class: start === '—' ? 'run-time-value is-empty' : 'run-time-value' }, start),
      ]),
      h('div', { class: 'run-time-row' }, [
        h('span', { class: 'run-time-tag is-end' }, '结束'),
        h('span', { class: end === '—' ? 'run-time-value is-empty' : end === '进行中' ? 'run-time-value is-running' : 'run-time-value' }, end),
      ]),
    ]);
  } },
  { title: '耗时', key: 'duration', width: 112, render: (row: ExecutionTask) => formatDuration(row) },
  { title: '操作', key: 'actions', width: 230, fixed: 'right', render: (row: ExecutionTask) => h(NSpace, { size: 12, wrap: false }, { default: () => [
    h(NButton, { text: true, type: 'primary', onClick: () => router.push(row.report_path) }, { default: () => '查看报告' }),
    row.can_recover ? h(NButton, { text: true, type: 'warning', onClick: () => recover(row) }, { default: () => '恢复调度' }) : null,
    row.can_stop ? h(NButton, { text: true, type: 'error', onClick: () => stop(row) }, { default: () => '停止' }) : null,
    !row.can_stop ? h(NButton, { text: true, type: 'error', onClick: () => confirmDelete(row) }, { default: () => '删除' }) : null,
  ].filter(Boolean) }) },
];

async function loadTasks() {
  const requestVersion = ++taskRequestVersion;
  tasksLoading.value = true;
  try {
    const result: any = await ExecutionControlAPI.tasks({
      ...filters,
      page: pagination.page,
      pageSize: pagination.pageSize,
      _t: Date.now(),
    });
    if (requestVersion !== taskRequestVersion) return;
    rows.value = asList(result);
    pagination.itemCount = Math.max(0, Number(result?.itemCount || 0));
    const lastPage = Math.max(1, Math.ceil(pagination.itemCount / pagination.pageSize));
    if (pagination.page > lastPage) {
      pagination.page = lastPage;
      await loadTasks();
      return;
    }
    const visibleIds = new Set(rows.value.map(item => item.id));
    checkedRowKeys.value = checkedRowKeys.value.filter(id => visibleIds.has(id));
  } finally {
    if (requestVersion === taskRequestVersion) tasksLoading.value = false;
  }
}
async function queryTasks() {
  pagination.page = 1;
  await loadTasks();
}
async function handlePageChange(page: number) {
  pagination.page = page;
  await loadTasks();
}
async function handlePageSizeChange(pageSize: number) {
  pagination.page = 1;
  pagination.pageSize = pageSize;
  await loadTasks();
}
async function loadAll() {
  if (loading.value) return;
  loading.value = true;
  try {
    // overview 会先完成任务诊断；列表直接读取诊断后的状态，
    // 避免两个并发接口对同一批活动任务重复遍历和更新。
    const summary = await ExecutionControlAPI.overview();
    await loadTasks();
    Object.assign(overview, summary);
  } catch (error: any) {
    message.error(error?.message || '执行控制中心加载失败');
  } finally { loading.value = false; }
}
async function recover(row: ExecutionTask) {
  try { await ExecutionControlAPI.recover(row.id); message.success('任务已重新入队'); await loadAll(); }
  catch (error: any) { message.error(error?.message || '恢复失败'); }
}
async function stop(row: ExecutionTask) {
  try { await ExecutionControlAPI.stop(row.id); message.success('已发送停止指令'); await loadAll(); }
  catch (error: any) { message.error(error?.message || '停止失败'); }
}
function confirmDelete(row: ExecutionTask) {
  dialog.warning({
    title: '删除执行与报告',
    content: `确定删除执行任务「${row.execution_no}」吗？对应报告和运行产物将一并删除。`,
    positiveText: '删除', negativeText: '取消',
    onPositiveClick: async () => {
      try { await ExecutionControlAPI.delete(row.id); message.success('已删除'); await loadAll(); }
      catch (error: any) { message.error(error?.message || '删除失败'); }
    },
  });
}
function compareReports() {
  const sourceIds = rows.value
    .filter(row => checkedRowKeys.value.includes(row.id) && row.source_type === 'performance')
    .map(row => row.source_id);
  if (sourceIds.length < 2 || sourceIds.length > 5) {
    message.warning('请选择 2 至 5 份已完成的性能报告');
    return;
  }
  router.push({ name: 'performance_compare', query: { ids: sourceIds.join(',') } });
}
function startPolling() { poller.stop(); poller.start(() => void loadAll(), refreshInterval.value); }
onMounted(async () => {
  try { projects.value = asList(await http.request({ url: '/project/project/', method: 'get', params: { pageSize: 1000 } })); } catch { projects.value = []; }
  await loadAll(); startPolling();
});
onActivated(loadAll);
watch(refreshInterval, startPolling);

</script>

<style scoped lang="less">
.control-page{padding:24px 28px;color:#263449}.page-header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.page-header h2{margin:0;font-size:24px}.page-header p{margin:8px 0 22px;color:#7b8ba3}.summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:16px}.summary-card{display:flex;min-height:112px;box-sizing:border-box;flex-direction:column;padding:18px 20px;border:1px solid #e2e8f0;border-radius:12px;background:#fff}.summary-card span{color:#64748b;font-size:13px}.summary-card strong{margin:7px 0 2px;color:#1e293b;font-size:28px;line-height:1}.summary-card small{color:#94a3b8}.summary-card.active{border-color:#bfdbfe;background:#f8fbff}.summary-card.active strong{color:#2563eb}.summary-card.danger{border-color:#fecaca;background:#fffafa}.summary-card.danger strong{color:#dc2626}.service-panel,.task-panel{margin-bottom:16px;border:1px solid #e2e8f0;border-radius:12px;background:#fff}.section-title{padding:16px 20px;border-bottom:1px solid #edf1f5}.section-title div{display:flex;align-items:baseline;gap:10px}.section-title span{color:#94a3b8;font-size:12px}.service-list{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0}.service-item{display:flex;min-width:0;align-items:center;gap:10px;padding:16px 20px;border-right:1px solid #edf1f5}.service-item:last-child{border-right:0}.service-item i{width:9px;height:9px;flex:none;border-radius:50%;background:#ef4444;box-shadow:0 0 0 4px #fee2e2}.service-item i.online{background:#16a34a;box-shadow:0 0 0 4px #dcfce7}.service-item i.degraded{background:#d97706;box-shadow:0 0 0 4px #fef3c7}.service-item i.not_configured{background:#94a3b8;box-shadow:0 0 0 4px #e2e8f0}.service-item div{display:flex;min-width:0;flex:1;flex-direction:column}.service-item div span{overflow:hidden;color:#8a97a9;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.service-item div small{margin-top:3px;color:#a4afbd;font-size:11px;white-space:nowrap}.service-item :deep(.n-tag){display:inline-flex;align-items:center;align-self:center;flex:none;height:auto;line-height:1;padding:4px 10px}.filters{display:grid;grid-template-columns:minmax(220px,1fr) 190px 170px 170px auto auto;gap:12px;padding:16px 20px;border-bottom:1px solid #edf1f5}.task-name,.diagnostic{display:flex;min-width:0;flex-direction:column}.task-name span,.diagnostic span{overflow:hidden;margin-top:3px;color:#8a97a9;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.run-time{display:flex;min-width:0;flex-direction:column;gap:4px}.run-time-row{display:flex;min-width:0;align-items:center;gap:6px}.run-time-tag{flex:none;padding:0 5px;border-radius:4px;color:#7b8ba3;font-size:11px;line-height:17px;background:#f1f5f9}.run-time-tag.is-start{color:#2563eb;background:#eff6ff}.run-time-tag.is-end{color:#7c3aed;background:#f5f3ff}.run-time-value{overflow:hidden;color:#526177;font-size:12px;font-variant-numeric:tabular-nums;text-overflow:ellipsis;white-space:nowrap}.run-time-value.is-empty{color:#aab4c4}.run-time-value.is-running{color:#d97706}.task-progress{display:flex;align-items:center;gap:10px}.task-progress .n-progress{min-width:85px;flex:1}.task-progress span{width:38px;color:#526177;font-variant-numeric:tabular-nums}.danger-text strong{color:#dc2626;font-size:12px}.healthy-text{color:#16a34a;font-size:13px}
.page-header{align-items:center;justify-content:flex-end;margin-bottom:16px}.refresh-frequency{display:flex;align-items:center;gap:9px;color:#7b8ba3;font-size:13px;white-space:nowrap}.refresh-frequency :deep(.n-select){width:112px}
@media(max-width:900px){.summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.service-list{grid-template-columns:repeat(2,minmax(0,1fr))}.filters{grid-template-columns:1fr 1fr}.filters .n-button{width:max-content}}
@media(max-width:640px){.control-page{padding:16px}.page-header{align-items:stretch;flex-direction:column;margin-bottom:16px}.page-header p{margin-bottom:0}.refresh-frequency{justify-content:space-between}.refresh-frequency :deep(.n-select){width:140px}.summary-grid,.service-list,.filters{grid-template-columns:1fr}.service-item{border-right:0;border-bottom:1px solid #edf1f5}.service-item:last-child{border-bottom:0}.filters .n-button,.page-header>.n-button{width:100%}}
.queue-stage{display:flex;min-width:0;flex-direction:column}.queue-stage strong{color:#d97706;font-size:13px}.queue-stage span{overflow:hidden;margin-top:3px;color:#8a97a9;font-size:12px;text-overflow:ellipsis;white-space:nowrap}
.task-name strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
</style>
