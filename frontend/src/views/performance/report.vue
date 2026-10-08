<template>
  <section class="report-page">
    <header class="report-header">
      <div><h2>性能报告</h2><p v-if="run">{{ run.scenario_name }} · {{ run.project_name }} · {{ run.environment_name }} · 执行人：{{ run.created_by_name || '-' }}</p></div>
      <div class="report-actions">
        <div class="refresh-control">
          <span>自动刷新</span>
          <n-select v-model:value="refreshInterval" :options="refreshIntervalOptions" size="small" />
        </div>
        <n-space>
          <n-button @click="load">刷新</n-button>
          <n-button v-if="run && isActive" type="error" secondary @click="stop">停止任务</n-button>
        </n-space>
      </div>
    </header>
    <n-spin :show="loading">
      <template v-if="run">
        <div class="run-context">
          <div><span>执行编号</span><strong>{{ run.execution_no }}</strong></div>
          <div><span>状态</span><n-tag :type="statusInfo.type">{{ statusInfo.label }}</n-tag></div>
          <div><span>执行进度</span><n-progress type="line" :percentage="run.progress" :height="8" /></div>
          <div><span>监控目标</span><strong>{{ run.monitor_target_name || '未关联' }}</strong></div>
          <div><span>压测开始时间</span><strong class="time-value">{{ formatDateTime(actualLoadStartedAt) }}</strong></div>
          <div><span>压测结束时间</span><strong class="time-value">{{ isActive && actualLoadStartedAt ? '执行中' : formatDateTime(actualLoadFinishedAt) }}</strong></div>
          <div><span>实际压测时长</span><strong class="time-value">{{ executionDuration }}</strong></div>
        </div>
        <n-alert v-if="run.error_message" type="error" class="run-error">{{ run.error_message }}</n-alert>
        <div class="metric-cards">
          <article v-for="item in overviewMetrics" :key="item.label"><span>{{ item.label }}</span><strong>{{ item.value }}</strong><small>{{ item.help }}</small></article>
        </div>
        <section class="panel">
          <header><div><strong>性能趋势</strong><span>分别展示负载、吞吐、响应时间和异常趋势</span></div></header>
          <div v-if="run.metric_buckets.length" class="performance-trend-grid">
            <article class="trend-item">
              <header><strong>负载趋势</strong><span>实际用户数与计划用户数</span></header>
              <div ref="loadChartRef" class="performance-trend-chart" />
            </article>
            <article class="trend-item">
              <header><strong>吞吐趋势</strong><span>每秒 HTTP 请求数与业务事务数</span></header>
              <div ref="throughputChartRef" class="performance-trend-chart" />
            </article>
            <article class="trend-item">
              <header><strong>响应时间趋势</strong><span>平均值、P99 与最大值</span></header>
              <div ref="responseChartRef" class="performance-trend-chart" />
            </article>
            <article class="trend-item">
              <header><strong>异常趋势</strong><span>错误率与失败请求数</span></header>
              <div ref="errorChartRef" class="performance-trend-chart" />
            </article>
          </div>
          <n-empty v-else description="任务执行完成后生成聚合趋势数据" class="chart-empty" />
        </section>
        <section v-if="run.monitor_target" class="panel">
          <header class="chart-header">
            <div><strong>服务器资源关联</strong><span>与本次性能任务使用同一时间范围</span></div>
            <n-select v-model:value="serverMetric" :options="serverMetricOptions" size="small" class="metric-filter" />
          </header>
          <n-alert v-if="serverMetricsError" type="warning" class="server-metrics-warning">{{ serverMetricsError }}</n-alert>
          <div v-if="serverMetricCards.length" class="server-stat-cards">
            <button
              v-for="item in serverMetricCards"
              :key="item.metric"
              type="button"
              class="server-stat-card"
              :class="{ active: serverMetric === item.metric }"
              @click="serverMetric = serverMetric === item.metric ? 'all' : item.metric"
            >
              <span>{{ item.averageLabel }}</span>
              <strong>{{ item.average }}</strong>
              <small>峰值 {{ item.peak }}</small>
            </button>
          </div>
          <div ref="serverChartRef" v-show="serverSeriesAvailable" class="trend-chart" />
          <n-empty v-if="!serverSeriesAvailable" :description="serverMetricsError ? '获取失败，可点击刷新重试' : '暂未获取到关联服务器指标'" class="chart-empty" />
        </section>
        <section class="panel aggregate-panel">
          <header><div><strong>聚合报告</strong><span>按接口汇总样本、响应时间、错误率、吞吐量及流量比例</span></div><n-space><n-input v-model:value="aggregateSearch" clearable placeholder="搜索接口" class="aggregate-search" /><n-select v-model:value="aggregateStatus" :options="aggregateStatusOptions" class="aggregate-status" /><n-button @click="exportAggregate">导出 CSV</n-button></n-space></header>
          <n-data-table :columns="endpointColumns" :data="filteredAggregateRows" :row-key="(row) => row.id" :scroll-x="2050" />
        </section>
        <section class="panel"><header><div><strong>阈值结果</strong><span>阈值不满足时任务状态为未通过</span></div></header><n-data-table :columns="thresholdColumns" :data="thresholdRows" :row-key="(row) => row.key" /></section>
        <section v-if="run.notification_deliveries?.length" class="panel"><header><div><strong>通知记录</strong><span>同时校验 HTTP 状态和通知平台业务码</span></div></header><n-data-table :columns="notificationColumns" :data="run.notification_deliveries" :row-key="(row) => row.id" /></section>
        <section class="panel"><header><div><strong>实时执行日志</strong><span>日志中的认证信息和项目变量不会明文输出</span></div></header><pre class="run-log">{{ logContent || '暂无日志' }}</pre></section>
      </template>
    </n-spin>
  </section>
</template>

<script setup lang="ts">
import { usePolling } from '@/hooks/web/usePolling';
import { performanceStatusMap as statusMap, isPerformanceActive } from '@/utils/executionStatus';

import { computed, nextTick, onMounted, onUnmounted, ref, watch, type Ref } from 'vue';
import { useRoute } from 'vue-router';
import { useMessage } from 'naive-ui';
import { PerformanceAPI, type PerformanceRun } from '@/api/performance/http';
import { MonitorAPI, type MonitorSnapshot } from '@/api/monitor/http';
import { useECharts } from '@/hooks/web/useECharts';
import { formatDateTime, formatDurationMilliseconds as formatDuration } from '@/utils/time';

const route = useRoute(); const message = useMessage(); const loading = ref(false); const run = ref<PerformanceRun>(); const logContent = ref(''); const serverMetrics = ref<MonitorSnapshot>(); const serverMetricsError = ref(''); const aggregateSearch = ref(''); const aggregateStatus = ref('all'); const serverMetric = ref('all'); const refreshInterval = ref(3000); const currentTime = ref(Date.now()); const poller = usePolling(); let clockTimer: number | undefined; let lastServerFetch = 0; let lastServerAttempt = 0; let loadInFlight = false;
const loadChartRef = ref<HTMLDivElement | null>(null); const throughputChartRef = ref<HTMLDivElement | null>(null); const responseChartRef = ref<HTMLDivElement | null>(null); const errorChartRef = ref<HTMLDivElement | null>(null); const serverChartRef = ref<HTMLDivElement | null>(null);
const loadChart = useECharts(loadChartRef as Ref<HTMLDivElement>); const throughputChart = useECharts(throughputChartRef as Ref<HTMLDivElement>); const responseChart = useECharts(responseChartRef as Ref<HTMLDivElement>); const errorChart = useECharts(errorChartRef as Ref<HTMLDivElement>); const serverChart = useECharts(serverChartRef as Ref<HTMLDivElement>);
const isActive = computed(() => Boolean(run.value && isPerformanceActive(run.value.status)));
 const statusInfo = computed(() => statusMap[run.value?.status || 'queued']);
const refreshIntervalOptions = [
  { label: '不自动刷新', value: 0 },
  { label: '1 秒', value: 1000 },
  { label: '3 秒', value: 3000 },
  { label: '5 秒', value: 5000 },
  { label: '10 秒', value: 10000 },
  { label: '30 秒', value: 30000 },
];
const firstBucket = computed(() => run.value?.metric_buckets?.[0]);
const summaryLoadDurationMs = computed(() => Number(run.value?.summary?.state?.testRunDurationMs || 0));
const actualLoadStartedAt = computed(() => run.value?.load_started_at || firstBucket.value?.timestamp);
const actualLoadFinishedAt = computed(() => {
  if (run.value?.load_finished_at) return run.value.load_finished_at;
  if (!actualLoadStartedAt.value || isActive.value) return undefined;
  const duration = Number(run.value?.load_duration_ms || summaryLoadDurationMs.value);
  if (duration > 0) return new Date(new Date(actualLoadStartedAt.value).getTime() + duration).toISOString();
  return latestBucket.value?.timestamp;
});
const executionDuration = computed(() => {
  if (!actualLoadStartedAt.value) return '-';
  const recordedDuration = Number(run.value?.load_duration_ms || summaryLoadDurationMs.value);
  if (!isActive.value && recordedDuration > 0) return formatDuration(recordedDuration);
  const start = new Date(actualLoadStartedAt.value).getTime();
  const end = actualLoadFinishedAt.value ? new Date(actualLoadFinishedAt.value).getTime() : currentTime.value;
  if (!Number.isFinite(start) || !Number.isFinite(end)) return '-';
  return formatDuration(end - start);
});
const summaryMetric = (name: string, key: string) => {
  const metric = run.value?.summary?.metrics?.[name] || {};
  return Number(metric?.values?.[key] ?? metric?.[key] ?? 0);
};
const latestBucket = computed(() => run.value?.metric_buckets?.[run.value.metric_buckets.length - 1]);
const reportTimeRange = computed(() => {
  const loadStart = actualLoadStartedAt.value || run.value?.started_at;
  if (!loadStart) return null;
  const start = new Date(loadStart).getTime() - 60_000;
  const lastBucket = latestBucket.value?.timestamp ? new Date(latestBucket.value.timestamp).getTime() + 5_000 : 0;
  const scriptEnd = isActive.value ? Date.now() : (lastBucket || (run.value.finished_at ? new Date(run.value.finished_at).getTime() : Date.now()));
  return { start, end: scriptEnd + (isActive.value ? 0 : 60_000) };
});
const overviewMetrics = computed(() => {
  const buckets = run.value?.metric_buckets || [];
  const requestCount = summaryMetric('http_reqs', 'count') || buckets.reduce((sum, item) => sum + item.request_count, 0);
  const failedCount = summaryMetric('http_req_failed', 'passes') || buckets.reduce((sum, item) => sum + item.failed_count, 0);
  const completed = Boolean(run.value && !activeStatuses.includes(run.value.status));
  const rps = completed ? summaryMetric('http_reqs', 'rate') : (run.value?.current_rps || latestBucket.value?.rps || 0);
  const tps = completed ? summaryMetric('iterations', 'rate') : (run.value?.current_tps || latestBucket.value?.tps || 0);
  const sampledPeakVus = Math.max(0, ...buckets.map((item) => Number(item.vus || 0)), Number(run.value?.current_vus || 0));
  const observedVus = completed
    ? Math.max(summaryMetric('vus', 'max'), summaryMetric('vus_max', 'max'), sampledPeakVus)
    : sampledPeakVus;
  const displayedVus = completed ? Number(run.value?.configured_vus || observedVus) : Number(run.value?.current_vus || latestBucket.value?.vus || 0);
  return [
    { label: '用户数', value: String(Math.round(displayedVus)), help: completed ? `实际观测峰值 ${Math.round(observedVus)} 人` : '当前并发用户数' },
    { label: '总请求数', value: String(Math.round(requestCount)), help: `${failedCount} 次失败` },
    { label: completed ? '平均 RPS' : '当前 RPS', value: `${Number(rps).toFixed(1)} req/s`, help: '每秒 HTTP 请求数' },
    { label: completed ? '平均 TPS' : '当前 TPS', value: `${Number(tps).toFixed(1)} txn/s`, help: '每秒完成业务事务数' },
    { label: '平均响应时间', value: `${(summaryMetric('http_req_duration', 'avg') || latestBucket.value?.duration_avg || 0).toFixed(1)} ms`, help: '全部请求平均耗时' },
    { label: '最大响应时间', value: `${(summaryMetric('http_req_duration', 'max') || latestBucket.value?.duration_max || 0).toFixed(1)} ms`, help: '最慢单次请求耗时' },
    { label: 'P95', value: `${(summaryMetric('http_req_duration', 'p(95)') || latestBucket.value?.duration_p95 || 0).toFixed(1)} ms`, help: `P99 ${(summaryMetric('http_req_duration', 'p(99)') || latestBucket.value?.duration_p99 || 0).toFixed(1)} ms` },
    { label: '错误率', value: `${((summaryMetric('http_req_failed', 'rate') * 100) || latestBucket.value?.error_rate || 0).toFixed(2)}%`, help: '请求失败占比' },
  ];
});
const thresholdRows = computed(() =>
  Object.entries(run.value?.threshold_results || {}).flatMap(([metric, rules]: any) =>
    Object.entries(rules || {}).map(([rule, result]: any) => ({
      key: `${metric}-${rule}`,
      metric,
      rule,
      passed: Boolean(result?.ok),
    }))
  )
);
const aggregateStatusOptions = [{ label: '全部结果', value: 'all' }, { label: '存在失败', value: 'failed' }, { label: '全部成功', value: 'passed' }];
const cleanEndpointName = (name: string) => String(name || '').replace(/^\[[^\]]+\]\s*/, '');
const kbPerSecond = (row: any, key: 'received_bytes' | 'sent_bytes') => { const elapsed = row.throughput > 0 ? row.request_count / row.throughput : 0; return elapsed > 0 ? Number(row[key] || 0) / 1024 / elapsed : 0; };
const aggregateRows = computed(() => {
  const rows = run.value?.endpoint_metrics || [];
  if (!rows.length) return [];
  const totalRequests = rows.reduce((sum, item) => sum + item.request_count, 0);
  const totalFailed = rows.reduce((sum, item) => sum + item.failed_count, 0);
  const totalP99 = Number(run.value?.summary?.aggregate?.duration_p99 || summaryMetric('http_req_duration', 'p(99)') || Math.max(0, ...rows.map((item) => Number(item.duration_p99 || 0))));
  return [...rows, { id: 'total', endpoint_name: '合计', method: '-', request_count: totalRequests, failed_count: totalFailed, error_rate: totalRequests ? totalFailed / totalRequests * 100 : 0, duration_avg: summaryMetric('http_req_duration', 'avg'), duration_min: summaryMetric('http_req_duration', 'min'), duration_median: summaryMetric('http_req_duration', 'med'), duration_max: summaryMetric('http_req_duration', 'max'), duration_p90: summaryMetric('http_req_duration', 'p(90)'), duration_p95: summaryMetric('http_req_duration', 'p(95)'), duration_p99: totalP99, throughput: run.value?.current_rps || 0, configured_ratio: 100, received_bytes: rows.reduce((sum, item) => sum + item.received_bytes, 0), sent_bytes: rows.reduce((sum, item) => sum + item.sent_bytes, 0) }];
});
const filteredAggregateRows = computed(() => aggregateRows.value.filter((item: any) => { if (item.id === 'total') return aggregateStatus.value === 'all' && !aggregateSearch.value; const matchesName = !aggregateSearch.value || item.endpoint_name.toLowerCase().includes(aggregateSearch.value.toLowerCase()); const matchesStatus = aggregateStatus.value === 'all' || (aggregateStatus.value === 'failed' ? item.failed_count > 0 : item.failed_count === 0); return matchesName && matchesStatus; }));
const endpointColumns: any[] = [
  { title: '接口', key: 'endpoint_name', width: 220, fixed: 'left', render: (row: any) => cleanEndpointName(row.endpoint_name) }, { title: '方法', key: 'method', width: 80 },
  { title: '样本数', key: 'request_count', width: 90, sorter: (a: any, b: any) => a.request_count - b.request_count },
  { title: '失败数', key: 'failed_count', width: 90, sorter: (a: any, b: any) => a.failed_count - b.failed_count },
  { title: '错误率', key: 'error_rate', width: 95, sorter: (a: any, b: any) => a.error_rate - b.error_rate, render: (row: any) => `${Number(row.error_rate).toFixed(2)}%` },
  { title: '平均值', key: 'duration_avg', width: 100, sorter: (a: any, b: any) => a.duration_avg - b.duration_avg, render: (row: any) => `${Number(row.duration_avg).toFixed(1)} ms` },
  { title: '中位数', key: 'duration_median', width: 100, render: (row: any) => `${Number(row.duration_median).toFixed(1)} ms` },
  { title: 'P90', key: 'duration_p90', width: 95, render: (row: any) => `${Number(row.duration_p90).toFixed(1)} ms` },
  { title: 'P95', key: 'duration_p95', width: 95, sorter: (a: any, b: any) => a.duration_p95 - b.duration_p95, render: (row: any) => `${Number(row.duration_p95).toFixed(1)} ms` },
  { title: 'P99', key: 'duration_p99', width: 95, render: (row: any) => `${Number(row.duration_p99).toFixed(1)} ms` },
  { title: '最小值', key: 'duration_min', width: 100, render: (row: any) => `${Number(row.duration_min).toFixed(1)} ms` },
  { title: '最大值', key: 'duration_max', width: 100, render: (row: any) => `${Number(row.duration_max).toFixed(1)} ms` },
  { title: '吞吐量', key: 'throughput', width: 110, sorter: (a: any, b: any) => a.throughput - b.throughput, render: (row: any) => `${Number(row.throughput).toFixed(2)} req/s` },
  { title: '配置比例', key: 'configured_ratio', width: 100, render: (row: any) => `${Number(row.configured_ratio).toFixed(1)}%` },
  { title: '接收 KB/s', key: 'received_bytes', width: 110, render: (row: any) => kbPerSecond(row, 'received_bytes').toFixed(2) },
  { title: '发送 KB/s', key: 'sent_bytes', width: 110, render: (row: any) => kbPerSecond(row, 'sent_bytes').toFixed(2) },
];
const thresholdColumns: any[] = [{ title: '指标', key: 'metric' }, { title: '规则', key: 'rule' }, { title: '结果', key: 'passed', render: (row: any) => row.passed ? '通过' : '未通过' }];
const notificationColumns: any[] = [{ title: '通知渠道', key: 'channel_name' }, { title: '状态', key: 'status', width: 110, render: (row: any) => row.status === 'sent' ? '已发送' : '发送失败' }, { title: '响应码', key: 'response_code', width: 100, render: (row: any) => row.response_code ?? '-' }, { title: '结果说明', key: 'response_summary', ellipsis: { tooltip: true } }, { title: '发送时间', key: 'created_at', width: 180, render: (row: any) => new Date(row.created_at).toLocaleString() }];
const serverMetricOptions = ['全部', 'CPU', '内存', '磁盘', '读取 IOPS', '写入 IOPS', '总 IOPS'].map((label) => ({ label, value: label === '全部' ? 'all' : label }));
const defaultServerMetrics = ['CPU', '内存', '磁盘', '总 IOPS'];
const serverMetricDefinitions = [
  { key: 'cpu', metric: 'CPU', averageLabel: 'CPU 平均值', unit: '%' },
  { key: 'memory', metric: '内存', averageLabel: '内存平均值', unit: '%' },
  { key: 'disk', metric: '磁盘', averageLabel: '磁盘平均值', unit: '%' },
  { key: 'disk_iops', metric: '总 IOPS', averageLabel: '总 IOPS 平均值', unit: ' IOPS' },
] as const;
const serverMetricCards = computed(() => serverMetricDefinitions.flatMap((definition) => {
  const values = (serverMetrics.value?.series?.[definition.key] || [])
    .map((item) => Number(item.value))
    .filter((value) => Number.isFinite(value));
  const currentRaw = serverMetrics.value?.current?.[definition.key];
  const currentValue = currentRaw == null ? Number.NaN : Number(currentRaw);
  if (!values.length && !Number.isFinite(currentValue)) return [];
  const samples = values.length ? values : [currentValue];
  const peak = Math.max(...samples);
  const average = samples.reduce((sum, value) => sum + value, 0) / samples.length;
  const format = (value: number) => `${value.toFixed(3)}${definition.unit}`;
  return [{ ...definition, peak: format(peak), average: format(average) }];
}));
const filterServerSeries = (series: any[], selected: string) => selected === 'all' ? series.filter((item) => defaultServerMetrics.includes(item.name)) : series.filter((item) => item.name === selected);
const formatTrendValue = (value: any) => {
  const rawValue = Array.isArray(value) ? value[value.length - 1] : value;
  const numericValue = Number(rawValue);
  return Number.isFinite(numericValue) ? numericValue.toFixed(3) : '-';
};
const hasServerMetricSeries = (snapshot?: MonitorSnapshot) => ['cpu', 'memory', 'disk', 'disk_iops'].some((key) => (snapshot?.series?.[key] || []).length);
const serverSeriesAvailable = computed(() => hasServerMetricSeries(serverMetrics.value));
function applyChartTimeRange() {
  const range = reportTimeRange.value;
  if (!range) return;
  const xAxis = { type: 'time' as const, min: range.start, max: range.end };
  loadChart.setOptions({ xAxis }, false);
  throughputChart.setOptions({ xAxis }, false);
  responseChart.setOptions({ xAxis }, false);
  errorChart.setOptions({ xAxis }, false);
  if (serverSeriesAvailable.value) serverChart.setOptions({ xAxis }, false);
}
async function renderCharts() {
  await nextTick();
  const buckets = run.value?.metric_buckets || [];
  if (buckets.length) {
    const times = buckets.map((item) => new Date(item.timestamp).getTime());
    const hasRecordedTargets = buckets.some((item) => Number(item.target_vus || 0) > 0);
    const common = { tooltip: { trigger: 'axis', valueFormatter: formatTrendValue }, grid: { left: 18, right: 22, top: 42, bottom: 20, containLabel: true }, xAxis: { type: 'time' } };
    loadChart.setOptions({ ...common, color: ['#1d4ed8', '#475569'], legend: { data: ['实际用户数', '计划用户数'] }, yAxis: { type: 'value', name: '用户数', min: 0, minInterval: 1 }, series: [
      { name: '实际用户数', type: 'line', showSymbol: false, lineStyle: { width: 2.5 }, data: buckets.map((item, index) => [times[index], item.vus]) },
      { name: '计划用户数', type: 'line', showSymbol: false, lineStyle: { width: 2, type: 'dashed' }, data: buckets.map((item, index) => [times[index], hasRecordedTargets ? item.target_vus : run.value?.configured_vus || 0]) },
    ] });
    throughputChart.setOptions({ ...common, color: ['#047857', '#6d28d9'], legend: { data: ['RPS', 'TPS'] }, yAxis: { type: 'value', name: '次/秒', min: 0 }, series: [
      { name: 'RPS', type: 'line', showSymbol: false, lineStyle: { width: 2.5 }, tooltip: { valueFormatter: (value: any) => `${formatTrendValue(value)} req/s` }, data: buckets.map((item, index) => [times[index], item.rps]) },
      { name: 'TPS', type: 'line', showSymbol: false, lineStyle: { width: 2.5, type: 'dashed' }, tooltip: { valueFormatter: (value: any) => `${formatTrendValue(value)} txn/s` }, data: buckets.map((item, index) => [times[index], item.tps]) },
    ] });
    responseChart.setOptions({ ...common, color: ['#b45309', '#6d28d9', '#1e293b'], legend: { data: ['平均值', 'P99', '最大值'] }, yAxis: { type: 'value', name: 'ms', min: 0 }, series: [
      { name: '平均值', type: 'line', showSymbol: false, lineStyle: { width: 2.5 }, data: buckets.map((item, index) => [times[index], item.duration_avg]) },
      { name: 'P99', type: 'line', showSymbol: false, lineStyle: { width: 2.2 }, data: buckets.map((item, index) => [times[index], item.duration_p99]) },
      { name: '最大值', type: 'line', showSymbol: false, lineStyle: { width: 1.8, type: 'dashed' }, data: buckets.map((item, index) => [times[index], item.duration_max]) },
    ] });
    errorChart.setOptions({ ...common, color: ['#dc2626', '#991b1b'], legend: { data: ['错误率', '失败请求数'] }, yAxis: [{ type: 'value', name: '错误率', min: 0, axisLabel: { formatter: '{value}%' } }, { type: 'value', name: '失败数', min: 0, minInterval: 1 }], series: [
      { name: '错误率', type: 'line', yAxisIndex: 0, showSymbol: false, lineStyle: { width: 2.5, color: '#dc2626' }, itemStyle: { color: '#dc2626' }, areaStyle: { color: '#fee2e2', opacity: 0.45 }, data: buckets.map((item, index) => [times[index], item.error_rate]) },
      { name: '失败请求数', type: 'line', yAxisIndex: 1, showSymbol: false, lineStyle: { width: 2.2, color: '#991b1b' }, itemStyle: { color: '#991b1b' }, data: buckets.map((item, index) => [times[index], item.failed_count]) },
    ] });
  }
  if (serverSeriesAvailable.value) serverChart.setOptions({ color: ['#047857', '#c2410c', '#1d4ed8', '#6d28d9', '#be185d', '#334155'], tooltip: { trigger: 'axis' }, legend: { data: serverMetric.value === 'all' ? defaultServerMetrics : [serverMetric.value] }, grid: { left: 20, right: 24, top: 42, bottom: 24, containLabel: true }, xAxis: { type: 'time' }, yAxis: [{ type: 'value', name: '使用率', axisLabel: { formatter: '{value}%' }, scale: true }, { type: 'value', name: 'IOPS', scale: true }], series: filterServerSeries(([['cpu', 'CPU', 0], ['memory', '内存', 0], ['disk', '磁盘', 0], ['disk_read_iops', '读取 IOPS', 1], ['disk_write_iops', '写入 IOPS', 1], ['disk_iops', '总 IOPS', 1]] as const).map(([key, name, yAxisIndex]) => ({ name, type: 'line', yAxisIndex, showSymbol: false, lineStyle: { width: 2.5 }, data: (serverMetrics.value?.series?.[key] || []).map((item) => [Number(item.timestamp) < 1_000_000_000_000 ? Number(item.timestamp) * 1000 : Number(item.timestamp), item.value]), tooltip: { valueFormatter: (value: any) => yAxisIndex === 0 ? `${formatTrendValue(value)}%` : `${formatTrendValue(value)} IOPS` } })), serverMetric.value) });
}
function stopPolling() { poller.stop(); }
function startPolling() {
  stopPolling();
  if (!isActive.value || refreshInterval.value <= 0) return;
  poller.start(() => void load(), refreshInterval.value);
}
async function load() {
  if (loadInFlight) return;
  loadInFlight = true;
  loading.value = !run.value;
  try {
    run.value = await PerformanceAPI.run(Number(route.params.id));
    currentTime.value = Date.now();
    logContent.value = (await PerformanceAPI.log(run.value.id)).content;
    const range = reportTimeRange.value;
    const now = Date.now();
    const shouldFetchServerMetrics = Boolean(
      run.value.monitor_target
      && range
      && (!serverSeriesAvailable.value || now - lastServerFetch >= 10_000 || !isActive.value)
      && now - lastServerAttempt >= 3_000
    );
    if (shouldFetchServerMetrics && run.value.monitor_target && range) {
      lastServerAttempt = now;
      try {
        const latestServerMetrics = await MonitorAPI.targetMetrics(run.value.monitor_target, { startTime: range.start, endTime: range.end });
        if (hasServerMetricSeries(latestServerMetrics)) {
          serverMetrics.value = latestServerMetrics;
          serverMetricsError.value = '';
          lastServerFetch = Date.now();
        } else {
          // Prometheus 偶发返回空序列时不覆盖页面上已经成功加载的曲线。
          serverMetricsError.value = serverSeriesAvailable.value
            ? '本次采集暂无新数据，已保留上次指标'
            : '暂未获取到关联服务器指标';
        }
      } catch (error: any) {
        // 临时请求失败时保留最后一次成功数据，避免折线图突然空白。
        serverMetricsError.value = error?.message || '服务器指标获取失败，将自动重试';
      }
    }
    await renderCharts();
    applyChartTimeRange();
    if (!isActive.value) stopPolling();
  } catch (error: any) {
    message.error(error?.message || '性能报告加载失败');
  } finally {
    loading.value = false;
    loadInFlight = false;
  }
}
async function exportAggregate() { if (!run.value) return; try { const blob = await PerformanceAPI.aggregateCsv(run.value.id); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `performance-${run.value.execution_no}-aggregate.csv`; link.click(); URL.revokeObjectURL(url); } catch (error: any) { message.error(error?.message || '聚合报告导出失败'); } }
async function stop() { if (!run.value) return; try { await PerformanceAPI.stop(run.value.id); message.success('已发送停止指令'); await load(); } catch (error: any) { message.error(error?.message || '停止失败'); } }
onMounted(async () => { clockTimer = window.setInterval(() => { currentTime.value = Date.now(); }, 1000); await load(); startPolling(); });
onUnmounted(() => { stopPolling(); if (clockTimer !== undefined) window.clearInterval(clockTimer); });
watch(() => route.params.id, async () => {
  serverMetrics.value = undefined;
  serverMetricsError.value = '';
  lastServerFetch = 0;
  lastServerAttempt = 0;
  await load();
  startPolling();
});
watch(refreshInterval, startPolling);
watch(serverMetric, renderCharts);
</script>

<style scoped lang="less">
.server-metrics-warning{margin-bottom:12px}
.server-stat-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px}.server-stat-card{min-width:0;padding:14px 16px;border:1px solid #e2e8f0;border-radius:9px;background:#f8fafc;font:inherit;text-align:left;cursor:pointer;transition:border-color .2s,background .2s,box-shadow .2s}.server-stat-card:hover,.server-stat-card.active{border-color:#5b6ff5;background:#f4f5ff;box-shadow:0 0 0 1px rgba(91,111,245,.08)}.server-stat-card span,.server-stat-card small{display:block;color:#8290a5;font-size:12px}.server-stat-card strong{display:block;margin:6px 0 4px;color:#243249;font-size:22px;font-variant-numeric:tabular-nums}.server-stat-card.active strong{color:#4f61e8}
.report-page{padding:24px 28px}.report-header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}.report-header h2{margin:0;color:#1e293b}.report-header p{margin:8px 0 22px;color:#7b8ba3}.report-actions{display:flex;align-items:center;gap:12px}.refresh-control{display:flex;align-items:center;gap:8px;color:#64748b;font-size:13px;white-space:nowrap}.refresh-control .n-select{width:128px}.run-context,.metric-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));overflow:hidden;border:1px solid #e2e8f0;border-radius:10px;background:#fff}.metric-cards{grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-top:16px}.run-context>div,.metric-cards article{padding:16px 18px;border-right:1px solid #e2e8f0}.run-context>div:last-child,.metric-cards article:last-child{border-right:0}.run-context span,.metric-cards span,.metric-cards small{display:block;color:#8290a5;font-size:12px}.run-context strong,.metric-cards strong{display:block;margin-top:6px;color:#243249;font-size:20px;font-variant-numeric:tabular-nums}.run-context .time-value{font-size:15px;line-height:1.5;white-space:nowrap}.metric-cards strong{font-size:25px}.metric-cards small{margin-top:4px}.run-error{margin-top:16px}.panel{margin-top:18px;padding:18px;border:1px solid #e2e8f0;border-radius:10px;background:#fff}.panel>header{margin-bottom:14px}.panel>header strong,.panel>header span{display:block}.panel>header strong{color:#243249}.panel>header span{margin-top:4px;color:#8290a5;font-size:12px}.chart-header{display:flex;align-items:center;justify-content:space-between;gap:16px}.metric-filter{width:150px;flex:0 0 150px}.performance-trend-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.trend-item{min-width:0;padding:14px 14px 6px;border:1px solid #e5eaf1;border-radius:9px;background:#fbfcfe}.trend-item>header{display:flex;align-items:baseline;justify-content:space-between;gap:12px;padding:0 4px}.trend-item>header strong{color:#334155;font-size:14px}.trend-item>header span{color:#8a97a9;font-size:12px}.performance-trend-chart{height:280px}.trend-chart{height:340px}.chart-empty{height:260px;padding-top:70px}.run-log{max-height:320px;margin:0;overflow:auto;padding:14px;border-radius:8px;background:#172033;color:#d9e3f1;font:12px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap}@media(max-width:1100px){.metric-cards{grid-template-columns:repeat(3,minmax(0,1fr))}.metric-cards article:nth-child(3){border-right:0}.metric-cards article:nth-child(-n+3){border-bottom:1px solid #e2e8f0}.server-stat-cards{grid-template-columns:repeat(2,minmax(0,1fr))}.performance-trend-grid{grid-template-columns:1fr}}@media(max-width:760px){.report-page{padding:16px}.report-header{flex-direction:column}.report-actions{width:100%;align-items:stretch;flex-direction:column}.refresh-control{justify-content:space-between}.refresh-control .n-select{width:160px}.run-context,.metric-cards{grid-template-columns:repeat(2,minmax(0,1fr))}.run-context>div:nth-child(2),.metric-cards article:nth-child(2n){border-right:0}.run-context>div:nth-child(-n+2),.metric-cards article:not(:nth-last-child(-n+2)){border-bottom:1px solid #e2e8f0}.chart-header{align-items:stretch;flex-direction:column}.metric-filter{width:100%;flex-basis:auto}.trend-item>header{align-items:flex-start;flex-direction:column;gap:4px}.performance-trend-chart{height:250px}}
.aggregate-panel>header{display:flex;align-items:center;justify-content:space-between;gap:16px}.aggregate-search{width:190px}.aggregate-status{width:130px}@media(max-width:760px){.aggregate-panel>header{align-items:stretch;flex-direction:column}.aggregate-panel>header>.n-space{width:100%;flex-wrap:wrap!important}.aggregate-search,.aggregate-status{width:100%}}
</style>
