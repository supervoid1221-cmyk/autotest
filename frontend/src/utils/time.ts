export type DateTimeValue = string | number | Date | null | undefined;

export interface DateTimeFormatOptions {
  empty?: string;
  includeSeconds?: boolean;
}

export interface DurationFormatOptions {
  empty?: string;
  showMilliseconds?: boolean;
}

const pad = (value: number) => String(value).padStart(2, '0');

/**
 * 使用固定的本地时间格式，避免 toLocaleString 在不同浏览器中输出不一致。
 */
export function formatDateTime(
  value: DateTimeValue,
  { empty = '-', includeSeconds = true }: DateTimeFormatOptions = {}
): string {
  if (value === null || value === undefined || value === '') return empty;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return empty;
  const datePart = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  const timePart = `${pad(date.getHours())}:${pad(date.getMinutes())}`;
  return includeSeconds
    ? `${datePart} ${timePart}:${pad(date.getSeconds())}`
    : `${datePart} ${timePart}`;
}

/** 以毫秒为单位输出统一的中文耗时。 */
export function formatDurationMilliseconds(
  value: number | null | undefined,
  { empty = '-', showMilliseconds = true }: DurationFormatOptions = {}
): string {
  if (value === null || value === undefined) return empty;
  const milliseconds = Number(value);
  if (!Number.isFinite(milliseconds)) return empty;
  const safeMilliseconds = Math.max(0, milliseconds);
  if (showMilliseconds && safeMilliseconds < 1000) return `${Math.round(safeMilliseconds)} ms`;

  const totalSeconds = Math.floor(safeMilliseconds / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const parts: string[] = [];
  if (days) parts.push(`${days}天`);
  if (hours) parts.push(`${hours}小时`);
  if (minutes) parts.push(`${minutes}分`);
  if (seconds || !parts.length) parts.push(`${seconds}秒`);
  return parts.join('');
}

/** 以秒为单位输出统一的中文耗时。 */
export function formatDurationSeconds(
  value: number | null | undefined,
  options: Omit<DurationFormatOptions, 'showMilliseconds'> = {}
): string {
  if (value === null || value === undefined) return options.empty ?? '-';
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) return options.empty ?? '-';
  return formatDurationMilliseconds(seconds * 1000, { ...options, showMilliseconds: false });
}

/** 根据起止时间输出耗时；结束时间为空时可传入 Date.now() 表示实时计时。 */
export function formatElapsedDuration(
  start: DateTimeValue,
  end: DateTimeValue,
  options: DurationFormatOptions = {}
): string {
  if (
    start === null ||
    start === undefined ||
    start === '' ||
    end === null ||
    end === undefined ||
    end === ''
  ) {
    return options.empty ?? '-';
  }
  const startTime = start instanceof Date ? start.getTime() : new Date(start).getTime();
  const endTime = end instanceof Date ? end.getTime() : new Date(end).getTime();
  if (!Number.isFinite(startTime) || !Number.isFinite(endTime) || endTime < startTime) {
    return options.empty ?? '-';
  }
  return formatDurationMilliseconds(endTime - startTime, options);
}
