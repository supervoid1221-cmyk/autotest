import { isArray, isObject, isString } from '@/utils/is';

const DATE_TIME_FORMAT = 'YYYY-MM-DD HH:mm';

/** 后端错误体里可能出现文案的字段，按优先级排列。 */
const ERROR_TEXT_KEYS = ['detail', 'message', 'error', 'non_field_errors'];

function pickErrorText(value: unknown): string {
  if (isString(value)) {
    return value.trim();
  }
  if (isArray(value)) {
    for (const item of value) {
      const text = pickErrorText(item);
      if (text) {
        return text;
      }
    }
    return '';
  }
  if (isObject(value)) {
    const record = value as Recordable;
    for (const key of ERROR_TEXT_KEYS) {
      const text = pickErrorText(record[key]);
      if (text) {
        return text;
      }
    }
    for (const item of Object.values(record)) {
      const text = pickErrorText(item);
      if (text) {
        return text;
      }
    }
  }
  return '';
}

/**
 * @description: 从后端错误响应体里取出可以直接展示给用户的文案。
 *
 * 后端字段名并不统一：多数返回 `{"detail": "..."}`，但租户模块会返回
 * `{"status": "不能停用当前操作账号。"}`，密码校验走 `{"message": "..."}`，
 * 而且 DRF 会把值包成数组（`{"detail": ["..."]}`）。只读 `data.message`
 * 会拿到 undefined 或数组，最终弹出一个空白提示。这里统一摊平成一句话；
 * 取不到就返回空串，由调用方决定兜底文案。
 */
export function extractErrorMessage(data: unknown): string {
  return pickErrorText(data);
}

export function joinTimestamp<T extends boolean>(
  join: boolean,
  restful: T
): T extends true ? string : object;

export function joinTimestamp(join: boolean, restful = false): string | object {
  if (!join) {
    return restful ? '' : {};
  }
  const now = new Date().getTime();
  if (restful) {
    return `?_t=${now}`;
  }
  return { _t: now };
}

/**
 * @description: Format request parameter time
 */
export function formatRequestDate(params: Recordable) {
  if (Object.prototype.toString.call(params) !== '[object Object]') {
    return;
  }

  for (const key in params) {
    if (params[key] && params[key]._isAMomentObject) {
      params[key] = params[key].format(DATE_TIME_FORMAT);
    }
    if (isString(key)) {
      const value = params[key];
      if (value) {
        try {
          params[key] = isString(value) ? value.trim() : value;
        } catch (error) {
          throw new Error(error as any);
        }
      }
    }
    if (isObject(params[key])) {
      formatRequestDate(params[key]);
    }
  }
}
