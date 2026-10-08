import { http } from '@/utils/http/axios';
import { Profile, ResetPass } from './models';

export interface TenantInfo {
  id: string;
  name: string;
  slug: string;
  status: 'active' | 'suspended';
  role: string;
  role_name: string;
  member_count: number;
  project_count: number;
  max_regular_concurrent_executions: number;
  max_performance_concurrent_executions: number;
  storage_quota_bytes: number;
  storage_used_bytes: number;
  created_at: string;
  updated_at: string;
}

export interface TenantMember {
  id: number;
  user: number;
  username: string;
  is_active: boolean;
  role: 'owner' | 'admin' | 'member' | 'viewer';
  role_name: string;
  status: 'active' | 'disabled';
  status_name: string;
}

export interface TenantUserCandidate {
  id: number;
  username: string;
  is_member: boolean;
}

export function login(params) {
  return http.request<Profile>(
    {
      url: '/account/profile/login/',
      method: 'POST',
      params,
    },
    {
      isTransformResponse: false,
      withToken: false,
    }
  );
}

export function profile(params?) {
  return http.request<Profile>({
    url: '/account/profile/profile/',
    method: 'GET',
    params,
  });
}

// 修改密码
export function reset_password(params: ResetPass) {
  return http.request(
    {
      url: '/account/profile/reset_password/',
      method: 'POST',
      params,
    },
    {
      isTransformResponse: false,
    }
  );
}

// 查询用户列表
export function get_user_list() {
  return http.request<Profile[]>({
    url: '/account/profile/all_user/',
    method: 'GET',
  });
}

export function renewSession() {
  return http.request<{ token_expires_at: string }>({
    url: '/account/profile/renew-session/',
    method: 'POST',
  });
}

export function getTenants(params?: { include_inactive?: boolean }) {
  return http.request<TenantInfo[]>({
    url: '/account/tenant/',
    method: 'GET',
    params,
  });
}

export const TenantAPI = {
  list: (includeInactive = false) => getTenants(
    includeInactive ? { include_inactive: true } : undefined
  ),
  create: (data: Pick<TenantInfo, 'name' | 'slug' | 'status'> & Partial<Pick<TenantInfo, 'max_regular_concurrent_executions' | 'max_performance_concurrent_executions' | 'storage_quota_bytes'>>) =>
    http.request<TenantInfo>({ url: '/account/tenant/', method: 'POST', data }),
  update: (id: string, data: Partial<Pick<TenantInfo, 'name' | 'slug' | 'status' | 'max_regular_concurrent_executions' | 'max_performance_concurrent_executions' | 'storage_quota_bytes'>>) =>
    http.request<TenantInfo>({ url: `/account/tenant/${id}/`, method: 'PATCH', data }),
  remove: (id: string) =>
    http.request({ url: `/account/tenant/${id}/`, method: 'DELETE' }),
  members: (id: string) =>
    http.request<TenantMember[]>({ url: `/account/tenant/${id}/members/`, method: 'GET' }),
  memberCandidates: (id: string, search = '') =>
    http.request<TenantUserCandidate[]>({
      url: `/account/tenant/${id}/member-candidates/`, method: 'GET', params: { search },
    }),
  addMember: (id: string, data: { user?: number; username?: string; role: TenantMember['role'] }) =>
    http.request<TenantMember>({ url: `/account/tenant/${id}/members/`, method: 'POST', data }),
  updateMember: (
    id: string,
    userId: number,
    data: Partial<Pick<TenantMember, 'role' | 'status'>>
  ) => http.request<TenantMember>({
    url: `/account/tenant/${id}/members/${userId}/`, method: 'PATCH', data,
  }),
  removeMember: (id: string, userId: number) =>
    http.request({ url: `/account/tenant/${id}/members/${userId}/`, method: 'DELETE' }),
};

export class UserManageAPI {
  base_url = '/account/user/';
  getDataList(params?) { return http.request<any[]>({ url: this.base_url, method: 'GET', params }); }
  getDataByID(id: number) { return http.request<any>({ url: `${this.base_url}${id}/`, method: 'GET' }); }
  createData(data: any) { return http.request<any>({ url: this.base_url, method: 'POST', data }); }
  updateData(id: number, data: any) { return http.request<any>({ url: `${this.base_url}${id}/`, method: 'PUT', data }); }
  deleteData(id: number) { return http.request({ url: `${this.base_url}${id}/`, method: 'DELETE' }); }
  resetPassword(id: number, password: string) { return http.request({ url: `${this.base_url}${id}/reset-password/`, method: 'POST', data: { password } }); }
}
