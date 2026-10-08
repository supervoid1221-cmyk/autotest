<template>
  <div class="case-catalog">
    <aside class="project-panel">
      <header><strong>项目</strong><span>{{ projects.length }} 个</span></header>
      <n-input v-model:value="projectKeyword" clearable placeholder="搜索项目" aria-label="搜索项目"><template #prefix><PhMagnifyingGlass /></template></n-input>
      <nav class="project-list" aria-label="项目筛选">
        <button v-for="project in visibleProjects" :key="project.id ?? 'all'" type="button" :class="{ active: selectedProject === project.id }" @click="selectProject(project.id)">
          <i :style="{ background: project.color || '#93a3b3' }"></i>
          <span>{{ project.name }}</span><b>{{ project.count }}</b>
        </button>
      </nav>
      <p class="project-hint"><PhInfo />每个用例只属于一个项目，切换项目即按项目筛选</p>
    </aside>

    <main class="catalog-main">
      <header class="page-heading">
        <div>
          <div class="breadcrumb"><span>UI 测试</span><i>/</i><span>UI 用例</span></div>
          <div class="title-line"><h1>UI 用例</h1><p>维护浏览器自动化用例，覆盖页面交互流程</p></div>
        </div>
        <n-button type="primary" class="create-button" @click="createCase"><template #icon><PhPlus /></template>新建 UI 用例</n-button>
      </header>

      <section class="kpi-row">
        <article class="kpi">
          <div class="kpi-top"><PhStack />用例总数</div>
          <div class="kpi-val num">{{ overview.stats.total }}</div>
          <div class="kpi-foot">覆盖 {{ overview.stats.project_count }} 个项目</div>
        </article>
        <article class="kpi">
          <div class="kpi-top"><PhArrowsClockwise />近 7 天执行<span v-if="overview.stats.scan_truncated" class="flag" :title="`后端只统计最近 ${overview.stats.run_scan_limit} 条执行记录，实际次数可能更多`">已达上限</span></div>
          <div class="kpi-val num">{{ overview.stats.runs_this_week }} <small>次</small></div>
          <div class="kpi-foot">
            <span v-if="weekDelta !== null" class="trend" :class="weekDelta >= 0 ? 'up' : 'down'">{{ weekDelta >= 0 ? '▲' : '▼' }} {{ Math.abs(weekDelta) }}%</span>
            <span>上周 {{ overview.stats.runs_last_week }} 次</span>
          </div>
        </article>
        <article class="kpi">
          <div class="kpi-top"><PhCheckCircle />平均通过率</div>
          <div class="kpi-val num">{{ overview.stats.pass_rate ?? '—' }}<small v-if="overview.stats.pass_rate !== null">%</small></div>
          <div class="kpi-foot">{{ overview.stats.covered }} 个用例有执行数据 · 样本 {{ overview.stats.sample_size }} 次</div>
        </article>
        <article class="kpi" :class="{ alert: overview.stats.abnormal > 0 }">
          <div class="kpi-top"><PhWarning />待处理异常</div>
          <div class="kpi-val num">{{ overview.stats.abnormal }}</div>
          <div class="kpi-foot">连续失败 ≥ 2 次 · 需人工介入</div>
        </article>
      </section>

      <div class="table-toolbar">
        <n-input v-model:value="searchName" clearable placeholder="搜索用例名称或描述" aria-label="搜索用例" class="search-input"><template #prefix><PhMagnifyingGlass /></template></n-input>
        <div class="segmented status-filter" role="tablist" aria-label="执行状态筛选">
          <button v-for="item in statusOptions" :key="item.key" type="button" :class="{ on: statusFilter === item.key }" @click="statusFilter = item.key">
            {{ item.label }} <i>{{ item.count }}</i>
          </button>
        </div>
        <span class="toolbar-spacer"></span>
        <div class="segmented view-switch" aria-label="视图切换">
          <button type="button" :class="{ on: viewMode === 'list' }" aria-label="列表视图" @click="viewMode = 'list'"><PhListBullets /></button>
          <button type="button" :class="{ on: viewMode === 'card' }" aria-label="卡片视图" @click="viewMode = 'card'"><PhDotsNine /></button>
        </div>
        <button type="button" class="refresh-button" aria-label="刷新列表" :disabled="loading" @click="load"><PhArrowsClockwise :class="{ spinning: loading }" /></button>
      </div>

      <section class="list-card">
        <table v-show="viewMode === 'list'" class="case-table">
          <colgroup><col class="c1" /><col class="c2" /><col class="c3" /><col class="c4" /><col class="c5" /><col class="c6" /><col class="c7" /><col class="c8" /></colgroup>
          <thead><tr><th>用例名称</th><th>所属项目</th><th>浏览器 / 模式</th><th>步骤</th><th>最近执行</th><th>通过率</th><th>创建人</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="row in pagedCases" :key="row.id" :class="{ selected: drawerCase?.id === row.id }" @click="openDrawer(row)">
              <td>
                <div class="case-name">
                  <div class="name-line"><strong>{{ row.name }}</strong><span v-if="flagOf(row)" class="flag" :class="flagOf(row).tone">{{ flagOf(row).text }}</span></div>
                  <small>{{ row.description || '暂无用例描述' }}</small>
                </div>
              </td>
              <td>
                <div class="project-tags"><span v-if="row.project_name">{{ row.project_name }}</span><em v-else>—</em></div>
              </td>
              <td><div class="meta-text"><b>{{ browserLabel(row.browser) }}</b><small>{{ row.run_mode === 'headed' ? '有界面' : '无头' }}</small></div></td>
              <td><span class="step-count"><PhFlowArrow />{{ row.step_count || 0 }} 步</span></td>
              <td><div class="run-cell"><i class="dot" :class="runStateOfRow(row).tone"></i><div><b :class="runStateOfRow(row).tone">{{ runStateOfRow(row).text }}</b><span>{{ runStateOfRow(row).hint }}</span></div></div></td>
              <td>
                <div v-if="metricOf(row)" class="rate-cell" :class="rateToneOf(row)"><div class="rate-top"><b>{{ metricOf(row).pass_rate }}%</b><span>近 {{ metricOf(row).sample_size }} 次</span></div><div class="rate-bar"><i :style="{ width: `${metricOf(row).pass_rate}%` }"></i></div></div>
                <div v-else class="rate-cell none"><div class="rate-top"><b>—</b><span>暂无数据</span></div></div>
              </td>
              <td><span class="creator"><i>{{ creatorInitial(row.creator_name) }}</i>{{ row.creator_name || '—' }}</span></td>
              <td>
                <div class="row-actions" @click.stop>
                  <button type="button" @click="editCase(row)">编辑</button>
                  <button type="button" @click="removeCase(row)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-show="viewMode === 'card'" class="case-cards">
          <article v-for="row in pagedCases" :key="row.id" class="case-card" :class="{ selected: drawerCase?.id === row.id }" @click="openDrawer(row)">
            <h3><span v-if="flagOf(row)" class="flag" :class="flagOf(row).tone">{{ flagOf(row).text }}</span><span class="card-title">{{ row.name }}</span></h3>
            <p class="card-desc">{{ row.description || '暂无用例描述' }}</p>
            <div v-if="metricOf(row)" class="rate-cell" :class="rateToneOf(row)"><div class="rate-top"><b>{{ metricOf(row).pass_rate }}%</b><span>通过率</span></div><div class="rate-bar"><i :style="{ width: `${metricOf(row).pass_rate}%` }"></i></div></div>
            <div v-else class="rate-cell none"><div class="rate-top"><b>—</b><span>暂无执行数据</span></div></div>
            <div class="card-meta">
              <span class="run-inline"><i class="dot" :class="runStateOfRow(row).tone"></i><b :class="runStateOfRow(row).tone">{{ runStateOfRow(row).text }}</b></span>
              <em>·</em><span><b>{{ row.step_count || 0 }}</b> 步</span>
              <em>·</em><span>{{ browserLabel(row.browser) }}</span>
              <em>·</em><span>{{ row.project_name || '未关联项目' }}</span>
            </div>
          </article>
        </div>

        <div v-if="loading" class="table-state"><n-spin size="small" />正在加载用例…</div>
        <n-empty v-else-if="!pagedCases.length" class="table-state" size="small" description="没有找到符合条件的用例" />

        <PaginationFooter
          v-model:page="page"
          v-model:page-size="pageSize"
          :total="displayCases.length"
          :page-sizes="[12, 24, 48]"
        />
      </section>
    </main>

    <div class="drawer-scrim" :class="{ open: Boolean(drawerCase) }" @click="closeDrawer"></div>
    <aside class="detail-drawer" :class="{ open: Boolean(drawerCase) }" :aria-hidden="!drawerCase">
      <template v-if="drawerCase">
        <header class="drawer-head">
          <div class="drawer-title"><h2>{{ drawerCase.name }}</h2><button type="button" class="drawer-close" aria-label="关闭" @click="closeDrawer"><PhX /></button></div>
          <div class="drawer-meta">
            <span><PhUser />{{ drawerCase.creator_name || '—' }}</span>
            <span><PhFlowArrow />{{ drawerCase.step_count || 0 }} 步</span>
            <span><PhMonitor />{{ browserLabel(drawerCase.browser) }} · {{ drawerCase.run_mode === 'headed' ? '有界面' : '无头' }}</span>
            <span><PhClock />{{ runStateOfRow(drawerCase).hint }}</span>
          </div>
          <div class="drawer-environment-control">
            <span>执行环境</span>
            <n-select v-model:value="drawerEnvironmentId" :options="drawerEnvironmentOptions" placeholder="请选择环境" />
          </div>
          <div class="drawer-actions">
            <n-button type="primary" size="small" :loading="runningId === drawerCase.id" :disabled="!drawerEnvironmentId" @click="runCase(drawerCase)"><template #icon><PhPlay weight="fill" /></template>立即执行</n-button>
            <n-button size="small" @click="editCase(drawerCase)"><template #icon><PhPencilSimple /></template>编辑用例</n-button>
          </div>
        </header>
        <div class="drawer-body">
          <section>
            <h4>步骤流程 <em>共 {{ previewSteps.length }} 步</em></h4>
            <div v-if="previewLoading" class="drawer-state"><n-spin size="small" />正在加载步骤…</div>
            <div v-else-if="previewSteps.length" class="flow-list">
              <div v-for="(step, index) in previewSteps" :key="step.id ?? index" class="flow-step">
                <span class="flow-index">{{ String(index + 1).padStart(2, '0') }}</span>
                <div class="flow-body">
                  <b>{{ stepLabel(step) }}</b>
                  <small>
                    <span class="method" :class="actionTone(step.action)">{{ step.action_name || step.action }}</span>
                    <span class="path">{{ step.value || '—' }}</span>
                    <span v-if="tabLabel(step.tab_key)" class="step-tab">{{ tabLabel(step.tab_key) }}</span>
                  </small>
                </div>
              </div>
            </div>
            <div v-else class="drawer-state"><PhFlowArrow />该用例还没有配置步骤</div>
          </section>
          <section>
            <h4>最近执行 <em>{{ drawerHistory.length ? `最近 ${drawerHistory.length} 次` : '暂无记录' }}</em></h4>
            <div v-if="drawerHistory.length" class="history-list">
              <div v-for="(item, index) in drawerHistory" :key="index" class="history-row">
                <i class="dot" :class="item.passed ? 'ok' : 'bad'"></i>
                <span class="history-name">{{ item.suite_name || '测试计划' }} · {{ item.executor }}</span>
                <span class="history-time">{{ relativeTime(item.finished_at) }}</span>
                <b :class="item.passed ? 'ok' : 'bad'">{{ item.passed ? '通过' : '失败' }}</b>
              </div>
            </div>
            <p v-else class="drawer-empty">该用例尚未被测试计划执行过。列表中的通过率与最近执行都依赖计划运行结果，即席试跑不落库、不计入统计。</p>
          </section>
        </div>
      </template>
    </aside>
  </div>
</template>

<script lang="ts" setup>
import { asList } from '@/utils/list';

import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useMessage } from 'naive-ui';
import {
  PhArrowsClockwise, PhCheckCircle, PhClock, PhDotsNine, PhFlowArrow, PhInfo, PhListBullets,
  PhMagnifyingGlass, PhMonitor, PhPencilSimple, PhPlay, PhPlus, PhStack, PhUser, PhWarning, PhX,
} from '@phosphor-icons/vue';
import { UiCaseAPI, UiStepAPI } from '@/api/case_ui/http';
import { EMPTY_OVERVIEW_STATS, normalizeOverview, type CaseOverview } from '@/api/case_overview';
import { EnvironmentAPI, ProjectAPI } from '@/api/project/http';
import {
  actionTone, applyStatusFilter, buildProjectEntries, creatorInitial, filterProjects,
  environmentOptionsForProject, filterRows, rateTone, relativeTime, runStateOf, statusFlagOf, statusOptionsOf, weekDeltaOf,
  type StatusKey,
} from '@/views/case_shared/catalog';
import PaginationFooter from '@/components/PaginationFooter/index.vue';

const router = useRouter();
const message = useMessage();
const api = new UiCaseAPI();
const stepApi = new UiStepAPI();
const projectApi = new ProjectAPI();
const environmentApi = new EnvironmentAPI();

const cases = ref<any[]>([]);
const projects = ref<any[]>([]);
const environments = ref<any[]>([]);
const overview = ref<CaseOverview>({ stats: EMPTY_OVERVIEW_STATS(), items: {} });
const loading = ref(false);
const previewLoading = ref(false);
const previewSteps = ref<any[]>([]);
const drawerCase = ref<any>(null);
const drawerEnvironmentId = ref<number | null>(null);
const runningId = ref<number | null>(null);

const projectKeyword = ref('');
const searchName = ref('');
const selectedProject = ref<number | null>(null);
const statusFilter = ref<StatusKey>('all');
const viewMode = ref<'list' | 'card'>('card');
const page = ref(1);
const pageSize = ref(12);

/** 浏览器取值是后端枚举，这里只做展示名映射。 */
const BROWSER_LABELS: Record<string, string> = {
  chrome: 'Chrome', chromium: 'Chromium', firefox: 'Firefox', webkit: 'WebKit', edge: 'Edge',
};
function browserLabel(value?: string) { return BROWSER_LABELS[String(value || '').toLowerCase()] || value || '—'; }

const metricOf = (row: any) => overview.value.items[String(row.id)] || null;
const flagOf = (row: any) => statusFlagOf(row, metricOf(row));
const runStateOfRow = (row: any) => runStateOf(metricOf(row), { createdAt: row.create_datetime });
const rateToneOf = (row: any) => rateTone(metricOf(row)?.pass_rate);
const drawerHistory = computed(() => metricOf(drawerCase.value)?.history || []);
const drawerEnvironmentOptions = computed(() => environmentOptionsForProject(environments.value, drawerCase.value?.project));

const baseCases = computed(() => filterRows(cases.value, {
  projectId: selectedProject.value,
  keyword: searchName.value,
  projectIdsOf: (row: any) => [row.project],
  textOf: (row: any) => `${row.name || ''} ${row.description || ''}`,
}));
const statusOptions = computed(() => statusOptionsOf(baseCases.value, metricOf));
const displayCases = computed(() => applyStatusFilter(baseCases.value, statusFilter.value, metricOf));
const pageCount = computed(() => Math.max(1, Math.ceil(displayCases.value.length / pageSize.value)));
const pagedCases = computed(() => displayCases.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value));
const weekDelta = computed(() => weekDeltaOf(overview.value.stats));

const projectEntries = computed(() => buildProjectEntries(cases.value, projects.value, (row: any) => [row.project]));
const visibleProjects = computed(() => filterProjects(projectEntries.value, projectKeyword.value));

/** 步骤所属页签的展示名。用例只有一个页签时不显示，避免每行挂一个无信息量的标签。 */
const tabLabels = computed<Record<string, string>>(() => {
  const tabs = drawerCase.value?.tabs;
  if (!Array.isArray(tabs) || tabs.length < 2) return {};
  return Object.fromEntries(tabs.filter((tab: any) => tab?.key).map((tab: any) => [String(tab.key), String(tab.name || tab.key)]));
});
function tabLabel(key?: string) { return tabLabels.value[String(key || '')] || ''; }

/** 步骤主语：优先页面元素，其次操作名（goto / sleep 这类没有元素）。 */
function stepLabel(step: any) { return step.element_name || step.action_name || step.action || '未命名步骤'; }

function selectProject(id: number | null) { selectedProject.value = id; page.value = 1; }
function createCase() { router.push({ name: 'case_ui_case_edit', params: { id: 0 } }); }
function editCase(row: any) { router.push({ name: 'case_ui_case_edit', params: { id: row.id } }); }
function openDrawer(row: any) {
  drawerCase.value = row;
  const options = environmentOptionsForProject(environments.value, row.project);
  drawerEnvironmentId.value = options.find((option) => option.label === row.environment_name)?.value || options[0]?.value || null;
  void loadPreview(row.id);
}
function closeDrawer() { drawerCase.value = null; drawerEnvironmentId.value = null; previewSteps.value = []; }

async function loadPreview(caseId: number) {
  previewLoading.value = true;
  try {
    const response: any = await stepApi.getDataList({ ui_case: caseId, pageSize: 999 });
    previewSteps.value = asList(response).sort((a: any, b: any) => Number(a.order || 0) - Number(b.order || 0));
  } catch (error: any) {
    previewSteps.value = [];
    message.error(error?.message || '步骤加载失败');
  } finally {
    previewLoading.value = false;
  }
}

async function runCase(row: any) {
  if (!row?.id || !drawerEnvironmentId.value) return message.warning('请选择执行环境');
  runningId.value = Number(row.id);
  try {
    const result: any = await api.run(Number(row.id), drawerEnvironmentId.value);
    if (result?.passed) message.success(`「${row.name}」执行通过`);
    else message.error(result?.error || `「${row.name}」执行未通过`);
  } catch (error: any) {
    message.error(error?.message || '执行失败');
  } finally {
    runningId.value = null;
  }
}

async function removeCase(row: any) {
  try {
    await api.DeleteDataByID(row.id);
    cases.value = cases.value.filter((item) => Number(item.id) !== Number(row.id));
    if (Number(drawerCase.value?.id) === Number(row.id)) closeDrawer();
    message.success('用例已删除');
  } catch (error: any) {
    message.error(error?.message || '删除用例失败');
  }
}

async function load() {
  loading.value = true;
  try {
    const [caseResponse, projectResponse, environmentResponse, overviewResponse]: any[] = await Promise.all([
      api.getDataList({ page: 1, pageSize: 999 }),
      projectApi.getDataList({ page: 1, pageSize: 1000 }),
      environmentApi.getDataList({ page: 1, pageSize: 999 }),
      api.overview(),
    ]);
    cases.value = asList(caseResponse);
    projects.value = asList(projectResponse);
    environments.value = asList(environmentResponse);
    overview.value = normalizeOverview(overviewResponse);
  } catch (error: any) {
    message.error(error?.message || '用例列表加载失败');
  } finally {
    loading.value = false;
  }
}

watch(displayCases, () => { if (page.value > pageCount.value) page.value = pageCount.value; });
watch([selectedProject, searchName, statusFilter, pageSize], () => { page.value = 1; });
onMounted(load);
</script>

<style scoped>
/* 版式来自全局 styles/case-catalog.less，本页 scoped 里只放列宽。
   列宽必须合计 100%：table-layout:fixed 下超出部分会被浏览器按比例压缩。

   隐藏列必须同时隐藏 col 与 th/td：只写 col 会让它退出宽度分配，后续 col 整体
   前移一格，表头与列宽错位（末列会塌成 0 宽度，操作按钮直接看不见）。 */
.case-table .c1 { width: 24%; }
.case-table .c2 { width: 13%; }
.case-table .c3 { width: 10%; }
.case-table .c4 { width: 8%; }
.case-table .c5 { width: 12%; }
.case-table .c6 { width: 11%; }
.case-table .c7 { width: 10%; }
.case-table .c8 { width: 12%; }

/* ≤1240：隐藏「所属项目」「创建人」。剩余 c1/c3/c4/c5/c6/c8 合计 100%。 */
@media (max-width: 1240px) {
  .case-table col.c2, .case-table th:nth-child(2), .case-table td:nth-child(2),
  .case-table col.c7, .case-table th:nth-child(7), .case-table td:nth-child(7) { display: none; }
  .case-table .c1 { width: 31%; }
  .case-table .c3 { width: 13%; }
  .case-table .c4 { width: 10%; }
  .case-table .c5 { width: 16%; }
  .case-table .c6 { width: 14%; }
  .case-table .c8 { width: 16%; }
}

/* ≤1050：再隐藏「浏览器 / 模式」。剩余 c1/c4/c5/c6/c8 合计 100%。 */
@media (max-width: 1050px) {
  .case-table col.c3, .case-table th:nth-child(3), .case-table td:nth-child(3) { display: none; }
  .case-table .c1 { width: 34%; }
  .case-table .c4 { width: 10%; }
  .case-table .c5 { width: 20%; }
  .case-table .c6 { width: 16%; }
  .case-table .c8 { width: 20%; }
}
</style>
