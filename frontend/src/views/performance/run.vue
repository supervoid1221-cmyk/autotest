<template>
  <section class="performance-page">
    <header class="page-header"><div><h2>执行任务</h2><p>查看性能测试执行状态、实时压力和最终结论。</p></div><n-button type="primary" :disabled="checkedRowKeys.length < 2 || checkedRowKeys.length > 5" @click="compareReports">对比报告（{{ checkedRowKeys.length }}）</n-button></header>
    <div class="filters">
      <n-select v-model:value="filters.project" clearable :options="projectOptions" placeholder="全部项目" @update:value="handleProjectChange" />
      <n-select v-model:value="filters.environment" clearable :options="environmentOptions" placeholder="全部环境" @update:value="load" />
      <n-select v-model:value="filters.status" clearable :options="statusOptions" placeholder="全部状态" @update:value="load" />
      <n-button @click="load">刷新</n-button>
    </div>
    <n-data-table :loading="loading" :columns="columns" :data="rows" :row-key="(row) => row.id" v-model:checked-row-keys="checkedRowKeys" />
  </section>
</template>

<script setup lang="ts">
import { usePolling } from '@/hooks/web/usePolling';
import { performanceStatusMap as statusMap, isPerformanceActive as active } from '@/utils/executionStatus';

import { asList } from '@/utils/list';

import { computed, h, onActivated, onMounted, reactive, ref } from 'vue';
import { NButton, NProgress, NSpace, NTag, useDialog, useMessage } from 'naive-ui';
import { useRouter } from 'vue-router';
import { http } from '@/utils/http/axios';
import { PerformanceAPI, type PerformanceRun, type PerformanceStatus } from '@/api/performance/http';

const message = useMessage(); const dialog = useDialog(); const router = useRouter(); const rows = ref<PerformanceRun[]>([]); const projects = ref<any[]>([]); const environments = ref<any[]>([]); const loading = ref(false); const poller = usePolling();
const checkedRowKeys = ref<number[]>([]);
const filters = reactive({ project: null as number | null, environment: null as string | null, status: null as PerformanceStatus | null });

const projectOptions = computed(() => projects.value.map((item) => ({ label: item.name, value: Number(item.id) })));
const environmentOptions = computed(() => {
  const uniqueNames = new Map<string, string>();
  environments.value
    .filter((item) => !filters.project || Number(item.project) === Number(filters.project))
    .forEach((item) => {
      const name = String(item.name || '').trim();
      const normalizedName = name.toLocaleLowerCase();
      if (name && !uniqueNames.has(normalizedName)) uniqueNames.set(normalizedName, name);
    });
  return Array.from(uniqueNames.values()).map((name) => ({ label: name, value: name }));
});

const statusOptions = Object.entries(statusMap).map(([value, item]) => ({ label: item.label, value }));

const progressColor = (status: string) => {
  if (status === 'passed') return '#16a34a';
  if (status === 'failed' || status === 'error') return '#dc2626';
  if (status === 'stopped') return '#94a3b8';
  return '#2563eb';
};
const columns: any[] = [
  { type: 'selection', disabled: (row: PerformanceRun) => active(row.status) },
  { title: '执行编号', key: 'execution_no', width: 140 }, { title: '性能场景', key: 'scenario_name' }, { title: '所属项目', key: 'project_name' }, { title: '执行环境', key: 'environment_name' },
  { title: '状态', key: 'status', width: 100, render: (row: PerformanceRun) => h(NTag, { type: statusMap[row.status]?.type || 'default', size: 'small' }, { default: () => statusMap[row.status]?.label || row.status }) },
  { title: '进度', key: 'progress', width: 180, render: (row: PerformanceRun) => {
    const percentage = Math.max(0, Math.min(100, Number(row.progress || 0)));
    return h('div', { class: 'task-progress' }, [
      h(NProgress, {
        class: 'task-progress__bar',
        type: 'line',
        percentage,
        height: 6,
        borderRadius: 4,
        showIndicator: false,
        color: progressColor(row.status),
        railColor: '#e8edf4',
      }),
      h('span', { class: 'task-progress__value' }, `${percentage}%`),
    ]);
  } },
  { title: '当前压力', key: 'current', width: 210, render: (row: PerformanceRun) => `${row.current_vus || 0} VUs / ${(row.current_rps || 0).toFixed(1)} RPS / ${(row.current_tps || 0).toFixed(1)} TPS` },
  { title: '开始时间', key: 'started_at', width: 170, render: (row: PerformanceRun) => row.started_at ? new Date(row.started_at).toLocaleString() : '-' },
  { title: '操作', key: 'actions', width: 220, render: (row: PerformanceRun) => h(NSpace, { size: 14, wrap: false }, { default: () => [
    h(NButton, { text: true, type: 'primary', onClick: () => router.push({ name: 'execution_report', params: { sourceType: 'performance', id: row.id } }) }, { default: () => '查看报告' }),
    active(row.status)
      ? h(NButton, { text: true, type: 'error', onClick: () => stop(row) }, { default: () => '停止' })
      : h(NButton, { text: true, type: 'error', onClick: () => confirmRemove(row) }, { default: () => '删除' }),
  ] }) },
];
function compareReports() { if (checkedRowKeys.value.length < 2 || checkedRowKeys.value.length > 5) return message.warning('请选择 2 至 5 份已完成报告'); router.push({ name: 'performance_compare', query: { ids: checkedRowKeys.value.join(',') } }); }
async function load() { loading.value = true; try { rows.value = asList(await PerformanceAPI.runs({ project: filters.project, environment_name: filters.environment, status: filters.status, _t: Date.now() })); } catch (error: any) { message.error(error?.message || '执行任务加载失败'); } finally { loading.value = false; } }
function handleProjectChange() { filters.environment = null; void load(); }
async function stop(row: PerformanceRun) { try { await PerformanceAPI.stop(row.id); message.success('已发送停止指令'); await load(); } catch (error: any) { message.error(error?.message || '停止失败'); } }
function confirmRemove(row: PerformanceRun) {
  dialog.warning({
    title: '删除执行任务',
    content: `确定删除执行任务「${row.execution_no}」吗？相关报告和运行产物将一并删除。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await PerformanceAPI.deleteRun(row.id);
        rows.value = rows.value.filter((item) => item.id !== row.id);
        checkedRowKeys.value = checkedRowKeys.value.filter((id) => id !== row.id);
        message.success('已删除');
      } catch (error: any) {
        message.error(error?.message || '删除失败');
      }
    },
  });
}
function startPolling() { poller.stop(); poller.start(() => { if (rows.value.some((row) => active(row.status))) void load(); }, 3000); }
onMounted(async () => { const [p, e] = await Promise.all([http.request({ url: '/project/project/', method: 'get', params: { pageSize: 1000 } }), http.request({ url: '/project/environment/', method: 'get', params: { pageSize: 1000 } })]); projects.value = asList(p); environments.value = asList(e); await load(); startPolling(); });
onActivated(load); 
</script>

<style scoped lang="less">
.task-progress{display:flex;align-items:center;gap:10px;width:100%}.task-progress__bar{min-width:88px;flex:1}.task-progress__value{width:42px;color:#475569;font-size:13px;font-weight:600;text-align:right;font-variant-numeric:tabular-nums}
.performance-page{padding:24px 28px}.page-header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.page-header h2{margin:0;color:#1e293b}.page-header p{margin:8px 0 22px;color:#7b8ba3}.filters{display:flex;align-items:center;gap:12px;margin-bottom:16px}.filters :deep(.n-select){width:210px}@media(max-width:640px){.performance-page{padding:16px}.page-header{flex-direction:column}.filters{align-items:stretch;flex-direction:column}.filters :deep(.n-select){width:100%}}
</style>
