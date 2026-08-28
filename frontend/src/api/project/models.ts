import { components } from '../schema';

export type Project = components['schemas']['Project'];

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
  ssl_mode: 'preferred' | 'required' | 'disabled';
  connect_timeout: number;
  allow_write: boolean;
  enabled: boolean;
}
