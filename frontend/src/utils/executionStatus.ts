import type { PerformanceStatus } from '@/api/performance/http';

type StatusInfo = { label: string; type: 'default' | 'info' | 'warning' | 'success' | 'error' };
export const performanceStatusMap: Record<PerformanceStatus, StatusInfo> = {
  queued: { label: '等待执行', type: 'default' },
  preparing: { label: '准备环境', type: 'info' },
  running: { label: '执行中', type: 'info' },
  reporting: { label: '汇总报告', type: 'warning' },
  passed: { label: '通过', type: 'success' },
  failed: { label: '未通过', type: 'error' },
  error: { label: '执行异常', type: 'error' },
  stopped: { label: '已停止', type: 'default' },
};
export const performanceStatusLabels = Object.fromEntries(
  Object.entries(performanceStatusMap).map(([key, value]) => [key, value.label])
) as Record<PerformanceStatus, string>;
export const isPerformanceActive = (status: string) => ['queued', 'preparing', 'running', 'reporting'].includes(status);
export const appStatusLabels: Record<string, [string, StatusInfo['type']]> = Object.fromEntries(
  Object.entries({
    ...performanceStatusMap,
    queued: { label: '等待设备', type: 'default' } as StatusInfo,
    installing: { label: '安装应用', type: 'warning' } as StatusInfo,
  }).map(([key, value]): [string, [string, StatusInfo['type']]] => [key, [value.label, value.type]])
);
export const isAppActive = (status: string) => status === 'installing' || isPerformanceActive(status);
