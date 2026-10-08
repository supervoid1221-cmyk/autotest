<template>
  <section class="compare-page">
    <header class="page-header">
      <div><h2>性能报告对比</h2><p>同一项目支持同时对比 2 至 5 次性能执行结果。</p></div>
      <n-space><n-button @click="router.back()">返回</n-button><n-button @click="load">刷新</n-button></n-space>
    </header>
    <n-spin :show="loading">
      <n-alert v-if="errorMessage" type="error" class="compare-error">{{ errorMessage }}</n-alert>
      <template v-if="runs.length">
        <div class="run-cards">
          <article v-for="(run, index) in runs" :key="run.id" :style="{ '--run-color': colors[index] }">
            <i />
            <div><strong>{{ run.execution_no }}</strong><span>{{ run.scenario_name }} · {{ run.environment_name }}</span></div>
            <n-tag :type="run.status === 'passed' ? 'success' : 'error'" size="small">{{ statusLabel(run.status) }}</n-tag>
          </article>
        </div>

        <section class="panel">
          <header><div><strong>核心指标对比</strong><span>第一列报告作为基准，变化值为相对基准的差异</span></div></header>
          <div class="comparison-table-wrap">
            <table class="comparison-table">
              <thead><tr><th>指标</th><th v-for="run in runs" :key="run.id">{{ run.execution_no }}</th></tr></thead>
              <tbody>
                <tr v-for="metric in comparisonMetrics" :key="metric.key">
                  <th>{{ metric.label }}</th>
                  <td v-for="(run, index) in runs" :key="run.id">
                    <strong>{{ formatMetric(metric.key, metric.value(run)) }}</strong>
                    <small v-if="index > 0" :class="deltaClass(metric, metric.value(run))">{{ deltaText(metric, metric.value(run)) }}</small>
                    <small v-else>基准</small>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <header class="trend-header">
            <div><strong>趋势对比</strong><span>横轴统一转换为任务开始后的运行秒数</span></div>
            <n-select v-model:value="selectedMetric" :options="trendOptions" class="metric-select" @update:value="renderChart" />
          </header>
          <div v-if="hasTrend" ref="chartRef" class="trend-chart" />
          <n-empty v-else description="所选报告暂无趋势数据" class="trend-empty" />
        </section>
      </template>
    </n-spin>
  </section>
</template>

<script setup lang="ts">
import { performanceStatusLabels as statusLabels } from '@/utils/executionStatus';

import { computed, nextTick, onMounted, ref, watch, type Ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useMessage } from 'naive-ui';
import { PerformanceAPI, type PerformanceRun, type PerformanceStatus } from '@/api/performance/http';
import { MonitorAPI, type MonitorSnapshot } from '@/api/monitor/http';
import { useECharts } from '@/hooks/web/useECharts';

type MetricKey = 'users' | 'requests' | 'failures' | 'rps' | 'tps' | 'avg' | 'max' | 'p95' | 'p99' | 'error_rate' | 'server_cpu' | 'server_memory' | 'server_disk' | 'server_iops';
type TrendMetricKey = 'rps' | 'tps' | 'p95' | 'error_rate';
interface ComparisonMetric { key: MetricKey; label: string; lowerIsBetter: boolean; value: (run: PerformanceRun) => number; }

const route = useRoute(); const router = useRouter(); const message = useMessage();
const loading = ref(false); const errorMessage = ref(''); const runs = ref<PerformanceRun[]>([]);
const serverMetricsByRun = ref<Record<number, MonitorSnapshot>>({});
const selectedMetric = ref<TrendMetricKey>('rps');
const chartRef = ref<HTMLDivElement | null>(null); const chart = useECharts(chartRef as Ref<HTMLDivElement>);
const colors = ['#2563eb', '#16a36a', '#f08b0b', '#8b5cf6', '#e34d59'];

const statusLabel = (status: PerformanceStatus) => statusLabels[status] || status;
const metric = (run: PerformanceRun, name: string, key: string) => { const item = run.summary?.metrics?.[name] || {}; return Number(item?.values?.[key] ?? item?.[key] ?? 0); };
const bucketMax = (run: PerformanceRun, key: keyof PerformanceRun['metric_buckets'][number]) => Math.max(0, ...(run.metric_buckets || []).map((item) => Number(item[key] || 0)));
const bucketSum = (run: PerformanceRun, key: keyof PerformanceRun['metric_buckets'][number]) => (run.metric_buckets || []).reduce((sum, item) => sum + Number(item[key] || 0), 0);
const serverAverage = (run: PerformanceRun, key: keyof MonitorSnapshot['current']) => {
  const snapshot = serverMetricsByRun.value[run.id];
  const values = (snapshot?.series?.[key] || []).map((item) => Number(item.value)).filter(Number.isFinite);
  if (values.length) return values.reduce((sum, value) => sum + value, 0) / values.length;
  const current = snapshot?.current?.[key];
  return current == null ? Number.NaN : Number(current);
};
const comparisonMetrics: ComparisonMetric[] = [
  { key: 'users', label: '峰值用户数', lowerIsBetter: false, value: (run) => Math.max(metric(run, 'vus', 'max'), metric(run, 'vus_max', 'max'), bucketMax(run, 'vus')) || Number(run.configured_vus || 0) },
  { key: 'requests', label: '总请求数', lowerIsBetter: false, value: (run) => metric(run, 'http_reqs', 'count') || bucketSum(run, 'request_count') },
  { key: 'failures', label: '失败请求数', lowerIsBetter: true, value: (run) => metric(run, 'http_req_failed', 'passes') || bucketSum(run, 'failed_count') },
  { key: 'rps', label: '平均 RPS', lowerIsBetter: false, value: (run) => metric(run, 'http_reqs', 'rate') || Number(run.current_rps || 0) },
  { key: 'tps', label: '平均 TPS', lowerIsBetter: false, value: (run) => metric(run, 'iterations', 'rate') || Number(run.current_tps || 0) },
  { key: 'avg', label: '平均响应时间', lowerIsBetter: true, value: (run) => metric(run, 'http_req_duration', 'avg') },
  { key: 'max', label: '最大响应时间', lowerIsBetter: true, value: (run) => metric(run, 'http_req_duration', 'max') || bucketMax(run, 'duration_max') },
  { key: 'p95', label: 'P95 响应时间', lowerIsBetter: true, value: (run) => metric(run, 'http_req_duration', 'p(95)') || bucketMax(run, 'duration_p95') },
  { key: 'p99', label: 'P99 响应时间', lowerIsBetter: true, value: (run) => metric(run, 'http_req_duration', 'p(99)') || bucketMax(run, 'duration_p99') },
  { key: 'error_rate', label: '错误率', lowerIsBetter: true, value: (run) => metric(run, 'http_req_failed', 'rate') * 100 || bucketMax(run, 'error_rate') },
  { key: 'server_cpu', label: '平均 CPU 使用率', lowerIsBetter: true, value: (run) => serverAverage(run, 'cpu') },
  { key: 'server_memory', label: '平均内存使用率', lowerIsBetter: true, value: (run) => serverAverage(run, 'memory') },
  { key: 'server_disk', label: '平均磁盘使用率', lowerIsBetter: true, value: (run) => serverAverage(run, 'disk') },
  { key: 'server_iops', label: '平均总 IOPS', lowerIsBetter: false, value: (run) => serverAverage(run, 'disk_iops') },
];
const trendOptions = [{ label: 'RPS', value: 'rps' }, { label: 'TPS', value: 'tps' }, { label: 'P95 响应时间', value: 'p95' }, { label: '错误率', value: 'error_rate' }];
const baselineValue = (metricItem: ComparisonMetric) => runs.value.length ? metricItem.value(runs.value[0]) : 0;
function formatMetric(key: MetricKey, value: number) { if (!Number.isFinite(value)) return '-'; if (['avg', 'max', 'p95', 'p99'].includes(key)) return `${value.toFixed(3)} ms`; if (key === 'error_rate' || ['server_cpu', 'server_memory', 'server_disk'].includes(key)) return `${value.toFixed(3)}%`; if (key === 'server_iops') return `${value.toFixed(3)} IOPS`; if (key === 'requests' || key === 'failures') return Math.round(value).toLocaleString(); if (key === 'users') return `${Math.round(value)} 人`; if (key === 'rps') return `${value.toFixed(3)} req/s`; if (key === 'tps') return `${value.toFixed(3)} txn/s`; return value.toFixed(3); }
function delta(metricItem: ComparisonMetric, value: number) { const baseline = baselineValue(metricItem); return Number.isFinite(value) && Number.isFinite(baseline) && baseline ? (value - baseline) / baseline * 100 : Number.NaN; }
function deltaText(metricItem: ComparisonMetric, value: number) { const valueDelta = delta(metricItem, value); return Number.isFinite(valueDelta) ? `${valueDelta >= 0 ? '+' : ''}${valueDelta.toFixed(1)}%` : '-'; }
function deltaClass(metricItem: ComparisonMetric, value: number) { const valueDelta = delta(metricItem, value); return !Number.isFinite(valueDelta) || valueDelta === 0 ? 'neutral' : valueDelta < 0 ? 'better' : 'worse'; }
const hasTrend = computed(() => runs.value.some((run) => run.metric_buckets?.length));
function trendValue(run: PerformanceRun, bucket: any) { if (selectedMetric.value === 'rps') return bucket.rps; if (selectedMetric.value === 'tps') return bucket.tps; if (selectedMetric.value === 'p95') return bucket.duration_p95; return bucket.error_rate; }
async function renderChart() { if (!hasTrend.value) return; await nextTick(); const unit = selectedMetric.value === 'p95' ? 'ms' : selectedMetric.value === 'error_rate' ? '%' : ''; chart.setOptions({ tooltip: { trigger: 'axis', valueFormatter: (value: any) => `${Number(value).toFixed(2)}${unit ? ` ${unit}` : ''}` }, legend: { data: runs.value.map((run) => String(run.execution_no)) }, grid: { left: 20, right: 24, top: 46, bottom: 28, containLabel: true }, xAxis: { type: 'value', name: '运行秒数', min: 0 }, yAxis: { type: 'value', name: trendOptions.find((item) => item.value === selectedMetric.value)?.label, scale: selectedMetric.value !== 'error_rate' }, color: colors, series: runs.value.map((run) => { const first = run.metric_buckets?.length ? new Date(run.metric_buckets[0].timestamp).getTime() : 0; return { name: String(run.execution_no), type: 'line', smooth: 0.15, showSymbol: false, data: (run.metric_buckets || []).map((bucket) => [Math.max(0, (new Date(bucket.timestamp).getTime() - first) / 1000), trendValue(run, bucket)]) }; }) }); }
function monitorRange(run: PerformanceRun) {
  const firstBucket = run.metric_buckets?.[0]?.timestamp;
  const lastBucket = run.metric_buckets?.[run.metric_buckets.length - 1]?.timestamp;
  const startValue = run.load_started_at || firstBucket || run.started_at;
  if (!startValue) return null;
  const start = new Date(startValue).getTime();
  let end = run.load_finished_at ? new Date(run.load_finished_at).getTime() : 0;
  if (!end && run.load_duration_ms) end = start + Number(run.load_duration_ms);
  if (!end && lastBucket) end = new Date(lastBucket).getTime();
  if (!end && run.finished_at) end = new Date(run.finished_at).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= 0) return null;
  return { startTime: start - 60_000, endTime: end + 60_000 };
}
async function loadServerMetrics(items: PerformanceRun[]) {
  const entries = await Promise.all(items.map(async (run) => {
    const range = monitorRange(run);
    if (!run.monitor_target || !range) return null;
    try { return [run.id, await MonitorAPI.targetMetrics(run.monitor_target, range)] as const; } catch { return null; }
  }));
  serverMetricsByRun.value = Object.fromEntries(entries.filter((item): item is readonly [number, MonitorSnapshot] => Boolean(item)));
}
async function load() { const ids = String(route.query.ids || '').split(',').map(Number).filter(Boolean); loading.value = true; errorMessage.value = ''; try { runs.value = await PerformanceAPI.compare(ids); await loadServerMetrics(runs.value); await renderChart(); } catch (error: any) { errorMessage.value = error?.message || '报告对比加载失败'; message.error(errorMessage.value); } finally { loading.value = false; } }
onMounted(load); watch(() => route.query.ids, load);
</script>

<style scoped lang="less">
.compare-page{min-height:100%;padding:24px 28px;background:#f5f7fb}.page-header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}.page-header h2{margin:0;color:#1e293b}.page-header p{margin:8px 0 22px;color:#7b8ba3}.compare-error{margin-bottom:16px}.run-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}.run-cards article{display:flex;align-items:center;gap:12px;padding:15px 16px;border:1px solid #e1e7ef;border-radius:10px;background:#fff}.run-cards i{width:10px;height:38px;border-radius:5px;background:var(--run-color)}.run-cards div{min-width:0;flex:1}.run-cards strong,.run-cards span{display:block}.run-cards strong{color:#25344b}.run-cards span{overflow:hidden;margin-top:4px;color:#8290a5;font-size:12px;white-space:nowrap;text-overflow:ellipsis}.panel{margin-top:18px;padding:18px;border:1px solid #e1e7ef;border-radius:10px;background:#fff}.panel>header{margin-bottom:14px}.panel>header strong,.panel>header span{display:block}.panel>header span{margin-top:4px;color:#8290a5;font-size:12px}.comparison-table-wrap{overflow:auto}.comparison-table{width:100%;border-collapse:collapse}.comparison-table th,.comparison-table td{min-width:150px;padding:13px 14px;border-bottom:1px solid #e8edf3;text-align:left}.comparison-table thead th{background:#f7f9fc;color:#64748b;font-size:12px}.comparison-table tbody th{color:#475569;font-weight:500}.comparison-table td strong,.comparison-table td small{display:block}.comparison-table td strong{color:#1f2e46;font-size:16px}.comparison-table td small{margin-top:4px;color:#94a0b2}.comparison-table td small.better{color:#159b67}.comparison-table td small.worse{color:#e14c58}.trend-header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.metric-select{width:190px}.trend-chart{height:380px}.trend-empty{height:260px;padding-top:70px}@media(max-width:640px){.compare-page{padding:16px}.page-header,.trend-header{flex-direction:column}.metric-select{width:100%}}
</style>
