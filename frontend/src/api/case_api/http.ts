import {
  Endpoint,
  EndpointModule,
  EndpointRunResult,
  Scenario,
  ScenarioBranch,
  ScenarioFlowNode,
  ScenarioStep,
} from './models';
import { BaseModelAPI } from '../base_api';
import { http } from '@/utils/http/axios';

export class EndpointAPI extends BaseModelAPI<Endpoint> {
  base_url = '/case_api/endpoint/';

  runById(id: number, environment: number) {
    return http.request<EndpointRunResult>({
      url: `${this.base_url}${id}/run/`,
      method: 'POST',
      data: { environment },
      timeout: 30 * 60 * 1000,
    });
  }

  async uploadFile(file: File) {
    const data = new FormData();
    data.append('file', file);
    // 浏览器必须自行生成 multipart boundary，不能沿用全局 JSON Content-Type。
    const response: any = await http.getAxios().request({
      // 这里直接使用 Axios 实例，不会经过 http.request 的 apiUrl 拼接逻辑，
      // 因此需显式补上前端统一的 /api 前缀。
      url: `/api${this.base_url}upload-file/`,
      method: 'POST',
      data,
      headers: { 'Content-Type': undefined },
    });
    return response?.data?.result as { name: string; path: string; size: number };
  }
}

export class EndpointModuleAPI extends BaseModelAPI<EndpointModule> {
  base_url = '/case_api/endpoint-module/';

  deleteModule(id: number, deleteEndpoints = false) {
    return http.request<{
      detail: string;
      deleted_endpoint_count: number;
      unassigned_endpoint_count: number;
    }>(
      {
        url: `${this.base_url}${id}/`,
        method: 'DELETE',
        params: { delete_endpoints: deleteEndpoints },
      },
      { isShowErrorMessage: false, errorMessageMode: 'none' }
    );
  }
}

export class RecordingAPI {
  private base_url = '/case_api/recording/';

  parse(data: Record<string, unknown>) {
    return http.request<{ records: RecordedRequest[]; count: number }>({
      url: `${this.base_url}parse/`,
      method: 'POST',
      data,
    });
  }

  importRecords(data: Record<string, unknown>) {
    return http.request<{
      created: number;
      updated: number;
      skipped: number;
      scenario_id?: number;
    }>({ url: `${this.base_url}import_records/`, method: 'POST', data });
  }
}

export interface RecordedRequest {
  record_id: string;
  selected: boolean;
  name: string;
  method: string;
  url: string;
  original_url?: string;
  base_url?: string;
  headers: Record<string, unknown>;
  params: Record<string, unknown>;
  data: Record<string, unknown>;
  json: Record<string, unknown>;
  status_code: number;
  duration_ms: number;
  response_preview?: string;
  auth_suggestion?: string;
  recommended_assertions?: Record<string, unknown>;
}

export class ScenarioAPI extends BaseModelAPI<Scenario> {
  base_url = '/case_api/scenario/';
  runById(id: number, environment: number) {
    // 场景可配置轮询，不能沿用全局 10 秒请求超时。
    return http.request({
      url: `${this.base_url}${id}/run/`,
      method: 'POST',
      data: { environment },
      timeout: 30 * 60 * 1000,
    });
  }
}
export class ScenarioStepAPI extends BaseModelAPI<ScenarioStep> {
  base_url = '/case_api/scenario-step/';

  reorder(scenario: number, stepIds: number[]) {
    return http.request({
      url: `${this.base_url}reorder/`,
      method: 'POST',
      data: { scenario, step_ids: stepIds },
    });
  }
  runById(id: number, environment: number) {
    return http.request({
      url: `${this.base_url}${id}/run/`,
      method: 'POST',
      data: { environment },
      timeout: 30 * 60 * 1000,
    });
  }
}

export class ScenarioFlowNodeAPI extends BaseModelAPI<ScenarioFlowNode> {
  base_url = '/case_api/scenario-flow-node/';
  reorder(scenario: number, nodeIds: number[], parentBranch?: number | null) {
    return http.request({
      url: `${this.base_url}reorder/`,
      method: 'POST',
      data: { scenario, node_ids: nodeIds, parent_branch: parentBranch || null },
    });
  }
}

export class ScenarioBranchAPI extends BaseModelAPI<ScenarioBranch> {
  base_url = '/case_api/scenario-branch/';
}
