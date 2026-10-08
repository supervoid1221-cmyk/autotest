import {
  DatabaseConnection,
  DynamicFunction,
  Environment,
  EnvironmentAuthStatus,
  EnvironmentValidationResult,
  Module,
  Project,
  ProjectVariable,
} from './models';
import { BaseModelAPI } from '../base_api';
import { http } from '@/utils/http/axios';

export class ProjectAPI extends BaseModelAPI<Project> {
  base_url = '/project/project/';
}

/** 三个 case 模块共用的目录，见后端 project.models.Module。 */
export class ModuleAPI extends BaseModelAPI<Module> {
  base_url = '/project/module/';

  /**
   * 删除目录。
   *
   * `cascade` 必须写在 URL 里而不是 params 上：请求拦截器会把非 GET 请求的 params
   * 搬进请求体，后端读的是 query_params，用 params 传会被静默忽略（旧的
   * delete_endpoints / delete_elements 就是这么失效的）。
   */
  deleteModule(id: number, cascade = false) {
    return http.request<{
      detail: string;
      cascade: boolean;
      counts: { endpoint_count: number; ui_element_count: number; app_element_count: number };
    }>(
      {
        url: `${this.base_url}${id}/?cascade=${cascade ? 'true' : 'false'}`,
        method: 'DELETE',
      },
      { isShowErrorMessage: false, errorMessageMode: 'none' }
    );
  }
}

export class ProjectVariableAPI extends BaseModelAPI<ProjectVariable> {
  base_url = '/project/variable/';
}

export class EnvironmentAPI extends BaseModelAPI<Environment> {
  base_url = '/project/environment/';

  getAuthStatus(id: number) {
    return http.request<EnvironmentAuthStatus>({
      url: `${this.base_url}${id}/auth-status/`,
      method: 'GET',
    });
  }

  getTokenValue(id: number) {
    return http.request<{ token: string }>({
      url: `${this.base_url}${id}/token-value/`,
      method: 'GET',
    });
  }

  validateAuth(id: number) {
    return http.request<EnvironmentValidationResult>({
      url: `${this.base_url}${id}/validate-auth/`,
      method: 'POST',
    });
  }

  refreshToken(id: number) {
    return http.request<EnvironmentAuthStatus>({
      url: `${this.base_url}${id}/refresh-token/`,
      method: 'POST',
    });
  }

  clearToken(id: number) {
    return http.request<EnvironmentAuthStatus>({
      url: `${this.base_url}${id}/clear-token/`,
      method: 'POST',
    });
  }
}

export class DynamicFunctionAPI extends BaseModelAPI<DynamicFunction> {
  base_url = '/project/dynamic-function/';

  test(code: string, functionName: string, argumentText = '', timeoutSeconds = 3, memoryMb = 128) {
    return http.request<any>({
      url: `${this.base_url}test/`,
      method: 'POST',
      data: { code, function_name: functionName, arguments: argumentText, timeout_seconds: timeoutSeconds, memory_mb: memoryMb },
    });
  }

  approve(id: number) {
    return http.request<DynamicFunction>({ url: `${this.base_url}${id}/approve/`, method: 'POST' });
  }

  reject(id: number) {
    return http.request<DynamicFunction>({ url: `${this.base_url}${id}/reject/`, method: 'POST' });
  }

  getWhitelist() {
    return http.request<any>({ url: `${this.base_url}whitelist/`, method: 'GET' });
  }

  checkConflicts(projects: number[], code: string, excludeId?: number) {
    return http.request<{
      conflicts: Array<{ project_id: number; project_name: string; functions: string[] }>;
    }>({
      url: `${this.base_url}check-conflicts/`,
      method: 'POST',
      data: { projects, code, exclude_id: excludeId || undefined },
    });
  }
}

export class DatabaseConnectionAPI extends BaseModelAPI<DatabaseConnection> {
  base_url = '/project/database-connection/';

  testConnection(data: DatabaseConnection) {
    return http.request<{ connected: boolean; elapsed_ms: number }>({
      url: `${this.base_url}test-connection/`,
      method: 'POST',
      data,
    });
  }

  testSql(data: DatabaseConnection & { sql: string; confirm_write?: boolean }) {
    return http.request<{
      operation: 'select' | 'update' | 'delete';
      columns?: string[];
      row?: Record<string, unknown> | null;
      row_count?: number;
      affected_rows?: number;
      elapsed_ms: number;
    }>({
      url: `${this.base_url}test-sql/`,
      method: 'POST',
      data,
    });
  }
}
