<template>
  <n-modal
    :show="show"
    preset="card"
    title="服务器指标详情"
    class="platform-form-modal server-metrics-modal"
    @update:show="emit('update:show', $event)"
  >
    <n-spin :show="loading">
      <div v-if="target" class="detail-content">
        <header class="target-context">
          <div>
            <strong>{{ target.name }}</strong>
            <span>{{ target.instance_label }} · {{ target.job || 'node' }}</span>
          </div>
          <n-tag :type="detail?.current.up ? 'success' : 'error'" size="small">
            {{ detail?.current.up ? '在线' : '离线' }}
          </n-tag>
        </header>

        <div v-if="detail" class="metric-summary" role="tablist" aria-label="选择要分析的服务器指标">
          <button
            v-for="item in metricItems"
            :key="item.key"
            type="button"
            role="tab"
            :aria-selected="selectedMetric === item.key"
            :class="['metric-selector', { active: selectedMetric === item.key }]"
            :style="{ '--metric-color': item.color, '--metric-soft-color': item.softColor }"
            @click="selectMetric(item.key)"
          >
            <span>{{ item.label }}</span>
            <strong :class="item.tone">{{ item.value }}</strong>
            <small>{{ selectedMetric === item.key ? '正在分析' : '点击单独分析' }}</small>
          </button>
        </div>

        <section class="range-panel" aria-label="指标时间范围筛选">
          <div class="preset-ranges">
            <span>时间范围</span>
            <n-button-group>
              <n-button
                v-for="item in presets"
                :key="item.key"
                size="small"
                :type="activeRange === item.key ? 'primary' : 'default'"
                :secondary="activeRange !== item.key"
                @click="loadPreset(item)"
              >
                {{ item.label }}
              </n-button>
            </n-button-group>
          </div>
          <div class="custom-range">
            <n-date-picker
              v-model:value="customRange"
              type="datetimerange"
              clearable
              :is-date-disabled="disableFutureDate"
              start-placeholder="开始时间"
              end-placeholder="结束时间"
              @update:value="activeRange = 'custom'"
            />
            <n-button type="primary" secondary :disabled="!customRange" @click="loadCustomRange">查询</n-button>
          </div>
        </section>

        <n-alert v-if="errorMessage" type="error" :show-icon="true" class="detail-error">
          {{ errorMessage }}
        </n-alert>

        <section v-if="hasSeries && selectedMetric !== 'all'" class="analysis-summary" aria-label="所选指标区间分析">
          <div v-for="item in analysisItems" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </section>

        <section class="chart-panel">
          <header>
            <div>
              <div class="chart-title-row">
                <strong>{{ chartTitle }}</strong>
                <n-button v-if="selectedMetric !== 'all'" text type="primary" size="tiny" @click="selectMetric('all')">
                  查看全部
                </n-button>
              </div>
              <span>{{ selectedRangeLabel }}</span>
            </div>
            <div class="chart-meta">
              <template v-if="selectedMetric !== 'all'">
                <span>预警 {{ selectedThresholds.warning }}%</span>
                <span>严重 {{ selectedThresholds.critical }}%</span>
              </template>
              <small>纵轴已按实际波动范围自适应</small>
            </div>
          </header>
          <div
            v-show="hasSeries"
            ref="chartRef"
            class="metric-chart"
            role="img"
            :aria-label="`服务器 ${target.name} ${chartTitle}`"
          />
          <n-empty v-if="!loading && !hasSeries" :description="emptyDescription" class="chart-empty" />
        </section>
      </div>
    </n-spin>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch, type Ref } from 'vue';
import { MonitorAPI, type MonitorSnapshot, type MonitorTarget } from '@/api/monitor/http';
import { useECharts } from '@/hooks/web/useECharts';
import { useDesignSetting } from '@/hooks/setting/useDesignSetting';

interface RangePreset {
  key: string;
  label: string;
  seconds: number;
}

type MetricKey = 'cpu' | 'memory' | 'disk';
type MetricSelection = 'all' | MetricKey;

interface MetricDefinition {
  key: MetricKey;
  label: string;
  chartName: string;
  color: string;
  softColor: string;
}

const props = defineProps<{ show: boolean; target?: MonitorTarget }>();
const emit = defineEmits<{ (event: 'update:show', value: boolean): void }>();

const presets: RangePreset[] = [
  { key: '1h', label: '1 小时', seconds: 3600 },
  { key: '6h', label: '6 小时', seconds: 21600 },
  { key: '24h', label: '24 小时', seconds: 86400 },
  { key: '7d', label: '7 天', seconds: 604800 },
];
const activeRange = ref('1h');
const customRange = ref<[number, number] | null>(null);
const loading = ref(false);
const errorMessage = ref('');
const detail = ref<(MonitorSnapshot & { target: MonitorTarget })>();
const selectedMetric = ref<MetricSelection>('all');
const chartRef = ref<HTMLDivElement | null>(null);
const { setOptions, resize } = useECharts(chartRef as Ref<HTMLDivElement>);
const { getDarkTheme } = useDesignSetting();

const metricDefinitions: Record<MetricKey, MetricDefinition> = {
  cpu: { key: 'cpu', label: 'CPU 使用率', chartName: 'CPU', color: '#18a36b', softColor: 'rgba(24, 163, 107, 0.09)' },
  memory: { key: 'memory', label: '内存使用率', chartName: '内存', color: '#f08b0b', softColor: 'rgba(240, 139, 11, 0.09)' },
  disk: { key: 'disk', label: '磁盘最高使用率', chartName: '磁盘', color: '#2574e8', softColor: 'rgba(37, 116, 232, 0.09)' },
};

const percent = (value: number | null | undefined) => value == null ? '-' : `${value.toFixed(1)}%`;
const metricItems = computed(() => [
  { ...metricDefinitions.cpu, value: percent(detail.value?.current.cpu), tone: detail.value?.current.cpu != null && detail.value.current.cpu >= selectedThreshold('cpu').critical ? 'danger' : 'cpu' },
  { ...metricDefinitions.memory, value: percent(detail.value?.current.memory), tone: detail.value?.current.memory != null && detail.value.current.memory >= selectedThreshold('memory').critical ? 'danger' : 'memory' },
  { ...metricDefinitions.disk, value: percent(detail.value?.current.disk), tone: detail.value?.current.disk != null && detail.value.current.disk >= selectedThreshold('disk').critical ? 'danger' : 'disk' },
]);
const selectedMetricKeys = computed<MetricKey[]>(() => selectedMetric.value === 'all'
  ? ['cpu', 'memory', 'disk']
  : [selectedMetric.value]);
const selectedMetricDefinition = computed(() => selectedMetric.value === 'all' ? null : metricDefinitions[selectedMetric.value]);
const selectedSeries = computed(() => selectedMetricKeys.value.map((key) => ({
  definition: metricDefinitions[key],
  points: detail.value?.series?.[key] || [],
})));
const selectedValues = computed(() => selectedSeries.value
  .flatMap((series) => series.points)
  .map((point) => Number(point.value))
  .filter(Number.isFinite));
const hasSeries = computed(() => selectedValues.value.length > 0);

function selectedThreshold(key: MetricKey) {
  const target = props.target as (MonitorTarget & Record<string, unknown>) | undefined;
  const defaults = key === 'memory' ? { warning: 85, critical: 95 } : { warning: 80, critical: 90 };
  return {
    warning: Number(target?.[`${key}_warning_threshold`] ?? defaults.warning),
    critical: Number(target?.[`${key}_critical_threshold`] ?? defaults.critical),
  };
}

const selectedThresholds = computed(() => selectedMetric.value === 'all'
  ? { warning: 0, critical: 0 }
  : selectedThreshold(selectedMetric.value));
const chartTitle = computed(() => selectedMetricDefinition.value
  ? `${selectedMetricDefinition.value.label}趋势`
  : '资源使用率趋势');
const emptyDescription = computed(() => selectedMetricDefinition.value
  ? `所选时间范围暂无${selectedMetricDefinition.value.label}数据`
  : '所选时间范围暂无服务器指标数据');
const intervalStats = computed(() => {
  const values = selectedValues.value;
  if (!values.length) return null;
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  return {
    minimum,
    maximum,
    average: values.reduce((sum, value) => sum + value, 0) / values.length,
    fluctuation: maximum - minimum,
  };
});
const analysisItems = computed(() => {
  const stats = intervalStats.value;
  if (!stats) return [];
  return [
    { label: '区间最低', value: `${stats.minimum.toFixed(2)}%` },
    { label: '区间平均', value: `${stats.average.toFixed(2)}%` },
    { label: '区间峰值', value: `${stats.maximum.toFixed(2)}%` },
    { label: '波动幅度', value: `${stats.fluctuation.toFixed(2)} 个百分点` },
  ];
});
const adaptiveAxis = computed(() => {
  const values = selectedValues.value;
  if (!values.length) return { min: 0, max: 100, splitNumber: 4, decimals: 0 };

  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const spread = rawMax - rawMin;
  const padding = Math.max(spread * 0.18, 0.5);
  let min = Math.max(0, Math.floor((rawMin - padding) * 10) / 10);
  let max = Math.min(100, Math.ceil((rawMax + padding) * 10) / 10);

  if (max - min < 2) {
    const center = (rawMin + rawMax) / 2;
    min = Math.max(0, Math.floor((center - 1) * 10) / 10);
    max = Math.min(100, Math.ceil((center + 1) * 10) / 10);
  }

  return { min, max, splitNumber: 4, decimals: max - min < 10 ? 1 : 0 };
});

const selectMetric = (key: MetricSelection) => {
  selectedMetric.value = key;
};
const selectedRangeLabel = computed(() => {
  const range = detail.value?.range;
  if (!range) return '等待选择时间范围';
  const format = (value: number) => new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
  return `${format(range.start)} 至 ${format(range.end)}`;
});

const disableFutureDate = (timestamp: number) => timestamp > Date.now();
const formatAxisTime = (timestamp: number) => {
  const date = new Date(timestamp);
  const span = (detail.value?.range?.end || 0) - (detail.value?.range?.start || 0);
  return span > 86400000
    ? date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
    : date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false });
};

const renderChart = async () => {
  if (!hasSeries.value) return;
  await nextTick();
  const axis = adaptiveAxis.value;
  const isAllMetrics = selectedMetric.value === 'all';
  const isDark = getDarkTheme.value;
  const chartTextColor = isDark ? '#8996a8' : '#8290a5';
  const chartStrongTextColor = isDark ? '#b8c0cc' : '#5d6c82';
  const chartLineColor = isDark ? '#3a3a3a' : '#dce4ee';
  const chartGridColor = isDark ? '#303030' : '#e7edf4';
  const zoomBackground = isDark ? '#252525' : '#f5f7fa';
  setOptions({
    animationDuration: 220,
    aria: { enabled: true, decal: { show: false } },
    color: selectedSeries.value.map((series) => series.definition.color),
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(24, 36, 58, 0.94)',
      borderWidth: 0,
      textStyle: { color: '#f7f9fc' },
      axisPointer: { type: 'line', lineStyle: { color: '#9aa8ba', type: 'dashed' } },
      valueFormatter: (value: unknown) => `${Number(value).toFixed(2)}%`,
    },
    legend: {
      show: isAllMetrics,
      top: 0,
      right: 8,
      itemWidth: 16,
      itemHeight: 3,
      textStyle: { color: chartStrongTextColor },
    },
    grid: { left: 12, right: 20, top: isAllMetrics ? 38 : 24, bottom: 62, containLabel: true },
    xAxis: {
      type: 'time',
      min: detail.value?.range?.start,
      max: detail.value?.range?.end,
      boundaryGap: false,
      axisLine: { lineStyle: { color: chartLineColor } },
      axisTick: { show: false },
      axisLabel: { color: chartTextColor, hideOverlap: true, formatter: formatAxisTime },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      min: axis.min,
      max: axis.max,
      splitNumber: axis.splitNumber,
      axisLabel: { color: chartTextColor, formatter: (value: number) => `${Number(value).toFixed(axis.decimals)}%` },
      splitLine: { lineStyle: { color: chartGridColor, type: 'dashed' } },
    },
    dataZoom: [
      { type: 'inside', filterMode: 'none' },
      {
        type: 'slider',
        height: 20,
        bottom: 12,
        borderColor: chartLineColor,
        backgroundColor: zoomBackground,
        fillerColor: selectedMetricDefinition.value?.softColor || 'rgba(37, 116, 232, 0.12)',
        handleStyle: { color: selectedMetricDefinition.value?.color || '#2574e8' },
        textStyle: { color: chartTextColor },
      },
    ],
    series: selectedSeries.value.map(({ definition, points }) => ({
      name: definition.chartName,
      type: 'line',
      smooth: 0.18,
      showSymbol: false,
      connectNulls: false,
      sampling: 'lttb',
      lineStyle: { width: 2.6, color: definition.color },
      emphasis: { focus: 'series', lineStyle: { width: 3.2 } },
      areaStyle: { opacity: 0.08, color: definition.color },
      data: points.map((point) => [Number(point.timestamp), Number(point.value)]),
    })),
  });
  resize();
};

const fetchMetrics = async (range: number | { startTime: number; endTime: number }) => {
  if (!props.target?.id) return;
  loading.value = true;
  errorMessage.value = '';
  try {
    detail.value = await MonitorAPI.targetMetrics(props.target.id, typeof range === 'number' ? range : range);
    await renderChart();
  } catch (error: any) {
    errorMessage.value = error?.message || '服务器指标加载失败';
  } finally {
    loading.value = false;
  }
};

const loadPreset = (preset: RangePreset) => {
  activeRange.value = preset.key;
  const end = Date.now();
  customRange.value = [end - preset.seconds * 1000, end];
  void fetchMetrics(preset.seconds);
};

const loadCustomRange = () => {
  if (!customRange.value) return;
  const [startTime, endTime] = customRange.value;
  const duration = endTime - startTime;
  if (duration < 300000) {
    errorMessage.value = '查询时间范围不能小于 5 分钟。';
    return;
  }
  if (duration > 2592000000) {
    errorMessage.value = '查询时间范围不能超过 30 天。';
    return;
  }
  if (endTime > Date.now() + 60000) {
    errorMessage.value = '结束时间不能晚于当前时间。';
    return;
  }
  activeRange.value = 'custom';
  void fetchMetrics({ startTime, endTime });
};

watch(
  () => [props.show, props.target?.id] as const,
  ([visible, targetId], previous) => {
    if (!visible || !targetId) return;
    if (!previous || !previous[0] || previous[1] !== targetId) {
      selectedMetric.value = 'all';
      loadPreset(presets[0]);
    }
  },
  { immediate: true }
);

watch(selectedMetric, () => {
  void renderChart();
});

watch(getDarkTheme, () => {
  void renderChart();
});
</script>

<style scoped lang="less">
:global(.server-metrics-modal.n-card) {
  width: min(1280px, calc(100vw - 64px));
}

.detail-content { min-height: 520px; }
.target-context { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 0 2px 16px; border-bottom: 1px solid #e6ebf2; }
.target-context div { min-width: 0; }
.target-context strong { display: block; overflow: hidden; color: #1d2a40; font-size: 18px; text-overflow: ellipsis; white-space: nowrap; }
.target-context span { display: block; margin-top: 5px; overflow: hidden; color: #78869a; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.metric-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 18px 0; border: 1px solid #e1e8f0; border-radius: 10px; background: #fff; }
.metric-selector { position: relative; min-width: 0; padding: 16px 20px; border: 0; border-right: 1px solid #e6ebf2; border-radius: 0; background: transparent; text-align: left; cursor: pointer; transition: background-color 160ms ease, box-shadow 160ms ease; }
.metric-selector:first-child { border-radius: 9px 0 0 9px; }
.metric-selector:last-child { border-right: 0; border-radius: 0 9px 9px 0; }
.metric-selector:hover { background: #f8fafc; }
.metric-selector.active { z-index: 1; background: var(--metric-soft-color); box-shadow: inset 0 -3px 0 var(--metric-color); }
.metric-selector:focus-visible { z-index: 2; outline: 2px solid var(--metric-color); outline-offset: -2px; }
.metric-summary span, .metric-summary small { display: block; color: #8290a5; font-size: 12px; }
.metric-summary strong { display: block; margin: 6px 0 3px; color: #27364d; font-size: 24px; font-weight: 650; font-variant-numeric: tabular-nums; }
.metric-summary strong.cpu { color: #15895d; }
.metric-summary strong.memory { color: #d87807; }
.metric-summary strong.disk { color: #2469ca; }
.metric-summary strong.danger { color: #d6404c; }
.range-panel { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px 20px; padding: 14px 16px; border: 1px solid #e1e8f0; border-radius: 10px; background: #f7f9fc; }
.preset-ranges, .custom-range { display: flex; align-items: center; gap: 10px; }
.preset-ranges > span { color: #536178; font-size: 13px; font-weight: 600; white-space: nowrap; }
.custom-range :deep(.n-date-picker) { width: 340px; }
.detail-error { margin-top: 14px; }
.analysis-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 18px; overflow: hidden; border: 1px solid #e1e8f0; border-radius: 10px; background: #f8fafc; }
.analysis-summary div { padding: 13px 16px; border-right: 1px solid #e6ebf2; }
.analysis-summary div:last-child { border-right: 0; }
.analysis-summary span { display: block; color: #8290a5; font-size: 12px; }
.analysis-summary strong { display: block; margin-top: 5px; overflow: hidden; color: #27364d; font-size: 16px; font-variant-numeric: tabular-nums; text-overflow: ellipsis; white-space: nowrap; }
.chart-panel { margin-top: 18px; padding: 18px 18px 8px; border: 1px solid #e1e8f0; border-radius: 10px; background: #fff; }
.chart-panel > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.chart-panel > header strong { display: block; color: #243249; font-size: 15px; }
.chart-title-row { display: flex; align-items: center; gap: 12px; }
.chart-panel > header span, .chart-panel > header small { color: #8290a5; font-size: 12px; }
.chart-panel > header span { display: block; margin-top: 4px; }
.chart-meta { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 8px 14px; }
.chart-meta > span { margin-top: 0 !important; padding-left: 10px; border-left: 3px solid #dbe4ef; color: #5d6c82 !important; font-variant-numeric: tabular-nums; }
.chart-meta > span:nth-child(1) { border-left-color: #f0a229; }
.chart-meta > span:nth-child(2) { border-left-color: #d6404c; }
.chart-meta small { width: 100%; text-align: right; }
.metric-chart { width: 100%; height: 330px; margin-top: 8px; }
.chart-empty { height: 330px; padding-top: 94px; }

@media (max-width: 900px) {
  .range-panel { align-items: stretch; flex-direction: column; }
  .custom-range :deep(.n-date-picker) { width: 100%; }
  .custom-range { width: 100%; }
  .custom-range :deep(.n-date-picker) { flex: 1; min-width: 0; }
}
@media (max-width: 640px) {
  :global(.server-metrics-modal.n-card) { width: calc(100vw - 24px); }
  .detail-content { min-height: 480px; }
  .metric-summary { grid-template-columns: 1fr; }
  .metric-selector { border-right: 0; border-bottom: 1px solid #e6ebf2; }
  .metric-selector:first-child { border-radius: 9px 9px 0 0; }
  .metric-selector:last-child { border-bottom: 0; border-radius: 0 0 9px 9px; }
  .metric-selector.active { box-shadow: inset 3px 0 0 var(--metric-color); }
  .analysis-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .analysis-summary div:nth-child(2) { border-right: 0; }
  .analysis-summary div:nth-child(-n + 2) { border-bottom: 1px solid #e6ebf2; }
  .preset-ranges { align-items: flex-start; flex-direction: column; }
  .preset-ranges :deep(.n-button-group) { display: grid; grid-template-columns: repeat(4, 1fr); width: 100%; }
  .custom-range { align-items: stretch; flex-direction: column; }
  .chart-panel > header { flex-direction: column; gap: 5px; }
  .chart-meta { justify-content: flex-start; }
  .chart-meta small { text-align: left; }
  .metric-chart, .chart-empty { height: 300px; }
}
</style>
