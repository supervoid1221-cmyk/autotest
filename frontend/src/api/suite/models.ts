import { components } from '../schema';

export type Suite = components['schemas']['Suite'];

export type RunResult = components['schemas']['RunResult'];

export interface RunProgress { result: RunResult; log: string; active: boolean }

export interface SuiteScenario { id?: number; suite: number; scenario: number; scenario_name?: string; order: number; continue_on_failure: boolean }
export interface SuiteExecutionItem { type: 'api' | 'ui' | 'playwright_ui'; id: number; order?: number }
export interface NotificationChannel { id?: number; projects: number[]; project_names?: string[]; name: string; platform: 'lark' | 'wecom'; webhook_url: string; enabled: boolean }
export interface NotificationRule { id?: number; channel: number; channel_name?: string; suite?: number | null; suite_name?: string; event: 'succeeded' | 'failed'; enabled: boolean }
export interface NotificationDelivery { id: number; result: number; channel: number; rule?: number | null; event: string; status: string; response_code?: number | null; response_summary: string; created_at: string }
