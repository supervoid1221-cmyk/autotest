import { components } from '../schema';

export type Project = components['schemas']['Project'];

/**
 * 项目级共享目录。
 *
 * 接口管理、UI 元素管理、App 元素管理读写的是同一行数据，所以三个页面共用这一个
 * 类型；三个计数按域分开返回，各页面只展示自己那一类。
 */
export interface Module {
  id?: number;
  project: number;
  project_name?: string;
  name: string;
  created_by?: number | null;
  created_by_name?: string;
  endpoint_count?: number;
  ui_element_count?: number;
  app_element_count?: number;
  created_at?: string;
  updated_at?: string;
}

export interface ProjectVariable {
  id?: number;
  project: number;
  project_name?: string;
  name: string;
  value: string;
  description: string;
}

export interface Environment {
  id?: number;
  project: number | null;
  project_name?: string;
  name: string;
  base_url: string;
  auth_enabled: boolean;
  login_url: string;
  login_method: string;
  login_headers: Record<string, unknown>;
  login_params: Record<string, unknown>;
  login_data: Record<string, unknown>;
  login_json: Record<string, unknown>;
  token_jsonpath: string;
  token_name: string;
  token_header: string;
  token_prefix: string;
  token_ttl: number;
  browser_token_enabled: boolean;
  browser_token_storage: 'local_storage' | 'session_storage' | 'cookie';
  browser_token_key: string;
  browser_token_include_prefix: boolean;
  browser_cookie_domain: string;
  browser_cookie_path: string;
}

export interface EnvironmentAuthStatus {
  auth_enabled: boolean;
  cached: boolean;
  valid: boolean;
  masked_token: string;
  token_refreshed_at: string | null;
  token_expires_at: string | null;
  remaining_seconds: number;
}

export interface EnvironmentValidationResult extends EnvironmentAuthStatus {
  connected: boolean;
  detail: string;
  elapsed_ms: number;
}

export interface DynamicFunction {
  id?: number;
  projects: number[];
  project_names?: string[];
  function_names?: string[];
  name: string;
  description: string;
  code: string;
  enabled: boolean;
  language?: 'python';
  version?: number;
  code_hash?: string;
  approval_status?: 'draft' | 'approved' | 'rejected';
  timeout_seconds: number;
  memory_mb: number;
  created_by_name?: string;
  approved_by_name?: string;
  approved_at?: string | null;
}

export interface DatabaseConnection {
  id?: number;
  projects: number[];
  project_names?: string[];
  environment_name: 'Dev' | 'Test' | 'Pre' | 'Prod';
  database_type: 'mysql' | 'postgresql';
  database_type_display?: string;
  function_name: string;
  host: string;
  port: number;
  database: string;
  username: string;
  password?: string;
  password_configured?: boolean;
  use_ssh_tunnel: boolean;
  ssh_host: string;
  ssh_port: number;
  ssh_username: string;
  ssh_private_key_path: string;
  ssh_private_key_passphrase?: string;
  ssh_private_key_passphrase_configured?: boolean;
  ssh_strict_host_key: boolean;
  ssl_mode: 'preferred' | 'required' | 'disabled';
  connect_timeout: number;
  allow_write: boolean;
  allow_delete: boolean;
  enabled: boolean;
}
