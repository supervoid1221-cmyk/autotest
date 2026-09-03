<template>
  <div class="report-page">
    <n-spin :show="loading">
      <div class="report-header">
        <div class="report-heading">
          <div class="report-heading__title"
            ><h2>执行报告</h2
            ><n-tag size="small" type="info" :bordered="false">原生执行报告</n-tag></div
          >
          <p
            >{{ report?.suite || result?.suite_name || '测试套件'
            }}<span v-if="report?.environment"> · {{ report.environment }}</span
            ><span> · 执行人：{{ result?.executor_name || '-' }}</span></p
          >
        </div>
        <div class="report-actions"
          ><n-button quaternary @click="backToResults">返回</n-button
          ><n-button secondary :loading="loading" @click="refreshProgress">刷新</n-button
          ><n-button v-if="active" type="error" secondary :loading="canceling" @click="cancelRun"
            >取消执行</n-button
          ><n-dropdown
            trigger="click"
            placement="bottom-end"
            :show-arrow="true"
            :options="moreActionOptions"
            @select="handleMoreAction"
            ><n-button class="report-more-trigger"
              ><span>更多</span><i class="report-more-trigger__arrow"></i></n-button></n-dropdown
        ></div>
      </div>

      <section class="report-runline"
        ><span class="report-runline__label">执行状态</span
        ><n-tag size="small" :type="reportStatus.type">{{ reportStatus.label }}</n-tag
        ><span>开始时间：{{ formatTime(report.started_at) }}</span
        ><span>执行环境：{{ report?.environment || '-' }}</span
        ><span>总耗时：{{ formatDuration(report.duration_ms) }}</span></section
      >

      <AiInsight v-if="summary?.failed > 0" title="AI 失败分析" :content="aiAnalysis" />

      <div class="report-workspace">
        <main class="report-main">
          <section class="report-overview" v-if="summary">
            <div class="report-overview__metrics">
              <div class="pass-ring" :style="stepRingStyle"
                ><div class="pass-ring__value"
                  ><strong>{{ summary.total || 0 }}</strong
                  ><span>总步骤</span></div
                ></div
              >
              <div class="overview-stat overview-stat--pass"
                ><span>通过</span><strong>{{ summary.passed || 0 }}</strong
                ><small>{{ passRate }}%</small></div
              >
              <div class="overview-stat overview-stat--fail"
                ><span>失败</span><strong>{{ summary.failed || 0 }}</strong
                ><small>{{ failureRate }}%</small></div
              >
              <div class="overview-stat overview-stat--skip"
                ><span>跳过</span><strong>{{ summary.skipped || 0 }}</strong
                ><small>{{ skipRate }}%</small></div
              >
              <div class="overview-stat overview-stat--pending"
                ><span>未执行</span><strong>{{ summary.pending || 0 }}</strong
                ><small>{{ pendingRate }}%</small></div
              >
            </div>
            <div class="run-timeline"
              ><div
                v-for="(stage, index) in timelineStages"
                :key="stage.label"
                class="run-timeline__stage"
                :class="{
                  done: timelineProgress >= index,
                  current: timelineProgress === index && active,
                }"
                ><i></i><strong>{{ stage.label }}</strong
                ><span>{{ stage.time }}</span></div
              ></div
            >
          </section>
          <section v-if="scenarios.length" class="scenario-filterbar">
            <div class="scenario-filter-tabs" role="tablist" aria-label="报告筛选">
              <button
                v-for="item in scenarioFilterOptions"
                :key="item.key"
                type="button"
                :class="{ active: scenarioFilter === item.key }"
                @click="scenarioFilter = item.key"
                ><span>{{ item.label }}</span
                ><strong>（{{ item.count }}）</strong></button
              >
            </div>
            <div class="scenario-search-wrap">
              <n-input
                v-model:value="scenarioSearch"
                clearable
                size="small"
                placeholder="搜索场景名称"
                class="scenario-search"
              >
                <template #prefix>⌕</template>
              </n-input>
            </div>
          </section>
          <n-empty
            v-if="!visibleScenarios.length"
            :description="
              scenarios.length
                ? '未找到匹配的执行场景。'
                : '暂未生成执行步骤数据，请等待执行完成后刷新页面。'
            "
            class="empty"
          />
          <div v-if="visibleScenarios.length" class="scenario-columns" aria-hidden="true">
            <span>场景名称</span>
            <span>状态</span>
            <span>耗时</span>
            <span></span>
          </div>
          <div v-if="visibleScenarios.length" class="scenarios">
            <n-card
              v-for="scenario in visibleScenarios"
              :key="String(scenario.id)"
              size="small"
              class="scenario-card"
            >
              <template #header
                ><button
                  type="button"
                  class="scenario-title scenario-title-button"
                  :aria-expanded="isScenarioExpanded(scenario)"
                  @click="toggleScenario(scenario)"
                  ><span class="scenario-identity"
                    ><strong>{{ scenario.name }}</strong
                    ><n-tag size="small" :type="isUiScenario(scenario) ? 'info' : 'default'">{{
                      scenarioTypeLabel(scenario)
                    }}</n-tag
                    ><n-tag v-if="isUiScenario(scenario)" size="small" :bordered="false"
                      >{{ uiBrowserLabel(scenario.browser) }} ·
                      {{ scenario.run_mode === 'headed' ? '有界面' : '无头' }}</n-tag
                    ><span class="scenario-meta">{{ scenario.steps?.length || 0 }} 个步骤</span></span
                  ><span
                    class="scenario-status"
                    :class="`scenario-status--${stepStatus(scenario).type}`"
                    ><i></i>{{ stepStatus(scenario).label }}</span
                  ><span class="scenario-value">{{
                    formatDuration(scenarioDuration(scenario))
                  }}</span
                  ><span
                    class="scenario-toggle"
                    :class="{ collapsed: !isScenarioExpanded(scenario) }"
                    aria-hidden="true"
                    >⌄</span
                  ></button
                ></template
              >
              <div v-if="isScenarioExpanded(scenario)" class="scenario-content">
                <div class="scenario-step-groups">
                  <template
                    v-for="(group, groupIndex) in reportStepGroups(scenario)"
                    :key="`${scenario.id}-${group.key}`"
                  >
                    <article v-if="group.kind === 'condition'" class="condition-node">
                      <div
                        class="condition-node__heading condition-node__heading--collapsible"
                        role="button"
                        tabindex="0"
                        :aria-expanded="isConditionExpanded(scenario, group)"
                        @click="toggleCondition(scenario, group)"
                        @keydown.enter.prevent="toggleCondition(scenario, group)"
                        @keydown.space.prevent="toggleCondition(scenario, group)"
                      >
                        <span class="condition-node__diamond"></span>
                        <div
                          ><strong>{{ group.name }}</strong
                          ><span>{{ conditionDescription(group) }}</span></div
                        >
                        <n-tag size="small" :type="conditionStatus(group).type">{{
                          conditionStatus(group).label
                        }}</n-tag>
                        <span
                          class="condition-node__chevron"
                          :class="{ collapsed: !isConditionExpanded(scenario, group) }"
                          aria-hidden="true"
                          >⌄</span
                        >
                      </div>
                      <div
                        v-if="isConditionExpanded(scenario, group) && group.branches?.length"
                        class="condition-branch-list"
                      >
                        <details
                          v-for="(branch, branchIndex) in group.branches"
                          :key="`${group.key}-branch-${branch.id}`"
                          class="condition-branch"
                          :class="{
                            'condition-branch--selected': branch.selected,
                            'condition-branch--skipped': branch.skipped,
                          }"
                          :style="branchToneStyle(branchIndex)"
                          :open="branch.selected || !group.decision"
                        >
                          <summary class="condition-branch__heading">
                            <span class="condition-branch__marker"></span>
                            <strong>{{ branch.name }}</strong>
                            <span class="condition-branch__condition">{{
                              formatBranchConditions(branch)
                            }}</span>
                            <span
                              class="branch-state"
                              :class="{ selected: branch.selected, skipped: branch.skipped }"
                              >{{
                                branch.selected ? '已命中' : branch.skipped ? '未命中' : '待判断'
                              }}</span
                            >
                            <span>{{ branch.steps.length }} 个步骤</span>
                            <span class="condition-branch__chevron">⌄</span>
                          </summary>
                          <ReportApiStepList
                            v-if="branch.steps.length"
                            :steps="branch.steps"
                            :group-key="branch.key"
                          />
                          <div v-else class="condition-branch__empty">该分支未配置接口步骤</div>
                        </details>
                      </div>
                    </article>
                    <component
                      v-else
                      :is="group.showHeader ? 'details' : 'section'"
                      :open="group.showHeader || undefined"
                      :class="{
                        'ui-tab-group': group.showHeader,
                      }"
                    >
                      <summary v-if="group.showHeader" class="ui-tab-heading">
                        <span v-if="group.kind === 'tab'" class="ui-tab-order"
                          >Tab {{ groupIndex + 1 }}</span
                        >
                        <strong>{{ group.name }}</strong>
                        <span>{{ group.steps.length }} 个步骤</span>
                        <n-tag size="small" :type="stepGroupStatus(group.steps).type">{{
                          stepGroupStatus(group.steps).label
                        }}</n-tag>
                        <span class="ui-tab-chevron">⌄</span>
                      </summary>
                      <n-collapse arrow-placement="right">
                        <n-collapse-item
                          v-for="(step, index) in group.steps"
                          :key="`${scenario.id}-${group.key}-${step.source_step_id || index}`"
                          :name="`${scenario.id}-${group.key}-${index}`"
                        >
                          <template #header>
                            <div class="step-header">
                              <span class="step-identity">
                                <span class="step-index">{{ index + 1 }}</span>
                                <span class="method" :style="methodStyle(step.method)">{{
                                  step.method ||
                                  (isUiScenario(scenario) ? step.action || 'UI' : 'API')
                                }}</span>
                                <strong>{{ step.name }}</strong>
                                <span class="url">{{
                                  isUiScenario(scenario) ? formatUiLocator(step) : step.url
                                }}</span>
                              </span>
                              <span class="step-status"
                                ><n-tag :type="stepStatus(step).type" size="small">{{
                                  stepStatus(step).label
                                }}</n-tag></span
                              >
                              <span class="step-column-value">{{
                                formatDuration(step.duration_ms, step)
                              }}</span>
                            </div>
                          </template>
                          <div class="step-meta">
                            <span>执行时间：{{ formatTime(step.started_at) }}</span
                            ><span v-if="!isUiScenario(scenario)"
                              >状态码：{{ step.status_code ?? '-' }}</span
                            ><span>耗时：{{ formatDuration(step.duration_ms, step) }}</span
                            ><span v-if="!isUiScenario(scenario)"
                              >请求次数：{{ step.attempts || 1 }}</span
                            >
                          </div>
                          <n-alert
                            v-if="step.errors?.length"
                            type="error"
                            :show-icon="false"
                            class="errors"
                            >{{ step.errors.join('；') }}</n-alert
                          >
                          <n-alert
                            v-else-if="step.skip_reason"
                            type="warning"
                            :show-icon="false"
                            class="errors"
                            >{{ step.skip_reason }}</n-alert
                          >
                          <div v-if="isUiScenario(scenario)" class="ui-details">
                            <section class="detail-block"
                              ><h4>页面操作</h4><pre>{{ formatUiOperation(step) }}</pre>
                            </section>
                            <section class="detail-block"
                              ><h4>定位与页面</h4><pre>{{ formatUiRuntime(step) }}</pre>
                            </section>
                          </div>
                          <section
                            v-if="screenshotUrl(step)"
                            class="detail-block failure-screenshot"
                          >
                            <h4>{{ screenshotLabel(step) }}</h4>
                            <a :href="screenshotUrl(step)" target="_blank" rel="noopener"
                              >在新窗口查看原图</a
                            >
                            <img :src="screenshotUrl(step)" :alt="screenshotLabel(step)" />
                          </section>
                          <n-grid
                            v-if="!isUiScenario(scenario)"
                            :cols="2"
                            :x-gap="14"
                            :y-gap="14"
                            responsive="screen"
                          >
                            <n-gi
                              ><section class="detail-block"
                                ><h4>请求参数</h4><pre>{{ formatRequest(step.request) }}</pre>
                              </section></n-gi
                            >
                            <n-gi
                              ><section class="detail-block"
                                ><h4>响应结果</h4><pre>{{ formatResponse(step.response) }}</pre>
                              </section></n-gi
                            >
                          </n-grid>
                          <section v-if="step.assertions?.length" class="detail-block"
                            ><h4>断言结果</h4
                            ><div class="assertions"
                              ><div v-for="(item, itemIndex) in step.assertions" :key="itemIndex"
                                ><n-tag :type="item.passed ? 'success' : 'error'" size="small">{{
                                  item.passed ? '通过' : '失败'
                                }}</n-tag>
                                {{ item.actual_path || assertionName(item.type) }}：实际值
                                {{ item.actual }}，期望值 {{ item.expected }}</div
                              ></div
                            ></section
                          >
                          <section
                            v-if="Object.keys(step.extracted || {}).length"
                            class="detail-block"
                            ><h4>数据提取</h4><pre>{{ formatJson(step.extracted) }}</pre>
                          </section>
                        </n-collapse-item>
                      </n-collapse>
                    </component>
                  </template>
                </div>
              </div>
            </n-card>
          </div>
        </main>

        <aside class="report-log-rail">
          <section v-if="isAdmin" class="live-log">
            <div class="live-log-title"
              ><div
                ><h3>实时执行日志</h3
                ><small class="log-connection"
                  ><i></i>{{ active ? '日志流已连接' : '执行日志已归档' }}</small
                ></div
              ><div class="live-log-tools"
                ><n-input
                  v-model:value="logSearch"
                  clearable
                  size="small"
                  placeholder="搜索日志，回车定位下一个"
                  @keydown.enter.prevent="locateNextLogMatch"
                /><n-tooltip trigger="hover">
                  <template #trigger>
                    <n-button
                      size="small"
                      secondary
                      circle
                      aria-label="放大全屏"
                      @click="logFullscreen = true"
                    >
                      <template #icon><n-icon><FullscreenOutlined /></n-icon></template>
                    </n-button>
                  </template>
                  放大全屏
                </n-tooltip></div
              ></div
            >
            <pre
              ref="logContentRef"
              class="log-content"
              v-html="highlightedProgressLog || '等待执行器输出日志…'"
            ></pre>
          </section>
          <n-empty v-else description="仅管理员可查看实时执行日志" class="log-empty" />
          <div class="variable-entry"
            ><div
              ><strong>变量解析</strong
              ><span v-if="variableResolution.length"
                >{{ variableResolution.length }} 条记录</span
              ></div
            ><n-button
              type="primary"
              secondary
              size="small"
              :disabled="!variableResolution.length"
              @click="variableResolutionVisible = true"
              >查看详情</n-button
            ></div
          >
        </aside>
      </div>
      <n-modal
        v-model:show="logFullscreen"
        :z-index="10000"
        :mask-closable="false"
        :auto-focus="false"
      >
        <section class="live-log fullscreen-log-panel">
          <div class="live-log-title">
            <div>
              <h3>实时执行日志</h3>
              <small class="log-connection"
                ><i></i>{{ active ? '日志流已连接' : '执行日志已归档' }}</small
              >
            </div>
            <div class="live-log-tools">
              <n-input
                v-model:value="logSearch"
                clearable
                size="small"
                placeholder="搜索日志，回车定位下一个"
                @keydown.enter.prevent="locateNextLogMatch"
              />
              <n-tooltip trigger="hover">
                <template #trigger>
                  <n-button
                    size="small"
                    secondary
                    circle
                    aria-label="退出全屏"
                    @click="logFullscreen = false"
                  >
                    <template #icon><n-icon><FullscreenExitOutlined /></n-icon></template>
                  </n-button>
                </template>
                退出全屏
              </n-tooltip>
            </div>
          </div>
          <pre
            ref="fullscreenLogContentRef"
            class="log-content"
            v-html="highlightedProgressLog || '等待执行器输出日志…'"
          ></pre>
        </section>
      </n-modal>
      <n-modal
        v-model:show="variableResolutionVisible"
        preset="card"
        title="变量解析详情"
        style="width: min(820px, calc(100vw - 48px))"
      >
        <p class="resolution-description"
          >按变量的实际产生顺序展示；同名变量以最后一次设置为准，Token、密码等敏感值已遮罩。</p
        >
        <div class="resolution-table-wrap">
          <table class="resolution-table">
            <thead
              ><tr
                ><th>来源</th><th>变量名</th><th>解析值</th><th>产生位置</th><th>状态</th></tr
              ></thead
            >
            <tbody>
              <tr
                v-for="(item, index) in variableResolution"
                :key="`${item.name}-${index}`"
                :class="{ superseded: !item.effective }"
              >
                <td
                  ><n-tag size="small" :type="variableSourceType(item.source)">{{
                    item.source_label || variableSourceLabel(item.source)
                  }}</n-tag></td
                >
                <td
                  ><code>{{ variableReference(item.name) }}</code></td
                >
                <td>
                  <pre>{{ formatVariableValue(item.value) }}</pre>
                </td>
                <td>{{ variableContext(item) }}</td>
                <td
                  ><n-tag size="small" :type="item.effective ? 'success' : 'default'">{{
                    item.effective ? '最终生效' : '已被覆盖'
                  }}</n-tag></td
                >
              </tr>
            </tbody>
          </table>
        </div>
      </n-modal>
    </n-spin>
  </div>
</template>

<script lang="ts" setup>
  import { computed, nextTick, onActivated, onDeactivated, onMounted, onUnmounted, ref, watch } from 'vue';
  import { useRoute, useRouter } from 'vue-router';
  import { useMessage } from 'naive-ui';
  import { FullscreenExitOutlined, FullscreenOutlined } from '@vicons/antd';
  import { RunResultAPI } from '@/api/suite/http';
  import { AiInsight } from '@/components/Ai';
  import ReportApiStepList from './components/ReportApiStepList.vue';
  import { useUserStore } from '@/store/modules/user';

  const route = useRoute();
  const router = useRouter();
  const userStore = useUserStore();
  const isAdmin = computed(() => Boolean((userStore.info as any)?.is_admin));
  const result = ref<any>();
  const loading = ref(true);
  const progressLog = ref('');
  const logSearch = ref('');
  const logMatchIndex = ref(-1);
  const logContentRef = ref<HTMLElement | null>(null);
  const fullscreenLogContentRef = ref<HTMLElement | null>(null);
  const logFullscreen = ref(false);
  const active = ref(false);
  const canceling = ref(false);
  const pausing = ref(false);
  const rerunning = ref(false);
  const scenarioFilter = ref<'scenes' | 'branches' | 'failed'>('scenes');
  const scenarioSearch = ref('');
  const variableResolutionVisible = ref(false);
  const scenarioExpansion = ref<Record<string, boolean>>({});
  const conditionExpansion = ref<Record<string, boolean>>({});
  const screenshotUrls = ref<Record<string, string>>({});
  const message = useMessage();
  const api = new RunResultAPI();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let progressRequestVersion = 0;
  let progressPollingVersion = 0;
  const report = computed(() => result.value?.native_report || {});
  const scenarios = computed(() => report.value?.scenarios || []);
  const isPaused = computed(() => String(result.value?.status || '') === '已暂停');
  const variableResolution = computed(() => report.value?.variable_resolution || []);
  const summary = computed(() => report.value?.summary);
  const passRate = computed(() => {
    const total = Number(summary.value?.total || 0);
    if (!total) return 0;
    return Math.round((Number(summary.value?.passed || 0) / total) * 100 * 10) / 10;
  });
  const percentageOfTotal = (value: unknown) => {
    const total = Number(summary.value?.total || 0);
    return total ? Math.round((Number(value || 0) / total) * 1000) / 10 : 0;
  };
  const failureRate = computed(() => percentageOfTotal(summary.value?.failed));
  const skipRate = computed(() => percentageOfTotal(summary.value?.skipped));
  const pendingRate = computed(() => percentageOfTotal(summary.value?.pending));
  const stepRingStyle = computed(() => {
    const total = Number(summary.value?.total || 0);
    if (!total) return { background: '#eef2f6' };
    const segments = [
      ['#149463', Number(summary.value?.passed || 0)],
      ['#e5484d', Number(summary.value?.failed || 0)],
      ['#e58418', Number(summary.value?.skipped || 0)],
      ['#2563eb', Number(summary.value?.running || 0)],
      ['#a8b3c2', Number(summary.value?.pending || 0)],
    ] as const;
    let current = 0;
    const stops = segments.map(([color, value]) => {
      const next = current + (value / total) * 100;
      const stop = `${color} ${current.toFixed(3)}% ${next.toFixed(3)}%`;
      current = next;
      return stop;
    });
    return { background: `conic-gradient(${stops.join(', ')})` };
  });
  const reportStatus = computed(() => {
    if (isPaused.value) return { label: '已暂停', type: 'warning' as const };
    if (active.value) return { label: '执行中', type: 'warning' as const };
    if (Number(summary.value?.failed || 0) > 0)
      return { label: '执行失败', type: 'error' as const };
    if (Number(summary.value?.total || 0) > 0)
      return { label: '执行完成', type: 'success' as const };
    return { label: '等待执行', type: 'default' as const };
  });
  const timelineStages = computed(() => [
    { label: '执行开始', time: formatTime(report.value?.started_at) },
    { label: '场景执行中', time: active.value ? '进行中' : '已完成' },
    { label: '分支决策', time: Number(summary.value?.skipped || 0) ? '已处理' : '无分支' },
    {
      label: '执行汇总',
      time: active.value ? '等待中' : formatDuration(report.value?.duration_ms),
    },
  ]);
  const timelineProgress = computed(() => {
    if (!summary.value?.total) return 0;
    return active.value ? 1 : 3;
  });
  const aiAnalysis = computed(() => {
    if (!summary.value?.failed || summary.value.failed === 0) return '';
    const failedCount = summary.value.failed;
    const total = summary.value.total || 0;
    return `检测到 ${failedCount} 个失败步骤。建议逐一排查接口请求、页面元素定位和等待超时。共执行 ${total} 个步骤，通过率 ${passRate.value}%。`;
  });
  const moreActionOptions = computed(() => [
    {
      label: isPaused.value ? '继续执行' : '暂停',
      key: 'pause',
      disabled: !active.value || pausing.value,
    },
    { label: '重新执行', key: 'retry', disabled: active.value },
  ]);
  const escapeHtml = (value: string) =>
    value.replace(
      /[&<>'"]/g,
      (character) =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[
          character
        ] as string)
    );
  const logMatchCount = computed(() => {
    const keyword = logSearch.value.trim();
    if (!keyword) return 0;
    return (
      progressLog.value.match(new RegExp(keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')) ||
      []
    ).length;
  });
  const highlightedProgressLog = computed(() => {
    const content = escapeHtml(progressLog.value || '');
    const keyword = logSearch.value.trim();
    if (!keyword) return content;
    const expression = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return content.replace(new RegExp(expression, 'gi'), (matched) => `<mark>${matched}</mark>`);
  });
  const locateNextLogMatch = async () => {
    if (!logSearch.value.trim() || !logMatchCount.value) return;
    await nextTick();
    const contentElement = logFullscreen.value
      ? fullscreenLogContentRef.value
      : logContentRef.value;
    const matches = Array.from(contentElement?.querySelectorAll('mark') || []);
    if (!matches.length) return;
    logMatchIndex.value = (logMatchIndex.value + 1) % matches.length;
    matches.forEach((match, index) =>
      match.classList.toggle('active', index === logMatchIndex.value)
    );
    matches[logMatchIndex.value]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };
  watch(logSearch, async (keyword) => {
    logMatchIndex.value = -1;
    if (!keyword.trim()) return;
    await locateNextLogMatch();
  });
  const methodStyle = (method?: string) =>
    ({
      GET: { color: '#1677ff', background: '#eaf3ff' },
      POST: { color: '#20a162', background: '#ebf8f0' },
      PUT: { color: '#d97706', background: '#fff5e6' },
      PATCH: { color: '#7c3aed', background: '#f3edff' },
      DELETE: { color: '#dc2626', background: '#fff0f0' },
    }[String(method || '').toUpperCase()] || { color: '#667085', background: '#f2f4f7' });
  const formatJson = (data: unknown) => JSON.stringify(data || {}, null, 2);
  const formatVariableValue = (value: unknown) =>
    typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  const variableReference = (name: unknown) => `\${${String(name || '')}}`;
  const variableSourceLabel = (source?: string) =>
    ({
      project: '项目参数',
      environment_token: '环境 Token',
      template: '模板参数',
      api_extract: '接口提取',
      ui_extract: 'UI 提取',
    }[String(source || '')] ||
    source ||
    '未知来源');
  const variableSourceType = (source?: string) =>
    (({
      project: 'default',
      environment_token: 'warning',
      template: 'info',
      api_extract: 'success',
      ui_extract: 'success',
    }[String(source || '')] || 'default') as any);
  const extractionSourceLabel = (source?: string) =>
    ({ dom_value: 'DOM 值', dom_text: 'DOM 文本', ocr: 'OCR 识别' }[String(source || '')] ||
    source ||
    '');
  const variableContext = (item: any) => {
    if (item.source === 'environment_token')
      return item.environment ? `环境：${item.environment}` : '执行环境';
    if (item.source === 'api_extract')
      return `${item.step_name ? `接口：${item.step_name}` : '接口响应'}${
        item.expression ? ` · ${item.expression}` : ''
      }`;
    if (item.source === 'ui_extract')
      return `${item.step_name ? `UI 步骤：${item.step_name}` : 'UI 步骤'}${
        item.action ? ` · ${item.action}` : ''
      }${item.expression ? ` · ${item.expression}` : ''}${
        item.extraction_source ? ` · ${extractionSourceLabel(item.extraction_source)}` : ''
      }`;
    return item.source === 'template' ? '本次执行入参' : '项目配置';
  };
  const isEmpty = (value: unknown) =>
    value == null ||
    (typeof value === 'string' && value.trim() === '') ||
    (Array.isArray(value) && value.length === 0) ||
    (typeof value === 'object' && Object.keys(value).length === 0);
  const formatRequest = (request: any) => {
    const clone = { ...(request || {}) };
    (['params', 'data', 'json'] as const).forEach((key) => {
      if (isEmpty(clone[key])) delete clone[key];
    });
    return JSON.stringify(clone, null, 2);
  };
  const formatResponse = (data: any) =>
    JSON.stringify({ headers: data?.headers || {}, body: data?.body || '' }, null, 2);
  const isUiScenario = (scenario: any) =>
    ['ui', 'playwright_ui'].includes(String(scenario?.type || '')) ||
    Boolean(scenario?.browser && scenario?.run_mode);
  const scenarioTypeLabel = (scenario: any) =>
    scenario?.type === 'playwright_ui'
      ? 'Playwright UI'
      : scenario?.type === 'ui'
      ? 'UI 自动化'
      : '接口场景';
  const uiBrowserLabel = (browser?: string) =>
    ({ chrome: 'Chrome', chromium: 'Chromium', firefox: 'Firefox', webkit: 'WebKit' }[
      String(browser || '').toLowerCase()
    ] || '浏览器');
  const formatUiLocator = (step: any) => {
    const resolution = step?.detail?.resolution || {};
    const element =
      step?.target ||
      step?.element_name ||
      resolution?.element?.ariaLabel ||
      resolution?.element?.placeholder ||
      '';
    if (!element && step?.detail?.url) return step.detail.url;
    const strategy =
      resolution?.strategy || (step?.locator ? `${step.by || ''}=${step.locator}` : '');
    return [element, strategy].filter(Boolean).join(' · ');
  };
  const formatUiOperation = (step: any) =>
    JSON.stringify(
      {
        tab: step.tab_name || step.tab_key || '',
        action: step.action || step.action_key || '',
        page_element: step.target || step.element_name || '',
        operation_value: step.detail?.value ?? '',
        expected: step.detail?.expected,
        actual: step.detail?.actual,
      },
      null,
      2
    );
  const formatUiRuntime = (step: any) => {
    const resolution = step?.detail?.resolution || {};
    return JSON.stringify(
      {
        page_url: step.detail?.page_url || step.detail?.url || '',
        locator_strategy: resolution.strategy || (step.locator ? `manual:${step.by || ''}` : ''),
        confidence: resolution.confidence,
        matched_phrase: resolution.matched_phrase,
        fallback_used: resolution.fallback_used || false,
        element:
          resolution.element ||
          (step.locator
            ? { name: step.element_name || '', by: step.by || '', locator: step.locator }
            : {}),
        candidates: resolution.candidates || [],
      },
      null,
      2
    );
  };
  const screenshotMeta = (step: any) =>
    step?.detail?.screenshot ||
    step?.detail?.failure_screenshot ||
    step?.detail?.ocr_screenshot ||
    {};
  const screenshotSource = (step: any) => {
    const screenshotPath = String(screenshotMeta(step)?.path || '').replace(/^\/+/, '');
    const artifactsUrl = String(result.value?.artifacts_url || '');
    if (!screenshotPath || !artifactsUrl.endsWith('/artifacts.zip')) return '';
    return `${artifactsUrl.slice(0, -'artifacts.zip'.length)}${screenshotPath}`;
  };
  const screenshotUrl = (step: any) => screenshotUrls.value[screenshotSource(step)] || '';
  const screenshotLabel = (step: any) => screenshotMeta(step)?.label || '步骤截图';
  function clearScreenshotCache() {
    Object.values(screenshotUrls.value).forEach((url) => URL.revokeObjectURL(url));
    screenshotUrls.value = {};
  }
  async function loadScreenshots() {
    const sources = scenarios.value.flatMap((scenario: any) =>
      (scenario.steps || []).map(screenshotSource).filter(Boolean)
    );
    for (const source of sources) {
      if (screenshotUrls.value[source]) continue;
      try {
        const blob = await api.fetchScreenshot(source);
        screenshotUrls.value = { ...screenshotUrls.value, [source]: URL.createObjectURL(blob) };
      } catch {
        // 截图下载失败不影响报告其余内容；错误步骤本身仍会展示失败原因。
      }
    }
  }
  const assertionName = (type?: string) =>
    ({ assert_text: '文本断言', assert_value: '值断言' }[String(type || '')] || type || '断言');
  const formatTime = (value?: string) => {
    if (!value) return '-';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false });
  };
  const formatDuration = (value?: number, step?: any) => {
    let milliseconds = Number(value);
    if (!Number.isFinite(milliseconds) && step?.started_at && step?.finished_at) {
      milliseconds = new Date(step.finished_at).getTime() - new Date(step.started_at).getTime();
    }
    if (!Number.isFinite(milliseconds)) return '-';
    milliseconds = Math.max(0, milliseconds);
    return milliseconds >= 1000
      ? `${(milliseconds / 1000).toFixed(2)} 秒`
      : `${milliseconds.toFixed(0)} ms`;
  };
  const stepStatus = (step: any) => {
    const status =
      step?.status ||
      (step?.passed === true ? 'passed' : step?.passed === false ? 'failed' : 'pending');
    return (
      (
        {
          passed: { label: '通过', type: 'success' },
          failed: { label: '失败', type: 'error' },
          running: { label: '执行中', type: 'warning' },
          pending: { label: '待执行', type: 'default' },
          skipped: { label: '已跳过', type: 'warning' },
        } as any
      )[status] || { label: '待执行', type: 'default' }
    );
  };
  const scenarioKey = (scenario: any) => String(scenario?.id ?? scenario?.name ?? 'scenario');
  const isScenarioExpanded = (scenario: any) => {
    const key = scenarioKey(scenario);
    if (Object.prototype.hasOwnProperty.call(scenarioExpansion.value, key))
      return scenarioExpansion.value[key];
    return stepStatus(scenario).label !== '通过';
  };
  const toggleScenario = (scenario: any) => {
    const key = scenarioKey(scenario);
    scenarioExpansion.value = { ...scenarioExpansion.value, [key]: !isScenarioExpanded(scenario) };
  };
  const conditionKey = (scenario: any, group: any) => `${scenarioKey(scenario)}:${group?.key}`;
  const isConditionExpanded = (scenario: any, group: any) => {
    const key = conditionKey(scenario, group);
    return Object.prototype.hasOwnProperty.call(conditionExpansion.value, key)
      ? conditionExpansion.value[key]
      : true;
  };
  const toggleCondition = (scenario: any, group: any) => {
    const key = conditionKey(scenario, group);
    conditionExpansion.value = {
      ...conditionExpansion.value,
      [key]: !isConditionExpanded(scenario, group),
    };
  };
  const conditionStatus = (group: any) => {
    if (!group?.decision) return { label: '待判断', type: 'default' };
    return group.decision.status === 'matched'
      ? { label: '已命中', type: 'success' }
      : { label: '未命中', type: 'error' };
  };
  const conditionDescription = (group: any) => {
    const count = Array.isArray(group?.node?.branches) ? group.node.branches.length : 0;
    return `${count} 个分支 · 从上到下匹配，执行第一个满足条件的分支`;
  };
  const conditionOperatorLabel = (operator?: string) =>
    ({
      equals: '等于',
      not_equals: '不等于',
      gt: '大于',
      gte: '大于等于',
      lt: '小于',
      lte: '小于等于',
      contains: '包含',
      not_contains: '不包含',
      exists: '存在',
      not_exists: '不存在',
      regex: '匹配正则',
      in: '属于',
    }[String(operator || '')] ||
    operator ||
    '等于');
  const formatBranchConditions = (group: any) => {
    const conditions = Array.isArray(group?.conditions) ? group.conditions : [];
    if (!conditions.length) return '未配置条件';
    const separator =
      String(group?.conditionLogic || 'and').toLowerCase() === 'or' ? ' 或 ' : ' 且 ';
    return conditions
      .map((item: any) => {
        const displayStep = group?.stepLabels?.[String(item.step_id)] || '-';
        const source =
          item.source === 'step'
            ? `步骤 ${displayStep}${item.path ? ` ${item.path}` : ''}`
            : `变量 ${item.variable || '-'}${item.path ? ` ${item.path}` : ''}`;
        const operator = conditionOperatorLabel(item.operator);
        return ['exists', 'not_exists'].includes(String(item.operator || ''))
          ? `${source} ${operator}`
          : `${source} ${operator} ${String(item.expected ?? '')}`;
      })
      .join(separator);
  };
  const branchTones = [
    { color: '#2563eb', soft: '#eff6ff', border: '#bfdbfe' },
    { color: '#7c3aed', soft: '#f5f3ff', border: '#ddd6fe' },
    { color: '#0f8a72', soft: '#eefbf7', border: '#b9eadc' },
    { color: '#c24178', soft: '#fff1f6', border: '#fbcfe0' },
    { color: '#475569', soft: '#f8fafc', border: '#cbd5e1' },
  ];
  const branchToneStyle = (index: number) => {
    const tone = branchTones[index % branchTones.length];
    return {
      '--branch-color': tone.color,
      '--branch-soft': tone.soft,
      '--branch-border': tone.border,
    };
  };
  const reportStepGroups = (scenario: any) => {
    const steps = Array.isArray(scenario?.steps) ? scenario.steps : [];
    if (!isUiScenario(scenario)) {
      const flowNodes = Array.isArray(scenario?.flow_nodes) ? scenario.flow_nodes : [];
      if (!flowNodes.length) {
        const legacyDecisions = Array.isArray(scenario?.decisions) ? scenario.decisions : [];
        return [
          ...legacyDecisions.map((decision: any, index: number) => ({
            key: `legacy-condition-${decision.node_id || index}`,
            kind: 'condition',
            name: decision.name || '判断分支',
            node: { branches: decision.branches || [] },
            decision,
            showHeader: false,
            steps: [],
          })),
          { key: 'api', kind: 'steps', name: '', showHeader: false, steps },
        ];
      }

      const stepMap = new Map<string, any>();
      steps.forEach((step: any) => stepMap.set(String(step?.source_step_id), step));
      const stepLabels: Record<string, string> = {};
      const indexFlowSteps = (nodes: any[], prefix = '') => {
        (nodes || []).forEach((node: any, index: number) => {
          const label = prefix ? `${prefix}.${index + 1}` : String(index + 1);
          if (node?.node_type === 'endpoint') {
            if (node.source_step_id != null) stepLabels[String(node.source_step_id)] = label;
            return;
          }
          (node?.branches || []).forEach((branch: any) =>
            indexFlowSteps(branch.nodes || [], label)
          );
        });
      };
      indexFlowSteps(flowNodes);
      const groups: any[] = [];
      let mainSteps: any[] = [];
      let mainIndex = 0;
      const flushMain = () => {
        if (!mainSteps.length) return;
        groups.push({
          key: `main-${mainIndex++}`,
          kind: 'steps',
          name: '',
          showHeader: false,
          steps: mainSteps,
        });
        mainSteps = [];
      };
      const collectSteps = (nodes: any[]): any[] =>
        (nodes || []).flatMap((node: any) => {
          if (node?.node_type === 'endpoint') {
            const step = stepMap.get(String(node.source_step_id));
            return step ? [step] : [];
          }
          return (node?.branches || []).flatMap((branch: any) => collectSteps(branch.nodes || []));
        });
      flowNodes.forEach((node: any) => {
        if (node?.node_type === 'endpoint') {
          const step = stepMap.get(String(node.source_step_id));
          if (step) mainSteps.push(step);
          return;
        }
        flushMain();
        const decision = (scenario?.decisions || []).find(
          (item: any) => String(item?.node_id) === String(node?.node_id)
        );
        groups.push({
          key: `condition-${node.node_id}`,
          kind: 'condition',
          name: node.name || '判断分支',
          node,
          decision,
          showHeader: false,
          steps: [],
          branches: (node.branches || []).map((branch: any) => {
            const selected = Boolean(
              decision && String(decision.selected_branch_id) === String(branch.id)
            );
            return {
              id: branch.id,
              key: `condition-${node.node_id}-branch-${branch.id}`,
              name: branch.name || '未命名分支',
              conditions: branch.conditions || [],
              conditionLogic: node.condition_logic || 'and',
              stepLabels,
              selected,
              skipped: Boolean(decision && !selected),
              steps: collectSteps(branch.nodes || []),
            };
          }),
        });
      });
      flushMain();
      return groups;
    }

    const groups = new Map<string, any>();
    const configuredTabs = Array.isArray(scenario?.tabs)
      ? [...scenario.tabs].sort(
          (left: any, right: any) => Number(left?.order || 0) - Number(right?.order || 0)
        )
      : [];
    configuredTabs.forEach((tab: any, index: number) => {
      const key = String(tab?.key || `tab-${index + 1}`);
      groups.set(key, {
        key,
        kind: 'tab',
        name: String(tab?.name || `Tab ${index + 1}`),
        showHeader: true,
        steps: [],
      });
    });
    steps.forEach((step: any) => {
      const key = String(step?.tab_key || 'tab-1');
      if (!groups.has(key)) {
        groups.set(key, {
          key,
          kind: 'tab',
          name: String(step?.tab_name || `Tab ${groups.size + 1}`),
          showHeader: true,
          steps: [],
        });
      }
      groups.get(key).steps.push(step);
    });
    return Array.from(groups.values());
  };
  const scenarioGroups = (scenario: any) => reportStepGroups(scenario);
  const scenarioHasBranches = (scenario: any) =>
    scenarioGroups(scenario).some((group: any) => group.kind === 'condition');
  const scenarioBranchCount = (scenario: any) =>
    scenarioGroups(scenario).reduce(
      (count: number, group: any) =>
        count + (group.kind === 'condition' ? group.branches?.length || 0 : 0),
      0
    );
  const scenarioSteps = (scenario: any) =>
    scenarioGroups(scenario).flatMap((group: any) =>
      group.kind === 'condition'
        ? (group.branches || []).flatMap((branch: any) => branch.steps || [])
        : group.steps || []
    );
  const scenarioDuration = (scenario: any) => {
    if (scenario?.duration_ms !== undefined && scenario?.duration_ms !== null) {
      return Number(scenario.duration_ms) || 0;
    }
    return scenarioSteps(scenario).reduce(
      (total: number, step: any) => {
        const duration = Number(step?.duration_ms);
        if (Number.isFinite(duration)) return total + Math.max(0, duration);
        if (step?.started_at && step?.finished_at) {
          const derived = new Date(step.finished_at).getTime() - new Date(step.started_at).getTime();
          return total + (Number.isFinite(derived) ? Math.max(0, derived) : 0);
        }
        return total;
      },
      0,
    );
  };
  const scenarioFailed = (scenario: any) =>
    scenarioSteps(scenario).some((step: any) => stepStatus(step).type === 'error');
  const scenarioFilterOptions = computed(() => [
    { key: 'scenes', label: '场景', count: scenarios.value.length },
    {
      key: 'branches',
      label: '分支',
      count: scenarios.value.reduce(
        (count: number, scenario: any) => count + scenarioBranchCount(scenario),
        0
      ),
    },
    {
      key: 'failed',
      label: '失败场景',
      count: scenarios.value.filter(scenarioFailed).length,
    },
  ]);
  const visibleScenarios = computed(() => {
    const keyword = scenarioSearch.value.trim().toLocaleLowerCase();
    return scenarios.value.filter((scenario: any) => {
      if (scenarioFilter.value === 'branches' && !scenarioHasBranches(scenario)) return false;
      if (scenarioFilter.value === 'failed' && !scenarioFailed(scenario)) return false;
      if (!keyword) return true;
      const searchable = [
        scenario.name,
        ...scenarioGroups(scenario).flatMap((group: any) => [
          group.name,
          ...(group.branches || []).flatMap((branch: any) => [
            branch.name,
            ...(branch.steps || []).flatMap((step: any) => [step.name, step.url]),
          ]),
          ...(group.steps || []).flatMap((step: any) => [step.name, step.url]),
        ]),
      ]
        .filter(Boolean)
        .join(' ')
        .toLocaleLowerCase();
      return searchable.includes(keyword);
    });
  });
  const stepGroupStatus = (steps: any[]) => {
    const statuses = (steps || []).map((step) => stepStatus(step));
    if (statuses.some((item) => item.type === 'error')) return { label: '失败', type: 'error' };
    if (statuses.some((item) => item.label === '执行中'))
      return { label: '执行中', type: 'warning' };
    if (statuses.length && statuses.every((item) => item.type === 'success'))
      return { label: '通过', type: 'success' };
    if (statuses.length && statuses.every((item) => item.label === '已跳过'))
      return { label: '已跳过', type: 'warning' };
    return { label: '未完成', type: 'default' };
  };
  function stopProgressPolling() {
    progressPollingVersion += 1;
    if (timer) clearTimeout(timer);
    timer = undefined;
  }
  async function pollProgress(pollingVersion: number) {
    try {
      await refreshProgress();
    } catch {
      // 临时网络波动不终止本次执行的状态跟踪，下一轮继续获取最新报告。
    }
    if (pollingVersion !== progressPollingVersion || !active.value) return;
    timer = setTimeout(() => pollProgress(pollingVersion), 1500);
  }
  function startProgressPolling() {
    stopProgressPolling();
    if (!active.value) return;
    const pollingVersion = ++progressPollingVersion;
    void pollProgress(pollingVersion);
  }
  async function refreshProgress() {
    const requestVersion = ++progressRequestVersion;
    const data: any = await api.getProgress(Number(route.params.id));
    if (requestVersion !== progressRequestVersion) return;
    result.value = data.result;
    progressLog.value = data.log || '';
    active.value = Boolean(data.active);
    // 截图下载可能较慢，不能阻塞执行状态和步骤状态的实时刷新。
    void loadScreenshots();
    if (!active.value) stopProgressPolling();
  }
  async function init() {
    try {
      await refreshProgress();
      startProgressPolling();
    } finally {
      loading.value = false;
    }
  }
  async function cancelRun() {
    canceling.value = true;
    try {
      await api.cancelById(Number(route.params.id));
      message.success('已请求取消任务');
      await refreshProgress();
    } catch (error: any) {
      message.error(error?.message || '取消失败');
    } finally {
      canceling.value = false;
    }
  }
  async function pauseRun() {
    pausing.value = true;
    try {
      await api.pauseById(Number(route.params.id));
      message.success(isPaused.value ? '已恢复执行' : '已暂停执行');
      await refreshProgress();
    } catch (error: any) {
      message.error(error?.detail || error?.message || '暂停操作失败');
    } finally {
      pausing.value = false;
    }
  }
  function handleMoreAction(key: string) {
    if (key === 'pause') pauseRun();
    if (key === 'retry') retryRun();
  }
  async function retryRun() {
    rerunning.value = true;
    try {
      // 使上一轮轮询中的响应失效，避免旧报告覆盖刚提交的新一轮执行状态。
      progressRequestVersion += 1;
      stopProgressPolling();
      const response: any = await api.retryById(Number(route.params.id));
      message.success(`已重新提交执行记录：${response.result_id}`);
      // 与“直接运行套件”保持同一条进入报告页路径：使用相同执行编号重建
      // 报告页面实例，避免 keep-alive 中的旧状态、旧轮询和旧报告快照残留。
      await router.replace({
        name: 'suite_report',
        params: { id: response.result_id },
        query: { ...route.query, rerun: String(Date.now()) },
      });
    } catch (error: any) {
      message.error(error?.detail || error?.message || '重新执行失败');
    } finally {
      rerunning.value = false;
    }
  }
  function backToResults() {
    router.push({ name: 'suite_run_result' });
  }
  function handleLogFullscreenKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && logFullscreen.value) logFullscreen.value = false;
  }
  onMounted(init);
  onMounted(() => window.addEventListener('keydown', handleLogFullscreenKeydown));
  onActivated(() => {
    refreshProgress()
      .then(() => startProgressPolling())
      .catch(() => undefined);
  });
  onDeactivated(stopProgressPolling);
  onUnmounted(() => {
    stopProgressPolling();
    clearScreenshotCache();
    window.removeEventListener('keydown', handleLogFullscreenKeydown);
  });
</script>

<style lang="less" scoped>
  .report-page {
    min-height: 100%;
    padding: 24px 28px 30px;
    background: #f7f9fc;
  }
  .report-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    flex-wrap: wrap;
    gap: 12px;
  }
  .report-heading__title {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .report-heading__title .n-tag {
    font-weight: 600;
  }
  .report-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .report-more-trigger {
    min-width: 88px;
    border-color: #d8dee9;
    border-radius: 8px;
    background: #fff;
  }
  .report-more-trigger :deep(.n-button__content) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
  }
  .report-more-trigger__arrow {
    width: 7px;
    height: 7px;
    margin-top: -3px;
    border-right: 1.5px solid currentColor;
    border-bottom: 1.5px solid currentColor;
    transform: rotate(45deg);
  }
  .report-runline {
    display: flex;
    align-items: center;
    gap: 14px;
    min-height: 38px;
    margin-bottom: 16px;
    padding: 0 12px;
    border: 1px solid #e6ebf2;
    border-radius: 7px;
    color: #768399;
    background: #fff;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
  }
  .report-runline__label {
    color: #43516a;
    font-weight: 650;
  }
  .report-workspace {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(330px, 37%);
    gap: 16px;
    align-items: start;
  }
  .report-main {
    min-width: 0;
  }
  .report-overview {
    overflow: hidden;
    margin-bottom: 14px;
    border: 1px solid #e0e7f0;
    border-radius: 9px;
    background: #fff;
    box-shadow: 0 4px 16px rgb(25 52 86 / 4%);
  }
  .report-overview__metrics {
    display: grid;
    grid-template-columns: 174px repeat(4, minmax(82px, 1fr));
    min-height: 152px;
    align-items: center;
    padding: 15px 22px;
  }
  .pass-ring {
    position: relative;
    display: grid;
    width: 124px;
    height: 124px;
    place-items: center;
    border-radius: 50%;
  }
  .pass-ring::after {
    position: absolute;
    inset: 10px;
    border-radius: 50%;
    background: #fff;
    content: '';
  }
  .pass-ring__value {
    position: relative;
    z-index: 1;
    display: grid;
    gap: 2px;
    place-items: center;
  }
  .pass-ring__value strong {
    color: #1c293d;
    font-size: 26px;
    font-variant-numeric: tabular-nums;
  }
  .pass-ring__value span,
  .overview-stat span {
    color: #8190a5;
    font-size: 12px;
  }
  .overview-stat {
    display: grid;
    gap: 6px;
    align-content: center;
    min-height: 82px;
    padding-left: 22px;
    border-left: 1px solid #edf1f5;
  }
  .overview-stat strong {
    color: #526176;
    font-size: 25px;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }
  .overview-stat small {
    color: #94a0b1;
    font-size: 11px;
  }
  .overview-stat--pass strong {
    color: #149463;
  }
  .overview-stat--fail strong {
    color: #e5484d;
  }
  .overview-stat--skip strong {
    color: #e58418;
  }
  .overview-stat--pending strong {
    color: #8190a5;
  }
  .run-timeline {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    padding: 17px 26px 18px;
    border-top: 1px solid #edf1f5;
  }
  .run-timeline__stage {
    position: relative;
    display: grid;
    gap: 4px;
    min-width: 0;
    padding: 15px 8px 0 0;
    color: #8693a7;
    font-size: 11px;
  }
  .run-timeline__stage::before {
    position: absolute;
    top: 4px;
    left: 6px;
    width: calc(100% - 2px);
    height: 2px;
    content: '';
    background: #dbe4ee;
  }
  .run-timeline__stage:last-child::before {
    width: 6px;
  }
  .run-timeline__stage i {
    position: absolute;
    z-index: 1;
    top: 0;
    left: 0;
    width: 11px;
    height: 11px;
    box-sizing: border-box;
    border: 2px solid #b4c0cf;
    border-radius: 50%;
    background: #fff;
  }
  .run-timeline__stage strong {
    overflow: hidden;
    color: #526176;
    font-size: 12px;
    font-weight: 650;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .run-timeline__stage.done::before {
    background: #16a16a;
  }
  .run-timeline__stage.done i {
    border-color: #16a16a;
    background: #16a16a;
    box-shadow: 0 0 0 3px #eaf8f1;
  }
  .run-timeline__stage.current i {
    border-color: #e58418;
    background: #e58418;
    box-shadow: 0 0 0 3px #fff4e5;
  }
  .run-timeline__stage.current::before {
    background: #16a16a;
  }
  .scenario-filterbar {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 58px;
    margin-bottom: 14px;
    padding: 0 14px 0 12px;
    overflow: hidden;
    box-sizing: border-box;
    border: 1px solid #dfe6f0;
    border-radius: 10px;
    background: #fff;
  }
  .scenario-filter-tabs {
    display: flex;
    align-self: stretch;
    flex: 0 0 auto;
    gap: 0;
  }
  .scenario-filter-tabs button {
    position: relative;
    display: inline-flex;
    width: auto;
    align-items: center;
    gap: 7px;
    padding: 0 17px;
    border: 0;
    color: #768399;
    background: transparent;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
  }
  .scenario-filter-tabs button strong {
    color: inherit;
    font-size: 13px;
    font-weight: 600;
  }
  .scenario-filter-tabs button:hover,
  .scenario-filter-tabs button.active {
    color: #2563eb;
  }
  .scenario-filter-tabs button.active::after {
    position: absolute;
    right: 17px;
    bottom: 0;
    left: 17px;
    height: 2px;
    border-radius: 2px 2px 0 0;
    background: #2563eb;
    content: '';
  }
  .scenario-search-wrap {
    flex: 0 0 230px !important;
    width: 230px !important;
    min-width: 0;
    max-width: 230px;
    margin-left: auto;
    align-self: center;
  }
  .scenario-search {
    width: 100% !important;
    max-width: 100%;
    height: 40px;
    border-radius: 8px;
  }
  .report-log-rail {
    position: sticky;
    top: 16px;
    min-width: 0;
    overflow: hidden;
    border: 1px solid #e0e7f0;
    border-radius: 9px;
    background: #fff;
    box-shadow: 0 4px 16px rgb(25 52 86 / 4%);
  }
  .log-empty {
    min-height: 360px;
  }
  .variable-entry {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-height: 57px;
    padding: 0 16px;
    border-top: 1px solid #edf1f5;
  }
  .variable-entry > div {
    display: grid;
    gap: 2px;
  }
  .variable-entry strong {
    color: #344054;
    font-size: 13px;
  }
  .variable-entry span {
    color: #98a2b3;
    font-size: 11px;
  }
  h2 {
    margin: 0;
    color: #1f2937;
    font-size: 22px;
  }
  p {
    margin: 5px 0 0;
    color: #8a94a6;
    font-size: 13px;
  }
  .summary {
    display: flex;
    align-items: center;
    gap: 12px;
    color: #667085;
    font-size: 13px;
    flex-wrap: wrap;
  }
  .summary-meta {
    white-space: nowrap;
  }
  .pass-rate {
    text-align: center;
  }
  .pass-rate__num {
    font-size: 32px;
    font-weight: 500;
    color: #1d9e75;
    display: block;
    line-height: 1.2;
  }
  .pass-rate__label {
    font-size: 12px;
    color: #8a94a6;
  }
  .summary-stats {
    display: flex;
    gap: 8px;
  }
  .summary-stat {
    padding: 2px 10px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
    white-space: nowrap;
  }
  .summary-stat--pass {
    background: #e1f5ee;
    color: #0f6e56;
  }
  .summary-stat--fail {
    background: #faece7;
    color: #993c1d;
  }
  .summary-stat--skip {
    background: #fff4e5;
    color: #9a5b13;
  }
  .summary-stat--running {
    background: #eaf3ff;
    color: #175cd3;
  }
  .summary-stat--pending {
    background: #f1efe8;
    color: #5f5e5a;
  }
  h2 {
    margin: 0;
    color: #1f2937;
    font-size: 22px;
  }
  p {
    margin: 5px 0 0;
    color: #8a94a6;
    font-size: 13px;
  }
  .summary {
    display: flex;
    align-items: center;
    gap: 12px;
    color: #667085;
    font-size: 13px;
    flex-wrap: wrap;
  }
  .variable-button-icon {
    font: 700 11px/1 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }
  .resolution-description {
    margin: -2px 0 14px;
    color: #7a8ba5;
    font-size: 12px;
  }
  .resolution-table-wrap {
    overflow-x: auto;
  }
  .resolution-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    color: #475467;
    font-size: 12px;
  }
  .resolution-table th {
    padding: 10px 12px;
    background: #f8faff;
    color: #667085;
    font-weight: 600;
    text-align: left;
  }
  .resolution-table td {
    padding: 10px 12px;
    border-top: 1px solid #edf1f7;
    vertical-align: top;
  }
  .resolution-table th:nth-child(1) {
    width: 130px;
  }
  .resolution-table th:nth-child(2) {
    width: 180px;
  }
  .resolution-table th:nth-child(5) {
    width: 100px;
  }
  .resolution-table code {
    color: #376bff;
    font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }
  .resolution-table pre {
    max-height: 76px;
    padding: 0;
  }
  .resolution-table tr.superseded td {
    color: #98a2b3;
    background: #fafbfc;
  }
  .scenarios {
    display: grid;
    gap: 14px;
  }
  .scenario-columns {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 104px 108px 30px;
    gap: 16px;
    align-items: center;
    margin: 0 1px 8px;
    padding: 0 20px;
    color: #8a96a8;
    font-size: 12px;
    font-weight: 600;
  }
  .scenario-columns > :nth-child(2),
  .scenario-columns > :nth-child(3) {
    transform: translateX(54px);
  }
  .scenario-card {
    overflow: hidden;
    border-color: #dfe6f0;
    border-radius: 10px;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }
  .scenario-card:hover {
    border-color: #cfd9e8;
    box-shadow: 0 8px 24px rgb(33 58 99 / 5%);
  }
  .scenario-title {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 104px 108px 30px;
    width: 100%;
    align-items: center;
    min-width: 0;
    gap: 16px;
  }
  .scenario-title-button {
    padding: 2px 0;
    border: 0;
    color: inherit;
    background: transparent;
    cursor: pointer;
    font: inherit;
    text-align: left;
  }
  .scenario-title-button:focus-visible {
    border-radius: 4px;
    outline: 2px solid #7da7ff;
    outline-offset: 4px;
  }
  .scenario-identity {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: 10px;
  }
  .scenario-identity > strong {
    overflow: hidden;
    color: #1f2d42;
    font-size: 15px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .scenario-meta {
    color: #8a96a8;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .scenario-status,
  .scenario-value {
    color: #5f6f85;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    transform: translateX(54px);
    white-space: nowrap;
  }
  .scenario-status {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-weight: 600;
  }
  .scenario-status i {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #98a2b3;
    box-shadow: 0 0 0 3px rgb(152 162 179 / 12%);
  }
  .scenario-status--success { color: #15945f; }
  .scenario-status--success i { background: #19a66a; box-shadow: 0 0 0 3px rgb(25 166 106 / 12%); }
  .scenario-status--error { color: #e0444d; }
  .scenario-status--error i { background: #ef4d57; box-shadow: 0 0 0 3px rgb(239 77 87 / 12%); }
  .scenario-status--warning { color: #d97706; }
  .scenario-status--warning i { background: #f59e0b; box-shadow: 0 0 0 3px rgb(245 158 11 / 14%); }
  .scenario-status--info { color: #2563eb; }
  .scenario-status--info i { background: #3b82f6; box-shadow: 0 0 0 3px rgb(59 130 246 / 12%); }
  .scenario-toggle {
    display: grid;
    width: 30px;
    height: 30px;
    padding: 0;
    place-items: center;
    border: 0;
    border-radius: 6px;
    color: #66758b;
    background: transparent;
    cursor: pointer;
    font-size: 18px;
    transition: color 0.2s ease, background 0.2s ease, transform 0.2s ease;
  }
  .scenario-toggle:hover {
    color: #245fe7;
    background: #eef4ff;
  }
  .scenario-toggle:focus-visible {
    outline: 2px solid #7da7ff;
    outline-offset: 2px;
  }
  .scenario-toggle.collapsed {
    transform: rotate(-90deg);
  }
  .scenario-content {
    animation: scenario-content-in 0.18s ease-out;
  }
  @keyframes scenario-content-in {
    from {
      opacity: 0;
      transform: translateY(-4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  .scenario-step-groups {
    display: grid;
    gap: 12px;
  }
  .ui-tab-group {
    overflow: hidden;
    border: 1px solid #e3eaf5;
    border-radius: 8px;
    background: #fff;
  }
  .ui-tab-group :deep(.n-collapse) {
    margin-top: 8px;
  }
  .ui-tab-heading {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 46px;
    padding: 0 14px;
    border-bottom: 1px solid #e7edf5;
    color: #667085;
    font-size: 12px;
    background: #f8faff;
  }
  .ui-tab-heading {
    cursor: pointer;
    list-style: none;
    user-select: none;
  }
  .ui-tab-heading::-webkit-details-marker {
    display: none;
  }
  .ui-tab-heading strong {
    color: #27364d;
    font-size: 14px;
  }
  .ui-tab-heading .n-tag {
    margin-left: auto;
  }
  .ui-tab-chevron {
    color: #7b8aa1;
    font-size: 18px;
    transition: transform 0.18s ease;
  }
  .ui-tab-group:not([open]) .ui-tab-heading {
    border-bottom-color: transparent;
  }
  .ui-tab-group:not([open]) .ui-tab-chevron {
    transform: rotate(-90deg);
  }
  .ui-tab-order {
    padding: 3px 8px;
    border-radius: 4px;
    color: #1769e8;
    font-weight: 650;
    background: #eaf2ff;
  }
  .condition-node {
    overflow: hidden;
    border: 1px solid #dce5f2;
    border-left: 3px solid #d28a18;
    border-radius: 8px;
    background: #fbfcfe;
  }
  .condition-node__heading {
    display: flex;
    min-height: 58px;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
  }
  .condition-node__heading--collapsible {
    cursor: pointer;
    user-select: none;
  }
  .condition-node__heading--collapsible:hover {
    background: #fffaf0;
  }
  .condition-node__heading--collapsible:focus-visible {
    outline: 2px solid #93c5fd;
    outline-offset: -2px;
  }
  .condition-node__diamond {
    width: 16px;
    height: 16px;
    flex: none;
    border: 2px solid #d07a00;
    transform: rotate(45deg);
  }
  .condition-node__heading > div {
    display: grid;
    min-width: 0;
    gap: 3px;
  }
  .condition-node__heading strong {
    color: #243247;
    font-size: 14px;
  }
  .condition-node__heading span:not(.condition-node__diamond) {
    overflow: hidden;
    color: #8490a3;
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .condition-node__heading .n-tag {
    margin-left: auto;
  }
  .condition-node__chevron {
    width: 22px;
    flex: none;
    color: #7b8aa1 !important;
    font-size: 18px !important;
    text-align: center;
    transition: transform 0.18s ease;
  }
  .condition-node__chevron.collapsed {
    transform: rotate(-90deg);
  }
  .condition-branch-list {
    display: grid;
    gap: 9px;
    padding: 12px 14px 14px 42px;
    border-top: 1px solid #edf1f6;
    background: #fffdf8;
  }
  .condition-branch {
    overflow: hidden;
    border: 1px solid var(--branch-border);
    border-left: 4px solid var(--branch-color);
    border-radius: 7px;
    background: #fff;
    transition: opacity 0.2s ease, box-shadow 0.2s ease;
  }
  .condition-branch--selected {
    box-shadow: 0 5px 18px color-mix(in srgb, var(--branch-color) 10%, transparent);
  }
  .condition-branch--skipped {
    opacity: 0.72;
  }
  .condition-branch__heading {
    display: flex;
    min-height: 44px;
    align-items: center;
    gap: 9px;
    padding: 0 12px;
    color: #637086;
    background: var(--branch-soft);
    cursor: pointer;
    font-size: 11px;
    list-style: none;
    user-select: none;
  }
  .condition-branch__heading::-webkit-details-marker {
    display: none;
  }
  .condition-branch__marker {
    width: 8px;
    height: 8px;
    flex: none;
    border-radius: 50%;
    background: var(--branch-color);
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--branch-color) 12%, transparent);
  }
  .condition-branch__heading strong {
    flex: none;
    color: var(--branch-color);
    font-size: 13px;
  }
  .condition-branch__condition {
    min-width: 0;
    overflow: hidden;
    color: #69778c;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .condition-branch__heading .branch-state {
    margin-left: auto;
  }
  .condition-branch__chevron {
    color: var(--branch-color);
    font-size: 16px;
    transition: transform 0.18s ease;
  }
  .condition-branch:not([open]) .condition-branch__chevron {
    transform: rotate(-90deg);
  }
  .condition-branch__empty {
    padding: 18px;
    color: #98a2b3;
    font-size: 12px;
    text-align: center;
  }
  .branch-state {
    flex: none;
    padding: 3px 7px;
    border-radius: 4px;
    color: #7b8797;
    font-size: 11px;
    font-weight: 650;
    background: #eef1f5;
  }
  .branch-state.selected {
    color: #147252;
    background: #e6f6ef;
  }
  .branch-state.skipped {
    color: #9b6921;
    background: #fff3df;
  }
  .step-header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 104px 108px;
    flex: 1;
    align-items: center;
    min-width: 0;
    gap: 16px;
  }
  .step-identity {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: 9px;
  }
  .step-status {
    flex: none;
  }
  .step-status,
  .step-column-value {
    transform: translateX(26px);
  }
  .step-column-value {
    color: #69778c;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .step-index {
    display: grid;
    flex: none;
    place-items: center;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: #f0f5ff;
    color: #1677ff;
    font-size: 12px;
  }
  .method {
    flex: none;
    min-width: 42px;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 700;
    text-align: center;
  }
  .url {
    overflow: hidden;
    color: #8a94a6;
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .step-meta {
    display: flex;
    gap: 18px;
    margin-bottom: 12px;
    color: #667085;
    font-size: 12px;
  }
  .errors {
    margin-bottom: 12px;
  }
  .detail-block {
    margin-top: 14px;
    overflow: hidden;
    border: 1px solid #e7ecf3;
    border-radius: 6px;
    background: #fff;
  }
  .detail-block h4 {
    margin: 0;
    padding: 9px 12px;
    border-bottom: 1px solid #edf1f5;
    color: #465468;
    font-size: 13px;
  }
  pre {
    max-height: 300px;
    margin: 0;
    padding: 11px 12px;
    overflow: auto;
    color: #344054;
    font: 12px/1.65 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .assertions {
    display: grid;
    gap: 8px;
    padding: 11px 12px;
    color: #475467;
    font-size: 12px;
  }
  .ui-details {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }
  .failure-screenshot > a {
    display: inline-block;
    margin: 10px 12px 0;
    color: #1677ff;
    font-size: 12px;
  }
  .failure-screenshot > img {
    display: block;
    width: min(100%, 1100px);
    max-height: 680px;
    margin: 10px 12px 12px;
    border: 1px solid #e7ecf3;
    border-radius: 5px;
    object-fit: contain;
    object-position: top left;
    background: #f8fafc;
  }
  .empty {
    padding: 80px 0;
    background: #fff;
  }
  .live-log {
    width: 100%;
    margin: 0;
    padding: 16px;
    box-sizing: border-box;
    border: 0;
    border-radius: 0;
    background: #fff;
  }
  .live-log-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 10px;
  }
  .live-log h3 {
    margin: 0;
    color: #344054;
    font-size: 14px;
  }
  .log-connection {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    margin-top: 4px;
    color: #7a8799;
    font-size: 11px;
  }
  .log-connection i {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #19a66e;
  }
  .live-log h3 small {
    color: #8a94a6;
    font-size: 12px;
    font-weight: 400;
  }
  .live-log-title :deep(.n-input) {
    width: 190px;
  }
  .live-log-tools {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .fullscreen-log-panel {
    position: fixed;
    z-index: 10001;
    inset: 0;
    display: flex;
    flex-direction: column;
    width: 100vw;
    height: 100vh;
    height: 100dvh;
    margin: 0;
    padding: 20px;
    overflow: hidden;
    border-radius: 0;
    background: #fff;
  }
  .fullscreen-log-panel .live-log-title {
    flex: 0 0 auto;
  }
  .fullscreen-log-panel .live-log-tools :deep(.n-input) {
    width: min(420px, 50vw);
  }
  .fullscreen-log-panel .log-content {
    flex: 1 1 auto;
    height: auto;
    min-height: 0;
  }
  .log-content {
    width: 100%;
    height: clamp(500px, calc(100vh - 290px), 760px);
    max-height: none;
    margin: 0;
    padding: 12px;
    box-sizing: border-box;
    overflow: auto;
    border: 1px solid #edf1f5;
    border-radius: 5px;
    color: #344054;
    font: 12px/1.65 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    white-space: pre;
    word-break: normal;
  }
  .log-content :deep(mark) {
    padding: 0 2px;
    color: #7a4b00;
    background: #fff3bf;
    border-radius: 2px;
  }
  .log-content :deep(mark.active) {
    color: #fff;
    background: #1677ff;
  }
  @media (max-width: 760px) {
    .report-page {
      padding: 16px;
    }
    .report-workspace {
      grid-template-columns: 1fr;
    }
    .report-log-rail {
      position: static;
    }
    .report-overview__metrics {
      grid-template-columns: 140px repeat(2, 1fr);
      gap: 6px;
    }
    .overview-stat {
      min-height: 56px;
      padding-left: 12px;
    }
    .run-timeline {
      overflow-x: auto;
      grid-template-columns: repeat(4, minmax(105px, 1fr));
    }
    .report-runline {
      align-items: flex-start;
      flex-wrap: wrap;
      padding: 9px 12px;
    }
    .scenario-columns {
      display: none;
    }
    .scenario-title {
      grid-template-columns: minmax(0, 1fr) 30px;
      gap: 10px;
    }
    .scenario-status,
    .scenario-value {
      display: none;
    }
    .step-header {
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
    }
    .step-column-value {
      display: none;
    }
    .live-log {
      width: 100%;
      margin-right: 0;
      margin-left: 0;
    }
    .live-log-title {
      align-items: stretch;
      flex-direction: column;
    }
    .live-log-title :deep(.n-input) {
      width: 100%;
    }
    .live-log-tools {
      width: 100%;
    }
    .live-log-tools :deep(.n-input),
    .fullscreen-log-panel .live-log-tools :deep(.n-input) {
      width: auto;
      flex: 1;
    }
    .log-content {
      height: clamp(360px, calc(100vh - 380px), 560px);
    }
  }
</style>
