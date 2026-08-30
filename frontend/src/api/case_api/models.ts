import { components } from '../schema';

export type UploadedEndpointFile = { name: string; path: string; size?: number };
export type Endpoint = components['schemas']['Endpoint'] & {
  files?: Record<string, UploadedEndpointFile[]>;
  /** [[字段名...], [数据行...]]，请求中通过 $ddt{字段名} 引用。 */
  parametrize?: Array<Array<string | number | boolean | null>>;
  module?: number | null;
  module_name?: string | null;
};

export interface EndpointRunResult {
  environment: string;
  passed: boolean;
  status_code?: number | null;
  duration_ms?: number;
  response_body?: string;
  response_json?: unknown;
  response_headers?: Record<string, string>;
  errors?: string[];
  attempts?: number;
  data_driven_results?: Array<Record<string, unknown>>;
}

export interface EndpointModule {
  id?: number;
  project: number;
  project_name?: string;
  name: string;
  endpoint_count?: number;
}

export interface Scenario {
  id?: number;
  project?: number | null;
  projects: number[];
  project_name?: string;
  project_names?: string[];
  name: string;
  description: string;
  step_count?: number;
}
export interface ScenarioStep {
  id?: number;
  scenario: number;
  endpoint?: number | null;
  endpoint_name?: string;
  endpoint_info?: Endpoint;
  order: number;
  request_method?: string;
  request_url?: string;
  request_override: Record<string, unknown>;
  extract: Record<string, unknown>;
  validate: Record<string, unknown>;
  post_sql?: string[];
  polling?: Record<string, unknown>;
  continue_on_failure: boolean;
  retry_on_failure: boolean;
  failure_retry_count: number;
}

export type ScenarioConditionOperator =
  | 'equals'
  | 'not_equals'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'
  | 'contains'
  | 'not_contains'
  | 'exists'
  | 'not_exists'
  | 'regex'
  | 'in';
export interface ScenarioBranchCondition {
  source: 'variable' | 'step';
  variable?: string;
  step_id?: number | null;
  path?: string;
  operator: ScenarioConditionOperator;
  expected?: string | number | boolean | null;
}
export interface ScenarioBranch {
  id?: number;
  condition_node: number;
  condition_node_name?: string;
  name: string;
  order: number;
  conditions: ScenarioBranchCondition[];
  nodes?: ScenarioFlowNode[];
}
export interface ScenarioFlowNode {
  id?: number;
  scenario: number;
  node_type: 'endpoint' | 'condition';
  step?: number | null;
  step_info?: ScenarioStep;
  parent_branch?: number | null;
  name: string;
  order: number;
  condition_logic?: 'and' | 'or';
  branches?: ScenarioBranch[];
}
