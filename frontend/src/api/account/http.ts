import { http } from '@/utils/http/axios';
import { Profile, ResetPass } from './models';

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

export class UserManageAPI {
  base_url = '/account/user/';
  getDataList(params?) { return http.request<any[]>({ url: this.base_url, method: 'GET', params }); }
  getDataByID(id: number) { return http.request<any>({ url: `${this.base_url}${id}/`, method: 'GET' }); }
  createData(data: any) { return http.request<any>({ url: this.base_url, method: 'POST', data }); }
  updateData(id: number, data: any) { return http.request<any>({ url: `${this.base_url}${id}/`, method: 'PUT', data }); }
  deleteData(id: number) { return http.request({ url: `${this.base_url}${id}/`, method: 'DELETE' }); }
  resetPassword(id: number, password: string) { return http.request({ url: `${this.base_url}${id}/reset-password/`, method: 'POST', data: { password } }); }
}
