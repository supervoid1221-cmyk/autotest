import { http } from '@/utils/http/axios';

export interface SystemConfiguration {
  id?: number;
  report_retention_days: number;
  max_worker_count: number;
  max_performance_worker_count: number;
  platform_logo_light_url?: string;
  platform_logo_dark_url?: string;
  favicon_url?: string;
  updated_by_name?: string;
  created_at?: string;
  updated_at?: string;
}

const url = '/system/configuration/';

export const SystemConfigurationAPI = {
  detail: () => http.request<SystemConfiguration>({ url, method: 'get', params: { _t: Date.now() } }),
  branding: () => http.request<Pick<SystemConfiguration, 'platform_logo_light_url' | 'platform_logo_dark_url' | 'favicon_url' | 'updated_at'>>({ url: '/system/branding/', method: 'get', params: { _t: Date.now() } }, { withToken: false }),
  update: async (data: FormData) => {
    const response: any = await http.getAxios().request({
      url: '/api/system/configuration/',
      method: 'PUT',
      data,
      headers: { 'Content-Type': undefined },
    });
    return response?.data?.result as SystemConfiguration;
  },
};
