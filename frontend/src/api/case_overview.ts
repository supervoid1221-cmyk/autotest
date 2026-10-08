/**
 * 四类用例列表页共用的执行聚合数据结构。
 *
 * API 场景 / UI 用例 / 智能用例 / App 用例的列表页都要展示「平台 KPI + 每个用例的
 * 最近执行与通过率」，后端由 `suite/run_metrics.py` 的 `build_overview()` 统一产出，
 * 因此前端也只维护一份类型。
 *
 * 口径说明：这些指标来自**测试计划的执行报告**，不是列表页上的即席试跑
 * （试跑是同步执行且不落库）。
 */

/** 单次执行记录的摘要，用于详情抽屉里的「最近执行」列表。 */
export interface CaseOverviewHistory {
  passed: boolean;
  finished_at: string | null;
  /** 来源测试计划名称。 */
  suite_name: string;
  executor: string;
}

/** 单个用例的执行指标。 */
export interface CaseOverviewItem {
  last_passed: boolean;
  last_finished_at: string | null;
  /** 最近 `sample_size` 次执行的通过率（百分比，保留 1 位小数）。 */
  pass_rate: number | null;
  passed_count: number;
  sample_size: number;
  /** 从最近一次往前数的连续失败次数，用于判定「待处理异常」。 */
  consecutive_failures: number;
  history: CaseOverviewHistory[];
}

export interface CaseOverviewStats {
  /** 当前用户可见的用例总数。 */
  total: number;
  /** 这些用例覆盖的项目数。 */
  project_count: number;
  /** 有执行数据、因而能算出通过率的用例数。 */
  covered: number;
  /** 近 7 天「包含本类型用例」的计划执行次数。 */
  runs_this_week: number;
  /** 上周同口径次数。 */
  runs_last_week: number;
  pass_rate: number | null;
  /** 连续失败 ≥ 2 次的用例数。 */
  abnormal: number;
  /** 通过率统计的样本总数。 */
  sample_size: number;
  /** 后端扫描执行记录的上限。 */
  run_scan_limit: number;
  /** 扫描窗口被上限填满，说明周统计可能偏低。 */
  scan_truncated: boolean;
}

export interface CaseOverview {
  stats: CaseOverviewStats;
  /** key 为用例 id 的字符串形式。 */
  items: Record<string, CaseOverviewItem>;
}

/** 接口可能直接返回 result，也可能再包一层，这里统一收口，避免页面拿到 undefined。 */
export function normalizeOverview(payload: any): CaseOverview {
  const source = payload?.stats
    ? payload
    : payload?.result?.stats
      ? payload.result
      : payload?.data?.stats
        ? payload.data
        : null;
  if (!source) return { stats: EMPTY_OVERVIEW_STATS(), items: {} };
  return {
    stats: { ...EMPTY_OVERVIEW_STATS(), ...source.stats },
    items: source.items || {},
  };
}

export function EMPTY_OVERVIEW_STATS(): CaseOverviewStats {
  return {
    total: 0,
    project_count: 0,
    covered: 0,
    runs_this_week: 0,
    runs_last_week: 0,
    pass_rate: null,
    abnormal: 0,
    sample_size: 0,
    run_scan_limit: 0,
    scan_truncated: false,
  };
}
