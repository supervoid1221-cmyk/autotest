import { http } from '@/utils/http/axios';

export interface PrometheusInstance {
  id?: number;
  project: number | null;
  project_name?: string;
  name: string;
  base_url: string;
  access_token?: string;
  access_token_configured?: boolean;
  enabled: boolean;
  description?: string;
}

export interface MonitorTarget {
  id?: number;
  prometheus: number | null;
  prometheus_name?: string;
  project: number | null;
  project_name?: string;
  server: number | null;
  server_name?: string;
  mode?: 'standalone' | 'cluster'; cluster?: number | null; cluster_name?: string; discovered?: boolean; discovery_active?: boolean;
  name: string;
  job: string;
  instance_label: string;
  extra_labels: Record<string, string>;
  enabled: boolean;
  cpu_warning_threshold: number;
  cpu_critical_threshold: number;
  memory_warning_threshold: number;
  memory_critical_threshold: number;
  disk_warning_threshold: number;
  disk_critical_threshold: number;
}
export interface MonitorCluster { id?: number; project: number | null; project_name?: string; prometheus: number | null; prometheus_name?: string; server: number | null; server_name?: string; name: string; discovery_type: 'prometheus' | 'kubernetes' | 'file_sd' | 'cloud'; job: string; label_rules: Record<string, string>; instance_label_key: string; node_name_label: string; enabled: boolean; target_count?: number; last_synced_at?: string | null; last_sync_status?: string; last_sync_message?: string; cpu_warning_threshold: number; cpu_critical_threshold: number; memory_warning_threshold: number; memory_critical_threshold: number; disk_warning_threshold: number; disk_critical_threshold: number; }

export interface ServiceMonitor {
  id?: number;
  project: number | null;
  project_name?: string;
  server: number | null;
  server_name?: string;
  name: string;
  monitor_type: 'http' | 'tcp' | 'docker';
  address: string;
  port: number | null;
  expected_status_codes: number[];
  timeout_seconds: number;
  enabled: boolean;
}
export interface ServiceSnapshot { up: boolean; status_code: number | null; response_time_ms: number | null; message: string; }
export interface MonitorNotificationRule { id?: number; channel: number | null; channel_name?: string; channel_platform?: string; target: number | null; target_name?: string; services: number[]; service_names?: string[]; all_services: boolean; event: 'alert' | 'recovered' | 'all'; enabled: boolean; }
export interface MonitorNotificationDelivery { id: number; channel_name?: string; target_name?: string; service_name?: string; event: string; status: string; response_code?: number; response_summary?: string; created_at: string; }
export interface MonitorServiceEvent { id: number; service: number; service_name: string; project_name?: string; status: 'up' | 'down'; message: string; response_time_ms?: number | null; occurred_at: string; }
export interface MonitorServiceRecovery extends MonitorServiceEvent { alert_event_id: number; started_at: string; recovered_at: string; }

export interface MonitorMetricRange { rangeSeconds?: number; startTime?: number; endTime?: number; }
export interface MonitorSnapshot { current: { up: number | null; cpu: number | null; memory: number | null; disk: number | null; disk_iops: number | null; disk_read_iops: number | null; disk_write_iops: number | null }; series?: Record<string, Array<{ timestamp: number; value: number }>>; range?: { start: number; end: number }; }
export interface MonitorOverview { targets: Array<{ target: MonitorTarget } & MonitorSnapshot>; services: Array<{ service: ServiceMonitor } & ServiceSnapshot>; service_alerts: MonitorServiceEvent[]; service_recoveries: MonitorServiceRecovery[]; errors: Array<{ target_id: number; target_name: string; message: string }>; summary: { total: number; online: number; services_total: number; services_online: number; alerts: number }; }
export interface MonitorAlertEvent { id: number; target: number; target_name: string; project_name?: string; alert_key: string; severity: 'warning' | 'critical'; status: 'active' | 'recovered'; metric_value?: number; threshold?: number; message: string; started_at: string; recovered_at?: string; }
export interface MonitorCheckSettings {
  id?: number;
  target_check_interval_seconds: number;
  service_check_interval_seconds: number;
  last_target_check_at?: string | null;
  last_service_check_at?: string | null;
  updated_by_name?: string;
  updated_at?: string;
}

const base = '/monitor/';
export const MonitorAPI = {
  prometheusList: (project?: number | null) => http.request<PrometheusInstance[]>({ url: `${base}prometheus/`, method: 'get', params: project ? { project } : {} }),
  createPrometheus: (data: PrometheusInstance) => http.request<PrometheusInstance>({ url: `${base}prometheus/`, method: 'post', data }),
  updatePrometheus: (id: number, data: PrometheusInstance) => http.request<PrometheusInstance>({ url: `${base}prometheus/${id}/`, method: 'put', data }),
  deletePrometheus: (id: number) => http.request({ url: `${base}prometheus/${id}/`, method: 'delete' }),
  testPrometheus: (id: number) => http.request<{ connected: boolean }>({ url: `${base}prometheus/${id}/test/`, method: 'post' }),
  clusterList: (project?: number | null) => http.request<MonitorCluster[]>({ url: `${base}cluster/`, method: 'get', params: project ? { project } : {} }),
  createCluster: (data: MonitorCluster) => http.request<MonitorCluster>({ url: `${base}cluster/`, method: 'post', data }),
  updateCluster: (id: number, data: MonitorCluster) => http.request<MonitorCluster>({ url: `${base}cluster/${id}/`, method: 'put', data }),
  deleteCluster: (id: number) => http.request({ url: `${base}cluster/${id}/`, method: 'delete' }),
  syncCluster: (id: number) => http.request<{ created: number; updated: number; offline: number; matched: number }>({ url: `${base}cluster/${id}/sync/`, method: 'post' }),
  targetList: (project?: number | null) => http.request<MonitorTarget[]>({ url: `${base}target/`, method: 'get', params: project ? { project } : {} }),
  createTarget: (data: MonitorTarget) => http.request<MonitorTarget>({ url: `${base}target/`, method: 'post', data }),
  updateTarget: (id: number, data: MonitorTarget) => http.request<MonitorTarget>({ url: `${base}target/${id}/`, method: 'put', data }),
  deleteTarget: (id: number) => http.request({ url: `${base}target/${id}/`, method: 'delete' }),
  testTarget: (id: number) => http.request<MonitorSnapshot>({ url: `${base}target/${id}/test/`, method: 'post' }),
  serviceList: (project?: number | null) => http.request<ServiceMonitor[]>({ url: `${base}service/`, method: 'get', params: project ? { project } : {} }),
  createService: (data: ServiceMonitor) => http.request<ServiceMonitor>({ url: `${base}service/`, method: 'post', data }),
  updateService: (id: number, data: ServiceMonitor) => http.request<ServiceMonitor>({ url: `${base}service/${id}/`, method: 'put', data }),
  deleteService: (id: number) => http.request({ url: `${base}service/${id}/`, method: 'delete' }),
  testService: (id: number) => http.request<ServiceSnapshot>({ url: `${base}service/${id}/test/`, method: 'post' }),
  notificationRules: () => http.request<MonitorNotificationRule[]>({ url: `${base}notification-rule/`, method: 'get' }),
  createNotificationRule: (data: MonitorNotificationRule) => http.request<MonitorNotificationRule>({ url: `${base}notification-rule/`, method: 'post', data }),
  updateNotificationRule: (id: number, data: MonitorNotificationRule) => http.request<MonitorNotificationRule>({ url: `${base}notification-rule/${id}/`, method: 'put', data }),
  deleteNotificationRule: (id: number) => http.request({ url: `${base}notification-rule/${id}/`, method: 'delete' }),
  notificationDeliveries: () => http.request<MonitorNotificationDelivery[]>({ url: `${base}notification-delivery/`, method: 'get' }),
  targetMetrics: (id: number, range: number | MonitorMetricRange = 3600) => {
    const options = typeof range === 'number' ? { rangeSeconds: range } : range;
    return http.request<MonitorSnapshot & { target: MonitorTarget }>({
      url: `${base}target/${id}/metrics/`,
      method: 'get',
      params: {
        ...(options.rangeSeconds ? { range_seconds: options.rangeSeconds } : {}),
        ...(options.startTime ? { start_time: Math.floor(options.startTime / 1000) } : {}),
        ...(options.endTime ? { end_time: Math.floor(options.endTime / 1000) } : {}),
      },
    });
  },
  overview: (project?: number | null) => http.request<MonitorOverview>({ url: `${base}dashboard/overview/`, method: 'get', params: project ? { project } : {} }),
  alerts: () => http.request<MonitorAlertEvent[]>({ url: `${base}alert-event/`, method: 'get' }),
  serviceEvents: (project?: number | null) => http.request<MonitorServiceEvent[]>({ url: `${base}service-event/`, method: 'get', params: project ? { project } : {} }),
  checkSettings: () => http.request<MonitorCheckSettings>({ url: `${base}check-settings/`, method: 'get' }),
  updateCheckSettings: (data: MonitorCheckSettings) => http.request<MonitorCheckSettings>({ url: `${base}check-settings/current/`, method: 'put', data }),
  runChecksNow: () => http.request({ url: `${base}check-settings/run-now/`, method: 'post' }),
};
