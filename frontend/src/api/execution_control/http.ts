import { http } from '@/utils/http/axios';

export type UnifiedTaskStatus = 'queued' | 'preparing' | 'running' | 'paused' | 'reporting' | 'succeeded' | 'failed' | 'error' | 'canceled' | 'stopped';

export interface ExecutionTask {
  id: number;
  source_type: 'suite' | 'app' | 'performance';
  source_type_name: string;
  source_id: number;
  execution_no: string;
  project: number;
  project_name: string;
  // 执行人名称快照，由服务端从源任务推导。补字段之前的历史任务为空串。
  executor_name: string;
  name: string;
  engine: string;
  status: UnifiedTaskStatus;
  status_name: string;
  stage: string;
  progress: number;
  diagnostic_code: string;
  diagnostic_message: string;
  resource_keys: string[];
  dispatched_at?: string | null;
  dispatch_attempts: number;
  waiting_reason: string;
  queue_position?: number | null;
  recovery_count: number;
  queued_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  last_activity_at: string;
  report_path: string;
  can_stop: boolean;
  can_recover: boolean;
}

export interface ExecutionService {
  key: string;
  name: string;
  status: 'online' | 'offline' | 'degraded' | 'not_configured';
  message: string;
  last_heartbeat_at?: string | null;
}

export interface ExecutionOverview {
  total: number;
  active: number;
  abnormal: number;
  abnormal_tasks: number;
  abnormal_services: number;
  status_counts: Record<string, number>;
  services: ExecutionService[];
}

export interface ExecutionWorker {
  id: number;
  name: string;
  kind: string;
  kind_name: string;
  hostname: string;
  status: string;
  status_name: string;
  active_tasks: number;
  capacity: number;
  capabilities: string[];
  last_heartbeat_at: string;
  message: string;
}

const base = '/execution-control/';
export const ExecutionControlAPI = {
  tasks: (params: Record<string, any> = {}) => http.request<ExecutionTask[]>({ url: `${base}tasks/`, method: 'get', params }),
  overview: () => http.request<ExecutionOverview>({ url: `${base}tasks/overview/`, method: 'get', params: { _t: Date.now() } }),
  workers: () => http.request<ExecutionWorker[]>({ url: `${base}workers/`, method: 'get', params: { _t: Date.now() } }),
  stop: (id: number) => http.request<ExecutionTask>({ url: `${base}tasks/${id}/stop/`, method: 'post' }),
  recover: (id: number) => http.request<ExecutionTask>({ url: `${base}tasks/${id}/recover/`, method: 'post' }),
  delete: (id: number) => http.request({ url: `${base}tasks/${id}/`, method: 'delete' }),
  reconcile: () => http.request({ url: `${base}tasks/reconcile/`, method: 'post' }),
};
