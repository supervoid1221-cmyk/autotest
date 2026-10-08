/** 平台分页使用 list；兼容历史接口的 results、data 和直接数组响应。 */
export function asList<T = any>(payload: unknown): T[] {
  if (Array.isArray(payload)) return payload;
  if (!payload || typeof payload !== 'object') return [];
  const response = payload as Record<string, unknown>;
  for (const key of ['list', 'results', 'data']) {
    if (Array.isArray(response[key])) return response[key] as T[];
  }
  return [];
}
