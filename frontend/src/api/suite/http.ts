import { http } from '@/utils/http/axios';

import {
  NotificationChannel,
  NotificationDelivery,
  NotificationRule,
  Suite,
  RunResult,
  SuiteScenario,
  SuiteExecutionItem,
} from './models';
import { BaseModelAPI } from '../base_api';

export class SuiteAPI extends BaseModelAPI<Suite> {
  base_url = '/suite/suite/';

  runById(id) {
    return http.request({
      url: `${this.base_url}${id}/run/`,
      method: 'post',
    });
  }

  /** 列表页直接切换启用状态。用 PATCH 只提交 enabled，
   *  避免为了改一个开关先把整份套件数据取回来再 PUT。 */
  setEnabled(id: number, enabled: boolean) {
    return http.request<Suite>({
      url: `${this.base_url}${id}/`,
      method: 'PATCH',
      data: { enabled },
    });
  }

  syncScenarios(id: number, scenarioIds: number[]) {
    return http.request<Suite>({
      url: `${this.base_url}${id}/sync-scenarios/`,
      method: 'post',
      data: { scenario_ids: scenarioIds },
    });
  }

  syncUiCases(id: number, uiCaseIds: number[]) {
    return http.request<Suite>({
      url: `${this.base_url}${id}/sync-ui-cases/`,
      method: 'post',
      data: { ui_case_ids: uiCaseIds },
    });
  }

  syncExecutionItems(id: number, items: SuiteExecutionItem[]) {
    return http.request<Suite>({
      url: `${this.base_url}${id}/sync-execution-items/`,
      method: 'post',
      data: { items: items.map(({ type, id: itemId }) => ({ type, id: itemId })) },
    });
  }
}

export class RunResultAPI extends BaseModelAPI<RunResult> {
  base_url = '/suite/run_result/';

  cancelById(id: number) {
    return http.request({ url: `${this.base_url}${id}/cancel/`, method: 'post' });
  }

  retryById(id: number) {
    return http.request({ url: `${this.base_url}${id}/retry/`, method: 'post' });
  }

  pauseById(id: number) {
    return http.request({ url: `${this.base_url}${id}/pause/`, method: 'post' });
  }

  getProgress(id: number) {
    // 运行状态是实时数据，避免浏览器、代理或生产网关复用上一轮执行的 GET 缓存。
    return http.request({
      url: `${this.base_url}${id}/progress/`,
      method: 'get',
      params: { _t: Date.now() },
      headers: { 'Cache-Control': 'no-cache' },
    });
  }

  getExecutionLog(id: number) {
    return http.request({
      url: `${this.base_url}${id}/execution-log/`,
      method: 'get',
      params: { _t: Date.now() },
      headers: { 'Cache-Control': 'no-cache' },
    });
  }

  fetchScreenshot(url: string): Promise<Blob> {
    return http
      .getAxios()
      .get(url, { responseType: 'blob' })
      .then((response) => response.data as Blob);
  }
}

export class SuiteScenarioAPI extends BaseModelAPI<SuiteScenario> {
  base_url = '/suite/scenario/';
}
export class NotificationChannelAPI extends BaseModelAPI<NotificationChannel> {
  base_url = '/suite/notification-channel/';
  test(id: number) {
    return http.request({ url: `${this.base_url}${id}/test/`, method: 'post' });
  }
}
export class NotificationRuleAPI extends BaseModelAPI<NotificationRule> {
  base_url = '/suite/notification-rule/';
}
export class NotificationDeliveryAPI extends BaseModelAPI<NotificationDelivery> {
  base_url = '/suite/notification-delivery/';
}
