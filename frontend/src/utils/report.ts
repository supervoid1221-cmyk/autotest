import { formatDateTime, formatDurationMilliseconds } from './time';

export const methodStyle = (method?: string) =>
  ({
    GET: { color: '#318357', background: '#eef8f2' },
    POST: { color: '#da820b', background: '#fff6e8' },
    PUT: { color: '#277bc5', background: '#eef5fb' },
    PATCH: { color: '#277bc5', background: '#eef5fb' },
    DELETE: { color: '#d44857', background: '#fff0f2' },
  }[String(method || '').toUpperCase()] || { color: '#667085', background: '#f2f4f7' });

export const stepStatus = (step: any) => {
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

export const formatTime = formatDateTime;

export const formatDuration = (value?: number, step?: any) => {
  let milliseconds = Number(value);
  if (!Number.isFinite(milliseconds) && step?.started_at && step?.finished_at) {
    milliseconds = new Date(step.finished_at).getTime() - new Date(step.started_at).getTime();
  }
  if (!Number.isFinite(milliseconds)) return '-';
  return formatDurationMilliseconds(milliseconds);
};

export const formatJson = (data: unknown) => JSON.stringify(data || {}, null, 2);
export const isEmpty = (value: unknown) =>
  value == null ||
  (typeof value === 'string' && value.trim() === '') ||
  (Array.isArray(value) && value.length === 0) ||
  (typeof value === 'object' && Object.keys(value).length === 0);
export const formatRequest = (request: any) => {
  const clone = { ...(request || {}) };
  (['params', 'data', 'json'] as const).forEach((key) => {
    if (isEmpty(clone[key])) delete clone[key];
  });
  return JSON.stringify(clone, null, 2);
};
export const formatResponse = (data: any) =>
  JSON.stringify({ headers: data?.headers || {}, body: data?.body || '' }, null, 2);
