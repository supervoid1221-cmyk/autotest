import { http } from '@/utils/http/axios';
import { Element, ElementModule, PlaywrightCase, PlaywrightStep, UiCase, UiStep } from './models';
import { BaseModelAPI } from '../base_api';

export class ElementAPI extends BaseModelAPI<Element> {
  base_url = '/case_ui/element/';
}

export class ElementModuleAPI extends BaseModelAPI<ElementModule> {
  base_url = '/case_ui/element-module/';

  deleteModule(id: number, deleteElements = false) {
    return http.request<{ detail: string; deleted_element_count: number; unassigned_element_count: number }>(
      {
        url: `${this.base_url}${id}/`, method: 'DELETE',
        params: { delete_elements: deleteElements },
      },
      { isShowErrorMessage: false, errorMessageMode: 'none' }
    );
  }
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
  run(id: number) {
    return http.request<any>({ url: `${this.base_url}${id}/run/`, method: 'post' });
  }
  runTab(id: number, tabKey: string) {
    return http.request<any>({ url: `${this.base_url}${id}/run-tab/`, method: 'post', data: { tab_key: tabKey } });
  }
}

export class PlaywrightStepAPI extends BaseModelAPI<PlaywrightStep> {
  base_url = '/case_ui/playwright-step/';
}

