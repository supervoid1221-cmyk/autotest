import { http } from '@/utils/http/axios';

export type PerformanceStatus = 'queued' | 'preparing' | 'running' | 'reporting' | 'passed' | 'failed' | 'error' | 'stopped';

export interface LoadStage { duration: string; target: number; }
export interface PerformanceThresholds { p95_ms: number; error_rate: number; minimum_rps: number; }
export interface PerformanceBusinessMixItem { source_type: 'endpoint' | 'scenario'; source_endpoint: number | null; source_scenario: number | null; weight: number; name?: string; }
export interface PerformanceScenario {
  id?: number; project: number | null; project_name?: string; environment: number | null; environment_name?: string;
  source_mode: 'single' | 'mixed';
  source_type: 'endpoint' | 'scenario'; source_endpoint: number | null; source_endpoint_name?: string;
  source_scenario: number | null; source_scenario_name?: string; monitor_target: number | null; monitor_target_name?: string;
  notification_channels: number[]; name: string; description: string; load_type: string; load_mode: 'stages' | 'thread_group';
  thread_count: number; duration_seconds: number; ramp_up_seconds: number; graceful_stop_seconds: number; stages: LoadStage[];
  business_mix: PerformanceBusinessMixItem[]; parameter_filename: string;
  parameter_strategy: 'sequential' | 'random' | 'unique'; parameter_data: Array<Record<string, any>>;
  thresholds: PerformanceThresholds; enabled: boolean; created_by_name?: string; updated_at?: string;
}
export interface PerformanceMetricBucket {
  id: number; timestamp: string; vus: number; target_vus: number; rps: number; tps: number; request_count: number; failed_count: number; error_rate: number;
  duration_avg: number; duration_min: number; duration_max: number; duration_p90: number; duration_p95: number; duration_p99: number;
}
export interface PerformanceEndpointMetric {
  id: number; endpoint_name: string; method: string; url: string; request_count: number; failed_count: number;
  error_rate: number; duration_avg: number; duration_min: number; duration_median: number; duration_max: number;
  duration_p90: number; duration_p95: number; duration_p99: number; throughput: number;
  received_bytes: number; sent_bytes: number; configured_ratio: number;
}
export interface PerformanceNotificationDelivery {
  id: number; channel: number; channel_name: string; status: 'sent' | 'failed'; response_code?: number | null;
  response_summary: string; created_at: string;
}
export interface PerformanceRun {
  id: number; execution_no: number; scenario: number; scenario_name: string; project: number; project_name: string;
  environment: number; environment_name: string; monitor_target?: number | null; monitor_target_name?: string;
  status: PerformanceStatus; progress: number; current_vus: number; configured_vus: number; current_rps: number; current_tps: number; summary: Record<string, any>;
  threshold_results: Record<string, any>; error_message: string; started_at?: string; finished_at?: string;
  load_started_at?: string; load_finished_at?: string; load_duration_ms?: number | null; created_at: string;
  metric_buckets: PerformanceMetricBucket[]; endpoint_metrics: PerformanceEndpointMetric[];
  notification_deliveries: PerformanceNotificationDelivery[];
  // 执行人。后端用 source="created_by.username"，created_by 为空时该字段整个不出现，
  // 所以是可选的，渲染要写 `|| '-'`。
  created_by_name?: string;
}

const base = '/performance/';
export const PerformanceAPI = {
  scenarios: (params: Record<string, any> = {}) => http.request<PerformanceScenario[]>({ url: `${base}scenario/`, method: 'get', params }),
  scenario: (id: number) => http.request<PerformanceScenario>({ url: `${base}scenario/${id}/`, method: 'get' }),
  createScenario: (data: PerformanceScenario) => http.request<PerformanceScenario>({ url: `${base}scenario/`, method: 'post', data }),
  updateScenario: (id: number, data: PerformanceScenario) => http.request<PerformanceScenario>({ url: `${base}scenario/${id}/`, method: 'put', data }),
  deleteScenario: (id: number) => http.request({ url: `${base}scenario/${id}/`, method: 'delete' }),
  refreshSnapshot: (id: number) => http.request<PerformanceScenario>({ url: `${base}scenario/${id}/refresh-snapshot/`, method: 'post' }),
  parseParameters: (project: number, file: File) => { const data = new FormData(); data.append('project', String(project)); data.append('file', file); return http.request<{ filename: string; format: string; columns: string[]; row_count: number; rows: Array<Record<string, any>> }>({ url: `${base}scenario/parse-parameters/`, method: 'post', data }); },
  start: (id: number, confirmProduction = false) => http.request<PerformanceRun>({ url: `${base}scenario/${id}/run/`, method: 'post', data: { confirm_production: confirmProduction } }),
  runs: (params: Record<string, any> = {}) => http.request<PerformanceRun[]>({ url: `${base}run/`, method: 'get', params }),
  run: (id: number) => http.request<PerformanceRun>({ url: `${base}run/${id}/`, method: 'get', params: { _t: Date.now() } }),
  deleteRun: (id: number) => http.request({ url: `${base}run/${id}/`, method: 'delete' }),
  compare: (ids: number[]) => http.request<PerformanceRun[]>({ url: `${base}run/compare/`, method: 'get', params: { ids: ids.join(','), _t: Date.now() } }),
  stop: (id: number) => http.request({ url: `${base}run/${id}/stop/`, method: 'post' }),
  log: (id: number) => http.request<{ content: string }>({ url: `${base}run/${id}/log/`, method: 'get', params: { _t: Date.now() } }),
  aggregateCsv: (id: number) => http.request<Blob>({ url: `${base}run/${id}/aggregate-csv/`, method: 'get', responseType: 'blob' }),
};
