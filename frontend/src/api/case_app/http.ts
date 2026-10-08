import { http } from '@/utils/http/axios';
import type { CaseOverview } from '../case_overview';

export interface AppApplication { id?: number; project: number | null; project_name?: string; name: string; platform: 'android'; package_name: string; main_activity: string; startup_options: Record<string, any>; auto_install: boolean; replace_install: boolean; clear_data: boolean; enabled: boolean; description: string; versions?: AppVersion[]; version_count?: number; element_count?: number; module_count?: number; }
export interface AppVersion { id: number; application: number; application_name?: string; version_name: string; version_code: string; original_name: string; file_path: string; file_size: number; enabled: boolean; created_at: string; }
export interface AppExecutionNode { id?: number; project: number | null; project_name?: string; name: string; server_url: string; enabled: boolean; status?: 'unknown' | 'online' | 'offline'; last_message?: string; last_seen_at?: string; device_count?: number; }
export interface AppDevice { id?: number; project: number | null; project_name?: string; node: number | null; node_name?: string; name: string; udid: string; platform: 'android'; platform_version: string; model: string; resolution: string; state?: 'unknown' | 'online' | 'offline' | 'busy' | 'inspecting'; enabled: boolean; last_message?: string; last_seen_at?: string; }
export interface AppElement { id?: number; project: number | null; project_name?: string; application?: number | null; application_name?: string; module?: number | null; module_name?: string; name: string; page_name?: string; activity?: string; locator_type: string; locator_value: string; fallback_locator?: Array<Record<string, any>>; element_class?: string; snapshot?: Record<string, any>; description: string; }
export interface AppInspectorCandidate { type: string; label: string; value: string; stability: 'high' | 'medium' | 'low'; }
export interface AppInspectorElement { node_id: string; parent_id: string | null; depth: number; label: string; class_name: string; text: string; resource_id: string; content_desc: string; package: string; bounds: number[]; clickable: boolean; enabled: boolean; displayed: boolean; attributes: Record<string, string>; xpath: string; candidates: AppInspectorCandidate[]; }
export interface AppInspectorSnapshot { id: string; status: string; project: number; application: number; device: number; version?: number|null; activity: string; package_name: string; screen: { width: number; height: number }; screenshot: string; elements: AppInspectorElement[]; updated_at: string; recorded_step?: Partial<AppStep>; }
export interface AppStep { id?: number; case?: number; order: number; action: string; action_name?: string; element: number | null; element_name?: string; target: Record<string, any>; value: string; options: Record<string, any>; continue_on_failure: boolean; }
export interface AppCase { id?: number; project: number | null; project_name?: string; application: number | null; application_name?: string; default_device: number | null; default_device_name?: string; name: string; description: string; environment_name?: string; default_timeout: number; stop_on_failure: boolean; retry_count: number; enabled: boolean; step_count?: number; steps?: AppStep[]; created_by_name?: string; created_at?: string; updated_at?: string; }
export interface AppArtifact { id: number; artifact_type: string; name: string; download_url: string; }
export interface AppStepResult { id: number; order: number; action: string; name: string; status: string; duration_ms: number; message: string; started_at?: string; finished_at?: string; artifacts: AppArtifact[]; }
export interface AppRun { id: number; execution_no: number; case: number; case_name: string; project: number; project_name: string; application: number; application_name: string; version?: number | null; version_name?: string; device: number; device_name: string; status: string; progress: number; summary: Record<string, number>; error_message: string; log_content: string; started_at?: string; finished_at?: string; created_at: string; step_results: AppStepResult[]; artifacts: AppArtifact[]; created_by_name?: string; }
const list = <T>(url: string, params: Record<string, any> = {}) => http.request<T[]>({ url, method: 'get', params });
export const AppTestAPI = {
  applications: (params: Record<string, any> = {}) => list<AppApplication>('/case_app/application/', params),
  application: (id: number) => http.request<AppApplication>({ url: `/case_app/application/${id}/`, method: 'get' }),
  saveApplication: (data: AppApplication) => http.request<AppApplication>({ url: data.id ? `/case_app/application/${data.id}/` : '/case_app/application/', method: data.id ? 'put' : 'post', data }),
  deleteApplication: (id: number) => http.request({ url: `/case_app/application/${id}/`, method: 'delete' }),
  uploadVersion: async (application: number, versionName: string, versionCode: string, file: File) => {
    const data = new FormData();
    data.append('version_name', versionName);
    data.append('version_code', versionCode);
    data.append('file', file);
    // Do not inherit the global JSON content type. The browser must add the
    // multipart boundary to Content-Type for Django's multipart parser.
    const response: any = await http.getAxios().request({
      url: `/api/case_app/application/${application}/upload-version/`,
      method: 'POST',
      data,
      headers: { 'Content-Type': undefined },
    });
    return response?.data?.result as AppVersion;
  },
  versions: (application?: number) => list<AppVersion>('/case_app/version/', application ? { application, pageSize: 1000 } : { pageSize: 1000 }),
  deleteVersion: (id: number) => http.request({ url: `/case_app/version/${id}/`, method: 'delete' }),
  nodes: (params: Record<string, any> = {}) => list<AppExecutionNode>('/case_app/node/', params),
  saveNode: (data: AppExecutionNode) => http.request<AppExecutionNode>({ url: data.id ? `/case_app/node/${data.id}/` : '/case_app/node/', method: data.id ? 'put' : 'post', data }),
  deleteNode: (id: number) => http.request({ url: `/case_app/node/${id}/`, method: 'delete' }),
  testNode: (id: number) => http.request({ url: `/case_app/node/${id}/test/`, method: 'post' }),
  devices: (params: Record<string, any> = {}) => list<AppDevice>('/case_app/device/', params),
  saveDevice: (data: AppDevice) => http.request<AppDevice>({ url: data.id ? `/case_app/device/${data.id}/` : '/case_app/device/', method: data.id ? 'put' : 'post', data }),
  deleteDevice: (id: number) => http.request({ url: `/case_app/device/${id}/`, method: 'delete' }),
  testDevice: (id: number) => http.request({ url: `/case_app/device/${id}/test/`, method: 'post' }),
  elements: (params: Record<string, any> = {}) => list<AppElement>('/case_app/element/', params),
  element: (id: number) => http.request<AppElement>({ url: `/case_app/element/${id}/`, method: 'get' }),
  saveElement: (data: AppElement) => http.request<AppElement>({ url: data.id ? `/case_app/element/${data.id}/` : '/case_app/element/', method: data.id ? 'put' : 'post', data }),
  deleteElement: (id: number) => http.request({ url: `/case_app/element/${id}/`, method: 'delete' }),
  startInspector: (data: Record<string, any>) => http.request<AppInspectorSnapshot>({ url: '/case_app/inspector/', method: 'post', data }),
  currentInspector: () => http.request<{ active: boolean; session?: AppInspectorSnapshot; message?: string }>({ url: '/case_app/inspector/current/', method: 'get', params: { _t: Date.now() } }),
  refreshInspector: (id: string) => http.request<AppInspectorSnapshot>({ url: `/case_app/inspector/${id}/refresh/`, method: 'post' }),
  tapInspector: (id: string, data: Record<string, any>) => http.request<AppInspectorSnapshot>({ url: `/case_app/inspector/${id}/tap/`, method: 'post', data }),
  backInspector: (id: string, record = false) => http.request<AppInspectorSnapshot>({ url: `/case_app/inspector/${id}/back/`, method: 'post', data: { record } }),
  inputInspector: (id: string, data: Record<string, any>) => http.request<AppInspectorSnapshot>({ url: `/case_app/inspector/${id}/input/`, method: 'post', data }),
  swipeInspector: (id: string, data: Record<string, any>) => http.request<AppInspectorSnapshot>({ url: `/case_app/inspector/${id}/swipe/`, method: 'post', data }),
  finishInspectorRecording: (id: string, data: Record<string, any>) => http.request<AppCase>({ url: `/case_app/inspector/${id}/finish-recording/`, method: 'post', data }),
  validateInspector: (id: string, locator_type: string, locator_value: string) => http.request<{ matched: number; unique: boolean }>({ url: `/case_app/inspector/${id}/validate/`, method: 'post', data: { locator_type, locator_value } }),
  saveInspectorElement: (id: string, data: Record<string, any>) => http.request<AppElement>({ url: `/case_app/inspector/${id}/save-element/`, method: 'post', data }),
  closeInspector: (id: string) => http.request({ url: `/case_app/inspector/${id}/`, method: 'delete' }),
  cases: (params: Record<string, any> = {}) => list<AppCase>('/case_app/case/', params),
  appCase: (id: number) => http.request<AppCase>({ url: `/case_app/case/${id}/`, method: 'get' }),
  saveCase: (data: AppCase) => http.request<AppCase>({ url: data.id ? `/case_app/case/${data.id}/` : '/case_app/case/', method: data.id ? 'put' : 'post', data }),
  deleteCase: (id: number) => http.request({ url: `/case_app/case/${id}/`, method: 'delete' }),
  /** 列表页聚合数据：平台 KPI + 每个用例的最近执行与通过率。 */
  caseOverview: () => http.request<CaseOverview>({ url: '/case_app/case/overview/', method: 'get' }),
  /** 用例的步骤列表，详情抽屉用。过滤参数是 `case`。 */
  steps: (params: Record<string, any> = {}) => list<AppStep>('/case_app/step/', params),
  syncSteps: (id: number, steps: AppStep[]) => http.request<AppStep[]>({ url: `/case_app/case/${id}/sync-steps/`, method: 'post', data: { steps } }),
  start: (id: number, data: Record<string, any>) => http.request<AppRun>({ url: `/case_app/case/${id}/run/`, method: 'post', data }),
  runs: (params: Record<string, any> = {}) => list<AppRun>('/case_app/run/', params),
  run: (id: number) => http.request<AppRun>({ url: `/case_app/run/${id}/`, method: 'get', params: { _t: Date.now() } }),
  stop: (id: number) => http.request({ url: `/case_app/run/${id}/stop/`, method: 'post' }),
  deleteRun: (id: number) => http.request({ url: `/case_app/run/${id}/`, method: 'delete' }),
  log: (id: number) => http.request<{ content: string }>({ url: `/case_app/run/${id}/log/`, method: 'get', params: { _t: Date.now() } }),
  artifact: (runId: number, artifactId: number): Promise<Blob> =>
    http
      .getAxios()
      .get(`/api/case_app/run/${runId}/artifact/${artifactId}/`, { responseType: 'blob' })
      .then((response) => response.data as Blob),
};
