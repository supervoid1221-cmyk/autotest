<template>
  <div class="plan-page" @wheel.capture="handlePlanPageWheel">
    <header class="plan-heading">
      <div>
        <h1>测试计划</h1>
        <p>管理和执行自动化测试计划，保障业务质量</p>
      </div>
      <n-button type="primary" class="create-button" @click="addData">
        <template #icon><PhPlus /></template>新建计划
      </n-button>
    </header>

    <!-- 概览：原来列表页没有任何全局信息，看不出「有几个计划在失败」 -->
    <section class="plan-stats" aria-label="测试计划概览">
      <div class="stat">
        <span class="stat-ico"><PhChartLine /></span>
        <span class="stat-txt"><b>{{ plans.length }}</b><span>计划总数</span></span>
      </div>
      <div class="stat">
        <span class="stat-ico is-run"><PhClock /></span>
        <span class="stat-txt"><b>{{ cronCount }}</b><span>定时任务</span></span>
      </div>
      <button
        type="button"
        class="stat is-clickable"
        :class="{ 'is-on': onlyFailed }"
        title="点击只看近 7 天有失败的计划"
        @click="toggleOnlyFailed"
      >
        <span class="stat-ico is-fail"><PhWarningCircle /></span>
        <span class="stat-txt"><b>{{ recentFailedCount }}</b><span>近 7 天有失败</span></span>
      </button>
      <div class="stat">
        <span class="stat-ico is-ok"><PhCheckCircle /></span>
        <span class="stat-txt"><b>{{ enabledCount }}</b><span>已启用计划</span></span>
      </div>
    </section>

    <section class="plan-toolbar" aria-label="测试计划筛选">
      <n-input
        v-model:value="keyword"
        clearable
        placeholder="搜索计划名称或描述"
        aria-label="搜索计划名称"
      >
        <template #prefix><PhMagnifyingGlass /></template>
      </n-input>
      <n-select
        v-model:value="selectedProject"
        :options="projectOptionsWithAll"
        aria-label="项目筛选"
      />
      <n-select
        v-model:value="selectedEnvironment"
        :options="environmentOptions"
        aria-label="环境筛选"
      />
      <n-select
        v-model:value="selectedRunType"
        :options="runTypeOptions"
        aria-label="执行安排筛选"
      />
      <n-button text class="reset-button" :disabled="!hasActiveFilter" @click="resetFilters">
        <template #icon><PhArrowClockwise /></template>重置
      </n-button>
    </section>

    <div class="list-meta">
      <span class="count-text">{{ countText }}</span>
      <div class="filter-chips">
        <span v-for="chip in activeChips" :key="chip.key" class="filter-chip">
          {{ chip.label }}
          <button
            type="button"
            :aria-label="`移除筛选条件：${chip.label}`"
            @click="chip.clear()"
            >✕</button
          >
        </span>
      </div>
    </div>

    <section class="plan-list" :class="{ 'is-loading': loading }" :aria-busy="loading">
      <table class="plan-table">
        <colgroup>
          <col style="width: 17%" />
          <col style="width: 9%" />
          <col style="width: 8%" />
          <col style="width: 13%" />
          <col style="width: 9%" />
          <col style="width: 10%" />
          <col style="width: 12%" />
          <col style="width: 9%" />
          <col style="width: 13%" />
        </colgroup>
        <thead>
          <tr>
            <th class="is-sortable" @click="toggleSort('name')">
              <span class="th-inner"
                >计划名称
                <PhCaretDown v-if="isSorted('name', 'desc')" />
                <PhCaretUp v-else-if="isSorted('name', 'asc')" />
                <PhCaretUpDown v-else class="is-idle" />
              </span>
            </th>
            <th>项目</th>
            <th>创建人</th>
            <th>测试范围</th>
            <th>环境</th>
            <th>执行安排</th>
            <th class="is-sortable" @click="toggleSort('lastRunAt')">
              <span class="th-inner"
                >最近执行
                <PhCaretDown v-if="isSorted('lastRunAt', 'desc')" />
                <PhCaretUp v-else-if="isSorted('lastRunAt', 'asc')" />
                <PhCaretUpDown v-else class="is-idle" />
              </span>
            </th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in pagedRows"
            :key="row.id"
            :class="{ 'is-off': !row.enabled, 'is-open': current?.id === row.id }"
            @click="openDrawer(row)"
          >
            <td class="name-cell">
              <button
                type="button"
                class="plan-name"
                :title="row.name"
                @click.stop="openDrawer(row)"
                >{{ row.name }}</button
              >
              <span class="plan-desc" :title="row.description || ''">{{
                row.description || '暂无计划描述'
              }}</span>
            </td>
            <td>
              <span class="tag is-project" :title="projectName(row)">{{ projectName(row) }}</span>
            </td>
            <!-- 创建人是后端写入的名称快照。补字段之前建的历史计划没有这个信息，
                 接口返回空串，统一显示「-」而不是留空白单元格。 -->
            <td>
              <span
                class="plan-owner"
                :class="{ 'is-empty': !row.creator_name }"
                :title="row.creator_name || '暂无创建人信息'"
                >{{ row.creator_name || '-' }}</span
              >
            </td>
            <td>
              <div v-if="row._scope.length" class="scope-list" aria-label="测试范围">
                <template v-for="(scope, index) in row._scope" :key="scope.type">
                  <em v-if="index"></em>
                  <span
                    class="scope"
                    :class="scope.type"
                    :title="`${scope.label} 步骤 ${scope.count} 条`"
                    ><i></i>{{ scope.label }}<b>{{ scope.count }}</b></span
                  >
                </template>
              </div>
              <span v-else class="scope-empty">未配置步骤</span>
            </td>
            <td>
              <span class="tag" :title="row.environment_name || '未配置'">{{
                row.environment_name || '未配置'
              }}</span>
            </td>
            <td>
              <div class="schedule">
                <PhClock v-if="row.run_type === 'C'" />
                <PhLink v-else-if="row.run_type === 'W'" />
                <PhPlay v-else />
                <span class="schedule-text">
                  <strong>{{ runTypeLabel(row) }}</strong>
                  <small :title="scheduleHint(row)">{{ scheduleHint(row) }}</small>
                </span>
              </div>
            </td>
            <td>
              <div class="lastrun">
                <div class="lastrun-top">
                  <button
                    type="button"
                    class="status"
                    :class="row._status.cls"
                    :disabled="!row.last_run_id"
                    :title="row.last_run_id ? '查看这次执行报告' : '暂无执行记录'"
                    @click.stop="openReport(row)"
                    ><i></i>{{ row._status.label }}</button
                  >
                  <span class="lastrun-time" :title="formatFullTime(row.last_run_at)">{{
                    row._timeText
                  }}</span>
                </div>
                <div class="lastrun-rate">
                  <span class="spark" :title="`近 ${row._spark.length} 次执行结果`">
                    <b
                      v-for="(bar, index) in row._spark"
                      :key="index"
                      :class="bar.cls"
                      :style="{ height: `${bar.height}px` }"
                    />
                  </span>
                  <em>{{ row._rateText }}</em>
                </div>
              </div>
            </td>
            <td>
              <span class="plan-state">
                <button
                  type="button"
                  class="switch"
                  :class="{ 'is-off': !row.enabled }"
                  :aria-label="row.enabled ? '停用计划' : '启用计划'"
                  :title="row.enabled ? '点击停用' : '点击启用'"
                  @click.stop="toggleEnabled(row)"
                />
                <span class="plan-state-text" :class="{ 'is-off': !row.enabled }">{{
                  row.enabled ? '已启用' : '已停用'
                }}</span>
              </span>
            </td>
            <td>
              <div class="row-actions">
                <button
                  type="button"
                  class="action"
                  :disabled="runningIds.has(row.id)"
                  @click.stop="handleRun(row)"
                >
                  <PhPlay weight="fill" />{{ runningIds.has(row.id) ? '提交中' : '运行' }}
                </button>
                <button type="button" class="action is-mute" @click.stop="handleEdit(row)">
                  <PhPencilSimple />编辑
                </button>
                <n-dropdown
                  trigger="click"
                  :options="actionOptions(row)"
                  @select="(key) => handleAction(key, row)"
                >
                  <button class="action-more" type="button" aria-label="更多操作" @click.stop>
                    <PhDotsThree weight="bold" />
                  </button>
                </n-dropdown>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="!pagedRows.length && !loading" class="empty-state">
        <PhClipboardText />
        <strong>没有找到测试计划</strong>
        <span>调整筛选条件，或新建一个测试计划</span>
      </div>
      <div v-if="loading" class="loading-state"><n-spin size="small" />正在加载测试计划…</div>
    </section>

    <PaginationFooter
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="filteredRows.length"
    />
  </div>

  <!-- 快速预览：避免「点进详情页才能看执行历史」的来回跳转 -->
  <n-drawer
    v-model:show="drawerVisible"
    class="plan-drawer"
    :width="466"
    placement="right"
    :trap-focus="false"
  >
    <div v-if="current" class="drawer-panel">
      <header class="drawer-head">
        <div class="drawer-title">
          <h2 :title="current.name">{{ current.name }}</h2>
          <div class="drawer-sub">
            <span class="status" :class="current._status.cls"><i></i>{{ current._status.label }}</span>
            <span class="drawer-time">{{ current._timeText }}</span>
          </div>
        </div>
        <n-button quaternary circle aria-label="关闭预览" @click="drawerVisible = false">
          <template #icon><PhX /></template>
        </n-button>
      </header>

      <div class="drawer-body">
        <section class="drawer-section">
          <h3>基本信息</h3>
          <dl class="kv">
            <dt>所属项目</dt>
            <dd>{{ projectName(current) }}</dd>
            <dt>创建人</dt>
            <dd :class="{ 'is-empty-kv': !current.creator_name }">
              {{ current.creator_name || '-' }}
            </dd>
            <dt>执行环境</dt>
            <dd>{{ current.environment_name || '未配置' }}</dd>
            <dt>执行安排</dt>
            <dd>{{ drawerScheduleText }}</dd>
            <dt>测试范围</dt>
            <dd>{{ drawerScopeText }}</dd>
            <dt>计划描述</dt>
            <dd>{{ current.description || '暂无计划描述' }}</dd>
            <dt>启用状态</dt>
            <dd>{{ current.enabled ? '已启用' : '已停用' }}</dd>
          </dl>
        </section>

        <section v-if="current._spark.length" class="drawer-section">
          <h3>近 {{ current._spark.length }} 次结果</h3>
          <div class="trend" title="左旧右新">
            <b
              v-for="(bar, index) in current._spark"
              :key="index"
              :class="bar.cls"
              :style="{ height: `${bar.height}px` }"
            />
          </div>
        </section>

        <section class="drawer-section">
          <h3>最近执行记录</h3>
          <div v-if="current._runs.length" class="history">
            <div v-for="run in current._runs" :key="run.id" class="history-row">
              <span class="status" :class="run.cls"><i></i>{{ run.label }}</span>
              <span class="history-when">{{ run.when }}</span>
              <span class="history-cost">{{ run.cost }}</span>
              <button type="button" class="history-link" @click="openReport(current, run.id)">
                报告
              </button>
            </div>
          </div>
          <p v-else class="history-empty">该计划还没有执行记录</p>
        </section>
      </div>

      <footer class="drawer-foot">
        <n-button
          type="primary"
          class="drawer-primary"
          :loading="runningIds.has(current.id)"
          :disabled="current._status.cls === 'is-running'"
          @click="handleRun(current)"
        >
          <template #icon><PhPlay weight="fill" /></template>运行计划
        </n-button>
        <n-button :disabled="!current.last_run_id" @click="openReport(current)">查看报告</n-button>
        <n-button @click="handleEdit(current)">编辑</n-button>
      </footer>
    </div>
  </n-drawer>
</template>

<script lang="ts" setup>
  import { computed, h, onMounted, ref, watch } from 'vue';
  import { NIcon, useDialog, useMessage } from 'naive-ui';
  import { useRouter } from 'vue-router';
  import {
    PhArrowClockwise,
    PhCaretDown,
    PhCaretUp,
    PhCaretUpDown,
    PhChartLine,
    PhCheckCircle,
    PhClipboardText,
    PhClock,
    PhDotsThree,
    PhFileText,
    PhLink,
    PhMagnifyingGlass,
    PhPencilSimple,
    PhPlay,
    PhPlus,
    PhTrash,
    PhWarningCircle,
    PhX,
  } from '@phosphor-icons/vue';
  import { SuiteAPI } from '@/api/suite/http';
  import { EnvironmentAPI, ProjectAPI } from '@/api/project/http';
  import { asList } from '@/utils/list';
  import { formatDateTime as formatFullTime, formatDurationSeconds as formatDuration } from '@/utils/time';
  import PaginationFooter from '@/components/PaginationFooter/index.vue';

  /** 执行结果在列表页只需要 4 种展示态，映射关系与后端 summarize_run_status 保持一致。 */
  const RUN_STATUS_META: Record<string, { cls: string; label: string }> = {
    pass: { cls: 'is-pass', label: '通过' },
    fail: { cls: 'is-fail', label: '失败' },
    running: { cls: 'is-running', label: '执行中' },
    canceled: { cls: 'is-canceled', label: '已取消' },
    idle: { cls: 'is-idle', label: '未执行' },
  };

  const RECENT_FAILED_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;
  const DAY_MS = 24 * 60 * 60 * 1000;

  interface RecentRun {
    id: number;
    status: string;
    at: string | null;
    duration_seconds: number | null;
  }

  interface PlanRow {
    id: number;
    name: string;
    description?: string;
    environment_name?: string;
    run_type?: string;
    next_run?: string | null;
    case_api_count?: number;
    ui_step_count?: number;
    app_step_count?: number;
    enabled?: boolean;
    last_run_id?: number | null;
    last_run_status?: string;
    last_run_at?: string | null;
    last_run_duration_seconds?: number | null;
    recent_run_results?: RecentRun[];
    recent_pass_rate?: number | null;
    _scope: { type: string; label: string; count: number }[];
    _status: { cls: string; label: string };
    _spark: { cls: string; height: number }[];
    _rateText: string;
    _timeText: string;
    _runs: {
      id: number;
      cls: string;
      label: string;
      when: string;
      cost: string;
    }[];
    _lastRunTs: number;
  }

  const router = useRouter();
  const message = useMessage();
  const dialog = useDialog();
  const api = new SuiteAPI();
  const projectApi = new ProjectAPI();
  const environmentApi = new EnvironmentAPI();

  const plans = ref<PlanRow[]>([]);
  const projects = ref<any[]>([]);
  const environments = ref<any[]>([]);
  const loading = ref(false);
  const keyword = ref('');
  const selectedProject = ref(0);
  const selectedEnvironment = ref('all');
  const selectedRunType = ref('all');
  const onlyFailed = ref(false);
  const runningIds = ref(new Set<number>());
  const togglingIds = new Set<number>();
  const deletingIds = new Set<number>();
  const sortKey = ref<'name' | 'lastRunAt'>('lastRunAt');
  const sortDir = ref<'asc' | 'desc'>('desc');
  const page = ref(1);
  const pageSize = ref(10);
  const drawerVisible = ref(false);
  const current = ref<PlanRow | null>(null);

  const runTypeOptions = [
    { label: '全部执行安排', value: 'all' },
    { label: '手动执行', value: 'O' },
    { label: '定时任务', value: 'C' },
    { label: 'Webhook', value: 'W' },
  ];

  const projectOptionsWithAll = computed(() => [
    { label: '全部项目', value: 0 },
    ...projects.value.map((item) => ({ label: item.name, value: Number(item.id) })),
  ]);
  const environmentOptions = computed(() => {
    const names = environments.value
      .filter((item) => !selectedProject.value || Number(item.project) === selectedProject.value)
      .map((item) => String(item.name || '').trim())
      .filter(Boolean);
    return [
      { label: '全部环境', value: 'all' },
      ...Array.from(new Set(names)).map((name) => ({ label: name, value: name })),
    ];
  });

  /** 把后端返回的原始记录补成列表要展示的形态，避免模板里反复计算。 */
  function decorate(row: any): PlanRow {
    const runs: RecentRun[] = Array.isArray(row.recent_run_results) ? row.recent_run_results : [];
    const settled = runs.filter((run) => run.status === 'pass' || run.status === 'fail');
    const passRate =
      typeof row.recent_pass_rate === 'number'
        ? row.recent_pass_rate
        : settled.length
          ? Math.round((settled.filter((run) => run.status === 'pass').length / settled.length) * 100)
          : null;

    return {
      ...row,
      _scope: [
        { type: 'api', label: 'API', count: Number(row.case_api_count || 0) },
        { type: 'ui', label: 'UI', count: Number(row.ui_step_count || 0) },
        { type: 'app', label: 'App', count: Number(row.app_step_count || 0) },
      ].filter((item) => item.count > 0),
      _status: RUN_STATUS_META[row.last_run_status] || RUN_STATUS_META.idle,
      _spark: runs
        .slice()
        .reverse()
        .map((run) => ({
          cls: run.status === 'fail' ? 'is-fail' : run.status === 'pass' ? '' : 'is-na',
          height: run.status === 'pass' || run.status === 'fail' ? 14 : 4,
        })),
      _rateText: settled.length ? `通过率 ${passRate}%` : '暂无数据',
      _timeText: relativeTime(row.last_run_at),
      // 不截断：上方「近 N 次结果」趋势图用的就是这份数据，
      // 列表只显示前 5 条会和趋势图条数对不上，也会让用户以为没有更早的记录了。
      // 后端 RECENT_RUN_LIMIT 已经限了条数，这里全量渲染即可。
      _runs: runs.map((run) => {
        const meta = RUN_STATUS_META[run.status] || RUN_STATUS_META.idle;
        return {
          id: run.id,
          cls: meta.cls,
          label: meta.label,
          when: run.at ? `${formatShortTime(run.at)}（${relativeTime(run.at)}）` : '无记录',
          cost: formatDuration(run.duration_seconds),
        };
      }),
      _lastRunTs: row.last_run_at ? new Date(row.last_run_at).getTime() : 0,
    };
  }

  const filteredRows = computed(() => {
    const search = keyword.value.trim().toLowerCase();
    const now = Date.now();
    const rows = plans.value.filter((row) => {
      if (search && !`${row.name || ''} ${row.description || ''}`.toLowerCase().includes(search))
        return false;
      if (selectedProject.value && Number((row as any).project) !== selectedProject.value)
        return false;
      if (selectedEnvironment.value !== 'all' && row.environment_name !== selectedEnvironment.value)
        return false;
      if (selectedRunType.value !== 'all' && row.run_type !== selectedRunType.value) return false;
      if (onlyFailed.value) {
        const recent = row._lastRunTs && now - row._lastRunTs <= RECENT_FAILED_WINDOW_MS;
        if (!(recent && row._status.cls === 'is-fail')) return false;
      }
      return true;
    });
    const direction = sortDir.value === 'asc' ? 1 : -1;
    return rows.slice().sort((a, b) => {
      if (sortKey.value === 'name') return a.name.localeCompare(b.name, 'zh-Hans-CN') * direction;
      return (a._lastRunTs - b._lastRunTs) * direction;
    });
  });

  const pageCount = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / pageSize.value)));
  const pagedRows = computed(() =>
    filteredRows.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value)
  );

  const cronCount = computed(() => plans.value.filter((row) => row.run_type === 'C').length);
  const enabledCount = computed(() => plans.value.filter((row) => row.enabled).length);
  const recentFailedCount = computed(() => {
    const now = Date.now();
    return plans.value.filter(
      (row) =>
        row._status.cls === 'is-fail' && row._lastRunTs && now - row._lastRunTs <= RECENT_FAILED_WINDOW_MS
    ).length;
  });

  const hasActiveFilter = computed(
    () =>
      Boolean(keyword.value.trim()) ||
      Boolean(selectedProject.value) ||
      selectedEnvironment.value !== 'all' ||
      selectedRunType.value !== 'all' ||
      onlyFailed.value
  );

  const activeChips = computed(() => {
    const chips: { key: string; label: string; clear: () => void }[] = [];
    if (keyword.value.trim())
      chips.push({ key: 'kw', label: `关键字：${keyword.value.trim()}`, clear: () => (keyword.value = '') });
    if (selectedProject.value) {
      const name = projects.value.find((item) => Number(item.id) === selectedProject.value)?.name;
      chips.push({
        key: 'project',
        label: `项目：${name || selectedProject.value}`,
        clear: () => (selectedProject.value = 0),
      });
    }
    if (selectedEnvironment.value !== 'all')
      chips.push({
        key: 'env',
        label: `环境：${selectedEnvironment.value}`,
        clear: () => (selectedEnvironment.value = 'all'),
      });
    if (selectedRunType.value !== 'all')
      chips.push({
        key: 'run',
        label: `执行安排：${runTypeOptions.find((item) => item.value === selectedRunType.value)?.label || ''}`,
        clear: () => (selectedRunType.value = 'all'),
      });
    if (onlyFailed.value)
      chips.push({ key: 'fail', label: '近 7 天有失败', clear: () => (onlyFailed.value = false) });
    return chips;
  });

  const countText = computed(() =>
    hasActiveFilter.value
      ? `筛选出 ${filteredRows.value.length} 条 / 共 ${plans.value.length} 条计划`
      : `共 ${plans.value.length} 条计划`
  );

  const drawerScheduleText = computed(() => {
    const row = current.value;
    if (!row) return '';
    const label = runTypeLabel(row);
    if (row.run_type === 'C' && row.enabled && row.next_run)
      return `${label}，下次 ${formatFullTime(row.next_run)}`;
    return label;
  });

  const drawerScopeText = computed(() => {
    const row = current.value;
    if (!row || !row._scope.length) return '未配置步骤';
    return row._scope.map((item) => `${item.label} ${item.count}`).join(' / ');
  });

  function relativeTime(value?: string | null): string {
    if (!value) return '尚未执行';
    const time = new Date(value).getTime();
    if (Number.isNaN(time)) return String(value);
    const diff = Date.now() - time;
    if (diff < 60_000) return '刚刚';
    if (diff < 3_600_000) return `${Math.round(diff / 60_000)} 分钟前`;
    if (diff < DAY_MS) return `${Math.round(diff / 3_600_000)} 小时前`;
    if (diff < 30 * DAY_MS) return `${Math.round(diff / DAY_MS)} 天前`;
    return formatShortTime(value);
  }

  function pad(value: number): string {
    return value < 10 ? `0${value}` : String(value);
  }

  function formatShortTime(value?: string | null): string {
    if (!value) return '待计算';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  function projectName(row: any): string {
    return (
      row.project_name ||
      projects.value.find((item) => Number(item.id) === Number(row.project))?.name ||
      '未归属项目'
    );
  }

  function runTypeLabel(row: any): string {
    return row.run_type === 'C' ? '定时任务' : row.run_type === 'W' ? 'Webhook' : '手动执行';
  }

  function scheduleHint(row: PlanRow): string {
    if (row.run_type === 'C') {
      if (!row.enabled) return '已停用';
      return row.next_run ? formatShortTime(row.next_run) : '待计算';
    }
    return row.run_type === 'W' ? '外部触发' : '按需触发';
  }

  function isSorted(key: string, direction: string): boolean {
    return sortKey.value === key && sortDir.value === direction;
  }

  function toggleSort(key: 'name' | 'lastRunAt') {
    if (sortKey.value === key) sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc';
    else {
      sortKey.value = key;
      sortDir.value = 'desc';
    }
    page.value = 1;
  }

  function actionOptions(row: PlanRow) {
    return [
      {
        label: '查看最近报告',
        key: 'report',
        disabled: !row.last_run_id,
        icon: () => h(NIcon, null, { default: () => h(PhFileText) }),
      },
      {
        label: '删除计划',
        key: 'delete',
        icon: () => h(NIcon, null, { default: () => h(PhTrash) }),
      },
    ];
  }

  function addData() {
    router.push({ name: 'suite_suite_edit', params: { id: 0 } });
  }

  function handleEdit(row: PlanRow) {
    router.push({ name: 'suite_suite_edit', params: { id: row.id } });
  }

  function openReport(row: PlanRow, runId?: number) {
    const target = runId ?? row.last_run_id;
    if (!target) {
      message.warning('该计划还没有执行记录');
      return;
    }
    router.push({ name: 'execution_report', params: { sourceType: 'suite', id: target } });
  }

  function openDrawer(row: PlanRow) {
    current.value = row;
    drawerVisible.value = true;
  }

  function toggleOnlyFailed() {
    onlyFailed.value = !onlyFailed.value;
    page.value = 1;
  }

  function resetFilters() {
    keyword.value = '';
    selectedProject.value = 0;
    selectedEnvironment.value = 'all';
    selectedRunType.value = 'all';
    onlyFailed.value = false;
    page.value = 1;
  }

  /**
   * 页面外层由 Naive UI 的多层 Layout 承担滚动。鼠标停在页头、统计卡、
   * 筛选区或小屏幕下的横向表格容器时，第一次纵向滚轮可能被内层接收。
   * 在整个测试计划页的捕获阶段统一转发纵向手势；横向触控板手势仍交给表格。
   */
  function handlePlanPageWheel(event: WheelEvent) {
    if (!event.deltaY || Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;

    let ancestor = (event.currentTarget as HTMLElement | null)?.parentElement || null;
    while (ancestor) {
      const style = window.getComputedStyle(ancestor);
      const canOverflowY = style.overflowY === 'auto' || style.overflowY === 'scroll';
      if (canOverflowY && ancestor.scrollHeight > ancestor.clientHeight + 1) {
        let delta = event.deltaY;
        if (event.deltaMode === WheelEvent.DOM_DELTA_LINE) delta *= 16;
        else if (event.deltaMode === WheelEvent.DOM_DELTA_PAGE) delta *= ancestor.clientHeight;
        const canMove =
          delta < 0
            ? ancestor.scrollTop > 0
            : ancestor.scrollTop + ancestor.clientHeight < ancestor.scrollHeight - 1;
        if (canMove) {
          event.preventDefault();
          ancestor.scrollBy({ top: delta, behavior: 'auto' });
        }
        return;
      }
      ancestor = ancestor.parentElement;
    }
  }

  function handleRun(row: PlanRow) {
    let runDialog: any;
    runDialog = dialog.info({
      title: '运行测试计划',
      content: `确定运行“${row.name}”吗？`,
      positiveText: '运行',
      negativeText: '取消',
      onPositiveClick: async () => {
        if (runningIds.value.has(row.id)) return false;
        runningIds.value = new Set(runningIds.value).add(row.id);
        try {
          runDialog?.update?.({
            positiveButtonProps: { loading: true, disabled: true },
            negativeButtonProps: { disabled: true },
          });
          const response: any = await api.runById(row.id);
          message.success('任务已提交');
          drawerVisible.value = false;
          router.push({
            name: 'execution_report',
            params: { sourceType: 'suite', id: response.result_id },
          });
        } catch (error: any) {
          runDialog?.update?.({
            positiveButtonProps: { loading: false, disabled: false },
            negativeButtonProps: { disabled: false },
          });
          message.error(error?.message || '任务提交失败');
          return false;
        } finally {
          const next = new Set(runningIds.value);
          next.delete(row.id);
          runningIds.value = next;
        }
      },
    });
  }

  async function toggleEnabled(row: PlanRow) {
    if (togglingIds.has(row.id)) return;
    const next = !row.enabled;
    togglingIds.add(row.id);
    try {
      // 停用/启用会重建 django-q 调度，用接口返回的完整数据回填，
      // 这样「下次执行时间」不需要整表重新加载也能立刻正确。
      const updated: any = await api.setEnabled(row.id, next);
      Object.assign(row, decorate({ ...row, ...updated }));
      message.success(next ? `已启用“${row.name}”` : `已停用“${row.name}”`);
    } catch (error: any) {
      message.error(error?.message || '状态切换失败');
    } finally {
      togglingIds.delete(row.id);
    }
  }

  function handleAction(key: string, row: PlanRow) {
    if (key === 'report') {
      openReport(row);
      return;
    }
    if (key !== 'delete') return;
    dialog.warning({
      title: '删除测试计划',
      content: `确定删除“${row.name}”吗？`,
      positiveText: '删除',
      negativeText: '取消',
      onPositiveClick: async () => {
        if (deletingIds.has(row.id)) return;
        deletingIds.add(row.id);
        try {
          await api.DeleteDataByID(row.id);
          plans.value = plans.value.filter((item) => Number(item.id) !== Number(row.id));
          if (current.value?.id === row.id) drawerVisible.value = false;
          message.success('删除成功');
        } catch (error: any) {
          message.error(error?.message || '删除失败');
        } finally {
          deletingIds.delete(row.id);
        }
      },
    });
  }

  async function load() {
    loading.value = true;
    try {
      const [planPayload, projectPayload, environmentPayload]: any[] = await Promise.all([
        api.getDataList({ page: 1, pageSize: 999 }),
        projectApi.getDataList({ page: 1, pageSize: 1000 }),
        environmentApi.getDataList({ page: 1, pageSize: 1000 }),
      ]);
      plans.value = asList<any>(planPayload).map(decorate);
      projects.value = asList(projectPayload);
      environments.value = asList(environmentPayload);
    } catch (error: any) {
      message.error(error?.message || '测试计划加载失败');
    } finally {
      loading.value = false;
    }
  }

  watch([keyword, selectedProject, selectedEnvironment, selectedRunType, pageSize, onlyFailed], () => {
    page.value = 1;
  });
  watch(selectedProject, () => {
    if (
      selectedEnvironment.value !== 'all' &&
      !environmentOptions.value.some((item) => item.value === selectedEnvironment.value)
    )
      selectedEnvironment.value = 'all';
  });
  watch(pageCount, (count) => {
    if (page.value > count) page.value = count;
  });
  watch(drawerVisible, (visible) => {
    if (!visible) current.value = null;
  });
  onMounted(load);
</script>

<style lang="less" scoped>
  /* 颜色全部走变量：浅色值在这里，深色值在 styles/dark-theme.less 里覆盖。
     不要在组件内写 @media (prefers-color-scheme)，项目统一用 html[data-theme]。

     抽屉会被 teleport 到 body，继承不到 .plan-page 上的变量，
     所以用 mixin 让页面和抽屉两个根节点各自持有一份。

     注意：mixin 必须挂在 .drawer-panel 上，不能挂在 .plan-drawer 上。
     n-drawer 会把 class 透传到 teleport 出来的 .n-drawer 节点，那个节点不带 scoped
     的 data-v 属性，于是 `.plan-drawer[data-v-x]` 这条规则永远不命中，变量全部落空
     （表现为抽屉背景透明、主按钮文字回落到默认灰、对比度不足）。
     .drawer-panel 是本组件模板里的元素、带 data-v，所以放这里才可靠。
     对应的深色覆盖写在 styles/dark-theme.less：html[data-theme='dark'] .plan-drawer .drawer-panel */
  .plan-theme-vars() {
    --plan-primary: #087f67;
    --plan-primary-hover: #0a9a7c;
    --plan-primary-pressed: #066651;
    --plan-primary-soft: #e5f5f1;
    --plan-on-primary: #fff;

    --plan-ink: #122039;
    --plan-ink-2: #15233b;
    --plan-ink-3: #283950;
    --plan-muted: #74839a;
    --plan-muted-2: #718097;

    --plan-line: #e0e6ec;
    --plan-line-2: #e7ebf0;
    --plan-line-3: #d6dee8;

    --plan-head-bg: #f3f6f8;
    --plan-head-ink: #25364d;
    --plan-row-hover: #fbfdfc;

    --plan-project-ink: #24649b;
    --plan-project-soft: #e8f2fb;

    --plan-ok: #0f7b45;
    --plan-ok-soft: #e6f5ed;
    --plan-fail: #c1384a;
    --plan-fail-soft: #fdeaec;
    --plan-run: #24649b;
    --plan-run-soft: #e8f2fb;
    --plan-idle: #7a899c;
    --plan-idle-soft: #eef1f5;
    --plan-track: #edf1f5;

    --plan-dot-api: #11a87f;
    --plan-dot-ui: #326fe5;
    --plan-dot-app: #ef7b18;

    --plan-surface: #fff;
    --plan-surface-soft: #f7f9fb;
    /* 抽屉单独一个面：深色下页面是 #181818，抽屉如果同色就看不出层级 */
    --plan-drawer-surface: #fff;
    --plan-overlay: rgba(255, 255, 255, 0.92);
  }

  .plan-page {
    .plan-theme-vars();

    min-height: calc(100vh - 100px);
    margin: -16px;
    padding: 30px 28px 24px;
    box-sizing: border-box;
    background: var(--plan-surface);
    color: var(--plan-ink);
    font-family: Inter, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei',
      sans-serif;
  }

  /* naive 默认 placeholder 是 #C2C2C2，白底上对比度只有 1.78，基本看不清。
     这里换成页面已有的弱化色（对比度约 3.96）。
     必须 !important：naive 把 --n-* 变量写成组件根节点的内联 style，
     普通选择器权重再高也盖不过内联样式。 */
  .plan-page :deep(.n-input),
  .plan-page :deep(.n-base-selection) {
    --n-placeholder-color: var(--plan-muted-2) !important;
  }

  .plan-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
  }
  .plan-heading h1 {
    margin: 0;
    color: var(--plan-ink);
    font-size: 29px;
    line-height: 1.25;
    font-weight: 720;
    letter-spacing: -0.4px;
  }
  .plan-heading p {
    margin: 7px 0 0;
    color: var(--plan-muted);
    font-size: 14px;
  }
  .create-button {
    height: 46px;
    padding: 0 22px;
    border-radius: 5px;
    background: var(--plan-primary);
    font-size: 15px;
    font-weight: 650;
    /* 只写 background 挡不住 naive 的 :hover（它的选择器权重更高），必须一并覆盖变量 */
    --n-color: var(--plan-primary) !important;
    --n-color-hover: var(--plan-primary-hover) !important;
    --n-color-pressed: var(--plan-primary-pressed) !important;
    --n-color-focus: var(--plan-primary) !important;
    --n-border: none !important;
    --n-border-hover: none !important;
    --n-border-pressed: none !important;
    --n-border-focus: none !important;
    /* 深色下主色是亮绿，配白字对比度只有 2.3，必须换成深色文字 */
    --n-text-color: var(--plan-on-primary) !important;
    --n-text-color-hover: var(--plan-on-primary) !important;
    --n-text-color-pressed: var(--plan-on-primary) !important;
    --n-text-color-focus: var(--plan-on-primary) !important;
  }

  /* ===== 概览统计条 ===== */
  .plan-stats {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin-top: 26px;
  }
  .stat {
    display: flex;
    align-items: center;
    gap: 13px;
    padding: 15px 18px;
    border: 1px solid var(--plan-line);
    border-radius: 6px;
    background: var(--plan-surface);
    font-family: inherit;
    text-align: left;
  }
  .stat.is-clickable {
    cursor: pointer;
    transition: border-color 0.15s;
  }
  .stat.is-clickable:hover {
    border-color: var(--plan-primary);
  }
  .stat.is-on {
    border-color: var(--plan-primary);
    background: var(--plan-primary-soft);
  }
  .stat-ico {
    flex: none;
    width: 36px;
    height: 36px;
    border-radius: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--plan-idle-soft);
    color: var(--plan-idle);
    font-size: 18px;
  }
  .stat-ico.is-ok {
    background: var(--plan-ok-soft);
    color: var(--plan-ok);
  }
  .stat-ico.is-fail {
    background: var(--plan-fail-soft);
    color: var(--plan-fail);
  }
  .stat-ico.is-run {
    background: var(--plan-primary-soft);
    color: var(--plan-primary);
  }
  .stat-txt {
    min-width: 0;
  }
  .stat-txt b {
    display: block;
    color: var(--plan-ink);
    font-size: 21px;
    line-height: 1.15;
    font-weight: 720;
  }
  .stat-txt span {
    display: block;
    margin-top: 3px;
    color: var(--plan-muted);
    font-size: 12px;
    white-space: nowrap;
  }

  /* ===== 工具栏 ===== */
  .plan-toolbar {
    display: grid;
    grid-template-columns: minmax(240px, 1fr) 200px 180px 180px auto;
    gap: 16px;
    margin-top: 22px;
    align-items: center;
  }
  .plan-toolbar :deep(.n-input),
  .plan-toolbar :deep(.n-base-selection) {
    --n-height: 44px !important;
    border-radius: 5px;
  }
  .plan-toolbar :deep(.n-input__border),
  .plan-toolbar :deep(.n-base-selection__border) {
    border-color: var(--plan-line-3) !important;
  }
  .reset-button {
    height: 44px;
    padding: 0 14px;
    border-radius: 5px;
    color: var(--plan-primary);
    font-size: 14px;
    font-weight: 600;
    white-space: nowrap;
  }
  .reset-button:not(.n-button--disabled):hover {
    background: var(--plan-primary-soft);
  }

  /* ===== 计数与筛选标签 ===== */
  .list-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-top: 18px;
    min-height: 26px;
  }
  .count-text {
    color: var(--plan-muted);
    font-size: 13px;
  }
  .filter-chips {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .filter-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 26px;
    padding: 0 10px;
    border-radius: 13px;
    background: var(--plan-primary-soft);
    color: var(--plan-primary);
    font-size: 12px;
    white-space: nowrap;
    flex: none;
  }
  .filter-chip button {
    border: 0;
    background: transparent;
    color: inherit;
    font-size: 13px;
    line-height: 1;
    padding: 0;
    cursor: pointer;
    font-family: inherit;
  }

  /* ===== 列表 ===== */
  .plan-list {
    position: relative;
    margin-top: 14px;
    border: 1px solid var(--plan-line);
    border-radius: 6px;
    /* hidden 会建立一个无法纵向滚动的内层滚动容器，导致首次滚轮被截获。
       clip 仍保留圆角裁剪，但不会参与页面纵向滚动。 */
    overflow: clip;
  }
  .plan-list.is-loading {
    /* 异步数据返回前预留一页表格高度，首次滚轮时页面已是可滚动状态。 */
    min-height: 720px;
  }
  .plan-table {
    width: 100%;
    min-width: 1340px;
    border-collapse: collapse;
    table-layout: fixed;
  }
  .plan-table th {
    height: 51px;
    padding: 0 24px;
    background: var(--plan-head-bg);
    color: var(--plan-head-ink);
    font-size: 13px;
    font-weight: 650;
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    vertical-align: middle;
  }
  .plan-table th.is-sortable {
    cursor: pointer;
    user-select: none;
  }
  .th-inner {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap;
  }
  .th-inner svg {
    flex: none;
    font-size: 13px;
  }
  .th-inner .is-idle {
    color: var(--plan-muted);
  }
  .plan-table th.is-sortable:hover {
    color: var(--plan-primary);
  }

  .plan-table td {
    height: 78px;
    padding: 11px 24px;
    border-top: 1px solid var(--plan-line-2);
    vertical-align: middle;
    font-size: 13px;
    color: var(--plan-ink-3);
  }
  .plan-table tbody tr {
    cursor: pointer;
    transition: background 0.15s;
  }
  .plan-table tbody tr:hover {
    background: var(--plan-row-hover);
  }
  .plan-table tbody tr.is-open {
    background: var(--plan-primary-soft);
  }
  .plan-table tbody tr.is-off {
    opacity: 0.62;
  }

  .name-cell {
    min-width: 0;
  }
  .plan-name {
    display: block;
    max-width: 100%;
    overflow: hidden;
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--plan-ink-2);
    font-size: 15px;
    font-weight: 680;
    font-family: inherit;
    text-align: left;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: pointer;
  }
  .plan-name:hover {
    color: var(--plan-primary);
  }
  .plan-desc {
    display: block;
    margin-top: 6px;
    overflow: hidden;
    color: var(--plan-muted-2);
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* 创建人列：名字可能长于列宽，用省略号收口，完整值走 title。
     历史计划没有创建人信息，用 --plan-muted 弱化，免得「-」看起来像真数据。
     （深色下的取值由 styles/dark-theme.less 覆盖 --plan-muted 提供，此处不写死颜色） */
  .plan-owner {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .plan-owner.is-empty {
    color: var(--plan-muted);
  }

  .tag {
    display: inline-flex;
    align-items: center;
    max-width: 100%;
    height: 29px;
    padding: 0 12px;
    overflow: hidden;
    border-radius: 5px;
    background: var(--plan-primary-soft);
    color: var(--plan-primary);
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: none;
  }
  .tag.is-project {
    background: var(--plan-project-soft);
    color: var(--plan-project-ink);
  }

  .scope-list {
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
    overflow: hidden;
  }
  .scope-list em {
    width: 1px;
    height: 14px;
    background: var(--plan-line-3);
    flex: none;
  }
  .scope {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    color: var(--plan-ink-3);
    font-size: 12px;
    white-space: nowrap;
    flex: none;
  }
  .scope i {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--plan-dot-api);
    flex: none;
  }
  .scope.ui i {
    background: var(--plan-dot-ui);
  }
  .scope.app i {
    background: var(--plan-dot-app);
  }
  .scope b {
    color: var(--plan-ink);
    font-weight: 650;
  }
  .scope-empty {
    color: var(--plan-muted);
    font-size: 12px;
    white-space: nowrap;
  }

  .schedule {
    display: flex;
    align-items: flex-start;
    gap: 9px;
    min-width: 0;
  }
  .schedule > svg {
    flex: none;
    margin-top: 2px;
    font-size: 18px;
    color: var(--plan-muted);
  }
  .schedule-text {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }
  .schedule-text strong {
    color: var(--plan-ink-2);
    font-size: 13px;
    font-weight: 600;
    white-space: nowrap;
  }
  .schedule-text small {
    overflow: hidden;
    color: var(--plan-muted-2);
    font-size: 11px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* ===== 最近执行列 ===== */
  .lastrun {
    display: flex;
    flex-direction: column;
    gap: 7px;
    min-width: 0;
  }
  .lastrun-top {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .status {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    height: 22px;
    padding: 0 9px;
    border: 0;
    border-radius: 11px;
    font-size: 12px;
    font-weight: 600;
    font-family: inherit;
    white-space: nowrap;
    flex: none;
    cursor: pointer;
  }
  .status i {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    flex: none;
  }
  .status.is-pass {
    background: var(--plan-ok-soft);
    color: var(--plan-ok);
  }
  .status.is-fail {
    background: var(--plan-fail-soft);
    color: var(--plan-fail);
  }
  .status.is-running {
    background: var(--plan-run-soft);
    color: var(--plan-run);
  }
  .status.is-canceled,
  .status.is-idle {
    background: var(--plan-idle-soft);
    color: var(--plan-idle);
  }
  .status:disabled {
    cursor: default;
  }
  .status:not(:disabled):hover {
    filter: brightness(0.94);
  }
  .lastrun-time {
    min-width: 0;
    overflow: hidden;
    color: var(--plan-muted-2);
    font-size: 11px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .lastrun-rate {
    display: flex;
    align-items: center;
    gap: 7px;
    min-width: 0;
  }
  .spark {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 14px;
    flex: none;
  }
  .spark b {
    display: block;
    width: 4px;
    border-radius: 1px;
    background: var(--plan-ok);
  }
  .spark b.is-fail {
    background: var(--plan-fail);
  }
  .spark b.is-na {
    background: var(--plan-track);
  }
  .lastrun-rate em {
    color: var(--plan-muted-2);
    font-size: 11px;
    font-style: normal;
    white-space: nowrap;
    flex: none;
  }

  /* ===== 启用状态列 ===== */
  .plan-state {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    white-space: nowrap;
    flex: none;
  }
  .switch {
    position: relative;
    flex: none;
    width: 32px;
    height: 18px;
    padding: 0;
    border: 0;
    border-radius: 9px;
    background: var(--plan-ok);
    cursor: pointer;
    transition: background 0.15s;
  }
  .switch::after {
    content: '';
    position: absolute;
    top: 3px;
    right: 3px;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #fff;
    transition:
      right 0.15s,
      background 0.15s;
  }
  .switch.is-off {
    background: var(--plan-track);
  }
  .switch.is-off::after {
    right: 17px;
    background: var(--plan-idle);
  }
  .plan-state-text {
    color: var(--plan-ink-3);
  }
  .plan-state-text.is-off {
    color: var(--plan-muted);
  }

  /* ===== 行内操作 ===== */
  .row-actions {
    display: flex;
    align-items: center;
    gap: 7px;
    justify-content: flex-start;
  }
  .action {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    height: 28px;
    padding: 0 5px;
    border: 0;
    border-radius: 5px;
    background: transparent;
    color: var(--plan-primary);
    font-size: 12px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    white-space: nowrap;
    flex: none;
  }
  .action:hover {
    background: var(--plan-primary-soft);
  }
  .action svg {
    flex: none;
    font-size: 15px;
  }
  .action.is-mute {
    color: var(--plan-muted-2);
    font-weight: 500;
  }
  .action.is-mute:hover {
    background: var(--plan-idle-soft);
    color: var(--plan-ink-3);
  }
  .action:disabled {
    opacity: 0.5;
    cursor: wait;
  }
  .action-more {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    border: 0;
    border-radius: 5px;
    background: transparent;
    color: var(--plan-ink-3);
    font-size: 17px;
    cursor: pointer;
    flex: none;
  }
  .action-more:hover {
    background: var(--plan-idle-soft);
  }

  /* ===== 空态 / 加载态 ===== */
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 330px;
    color: var(--plan-muted);
  }
  .empty-state svg {
    margin-bottom: 12px;
    color: var(--plan-muted);
    font-size: 40px;
  }
  .empty-state strong {
    color: var(--plan-ink-3);
    font-size: 14px;
  }
  .empty-state span {
    margin-top: 6px;
    font-size: 12px;
  }
  .loading-state {
    position: absolute;
    inset: 51px 0 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    background: var(--plan-overlay);
    color: var(--plan-muted);
    font-size: 13px;
  }

  /* ===== 快速预览抽屉 ===== */
  .plan-drawer :deep(.n-drawer-body) {
    padding: 0;
    overflow: hidden;
  }
  .plan-drawer :deep(.n-drawer-body-content-wrapper) {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 0;
  }
  .drawer-panel {
    .plan-theme-vars();

    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    background: var(--plan-drawer-surface);
    color: var(--plan-ink);
  }
  .drawer-head {
    flex: none;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 14px;
    padding: 20px 22px 16px;
    border-bottom: 1px solid var(--plan-line-2);
  }
  .drawer-title {
    min-width: 0;
  }
  .drawer-title h2 {
    margin: 0;
    color: var(--plan-ink);
    font-size: 18px;
    font-weight: 700;
    line-height: 1.3;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .drawer-sub {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
  }
  .drawer-time {
    color: var(--plan-muted-2);
    font-size: 11px;
    white-space: nowrap;
  }
  .drawer-body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 18px 22px;
  }
  .drawer-section {
    margin-bottom: 22px;
  }
  .drawer-section h3 {
    margin: 0 0 11px;
    color: var(--plan-muted);
    font-size: 12px;
    font-weight: 650;
    letter-spacing: 0.4px;
    white-space: nowrap;
  }
  .kv {
    display: grid;
    grid-template-columns: 88px minmax(0, 1fr);
    gap: 11px 14px;
    margin: 0;
    font-size: 13px;
  }
  .kv dt {
    color: var(--plan-muted);
    white-space: nowrap;
  }
  .kv dd {
    margin: 0;
    color: var(--plan-ink-2);
    min-width: 0;
    word-break: break-all;
  }
  /* 「无数据」的 dd 跟列表里的 .plan-owner.is-empty 用同一个弱化色。
     必须写在 `.kv dd` 之后并带上 dd：只写 `.is-empty-kv` 会被 `.kv dd` 的
     color 盖掉（子元素自己设过颜色就不会继承父级）。 */
  .kv dd.is-empty-kv {
    color: var(--plan-muted);
  }
  .trend {
    display: flex;
    align-items: flex-end;
    gap: 5px;
    height: 56px;
    padding: 0 2px;
    border-bottom: 1px solid var(--plan-line);
  }
  .trend b {
    display: block;
    flex: 1;
    min-height: 3px;
    border-radius: 2px 2px 0 0;
    background: var(--plan-ok);
  }
  .trend b.is-fail {
    background: var(--plan-fail);
  }
  .trend b.is-na {
    background: var(--plan-track);
  }
  .history {
    border: 1px solid var(--plan-line);
    border-radius: 6px;
    overflow: hidden;
  }
  .history-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 13px;
    border-top: 1px solid var(--plan-line-2);
  }
  .history-row:first-child {
    border-top: 0;
  }
  .history-when {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    color: var(--plan-ink-3);
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .history-cost {
    flex: none;
    color: var(--plan-muted-2);
    font-size: 11px;
    white-space: nowrap;
  }
  .history-link {
    flex: none;
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--plan-primary);
    font-size: 12px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    white-space: nowrap;
  }
  .history-empty {
    margin: 0;
    color: var(--plan-muted);
    font-size: 12px;
  }
  .drawer-foot {
    flex: none;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 22px;
    border-top: 1px solid var(--plan-line-2);
    background: var(--plan-surface-soft);
  }
  .drawer-primary {
    flex: 1;
    height: 40px;
    border-radius: 5px;
    font-weight: 650;
    /* 覆盖 naive 的 primary 色（=全局主题蓝），否则抽屉里会出现蓝底灰字 */
    --n-color: var(--plan-primary) !important;
    --n-color-hover: var(--plan-primary-hover) !important;
    --n-color-pressed: var(--plan-primary-pressed) !important;
    --n-color-focus: var(--plan-primary) !important;
    --n-border: none !important;
    --n-border-hover: none !important;
    --n-border-pressed: none !important;
    --n-border-focus: none !important;
    /* 深色下主色是亮绿，配白字对比度只有 2.3，必须换成深色文字 */
    --n-text-color: var(--plan-on-primary) !important;
    --n-text-color-hover: var(--plan-on-primary) !important;
    --n-text-color-pressed: var(--plan-on-primary) !important;
    --n-text-color-focus: var(--plan-on-primary) !important;
  }
  .drawer-foot :deep(.n-button) {
    height: 40px;
    border-radius: 5px;
  }

  /* ===== 响应式 ===== */
  @media (max-width: 1400px) {
    .plan-toolbar {
      grid-template-columns: minmax(200px, 1fr) 180px 160px 160px auto;
      gap: 12px;
    }
  }
  @media (max-width: 1180px) {
    .plan-stats {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .plan-page {
      padding: 24px 18px;
    }
    .plan-list {
      overflow-x: auto;
      overflow-y: clip;
    }
  }
  @media (max-width: 820px) {
    .plan-page {
      margin: -12px -8px;
      padding: 22px 16px;
    }
    .plan-heading {
      flex-direction: column;
      gap: 14px;
    }
    .plan-heading h1 {
      font-size: 25px;
    }
    .create-button {
      height: 40px;
      padding: 0 14px;
    }
    .plan-toolbar {
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 22px;
    }
    .plan-toolbar > :first-child {
      grid-column: 1 / -1;
    }
  }
</style>
