<template>
  <n-collapse class="api-step-list" arrow-placement="right">
    <n-collapse-item
      v-for="(step, index) in steps"
      :key="`${groupKey}-${step.source_step_id || index}`"
      :name="`${groupKey}-${index}`"
    >
      <template #header>
        <div class="step-header">
          <span class="step-identity">
            <span class="step-index">{{ index + 1 }}</span>
            <span class="method" :style="methodStyle(step.method)">{{ step.method || 'API' }}</span>
            <strong>{{ step.name }}</strong>
            <span class="url">{{ step.url }}</span>
          </span>
          <span class="step-status">
            <n-tag :type="stepStatus(step).type" size="small">{{ stepStatus(step).label }}</n-tag>
          </span>
          <span class="step-column-value">{{ formatDuration(step.duration_ms, step) }}</span>
        </div>
      </template>
      <div class="step-meta">
        <span>执行时间：{{ formatTime(step.started_at) }}</span>
        <span>状态码：{{ step.status_code ?? '-' }}</span>
        <span>耗时：{{ formatDuration(step.duration_ms, step) }}</span>
        <span>请求次数：{{ step.attempts || 1 }}</span>
      </div>
      <n-alert v-if="step.errors?.length" type="error" :show-icon="false" class="errors">
        {{ step.errors.join('；') }}
      </n-alert>
      <n-alert v-else-if="step.skip_reason" type="warning" :show-icon="false" class="errors">
        {{ step.skip_reason }}
      </n-alert>
      <n-grid :cols="2" :x-gap="14" :y-gap="14" responsive="screen">
        <n-gi>
          <section class="detail-block">
            <h4>请求参数</h4>
            <pre>{{ formatRequest(step.request) }}</pre>
          </section>
        </n-gi>
        <n-gi>
          <section class="detail-block">
            <h4>响应结果</h4>
            <pre>{{ formatResponse(step.response) }}</pre>
          </section>
        </n-gi>
      </n-grid>
      <section v-if="step.assertions?.length" class="detail-block">
        <h4>断言结果</h4>
        <div class="assertions">
          <div v-for="(item, itemIndex) in step.assertions" :key="itemIndex">
            <n-tag :type="item.passed ? 'success' : 'error'" size="small">
              {{ item.passed ? '通过' : '失败' }}
            </n-tag>
            {{ item.actual_path || item.type || '断言' }}：实际值 {{ item.actual }}，期望值
            {{ item.expected }}
          </div>
        </div>
      </section>
      <section v-if="Object.keys(step.extracted || {}).length" class="detail-block">
        <h4>数据提取</h4>
        <pre>{{ formatJson(step.extracted) }}</pre>
      </section>
    </n-collapse-item>
  </n-collapse>
</template>

<script lang="ts" setup>
  defineProps<{
    steps: any[];
    groupKey: string;
  }>();

  const methodStyle = (method?: string) =>
    ({
      GET: { color: '#1677ff', background: '#eaf3ff' },
      POST: { color: '#20a162', background: '#ebf8f0' },
      PUT: { color: '#d97706', background: '#fff5e6' },
      PATCH: { color: '#7c3aed', background: '#f3edff' },
      DELETE: { color: '#dc2626', background: '#fff0f0' },
    }[String(method || '').toUpperCase()] || { color: '#667085', background: '#f2f4f7' });
  const stepStatus = (step: any) => {
    const status =
      step?.status ||
      (step?.passed === true ? 'passed' : step?.passed === false ? 'failed' : 'pending');
    return (
      (
        {
          passed: { label: '通过', type: 'success' },
          failed: { label: '失败', type: 'error' },
          running: { label: '执行中', type: 'warning' },
          pending: { label: '待执行', type: 'default' },
          skipped: { label: '已跳过', type: 'warning' },
        } as any
      )[status] || { label: '待执行', type: 'default' }
    );
  };
  const formatTime = (value?: string) => {
    if (!value) return '-';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false });
  };
  const formatDuration = (value?: number, step?: any) => {
    let milliseconds = Number(value);
    if (!Number.isFinite(milliseconds) && step?.started_at && step?.finished_at) {
      milliseconds = new Date(step.finished_at).getTime() - new Date(step.started_at).getTime();
    }
    if (!Number.isFinite(milliseconds)) return '-';
    milliseconds = Math.max(0, milliseconds);
    return milliseconds >= 1000
      ? `${(milliseconds / 1000).toFixed(2)} 秒`
      : `${milliseconds.toFixed(0)} ms`;
  };
  const formatJson = (data: unknown) => JSON.stringify(data || {}, null, 2);
  const isEmpty = (value: unknown) =>
    value == null ||
    (typeof value === 'string' && value.trim() === '') ||
    (Array.isArray(value) && value.length === 0) ||
    (typeof value === 'object' && Object.keys(value).length === 0);
  const formatRequest = (request: any) => {
    const clone = { ...(request || {}) };
    (['params', 'data', 'json'] as const).forEach((key) => {
      if (isEmpty(clone[key])) delete clone[key];
    });
    return JSON.stringify(clone, null, 2);
  };
  const formatResponse = (data: any) =>
    JSON.stringify({ headers: data?.headers || {}, body: data?.body || '' }, null, 2);
</script>

<style scoped>
  .api-step-list {
    padding: 4px 12px 10px;
    background: #fff;
  }
  .step-header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 104px 108px;
    flex: 1;
    align-items: center;
    min-width: 0;
    gap: 16px;
  }
  .step-identity {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: 9px;
  }
  .step-header strong {
    color: #26354a;
    font-size: 13px;
  }
  .step-index {
    display: grid;
    width: 22px;
    height: 22px;
    flex: none;
    place-items: center;
    border-radius: 50%;
    color: var(--branch-color, #66758b);
    background: var(--branch-soft, #f2f4f7);
    font-size: 11px;
    font-variant-numeric: tabular-nums;
    font-weight: 650;
  }
  .method {
    min-width: 44px;
    flex: none;
    padding: 3px 7px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    text-align: center;
  }
  .url {
    overflow: hidden;
    color: #79869a;
    font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .step-status {
    flex: none;
  }
  .step-status,
  .step-column-value {
    transform: translateX(26px);
  }
  .step-column-value {
    color: #69778c;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .step-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 20px;
    margin-bottom: 10px;
    color: #7b8798;
    font-size: 11px;
  }
  .errors {
    margin-bottom: 10px;
  }
  .detail-block {
    min-width: 0;
    margin-top: 10px;
    padding: 10px 12px;
    border: 1px solid #e8edf4;
    border-radius: 6px;
    background: #f9fbfd;
  }
  .detail-block h4 {
    margin: 0 0 7px;
    color: #536176;
    font-size: 12px;
  }
  pre {
    max-height: 280px;
    margin: 0;
    overflow: auto;
    color: #344054;
    font: 11px/1.6 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .assertions {
    display: grid;
    gap: 7px;
    color: #58667b;
    font-size: 12px;
  }
  @media (max-width: 760px) {
    .step-header {
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
    }
    .step-column-value {
      display: none;
    }
  }
</style>
