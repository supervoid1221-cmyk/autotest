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
      <p class="project-hint"><PhInfo />跨项目场景可在多个项目下查看</p>
    </aside>

    <main class="catalog-main">
      <header class="page-heading">
        <div><div class="breadcrumb"><span>API 测试</span><i>/</i><span>场景管理</span></div><div class="title-line"><h1>场景管理</h1><p>组织业务流程，维护可复用的接口场景</p></div></div>
        <n-button type="primary" class="create-button" @click="createScenario"><template #icon><PhPlus /></template>新建场景</n-button>
      </header>

      <section class="kpi-row">
        <article class="kpi">
          <div class="kpi-top"><PhStack />场景总数</div>
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
          <div class="kpi-foot">{{ overview.stats.covered }} 个场景有执行数据 · 样本 {{ overview.stats.sample_size }} 次</div>
        </article>
        <article class="kpi" :class="{ alert: overview.stats.abnormal > 0 }">
          <div class="kpi-top"><PhWarning />待处理异常</div>
          <div class="kpi-val num">{{ overview.stats.abnormal }}</div>
          <div class="kpi-foot">连续失败 ≥ 2 次 · 需人工介入</div>
        </article>
      </section>

      <div class="table-toolbar">
        <n-input v-model:value="searchName" clearable placeholder="搜索场景名称或描述" aria-label="搜索场景" class="search-input"><template #prefix><PhMagnifyingGlass /></template></n-input>
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
          <colgroup><col class="c1" /><col class="c2" /><col class="c3" /><col class="c4" /><col class="c5" /><col class="c6" /><col class="c7" /></colgroup>
          <thead><tr><th>场景名称</th><th>关联项目</th><th>步骤</th><th>最近执行</th><th>通过率</th><th>创建人</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="row in pagedScenarios" :key="row.id" :class="{ selected: drawerScenario?.id === row.id }" @click="openDrawer(row)">
              <td>
                <div class="case-name">
                  <div class="name-line"><strong>{{ row.name }}</strong><span v-if="flagOf(row)" class="flag" :class="{ new: !metricOf(row) }">{{ flagOf(row) }}</span></div>
                  <small>{{ row.description || '暂无场景描述' }}</small>
                </div>
              </td>
              <td>
                <div class="project-tags">
                  <template v-if="scenarioProjectNames(row).length">
                    <span v-for="name in scenarioProjectNames(row).slice(0, 2)" :key="name">{{ name }}</span>
                    <span v-if="scenarioProjectNames(row).length > 2" class="more">+{{ scenarioProjectNames(row).length - 2 }}</span>
                  </template>
                  <em v-else>—</em>
                </div>
              </td>
              <td><span class="step-count"><PhFlowArrow />{{ row.step_count || 0 }} 步</span></td>
              <td><div class="run-cell"><i class="dot" :class="runStateOf(row).tone"></i><div><b :class="runStateOf(row).tone">{{ runStateOf(row).text }}</b><span>{{ runStateOf(row).hint }}</span></div></div></td>
              <td><div v-if="metricOf(row)" class="rate-cell" :class="rateTone(metricOf(row).pass_rate)"><div class="rate-top"><b>{{ metricOf(row).pass_rate }}%</b><span>近 {{ metricOf(row).sample_size }} 次</span></div><div class="rate-bar"><i :style="{ width: `${metricOf(row).pass_rate}%` }"></i></div></div><div v-else class="rate-cell none"><div class="rate-top"><b>—</b><span>暂无数据</span></div></div></td>
              <td><span class="creator"><i>{{ creatorInitial(row.creator_name) }}</i>{{ row.creator_name || '—' }}</span></td>
              <td>
                <div class="row-actions" @click.stop>
                  <n-dropdown trigger="click" :options="environmentOptions(row)" :disabled="!environmentOptions(row).length" @select="(key: string) => runScenario(row, Number(key))">
                    <button type="button" class="run-button" :disabled="runningId === row.id">
                      <n-spin v-if="runningId === row.id" :size="12" /><PhPlay v-else weight="fill" />{{ runningId === row.id ? '执行中' : '执行' }}
                    </button>
                  </n-dropdown>
                  <button type="button" @click="editScenario(row)">编辑</button>
                  <n-dropdown trigger="click" :options="actionOptions" @select="(key: string) => handleAction(key, row)"><button type="button" class="more-button" aria-label="更多操作"><PhDotsThree weight="bold" /></button></n-dropdown>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-show="viewMode === 'card'" class="case-cards">
          <article v-for="row in pagedScenarios" :key="row.id" class="case-card" :class="{ selected: drawerScenario?.id === row.id }" @click="openDrawer(row)">
            <h3><span v-if="flagOf(row)" class="flag" :class="{ new: !metricOf(row) }">{{ flagOf(row) }}</span><span class="card-title">{{ row.name }}</span></h3>
            <p class="card-desc">{{ row.description || '暂无场景描述' }}</p>
            <div v-if="metricOf(row)" class="rate-cell" :class="rateTone(metricOf(row).pass_rate)"><div class="rate-top"><b>{{ metricOf(row).pass_rate }}%</b><span>通过率</span></div><div class="rate-bar"><i :style="{ width: `${metricOf(row).pass_rate}%` }"></i></div></div>
            <div v-else class="rate-cell none"><div class="rate-top"><b>—</b><span>暂无执行数据</span></div></div>
            <div class="card-meta">
              <span class="run-inline"><i class="dot" :class="runStateOf(row).tone"></i><b :class="runStateOf(row).tone">{{ runStateOf(row).text }}</b></span>
              <em>·</em><span><b>{{ row.step_count || 0 }}</b> 步</span>
              <em>·</em><span>{{ scenarioProjectNames(row)[0] || '未关联' }}<template v-if="scenarioProjectNames(row).length > 1"> +{{ scenarioProjectNames(row).length - 1 }}</template></span>
            </div>
          </article>
        </div>

        <div v-if="loading" class="table-state"><n-spin size="small" />正在加载场景…</div>
        <n-empty v-else-if="!pagedScenarios.length" class="table-state" size="small" description="没有找到符合条件的场景" />

        <PaginationFooter
          v-model:page="page"
          v-model:page-size="pageSize"
          :total="displayScenarios.length"
          :page-sizes="[12, 24, 48]"
        />
      </section>
    </main>

    <div class="drawer-scrim" :class="{ open: Boolean(drawerScenario) }" @click="closeDrawer"></div>
    <aside class="detail-drawer" :class="{ open: Boolean(drawerScenario) }" :aria-hidden="!drawerScenario">
      <template v-if="drawerScenario">
        <header class="drawer-head">
          <div class="drawer-title"><h2>{{ drawerScenario.name }}</h2><button type="button" class="drawer-close" aria-label="关闭" @click="closeDrawer"><PhX /></button></div>
          <div class="drawer-meta">
            <span><PhUser />{{ drawerScenario.creator_name || '—' }}</span>
            <span><PhFlowArrow />{{ drawerScenario.step_count || 0 }} 步</span>
            <span><PhClock />{{ runStateOf(drawerScenario).hint }}</span>
          </div>
          <div class="drawer-environment-control">
            <span>执行环境</span>
            <n-select v-model:value="drawerEnvironmentId" :options="drawerEnvironmentOptions" placeholder="请选择环境" />
          </div>
          <div class="drawer-actions">
            <n-button type="primary" size="small" :loading="runningId === drawerScenario.id" :disabled="!drawerEnvironmentId" @click="runScenarioImmediately(drawerScenario)"><template #icon><PhPlay weight="fill" /></template>立即执行</n-button>
            <n-button size="small" @click="editScenario(drawerScenario)"><template #icon><PhPencilSimple /></template>编辑场景</n-button>
          </div>
        </header>
        <div class="drawer-body">
          <section>
            <h4>步骤流程 <em>主流程 {{ drawerScenario.step_count || 0 }} 步</em></h4>
            <div v-if="previewLoading" class="drawer-state"><n-spin size="small" />正在加载流程…</div>
            <div v-else-if="previewSteps.length" class="flow-list">
              <div v-for="(step, index) in previewSteps" :key="step.id" class="flow-step" :class="{ condition: step.type === 'condition' }">
                <span class="flow-index">{{ String(index + 1).padStart(2, '0') }}</span>
                <div class="flow-body">
                  <b>{{ step.name }}</b>
                  <small v-if="step.type === 'condition'"><span class="method put">分支</span><span class="path">条件判断</span></small>
                  <small v-else><span class="method" :class="step.method.toLowerCase()">{{ step.method }}</span><span class="path">{{ step.path || '—' }}</span></small>
                </div>
              </div>
            </div>
            <div v-else class="drawer-state"><PhFlowArrow />该场景暂无流程步骤</div>
          </section>
          <section>
            <h4>最近执行 <em>{{ metricOf(drawerScenario)?.history.length ? `最近 ${metricOf(drawerScenario)?.history.length} 次` : '暂无记录' }}</em></h4>
            <div v-if="metricOf(drawerScenario)?.history.length" class="history-list">
              <div v-for="(item, index) in metricOf(drawerScenario)?.history" :key="index" class="history-row">
                <i class="dot" :class="item.passed ? 'ok' : 'bad'"></i>
                <span class="history-name">{{ item.suite_name || '测试计划' }} · {{ item.executor }}</span>
                <span class="history-time">{{ relativeTime(item.finished_at) }}</span>
                <b :class="item.passed ? 'ok' : 'bad'">{{ item.passed ? '通过' : '失败' }}</b>
              </div>
            </div>
            <p v-else class="drawer-empty">该场景尚未被测试计划执行过，列表中的通过率与最近执行依赖计划运行结果。</p>
          </section>
        </div>
      </template>
    </aside>
  </div>
</template>

<script lang="ts" setup>
import { asList } from '@/utils/list';

import { computed, h, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { NIcon, useMessage } from 'naive-ui';
import { PhArrowsClockwise, PhCheckCircle, PhClock, PhDotsNine, PhDotsThree, PhFlowArrow, PhInfo, PhListBullets, PhMagnifyingGlass, PhPencilSimple, PhPlay, PhPlus, PhStack, PhTrash, PhUser, PhWarning, PhX } from '@phosphor-icons/vue';
import { ScenarioAPI, ScenarioFlowNodeAPI, type ScenarioOverview } from '@/api/case_api/http';
import { EMPTY_OVERVIEW_STATS, normalizeOverview } from '@/api/case_overview';
import { EnvironmentAPI, ProjectAPI } from '@/api/project/http';
import PaginationFooter from '@/components/PaginationFooter/index.vue';

const router = useRouter(); const message = useMessage();
const api = new ScenarioAPI(); const flowNodeApi = new ScenarioFlowNodeAPI(); const projectApi = new ProjectAPI(); const environmentApi = new EnvironmentAPI();

const scenarios = ref<any[]>([]); const projects = ref<any[]>([]); const environments = ref<any[]>([]);
const loading = ref(false); const previewLoading = ref(false); const projectKeyword = ref(''); const searchName = ref('');
const selectedProject = ref<number | null>(null); const previewNodes = ref<any[]>([]); const page = ref(1); const pageSize = ref(12);
const viewMode = ref<'list' | 'card'>('card'); const statusFilter = ref<'all' | 'ok' | 'bad' | 'none'>('all');
const drawerScenario = ref<any>(null); const runningId = ref<number | null>(null);
const drawerEnvironmentId = ref<number | null>(null);

const overview = ref<ScenarioOverview>({ stats: EMPTY_OVERVIEW_STATS(), items: {} });

const PROJECT_COLORS = ['#0f7b45', '#2563b8', '#b8790a', '#c1384a', '#6b45b5', '#00727b', '#8a99a8'];

const scenarioProjectIds = (row: any): number[] => Array.from(new Set([...(row.projects || []), row.project].filter(Boolean).map(Number)));
const scenarioProjectNames = (row: any): string[] => row.project_names?.length ? Array.from(new Set(row.project_names)) : scenarioProjectIds(row).map((id) => projects.value.find((project) => Number(project.id) === id)?.name).filter(Boolean);

const metricOf = (row: any) => overview.value.items[String(row.id)] || null;
const hasRun = (row: any) => Boolean(metricOf(row));
const isPass = (row: any) => Boolean(metricOf(row)?.last_passed);
const rateTone = (rate: number | null | undefined) => rate === null || rate === undefined ? 'none' : rate >= 95 ? 'good' : rate >= 80 ? 'warn' : 'bad';

/** 项目 + 关键词筛选，状态筛选在其之上叠加。 */
const baseScenarios = computed(() => {
  const keyword = searchName.value.trim().toLowerCase();
  return scenarios.value.filter((row) => (selectedProject.value === null || scenarioProjectIds(row).includes(Number(selectedProject.value))) && (!keyword || `${row.name || ''} ${row.description || ''}`.toLowerCase().includes(keyword)));
});
const statusOptions = computed(() => {
  const rows = baseScenarios.value;
  return [
    { key: 'all' as const, label: '全部', count: rows.length },
    { key: 'ok' as const, label: '通过', count: rows.filter(isPass).length },
    { key: 'bad' as const, label: '失败', count: rows.filter((row) => hasRun(row) && !isPass(row)).length },
    { key: 'none' as const, label: '未执行', count: rows.filter((row) => !hasRun(row)).length },
  ];
});
const displayScenarios = computed(() => {
  const rows = baseScenarios.value;
  if (statusFilter.value === 'ok') return rows.filter(isPass);
  if (statusFilter.value === 'bad') return rows.filter((row) => hasRun(row) && !isPass(row));
  if (statusFilter.value === 'none') return rows.filter((row) => !hasRun(row));
  return rows;
});
const pageCount = computed(() => Math.max(1, Math.ceil(displayScenarios.value.length / pageSize.value)));
const pagedScenarios = computed(() => displayScenarios.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value));
const weekDelta = computed(() => {
  const { runs_this_week: current, runs_last_week: previous } = overview.value.stats;
  if (!previous) return null;
  return Math.round((current - previous) / previous * 1000) / 10;
});
const projectEntries = computed(() => [
  { id: null as number | null, name: '全部项目', count: scenarios.value.length, color: '#008b95' },
  ...projects.value.map((project: any, index: number) => ({
    id: Number(project.id),
    name: project.name,
    count: scenarios.value.filter((row) => scenarioProjectIds(row).includes(Number(project.id))).length,
    color: PROJECT_COLORS[index % PROJECT_COLORS.length],
  })),
]);
const visibleProjects = computed(() => { const keyword = projectKeyword.value.trim().toLowerCase(); return projectEntries.value.filter((item) => item.id === null || !keyword || item.name.toLowerCase().includes(keyword)); });
const drawerEnvironmentOptions = computed(() => drawerScenario.value
  ? environmentOptions(drawerScenario.value).map((item) => ({ label: item.label, value: Number(item.key) }))
  : []);

const allPreviewSteps = computed(() => previewNodes.value.map((node) => {
  if (node.node_type === 'condition') return { id: `condition-${node.id}`, type: 'condition', method: '', name: node.name || '判断分支', path: '' };
  const step = node.step_info || {}; const endpoint = step.endpoint_info || {};
  return {
    id: `endpoint-${node.id}`,
    type: 'endpoint',
    method: String(step.request_method || endpoint.method || 'GET').toUpperCase(),
    name: step.name || step.endpoint_name || endpoint.name || '未命名接口',
    path: step.request_url || endpoint.url || endpoint.path || '',
  };
}));
const previewSteps = computed(() => allPreviewSteps.value.slice(0, 12));

const actionOptions = [{ label: '删除场景', key: 'delete', icon: () => h(NIcon, null, { default: () => h(PhTrash) }) }];

function creatorInitial(name?: string) { return String(name || '?').trim().slice(0, 1).toUpperCase(); }

function relativeTime(value?: string | null) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const diff = Date.now() - date.getTime(); const pad = (n: number) => String(n).padStart(2, '0');
  if (diff < 0) return '刚刚';
  if (diff < 60_000) return '刚刚';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`;
  if (diff < 172_800_000) return `昨天 ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  if (diff < 2_592_000_000) return `${Math.floor(diff / 86_400_000)} 天前`;
  return `${date.getMonth() + 1} 月 ${date.getDate()} 日`;
}

/** 行状态徽标：本地正在执行优先，其次取计划执行结果，都没有则视为从未执行。 */
function runStateOf(row: any) {
  if (runningId.value === Number(row.id)) return { tone: 'run', text: '执行中', hint: '刚刚触发' };
  const metric = metricOf(row);
  if (!metric) return { tone: 'idle', text: '从未执行', hint: `创建于 ${relativeTime(row.created_at)}` };
  return { tone: metric.last_passed ? 'ok' : 'bad', text: metric.last_passed ? '成功' : '失败', hint: relativeTime(metric.last_finished_at) };
}
function flagOf(row: any) {
  const metric = metricOf(row);
  if (!metric) return '新建';
  if (metric.consecutive_failures >= 2) return `连续失败 ${metric.consecutive_failures} 次`;
  return '';
}
/** 场景执行需要指定环境；环境下拉同时承担「该项目是否配好环境」的提示。 */
function environmentOptions(row: any) {
  const ids = scenarioProjectIds(row);
  const scopedEnvironments = environments.value.filter((env: any) => ids.includes(Number(env.project)));
  const names = Array.from(new Set(scopedEnvironments.map((env: any) => String(env.name || '').trim()).filter(Boolean)));
  return names
    .filter((name) => ids.every((projectId) => scopedEnvironments.some((env: any) => Number(env.project) === projectId && String(env.name || '').trim() === name)))
    .map((name) => {
      const environment = scopedEnvironments.find((env: any) => String(env.name || '').trim() === name);
      return { label: name, key: String(environment.id) };
    });
}

function runScenarioImmediately(row: any) {
  if (!drawerEnvironmentId.value) {
    message.warning('当前场景关联项目暂无可用执行环境');
    return;
  }
  void runScenario(row, drawerEnvironmentId.value);
}

function createScenario() { router.push({ name: 'case_api_scenario_edit', params: { id: 0 } }); }
function editScenario(row: any) { router.push({ name: 'case_api_scenario_edit', params: { id: row.id } }); }
function selectProject(id: number | null) { selectedProject.value = id; page.value = 1; }
function openDrawer(row: any) {
  drawerScenario.value = row;
  drawerEnvironmentId.value = Number(environmentOptions(row)[0]?.key) || null;
  void loadPreview(row.id);
  void refreshOverview();
}
function closeDrawer() { drawerScenario.value = null; drawerEnvironmentId.value = null; previewNodes.value = []; }

async function loadPreview(scenarioId: number) {
  previewLoading.value = true;
  try {
    const response: any = await flowNodeApi.getDataList({ scenario: scenarioId, main: true, pageSize: 999 });
    previewNodes.value = asList(response).sort((a: any, b: any) => Number(a.order || 0) - Number(b.order || 0));
  } catch (error: any) { previewNodes.value = []; message.error(error?.message || '流程步骤加载失败'); }
  finally { previewLoading.value = false; }
}

async function refreshOverview() {
  try {
    overview.value = normalizeOverview(await api.overview());
  } catch (error: any) {
    message.error(error?.message || '最近执行记录加载失败');
  }
}

async function runScenario(row: any, environmentId: number) {
  if (!row || !environmentId) return;
  runningId.value = Number(row.id);
  try {
    const result: any = await api.runById(Number(row.id), environmentId);
    // 即席执行是同步试跑且后端不落库，因此这里不刷新 overview —— 列表里的
    // 「最近执行 / 通过率」只反映场景被测试计划执行的结果。
    if (result?.passed) message.success(`「${row.name}」执行通过`);
    else message.error((result?.errors || []).join('；') || `「${row.name}」存在失败接口`);
  } catch (error: any) { message.error(error?.message || '场景执行失败'); }
  finally { runningId.value = null; }
}

async function handleAction(key: string, row: any) {
  if (key !== 'delete') return;
  try {
    await api.DeleteDataByID(row.id);
    scenarios.value = scenarios.value.filter((item) => Number(item.id) !== Number(row.id));
    if (Number(drawerScenario.value?.id) === Number(row.id)) closeDrawer();
    message.success('场景已删除');
  } catch (error: any) { message.error(error?.message || '删除场景失败'); }
}

async function load() {
  loading.value = true;
  try {
    const [scenarioResponse, projectResponse, environmentResponse, overviewResponse]: any[] = await Promise.all([
      api.getDataList({ page: 1, pageSize: 999 }),
      projectApi.getDataList({ page: 1, pageSize: 1000 }),
      environmentApi.getDataList({ page: 1, pageSize: 999 }),
      api.overview(),
    ]);
    scenarios.value = asList(scenarioResponse);
    projects.value = asList(projectResponse);
    environments.value = asList(environmentResponse);
    overview.value = normalizeOverview(overviewResponse);
  } catch (error: any) { message.error(error?.message || '场景列表加载失败'); }
  finally { loading.value = false; }
}

watch(displayScenarios, () => { if (page.value > pageCount.value) page.value = pageCount.value; });
watch([selectedProject, searchName, statusFilter, pageSize], () => { page.value = 1; });
onMounted(load);
</script>

<style scoped>
/* 版式来自全局 styles/case-catalog.less，本页 scoped 里只放列宽。
   列宽必须合计 100%：table-layout:fixed 下超出部分会被浏览器按比例压缩，
   列宽就与设计意图不符了。

   隐藏列必须同时隐藏 col 与 th/td：只写 col 会让它退出宽度分配，后续 col 整体
   前移一格，表头与列宽错位（末列会塌成 0 宽度，操作按钮直接看不见）。 */
.case-table .c1 { width: 23%; }
.case-table .c2 { width: 15%; }
.case-table .c3 { width: 8%; }
.case-table .c4 { width: 14%; }
.case-table .c5 { width: 12%; }
.case-table .c6 { width: 11%; }
.case-table .c7 { width: 17%; }

/* ≤1240：隐藏「关联项目」。剩余 c1/c3/c4/c5/c6/c7 合计 100%。 */
@media (max-width: 1240px) {
  .case-table col.c2,
  .case-table th:nth-child(2),
  .case-table td:nth-child(2) { display: none; }
  .case-table .c1 { width: 28%; }
  .case-table .c3 { width: 9%; }
  .case-table .c4 { width: 15%; }
  .case-table .c5 { width: 13%; }
  .case-table .c6 { width: 20%; }
  .case-table .c7 { width: 15%; }
}

/* ≤1050：再隐藏「创建人」。剩余 c1/c3/c4/c5/c7 合计 100%。 */
@media (max-width: 1050px) {
  .case-table col.c6,
  .case-table th:nth-child(6),
  .case-table td:nth-child(6) { display: none; }
  .case-table .c1 { width: 34%; }
  .case-table .c3 { width: 12%; }
  .case-table .c4 { width: 20%; }
  .case-table .c5 { width: 16%; }
  .case-table .c7 { width: 18%; }
}
</style>
