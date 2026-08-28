<template>
  <div class="console-page">
    <header class="page-head">
      <div>
        <h1>主控台</h1>
        <p>项目质量与自动化执行概览</p>
      </div>
      <div class="page-actions">
        <n-select v-model:value="selectedProjectId" :options="projectOptions" class="project-filter" @update:value="applyProjectFilter" />
        <n-button :loading="loading" @click="loadDashboard"><template #icon><n-icon><PhArrowClockwise /></n-icon></template>刷新数据</n-button>
      </div>
    </header>

    <section class="ai-strip">
      <div><n-icon size="19"><PhSparkle /></n-icon><span>AI 助手已就绪，可帮助生成测试用例、分析失败原因、优化接口参数</span></div>
      <n-button size="small" @click="openAiChat">开始对话</n-button>
    </section>

    <section class="stats-grid">
      <article class="metric-card">
        <span class="metric-icon"><n-icon><PhFolderSimple /></n-icon></span>
        <div><p>项目总数</p><strong>{{ visibleProjects.length }}</strong><small>{{ activeProjectCount }} 个项目运行中</small></div>
      </article>
      <article class="metric-card">
        <span class="metric-icon"><n-icon><PhPlugsConnected /></n-icon></span>
        <div><p>接口总数</p><strong>{{ visibleEndpointCount }}</strong><small>覆盖 {{ visibleScenarioCount }} 个业务场景</small></div>
      </article>
      <article class="metric-card">
        <span class="metric-icon"><n-icon><PhStack /></n-icon></span>
        <div><p>场景总数</p><strong>{{ visibleScenarioCount }}</strong><small>{{ visibleUpcomingRuns.length }} 个套件即将执行</small></div>
      </article>
      <article class="metric-card pass-metric">
        <span class="metric-icon success"><n-icon><PhShieldCheck /></n-icon></span>
        <div><p>整体通过率</p><strong>{{ overallPassRate }}%</strong><small>最近执行 {{ completedRunCount }} 次</small></div>
        <div class="pass-ring" :style="{ '--pass-rate': overallPassRate + '%' }"><span>{{ overallPassRate }}%</span></div>
      </article>
    </section>

    <section class="main-grid">
      <article class="panel quality-panel">
        <header class="panel-head">
          <div><h2>项目质量概览</h2><span>共 {{ visibleProjects.length }} 个项目</span></div>
          <button type="button" class="text-link" @click="goProjectList">查看全部 <n-icon><PhArrowRight /></n-icon></button>
        </header>
        <div class="table-scroll">
          <n-spin :show="loading">
            <table v-if="visibleProjects.length" class="quality-table">
              <thead><tr><th>项目</th><th>接口 / 场景</th><th>自动化覆盖率</th><th>通过率</th><th>最后执行</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="item in visibleProjects" :key="item.id" @click="goProject(item)">
                  <td><div class="project-name"><span class="project-avatar" :style="{ background: avatarColor(item) }">{{ (item.name || '?').charAt(0) }}</span><strong>{{ item.name }}</strong></div></td>
                  <td>{{ item.endpoint_count }} / {{ item.scenario_count }}</td>
                  <td><div class="progress-cell"><span>{{ item.coverage }}%</span><i><b :style="{ width: item.coverage + '%' }"></b></i></div></td>
                  <td><div class="progress-cell pass"><span>{{ item.pass_rate }}%</span><i><b :class="rateTone(item.pass_rate)" :style="{ width: item.pass_rate + '%' }"></b></i></div></td>
                  <td>{{ item.last_run || '-' }}</td>
                  <td><span class="quality-status" :class="item.quality.tone">{{ item.quality.label }}</span></td>
                </tr>
              </tbody>
            </table>
            <div v-else-if="!loading" class="empty-block">暂无项目数据</div>
          </n-spin>
        </div>
      </article>

      <article class="panel activity-panel">
        <header class="panel-head"><div><h2>执行动态</h2></div></header>
        <div class="activity-summary">
          <div><span>今日执行</span><strong>{{ todayRuns.length }}</strong></div>
          <div><span>通过</span><strong class="success-text">{{ todayPassed }}</strong></div>
          <div><span>失败</span><strong class="danger-text">{{ todayFailed }}</strong></div>
        </div>
        <div class="activity-title"><strong>最新动态</strong><button type="button" class="text-link" @click="goRunResults">查看执行结果 <n-icon><PhArrowRight /></n-icon></button></div>
        <div v-if="visibleRecentRuns.length" class="activity-list">
          <div v-for="item in visibleRecentRuns.slice(0, 5)" :key="item.id" class="activity-row">
            <span class="status-dot" :class="item.result"></span>
            <span class="activity-name">{{ item.project }} · {{ item.suite }}</span>
            <span class="status-tag" :class="item.result">{{ item.statusLabel }}</span>
            <time>{{ item.time }}</time>
          </div>
        </div>
        <div v-else class="activity-empty">暂无执行动态</div>
        <div class="trend-row"><span>失败趋势（近 7 天）</span><svg viewBox="0 0 120 24" aria-hidden="true"><polyline points="0,17 16,9 32,14 48,6 64,11 80,7 96,15 120,10" /></svg><strong>{{ failedRunCount }} 次</strong></div>
      </article>
    </section>

    <section class="bottom-grid">
      <article class="panel list-panel">
        <header class="panel-head"><div><h2>最近执行</h2></div></header>
        <div class="compact-table-head run-columns"><span>项目 / 套件</span><span>环境</span><span>状态</span><span>耗时</span><span>时间</span></div>
        <div v-if="visibleRecentRuns.length" class="compact-list">
          <button v-for="item in visibleRecentRuns.slice(0, 4)" :key="item.id" type="button" class="compact-row run-columns" @click="openReport(item)">
            <strong>{{ item.project }} / {{ item.suite }}</strong><span class="env-tag">{{ item.environment }}</span><span class="status-tag" :class="item.result">{{ item.statusLabel }}</span><span>{{ item.duration }}</span><time>{{ item.dateTime }}</time>
          </button>
        </div>
        <div v-else class="empty-block">暂无执行记录</div>
      </article>

      <article class="panel list-panel">
        <header class="panel-head"><div><h2>即将执行</h2></div></header>
        <div class="compact-table-head upcoming-columns"><span>项目 / 套件</span><span>环境</span><span>调度类型</span><span>下次执行时间</span><span>操作</span></div>
        <div v-if="visibleUpcomingRuns.length" class="compact-list">
          <div v-for="item in visibleUpcomingRuns.slice(0, 4)" :key="item.id" class="compact-row upcoming-columns">
            <strong>{{ item.project }} / {{ item.suite }}</strong><span class="env-tag">{{ item.environment }}</span><span>Cron</span><time>{{ item.time }}</time><button type="button" class="text-link" @click="openSuite(item)">查看套件</button>
          </div>
        </div>
        <div v-else class="empty-block">暂无计划执行的套件</div>
      </article>
    </section>

    <AiChat ref="aiChatRef" />
  </div>
</template>

<script lang="ts" setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { PhArrowClockwise, PhArrowRight, PhFolderSimple, PhPlugsConnected, PhShieldCheck, PhSparkle, PhStack } from '@phosphor-icons/vue';
import { ProjectAPI } from '@/api/project/http';
import { EndpointAPI, ScenarioAPI } from '@/api/case_api/http';
import { RunResultAPI, SuiteAPI } from '@/api/suite/http';
import AiChat from '@/components/Ai/AiChat.vue';

const router = useRouter();
const aiChatRef = ref();
const loading = ref(false);
const selectedProjectId = ref<number | null>(null);
const projects = ref<any[]>([]);
const endpoints = ref<any[]>([]);
const scenarios = ref<any[]>([]);
const recentRuns = ref<any[]>([]);
const upcomingRuns = ref<any[]>([]);
const avatarColors = ['#2563EB', '#D98B18', '#E5484D', '#16A36A'];

const projectOptions = computed(() => [{ label: '全部项目', value: null }, ...projects.value.map((item) => ({ label: item.name, value: item.id }))]);
const visibleProjects = computed(() => selectedProjectId.value ? projects.value.filter((item) => item.id === selectedProjectId.value) : projects.value);
const visibleRecentRuns = computed(() => selectedProjectId.value ? recentRuns.value.filter((item) => item.projectIds.includes(selectedProjectId.value)) : recentRuns.value);
const visibleUpcomingRuns = computed(() => selectedProjectId.value ? upcomingRuns.value.filter((item) => item.projectId === selectedProjectId.value) : upcomingRuns.value);
const visibleEndpointCount = computed(() => selectedProjectId.value ? endpoints.value.filter((item) => Number(item.project ?? item.project_id) === selectedProjectId.value).length : endpoints.value.length);
const visibleScenarioCount = computed(() => selectedProjectId.value ? scenarios.value.filter((item) => scenarioProjectIds(item).includes(selectedProjectId.value!)).length : scenarios.value.length);
const completedRuns = computed(() => visibleRecentRuns.value.filter((item) => ['pass', 'fail'].includes(item.result)));
const completedRunCount = computed(() => completedRuns.value.length);
const overallPassRate = computed(() => completedRuns.value.length ? Math.round(completedRuns.value.filter((item) => item.result === 'pass').length / completedRuns.value.length * 100) : 0);
const activeProjectCount = computed(() => visibleProjects.value.filter((item) => item.status !== 'draft').length);
const todayKey = () => new Date().toDateString();
const todayRuns = computed(() => visibleRecentRuns.value.filter((item) => item.rawDate && item.rawDate.toDateString() === todayKey()));
const todayPassed = computed(() => todayRuns.value.filter((item) => item.result === 'pass').length);
const todayFailed = computed(() => todayRuns.value.filter((item) => item.result === 'fail').length);
const failedRunCount = computed(() => visibleRecentRuns.value.filter((item) => item.result === 'fail').length);

function pickList(data: any) { return Array.isArray(data) ? data : data?.list ?? data?.results ?? []; }
function scenarioProjectIds(item: any) {
  const ids = new Set<number>();
  const primary = typeof item.project === 'object' ? item.project?.id : item.project ?? item.project_id;
  if (primary != null) ids.add(Number(primary));
  (item.projects || []).forEach((project: any) => ids.add(Number(typeof project === 'object' ? project.id : project)));
  return Array.from(ids);
}
function runState(run: any) {
  const status = String(run.status ?? '');
  if (status === '执行完毕' || status === '4') return run.is_pass ? { result: 'pass', label: '通过' } : { result: 'fail', label: '失败' };
  if (status === '执行出错' || status === '-1') return { result: 'fail', label: '失败' };
  if (status === '已取消' || status === '-2') return { result: 'canceled', label: '已取消' };
  if (['初始化', '准备开始', '正在执行', '正在正常报告', '0', '1', '2', '3'].includes(status)) return { result: 'running', label: '执行中' };
  return { result: 'pending', label: '待执行' };
}
function formatDateTime(value: any, withDate = false) {
  if (!value) return '-';
  const date = new Date(value);
  return date.toLocaleString('zh-CN', withDate ? { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false } : { hour: '2-digit', minute: '2-digit', hour12: false });
}
function formatDuration(start: any, finish: any) {
  if (!start || !finish) return '-';
  const seconds = Math.max(0, Math.round((new Date(finish).getTime() - new Date(start).getTime()) / 1000));
  return seconds >= 60 ? `${Math.floor(seconds / 60)}分${String(seconds % 60).padStart(2, '0')}秒` : `${seconds}秒`;
}
function environmentLabel(value: any) {
  const key = String(value || '').trim().toLowerCase();
  return ({ dev: '开发', test: '测试', pre: '预发', prod: '生产' } as Record<string, string>)[key] || (value ? String(value) : '-');
}
function projectQuality(endpointCount: number, scenarioCount: number, passRate: number) {
  if (!endpointCount || !scenarioCount) return { label: '待完善', tone: 'warning' };
  if (passRate >= 80) return { label: '健康', tone: 'healthy' };
  return { label: '有风险', tone: 'risk' };
}
function avatarColor(item: any) { return avatarColors[Number(item.id || 0) % avatarColors.length]; }
function rateTone(rate: number) { return rate >= 80 ? 'good' : rate >= 60 ? 'medium' : 'bad'; }
function applyProjectFilter() { /* computed 数据会自动响应 */ }
function openAiChat() { aiChatRef.value?.open(); }
function goProject(item: any) { router.push({ name: 'project_project_edit', params: { id: item.id } }); }
function goProjectList() { router.push({ name: 'project_project' }); }
function goRunResults() { router.push({ name: 'suite_run_result' }); }
function openReport(item: any) { if (item.id) router.push({ name: 'suite_report', params: { id: item.id } }); }
function openSuite(item: any) { router.push({ name: 'suite_suite_edit', params: { id: item.id } }); }

async function loadDashboard() {
  loading.value = true;
  try {
    const [projectData, endpointData, scenarioData, suiteData, runData] = await Promise.all([
      new ProjectAPI().getDataList({ page: 1, pageSize: 999 }), new EndpointAPI().getDataList({ page: 1, pageSize: 999 }),
      new ScenarioAPI().getDataList({ page: 1, pageSize: 999 }), new SuiteAPI().getDataList({ page: 1, pageSize: 999 }),
      new RunResultAPI().getDataList({ page: 1, pageSize: 50 }),
    ]);
    endpoints.value = pickList(endpointData);
    scenarios.value = pickList(scenarioData);
    const runList = pickList(runData);
    recentRuns.value = runList.map((run: any) => {
      const state = runState(run);
      const rawDate = new Date(run.started_at || run.create_datetime || run.update_datetime);
      const projectNames = String(run.project_names || run.project_name || '未知项目').split('/').filter(Boolean);
      return { id: run.id, project: projectNames.join('/'), projectIds: pickList(projectData).filter((project: any) => projectNames.includes(project.name)).map((project: any) => project.id), suite: run.suite_name || '未知套件', environment: environmentLabel(run.environment_name), result: state.result, statusLabel: state.label, rawDate, time: formatDateTime(rawDate), dateTime: formatDateTime(rawDate, true), duration: formatDuration(run.started_at, run.finished_at) };
    });
    const endpointCounts: Record<number, number> = {};
    endpoints.value.forEach((item) => { const id = Number(item.project ?? item.project_id); endpointCounts[id] = (endpointCounts[id] || 0) + 1; });
    const scenarioCounts: Record<number, number> = {};
    scenarios.value.forEach((item) => scenarioProjectIds(item).forEach((id) => { scenarioCounts[id] = (scenarioCounts[id] || 0) + 1; }));
    projects.value = pickList(projectData).map((project: any) => {
      const projectRuns = recentRuns.value.filter((run) => run.projectIds.includes(project.id) && ['pass', 'fail'].includes(run.result));
      const passRate = projectRuns.length ? Math.round(projectRuns.filter((run) => run.result === 'pass').length / projectRuns.length * 100) : 0;
      const endpointCount = endpointCounts[project.id] || 0; const scenarioCount = scenarioCounts[project.id] || 0;
      const coverage = endpointCount ? Math.min(100, Math.round(scenarioCount / endpointCount * 100)) : 0;
      const lastRun = recentRuns.value.find((run) => run.projectIds.includes(project.id));
      return { ...project, endpoint_count: endpointCount, scenario_count: scenarioCount, coverage, pass_rate: passRate, last_run: lastRun?.dateTime || '-', quality: projectQuality(endpointCount, scenarioCount, passRate) };
    });
    upcomingRuns.value = pickList(suiteData).filter((suite: any) => suite.run_type === 'C' && suite.next_run).sort((a: any, b: any) => new Date(a.next_run).getTime() - new Date(b.next_run).getTime()).map((suite: any) => ({ id: suite.id, projectId: Number(suite.project), project: suite.project_name || '未知项目', suite: suite.name || '未知套件', environment: environmentLabel(suite.environment_name), time: formatDateTime(suite.next_run, true) }));
  } catch (error: any) { window['$message']?.error(error?.message || '主控台数据加载失败'); }
  finally { loading.value = false; }
}

onMounted(loadDashboard);
</script>

<style lang="less" scoped>
.console-page { --blue:#2563eb; --text:#172033; --muted:#758195; --line:#e5eaf1; display:grid; gap:14px; max-width:1480px; margin:0 auto; padding:18px 24px 28px; color:var(--text); }
.page-head,.page-actions,.ai-strip,.ai-strip>div,.panel-head,.panel-head>div,.list-title,.activity-title { display:flex; align-items:center; }
.page-head { justify-content:space-between; gap:20px; }
.page-head h1 { margin:0; font-size:22px; font-weight:700; letter-spacing:-.02em; }
.page-head p { margin:4px 0 0; color:var(--muted); font-size:13px; }
.page-actions { gap:10px; }.project-filter{width:150px;}
.ai-strip { min-height:48px; justify-content:space-between; gap:16px; padding:0 16px; border:1px solid #dbe5f3; border-radius:8px; background:#fbfdff; }
.ai-strip>div{gap:10px;color:#526175;font-size:13px}.ai-strip .n-icon{color:var(--blue)}
.stats-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; }
.metric-card { position:relative; display:flex; align-items:center; gap:14px; min-height:112px; padding:16px 18px; border:1px solid var(--line); border-radius:8px; background:#fff; box-shadow:0 3px 12px rgba(50,75,110,.035); }
.metric-icon { display:grid; flex:0 0 48px; width:48px; height:48px; place-items:center; border:1px solid #d9e6f8; border-radius:8px; color:var(--blue); background:#f7faff; font-size:26px; }.metric-icon.success{color:#16a36a;border-color:#d8eee4;background:#f7fcf9}
.metric-card p{margin:0 0 2px;color:#526175;font-size:13px}.metric-card strong{display:block;font-size:30px;line-height:1.15;letter-spacing:-.03em}.metric-card small{display:block;margin-top:6px;color:var(--muted);font-size:12px}.pass-metric{padding-right:100px}
.pass-ring { position:absolute; right:18px; display:grid; width:66px; height:66px; place-items:center; border-radius:50%; background:conic-gradient(#16a36a var(--pass-rate),#edf2f4 0); }.pass-ring:after{position:absolute;width:52px;height:52px;border-radius:50%;background:#fff;content:''}.pass-ring span{z-index:1;color:#536174;font-size:12px;font-weight:600}
.main-grid{display:grid;grid-template-columns:minmax(0,1.8fr) minmax(360px,1fr);gap:14px}.bottom-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.panel{overflow:hidden;border:1px solid var(--line);border-radius:8px;background:#fff;box-shadow:0 3px 12px rgba(50,75,110,.03)}
.panel-head{min-height:48px;justify-content:space-between;padding:0 16px;border-bottom:1px solid var(--line)}.panel-head>div{gap:12px}.panel-head h2{margin:0;font-size:15px;font-weight:650}.panel-head span{color:var(--muted);font-size:12px}.text-link{display:inline-flex;align-items:center;gap:3px;padding:0;border:0;color:var(--blue);background:transparent;font-size:12px;cursor:pointer;white-space:nowrap}.text-link:hover{text-decoration:underline}
.table-scroll{overflow-x:auto}.quality-table{width:100%;min-width:720px;border-collapse:collapse;table-layout:fixed}.quality-table th{height:38px;padding:0 14px;color:#657286;background:#f8fafc;font-size:12px;font-weight:550;text-align:left}.quality-table td{height:60px;padding:0 14px;border-top:1px solid #edf1f5;color:#475569;font-size:12px}.quality-table tbody tr{cursor:pointer}.quality-table tbody tr:hover{background:#f8fbff}.project-name{display:flex;align-items:center;gap:10px}.project-name strong{overflow:hidden;color:#273449;font-size:13px;text-overflow:ellipsis;white-space:nowrap}.project-avatar{display:grid;flex:0 0 32px;width:32px;height:32px;place-items:center;border-radius:7px;color:#fff;font-size:13px;font-weight:600}.progress-cell{display:grid;gap:5px}.progress-cell>span{color:#536174}.progress-cell i{display:block;width:100%;height:5px;overflow:hidden;border-radius:3px;background:#edf1f5}.progress-cell b{display:block;height:100%;border-radius:3px;background:var(--blue)}.progress-cell.pass b.good{background:#16a36a}.progress-cell.pass b.medium{background:#d98b18}.progress-cell.pass b.bad{background:#e5484d}.quality-status,.status-tag,.env-tag{display:inline-flex;width:max-content;padding:2px 7px;border-radius:4px;font-size:11px;white-space:nowrap}.quality-status.healthy,.status-tag.pass{color:#0a7a50;background:#eaf8f2}.quality-status.warning{color:#a56608;background:#fff6e6}.quality-status.risk,.status-tag.fail{color:#c7353b;background:#fff0f1}.status-tag.running{color:#1d5eb8;background:#edf5ff}.status-tag.canceled,.status-tag.pending{color:#667386;background:#f0f3f6}.env-tag{color:#2563eb;background:#eef5ff}
.activity-summary{display:grid;grid-template-columns:repeat(3,1fr);padding:8px 12px;border-bottom:1px solid var(--line)}.activity-summary div{display:grid;gap:2px;place-items:center;padding:3px;border-left:1px solid var(--line)}.activity-summary div:first-child{border-left:0}.activity-summary span{color:var(--muted);font-size:11px}.activity-summary strong{font-size:20px}.success-text{color:#16a36a}.danger-text{color:#e5484d}.activity-title{justify-content:space-between;padding:10px 16px 5px;font-size:12px}.activity-list{padding:0 12px}.activity-row{display:grid;grid-template-columns:8px minmax(0,1fr) auto 42px;align-items:center;gap:8px;min-height:34px;font-size:12px}.status-dot{width:7px;height:7px;border-radius:50%;background:#b5bfcc}.status-dot.pass{background:#16a36a}.status-dot.fail{background:#e5484d}.status-dot.running{background:#2563eb}.activity-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.activity-row time{color:var(--muted);text-align:right}.activity-empty{display:grid;height:164px;place-items:center;color:var(--muted);font-size:12px}.trend-row{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:10px;margin:7px 14px 10px;padding-top:8px;border-top:1px solid var(--line);color:var(--muted);font-size:11px}.trend-row svg{width:100%;height:20px}.trend-row polyline{fill:none;stroke:#e5484d;stroke-width:1.4}.trend-row strong{color:#e5484d}
.compact-table-head,.compact-row{display:grid;align-items:center;gap:10px;padding:0 16px}.compact-table-head{height:34px;color:#657286;background:#f8fafc;font-size:11px}.compact-row{width:100%;min-height:39px;border:0;border-top:1px solid #edf1f5;color:#536174;background:#fff;font-size:12px;text-align:left}.compact-row:hover{background:#f8fbff}.compact-row strong{overflow:hidden;color:#334155;font-weight:550;text-overflow:ellipsis;white-space:nowrap}.compact-row time{color:var(--muted)}.run-columns{grid-template-columns:minmax(150px,1.5fr) 62px 58px 66px 80px}.upcoming-columns{grid-template-columns:minmax(150px,1.5fr) 62px 70px 90px 64px}.empty-block{display:grid;min-height:118px;place-items:center;color:var(--muted);font-size:12px}
@media(max-width:1100px){.stats-grid{grid-template-columns:repeat(2,1fr)}.main-grid{grid-template-columns:1fr}.bottom-grid{grid-template-columns:1fr}}
@media(max-width:680px){.console-page{padding:14px}.page-head,.ai-strip{align-items:flex-start;flex-direction:column}.page-actions{width:100%}.project-filter{flex:1}.ai-strip{padding:12px}.stats-grid{grid-template-columns:1fr}.bottom-grid{overflow-x:auto}.compact-table-head,.compact-row{min-width:620px}}
</style>
