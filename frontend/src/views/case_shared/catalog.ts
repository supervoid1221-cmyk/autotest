/**
 * 四类用例列表页共用的展示逻辑。
 *
 * 分工：
 *   - 版式（骨架、间距、配色）在 `styles/case-catalog.less`
 *   - 执行指标的数据结构在 `api/case_overview.ts`
 *   - 这里放「把指标翻译成界面上那几行字」的纯函数
 *
 * 四个页面必须给出完全一致的措辞、色档与筛选口径，所以这些逻辑只维护一份，
 * 而不是每页抄一遍 —— 抄出来的四份一定会慢慢漂移。
 */

import type { CaseOverviewItem, CaseOverviewStats } from '@/api/case_overview';

export type RunTone = 'ok' | 'bad' | 'run' | 'idle';
export type RateTone = 'good' | 'warn' | 'bad' | 'none';
/** 空字符串是「连续失败」这种警示角标，用 `.flag` 的默认橙色。 */
export type FlagTone = '' | 'new' | 'muted';
export type StatusKey = 'all' | 'ok' | 'bad' | 'none';

export interface RunState {
  tone: RunTone;
  text: string;
  hint: string;
}

export interface StatusFlag {
  text: string;
  tone: FlagTone;
}

export interface ProjectEntry {
  id: number | null;
  name: string;
  count: number;
  color: string;
}

export interface EnvironmentOption {
  label: string;
  value: number;
}

/** 项目面板里给每个项目分配的色点，按下标循环。 */
export const PROJECT_COLORS = ['#0f7b45', '#2563b8', '#b8790a', '#c1384a', '#6b45b5', '#00727b', '#8a99a8'];

/**
 * 相对时间。只用于列表里的「最近执行」提示，超过一个月就直接给日期。
 *
 * 负数（服务器时间比本机略快）并入「刚刚」，避免出现「-3 分钟前」。
 */
export function relativeTime(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const diff = Date.now() - date.getTime();
  const pad = (n: number) => String(n).padStart(2, '0');
  if (diff < 60_000) return '刚刚';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`;
  if (diff < 172_800_000) return `昨天 ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  if (diff < 2_592_000_000) return `${Math.floor(diff / 86_400_000)} 天前`;
  return `${date.getMonth() + 1} 月 ${date.getDate()} 日`;
}

/** 创建人头像里的首字母。 */
export function creatorInitial(name?: string | null): string {
  return String(name || '?').trim().slice(0, 1).toUpperCase();
}

/** 通过率色档：≥95 好，≥80 需关注，其余算差。 */
export function rateTone(rate?: number | null): RateTone {
  if (rate === null || rate === undefined) return 'none';
  if (rate >= 95) return 'good';
  if (rate >= 80) return 'warn';
  return 'bad';
}

/**
 * 步骤操作对应的徽标色调，复用 `.method` 已有的四个色调。
 *
 * 语义分组而不是照搬 HTTP 动词：断言/提取=绿，写操作=琥珀，流程与导航=蓝，
 * 清理/关闭=红。未收录的动作兜底给蓝色。
 */
const ACTION_TONES: Record<string, 'get' | 'post' | 'put' | 'delete'> = {
  // 只读观察：断言、提取、截图
  assert_text: 'get',
  assert_value: 'get',
  assert_visible: 'get',
  assert_exists: 'get',
  assert_attribute: 'get',
  save_text: 'get',
  get_text: 'get',
  screenshot: 'get',
  // 写操作：改变页面状态或数据
  click: 'post',
  input: 'post',
  upload_file: 'post',
  select: 'post',
  check: 'post',
  uncheck: 'post',
  set_variable: 'post',
  // 流程与导航
  goto: 'put',
  iframe_enter: 'put',
  iframe_exit: 'put',
  back: 'put',
  home: 'put',
  swipe: 'put',
  wait: 'put',
  wait_element: 'put',
  sleep: 'put',
  launch: 'put',
  restart: 'put',
  js_code: 'put',
  // 清理与关闭
  clear: 'delete',
  terminate: 'delete',
};

export function actionTone(action?: string | null): 'get' | 'post' | 'put' | 'delete' {
  return ACTION_TONES[String(action || '').toLowerCase()] || 'put';
}

export function hasRun(metric?: CaseOverviewItem | null): boolean {
  return Boolean(metric);
}

export function isPass(metric?: CaseOverviewItem | null): boolean {
  return Boolean(metric?.last_passed);
}

/**
 * 行状态徽标。本地正在执行优先，其次取计划执行结果，都没有则视为从未执行。
 */
export function runStateOf(
  metric: CaseOverviewItem | null | undefined,
  options: { running?: boolean; createdAt?: string | null } = {}
): RunState {
  if (options.running) return { tone: 'run', text: '执行中', hint: '刚刚触发' };
  if (!metric) return { tone: 'idle', text: '从未执行', hint: `创建于 ${relativeTime(options.createdAt)}` };
  return {
    tone: metric.last_passed ? 'ok' : 'bad',
    text: metric.last_passed ? '成功' : '失败',
    hint: relativeTime(metric.last_finished_at),
  };
}

/**
 * 名称后面的状态角标。优先级：停用 > 从未执行 > 连续失败。
 *
 * 只有用例有 `enabled` 字段（API 场景没有），所以必须用 `=== false` 判断，
 * 否则 undefined 会被当成「已停用」。
 */
export function statusFlagOf(row: { enabled?: boolean }, metric?: CaseOverviewItem | null): StatusFlag | null {
  if (row.enabled === false) return { text: '已停用', tone: 'muted' };
  if (!metric) return { text: '新建', tone: 'new' };
  if (metric.consecutive_failures >= 2) return { text: `连续失败 ${metric.consecutive_failures} 次`, tone: '' };
  return null;
}

/** 近 7 天与上周的环比（百分比）。上周为 0 时无法计算，返回 null。 */
export function weekDeltaOf(stats: Pick<CaseOverviewStats, 'runs_this_week' | 'runs_last_week'>): number | null {
  if (!stats.runs_last_week) return null;
  return Math.round(((stats.runs_this_week - stats.runs_last_week) / stats.runs_last_week) * 1000) / 10;
}

/**
 * 左侧项目面板的数据。`projectIdsOf` 由各页提供：场景可能关联多个项目，
 * 用例只属于一个项目。
 */
export function buildProjectEntries<T>(
  rows: T[],
  projects: any[],
  projectIdsOf: (row: T) => number[]
): ProjectEntry[] {
  return [
    { id: null, name: '全部项目', count: rows.length, color: '#008b95' },
    ...projects.map((project: any, index: number) => ({
      id: Number(project.id),
      name: project.name,
      count: rows.filter((row) => projectIdsOf(row).includes(Number(project.id))).length,
      color: PROJECT_COLORS[index % PROJECT_COLORS.length],
    })),
  ];
}

/** 项目面板的搜索。「全部项目」始终保留，否则搜完之后无法退回全量视图。 */
export function filterProjects(entries: ProjectEntry[], keyword: string): ProjectEntry[] {
  const kw = keyword.trim().toLowerCase();
  return entries.filter((item) => item.id === null || !kw || item.name.toLowerCase().includes(kw));
}

/**
 * 单项目用例的环境下拉选项：只展示环境名称，并按名称去重。
 *
 * 同名环境可能因历史数据或多条配置重复出现；选择值使用该名称下第一条有效环境记录。
 */
export function environmentOptionsForProject(
  environments: any[],
  projectId?: number | null
): EnvironmentOption[] {
  if (!projectId) return [];
  const scoped = environments.filter((environment: any) => Number(environment.project) === Number(projectId));
  const names = Array.from(new Set(
    scoped.map((environment: any) => String(environment.name || '').trim()).filter(Boolean)
  ));
  return names.map((name) => ({
    label: name,
    value: Number(scoped.find((environment: any) => String(environment.name || '').trim() === name)?.id),
  })).filter((option) => Number.isFinite(option.value) && option.value > 0);
}

/**
 * 项目 + 关键词筛选。状态筛选叠加在它的结果之上。
 */
export function filterRows<T>(
  rows: T[],
  options: {
    projectId: number | null;
    keyword: string;
    projectIdsOf: (row: T) => number[];
    textOf: (row: T) => string;
  }
): T[] {
  const keyword = options.keyword.trim().toLowerCase();
  return rows.filter((row) => {
    if (options.projectId !== null && !options.projectIdsOf(row).includes(Number(options.projectId))) return false;
    if (!keyword) return true;
    return options.textOf(row).toLowerCase().includes(keyword);
  });
}

/** 状态分段控件的选项与计数。 */
export function statusOptionsOf<T>(rows: T[], metricOf: (row: T) => CaseOverviewItem | null) {
  return [
    { key: 'all' as const, label: '全部', count: rows.length },
    { key: 'ok' as const, label: '通过', count: rows.filter((row) => isPass(metricOf(row))).length },
    {
      key: 'bad' as const,
      label: '失败',
      count: rows.filter((row) => hasRun(metricOf(row)) && !isPass(metricOf(row))).length,
    },
    { key: 'none' as const, label: '未执行', count: rows.filter((row) => !hasRun(metricOf(row))).length },
  ];
}

export function applyStatusFilter<T>(rows: T[], key: StatusKey, metricOf: (row: T) => CaseOverviewItem | null): T[] {
  if (key === 'ok') return rows.filter((row) => isPass(metricOf(row)));
  if (key === 'bad') return rows.filter((row) => hasRun(metricOf(row)) && !isPass(metricOf(row)));
  if (key === 'none') return rows.filter((row) => !hasRun(metricOf(row)));
  return rows;
}
