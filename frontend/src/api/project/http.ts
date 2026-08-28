import {
  DatabaseConnection,
  DynamicFunction,
  Environment,
  EnvironmentAuthStatus,
  EnvironmentValidationResult,
  Project,
  ProjectVariable,
} from './models';
import { BaseModelAPI } from '../base_api';
import { http } from '@/utils/http/axios';

export class ProjectAPI extends BaseModelAPI<Project> {
  base_url = '/project/project/';

  createData(data: Project) {
    return http.request<Project>({
      url: this.base_url,
      method: 'POST',
      data,
    });
  }
}

export class ProjectVariableAPI extends BaseModelAPI<ProjectVariable> {
  base_url = '/project/variable/';

  createData(data: ProjectVariable) {
    return http.request<ProjectVariable>({
      url: this.base_url,
      method: 'POST',
      data,
    });
  }
}

export class EnvironmentAPI extends BaseModelAPI<Environment> {
  base_url = '/project/environment/';

  createData(data: Environment) {
    return http.request<Environment>({
      url: this.base_url,
      method: 'POST',
      data,
    });
  }

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

  test(code: string, functionName: string, argumentText = '') {
    return http.request<any>({
      url: `${this.base_url}test/`,
      method: 'POST',
      data: { code, function_name: functionName, arguments: argumentText },
    });
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
      operation: 'select' | 'update';
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
