import { http } from '@/utils/http/axios';
import { BaseModelAPI } from '../base_api';

export interface TemplateParameter {
  key: string;
  label: string;
  type: 'text' | 'number' | 'boolean' | 'select';
  required: boolean;
  default_value: string;
  options: string[];
}

export interface ExecutionTemplate {
  id?: number;
  name: string;
  description: string;
  suite: number;
  parameters: TemplateParameter[];
  output_fields?: TemplateOutputField[];
  enabled: boolean;
  project?: number;
  project_name?: string;
  template_type?: 'api' | 'ui' | 'mixed' | 'empty';
  suite_name?: string;
  environment_name?: string;
}

export interface TemplateOutputField {
  key: string;
  label: string;
  source_step_id: number | null;
  json_path: string;
  display_type: 'text' | 'json';
  sort: number;
}

export class ExecutionTemplateAPI extends BaseModelAPI<ExecutionTemplate> {
  base_url = '/template/';

  runById(id: number, params: Record<string, any>, environment_id?: number | null) {
    return http.request<{ result_id: number }>({
      url: `${this.base_url}${id}/run/`,
      method: 'POST',
      data: { params, environment_id },
    });
  }

  getOutput(id: number, resultId: number) {
    return http.request<{
      result_id: number;
      status: string;
      active: boolean;
      fields: Array<TemplateOutputField & { value: unknown; error?: string }>;
    }>({
      url: `${this.base_url}${id}/output/`,
      method: 'GET',
      params: { result_id: resultId },
    });
  }
}
