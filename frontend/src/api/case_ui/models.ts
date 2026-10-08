import { components } from '../schema';

export type Element = components['schemas']['Element'] & {
  module?: number | null;
  module_name?: string | null;
  project_name?: string;
};

export interface UiCaseTab {
  key: string;
  name: string;
  order: number;
}

export interface UiCase {
  id?: number;
  project: number | null;
  project_name?: string;
  name: string;
  description: string;
  environment_name?: string;
  browser: 'chrome';
  run_mode: 'headless' | 'headed';
  tabs: UiCaseTab[];
  enabled: boolean;
  step_count?: number;
}

export interface UiStep {
  id?: number;
  ui_case?: number;
  order?: number;
  tab_key: string;
  action: string;
  action_name?: string;
  element: number | null;
  element_name?: string;
  element_by?: string;
  element_value?: string;
  value: string;
  options: Record<string, any>;
  continue_on_failure: boolean;
}

export type PlaywrightAction = 'goto' | 'input' | 'upload_file' | 'click' | 'select' | 'check' | 'assert_visible' | 'assert_text' | 'save_text' | 'sleep';

export interface PlaywrightCase {
  id?: number;
  project: number | null;
  project_name?: string;
  created_by?: number | null;
  creator_name?: string;
  name: string;
  description: string;
  browser: 'chromium' | 'firefox' | 'webkit';
  run_mode: 'headless' | 'headed';
  environment_name: string;
  default_timeout: number;
  viewport: { width: number; height: number };
  enabled: boolean;
  step_count?: number;
}

export interface PlaywrightStep {
  id?: number;
  case?: number;
  order?: number;
  action: PlaywrightAction;
  target: string;
  value: string;
  locator_mode: 'auto' | 'manual';
  fallback_type: string;
  fallback_value: string;
  options: Record<string, any>;
  continue_on_failure: boolean;
}
