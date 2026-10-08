// 先写出非面向对象的代码s
// 创建类，让代码建立关联
// 修改类，让类更加抽象

import { http } from '@/utils/http/axios';

// 删除确认按钮可能被连续触发。统一按资源地址去重，避免首个请求已成功后再发出 404 请求。
const deletingTargets = new Set<string>();

export class BaseModelAPI<T> {
  base_url = '/';
  // 查询数据列表
  getDataList(params?) {
    return http.request<T[]>({
      url: `${this.base_url}`,
      method: 'GET',
      params,
    });
  }

  // 创建数据
  createData(params: T) {
    return http.request<T>({
      url: `${this.base_url}`,
      method: 'POST',
      params,
    });
  }

  // 查询数据详情
  getDataByID(id) {
    return http.request<T>({
      url: `${this.base_url}${id}/`,
      method: 'GET',
    });
  }

  // 修改数据
  update(id, nweData: T) {
    return http.request<T>({
      url: `${this.base_url}${id}/`,
      method: 'PUT',
      data: nweData,
    });
  }

  // 删除数据
  async DeleteDataByID(id) {
    const url = `${this.base_url}${id}/`;
    if (deletingTargets.has(url)) return;
    deletingTargets.add(url);
    try {
      const response = await http.request<T>(
        { url, method: 'DELETE' },
        { isTransformResponse: false, isShowErrorMessage: false, errorMessageMode: 'none' }
      );
      return response;
    } finally {
      deletingTargets.delete(url);
    }
  }
}
