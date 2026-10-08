import { http } from '@/utils/http/axios';
import { Element, PlaywrightCase, PlaywrightStep, UiCase, UiStep } from './models';
import { BaseModelAPI } from '../base_api';
import type { CaseOverview } from '../case_overview';

export class ElementAPI extends BaseModelAPI<Element> {
  base_url = '/case_ui/element/';
}

export class UiCaseAPI extends BaseModelAPI<UiCase> {
  base_url = '/case_ui/case/';

  syncSteps(id: number, steps: UiStep[]) {
    return http.request<UiStep[]>({
      url: `${this.base_url}${id}/sync-steps/`,
      method: 'post',
      data: { steps },
    });
  }

  run(id: number, environment?: number | null) {
    return http.request<{ passed: boolean; case_id: number }>({
      url: `${this.base_url}${id}/run/`,
      method: 'post',
      data: environment ? { environment } : {},
      // UI 试跑需要启动浏览器，首次运行还可能需要解析本地驱动，不使用全局 10 秒超时。
      timeout: 180_000,
    });
  }

  /** 列表页聚合数据：平台 KPI + 每个用例的最近执行与通过率。 */
  overview() {
    return http.request<CaseOverview>({ url: `${this.base_url}overview/`, method: 'GET' });
  }
}

export class UiStepAPI extends BaseModelAPI<UiStep> {
  base_url = '/case_ui/step/';
}

export class UiUploadedFileAPI {
  private base_url = '/case_ui/uploaded-file/';

  async upload(project: number, file: File) {
    const data = new FormData();
    data.append('project', String(project));
    data.append('file', file);
    const response: any = await http.getAxios().request({
      url: `/api${this.base_url}`,
      method: 'POST',
      data,
      headers: { 'Content-Type': undefined },
    });
    return response?.data?.result;
  }

  list(project: number) {
    return http.request<any>({ url: this.base_url, method: 'GET', params: { project, pageSize: 1000 } });
  }
}

export class PlaywrightCaseAPI extends BaseModelAPI<PlaywrightCase> {
  base_url = '/case_ui/playwright-case/';
  previewRecording(events: Record<string, any>[]) {
    return http.request<any>({ url: `${this.base_url}preview-recording/`, method: 'post', data: { events } });
  }
  importRecording(data: Record<string, any>) {
    return http.request<any>({ url: `${this.base_url}import-recording/`, method: 'post', data });
  }
  syncSteps(id: number, steps: PlaywrightStep[]) {
    return http.request<PlaywrightStep[]>({ url: `${this.base_url}${id}/sync-steps/`, method: 'post', data: { steps } });
  }
  run(id: number, environment?: number | null) {
    return http.request<any>({
      url: `${this.base_url}${id}/run/`,
      method: 'post',
      data: environment ? { environment } : {},
      timeout: 180_000,
    });
  }
  runTab(id: number, tabKey: string) {
    return http.request<any>({ url: `${this.base_url}${id}/run-tab/`, method: 'post', data: { tab_key: tabKey } });
  }
  /** 列表页聚合数据，结构与 UI 用例一致。 */
  overview() {
    return http.request<CaseOverview>({ url: `${this.base_url}overview/`, method: 'GET' });
  }
}

export class PlaywrightScenarioFileAPI extends BaseModelAPI<any> {
  base_url = '/case_ui/playwright-scenario-file/';
  createFile(data: Record<string, any>) {
    return http.request<any>({ url: this.base_url, method: 'post', data });
  }
  preview(content: string) {
    return http.request<any>({ url: `${this.base_url}preview/`, method: 'post', data: { content } });
  }
  run(id: number) {
    return http.request<any>({ url: `${this.base_url}${id}/run/`, method: 'post', timeout: 180_000 });
  }
  convertToSmartCases(id: number) {
    return http.request<{ count: number; created_count: number; updated_count: number; cases: Array<{ id: number; name: string; scenario_id: string; step_count: number; change: 'created' | 'updated' }> }>({
      url: `${this.base_url}${id}/convert-to-smart-case/`, method: 'post',
    });
  }
}

export class PlaywrightStepAPI extends BaseModelAPI<PlaywrightStep> {
  base_url = '/case_ui/playwright-step/';
}
