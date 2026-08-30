import { http } from '@/utils/http/axios';

export interface ServerConnection {
  id?: number;
  project: number | null;
  project_name?: string;
  name: string;
  host: string;
  port: number;
  username: string;
  auth_type: 'private_key' | 'password';
  private_key_path?: string;
  private_key_passphrase?: string;
  private_key_passphrase_configured?: boolean;
  password?: string;
  password_configured?: boolean;
  strict_host_key: boolean;
  enabled: boolean;
  description?: string;
  last_tested_at?: string | null;
  last_test_status?: boolean | null;
  last_test_message?: string;
  created_by_name?: string;
  created_at?: string;
}

const baseUrl = '/system/server-connection/';

export const ServerConnectionAPI = {
  list: (project?: number | null) => http.request<ServerConnection[]>({ url: baseUrl, method: 'get', params: { ...(project ? { project } : {}), _t: Date.now() } }),
  create: (data: ServerConnection) => http.request<ServerConnection>({ url: baseUrl, method: 'post', data }),
  update: (id: number, data: ServerConnection) => http.request<ServerConnection>({ url: `${baseUrl}${id}/`, method: 'put', data }),
  remove: (id: number) => http.request({ url: `${baseUrl}${id}/`, method: 'delete' }),
  testDraft: (data: ServerConnection) => http.request<{ connected: boolean; elapsed_ms: number }>({ url: `${baseUrl}test-connection-draft/`, method: 'post', data }),
  test: (id: number) => http.request<{ connected: boolean; elapsed_ms: number }>({ url: `${baseUrl}${id}/test-connection/`, method: 'post' }),
};
