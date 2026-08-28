<template>
  <div class="suite-editor-page">
    <header class="page-header">
      <div>
        <div class="breadcrumb"><span>套件管理</span><i>/</i><strong>{{ id ? '编辑套件' : '新增套件' }}</strong></div>
        <div class="title-line">
          <h1>{{ id ? '编辑测试套件' : '新增测试套件' }}</h1>
          <p>统一编排接口场景与 UI 用例，严格按照列表顺序执行</p>
        </div>
      </div>
      <n-space>
        <n-button size="large" @click="goBack">取消</n-button>
        <n-button type="primary" size="large" :loading="saving" @click="save(false)">保存套件</n-button>
      </n-space>
    </header>

    <n-form ref="formRef" :model="formValue" :rules="rules" label-placement="top" class="editor-form">
      <section class="basic-section">
        <h2>基本信息</h2>
        <div class="basic-grid">
          <n-form-item label="套件名称" path="name">
            <n-input v-model:value="formValue.name" maxlength="32" placeholder="例如：充值回归测试" />
          </n-form-item>
          <n-form-item label="执行环境" path="environment">
            <n-select v-model:value="formValue.environment" :options="environmentOptions" placeholder="选择环境" />
          </n-form-item>
          <n-form-item label="执行方式" path="run_type">
            <n-select v-model:value="formValue.run_type" :options="runTypeOptions" />
          </n-form-item>
          <n-form-item label="套件描述">
            <n-input v-model:value="formValue.description" maxlength="250" show-count placeholder="请输入套件描述（选填）" />
          </n-form-item>
          <n-form-item label="启用" class="enabled-field">
            <n-switch v-model:value="formValue.enabled" />
          </n-form-item>
        </div>
        <div class="secondary-grid">
          <n-form-item label="执行超时（秒）">
            <n-input-number v-model:value="formValue.execution_timeout" :min="30" :max="86400" />
          </n-form-item>
          <n-form-item v-if="formValue.run_type === 'W'" label="Webhook 密钥" path="hook_key">
            <n-input v-model:value="formValue.hook_key" placeholder="保存后可自动生成" />
          </n-form-item>
        </div>
        <section v-if="formValue.run_type === 'C'" class="schedule-config-card">
          <div class="schedule-heading">
            <div><h3>定时设置</h3><p>选择触发规则，系统会自动生成可执行的 Cron 表达式</p></div>
            <n-switch v-model:value="formValue.enabled"><template #checked>已启用</template><template #unchecked>已停用</template></n-switch>
          </div>
          <div class="schedule-kind-row">
            <span>计划类型</span>
            <n-select
              v-model:value="formValue.schedule_kind"
              :options="scheduleKindOptions"
              class="schedule-kind-select"
              @update:value="changeScheduleKind"
            />
            <p>{{ scheduleKindDescription }}</p>
          </div>
          <div class="schedule-fields">
            <template v-if="formValue.schedule_kind === 'once'">
              <label><span>执行日期时间</span><n-date-picker v-model:value="onceAt" type="datetime" clearable /></label>
              <p class="schedule-tip">任务执行一次后自动完成，不会再次触发。</p>
            </template>
            <template v-else-if="formValue.schedule_kind === 'daily'">
              <label><span>执行时间</span><n-input v-model:value="formValue.schedule_config.time" type="time" /></label>
              <p class="schedule-tip">每天在指定时间执行一次。</p>
            </template>
            <template v-else-if="formValue.schedule_kind === 'weekly'">
              <label><span>执行时间</span><n-input v-model:value="formValue.schedule_config.time" type="time" /></label>
              <label class="schedule-multi-field">
                <span>执行星期</span>
                <n-select
                  v-model:value="formValue.schedule_config.weekdays"
                  :options="weekdayOptions"
                  multiple
                  clearable
                  placeholder="请选择周几执行"
                  :max-tag-count="'responsive'"
                />
              </label>
            </template>
            <template v-else-if="formValue.schedule_kind === 'monthly'">
              <label><span>执行时间</span><n-input v-model:value="formValue.schedule_config.time" type="time" /></label>
              <label class="schedule-multi-field">
                <span>执行日期</span>
                <n-select
                  v-model:value="formValue.schedule_config.days"
                  :options="monthDayOptions"
                  multiple
                  clearable
                  placeholder="请选择每月几号执行"
                  :max-tag-count="'responsive'"
                />
              </label>
              <p class="schedule-tip">不存在的日期会在当月自动跳过。</p>
            </template>
            <template v-else>
              <label class="cron-input"><span>Cron 表达式</span><n-input v-model:value="formValue.cron" placeholder="例如：0 9 * * *" /></label>
              <p class="schedule-tip">使用标准五段 Cron：分 时 日 月 周。</p>
            </template>
            <label class="timezone-field"><span>时区</span><n-select v-model:value="formValue.schedule_timezone" :options="timezoneOptions" /></label>
          </div>
          <footer class="schedule-preview"><span>规则摘要：<strong>{{ scheduleSummary }}</strong></span><span>实际表达式：<code>{{ scheduleCronPreview || '—' }}</code></span><span>下次执行：<strong>{{ formValue.next_run ? formatDateTime(formValue.next_run) : '保存后自动计算' }}</strong></span></footer>
        </section>
      </section>

      <section class="orchestration-section">
        <div class="section-heading">
          <div class="heading-copy">
            <h2>执行编排</h2>
            <p>从左侧选择接口场景、UI 用例或 Playwright 智能 UI，添加后可拖拽调整执行顺序</p>
          </div>
          <div class="count-badges">
            <span class="count-badge api"><n-icon><CodeOutlined /></n-icon>接口场景 <b>{{ apiCount }}</b></span>
            <span class="count-badge ui"><n-icon><DesktopOutlined /></n-icon>UI 用例 <b>{{ uiCount }}</b></span>
            <span class="count-badge playwright"><n-icon><DesktopOutlined /></n-icon>智能 UI <b>{{ playwrightCount }}</b></span>
          </div>
        </div>

        <div class="orchestration-grid">
          <aside class="source-panel">
            <h3>选择测试内容</h3>
            <div class="source-tabs">
              <button type="button" :class="{ active: activeType === 'api' }" @click="changeType('api')">
                <n-icon><CodeOutlined /></n-icon>接口场景
              </button>
              <button type="button" :class="{ active: activeType === 'ui' }" @click="changeType('ui')">
                <n-icon><DesktopOutlined /></n-icon>UI 用例
              </button>
              <button type="button" :class="{ active: activeType === 'playwright_ui' }" @click="changeType('playwright_ui')">
                <n-icon><DesktopOutlined /></n-icon>智能 UI
              </button>
            </div>
            <div class="source-filters">
              <n-select v-model:value="projectFilter" :options="projectOptions" placeholder="全部项目" clearable />
              <n-input v-model:value="keyword" clearable placeholder="搜索场景或用例">
                <template #suffix><n-icon><SearchOutlined /></n-icon></template>
              </n-input>
            </div>
            <div class="source-table-head">
              <span>场景/用例名称</span><span>所属项目</span><span>步骤数</span>
            </div>
            <div class="source-list">
              <label v-for="item in filteredSources" :key="item.key" class="source-row" :class="{ added: queuedKeys.has(item.key) }">
                <n-checkbox
                  :checked="selectedSourceKeys.includes(item.key)"
                  :disabled="queuedKeys.has(item.key)"
                  @update:checked="(checked) => toggleSource(item.key, checked)"
                />
                <span class="mini-type" :class="item.type"><n-icon><component :is="item.type === 'api' ? CodeOutlined : DesktopOutlined" /></n-icon></span>
                <span class="source-name" :title="item.name">{{ item.name }}</span>
                <span class="source-project" :title="item.projectName">{{ item.projectName || '-' }}</span>
                <span class="source-count">{{ item.stepCount }}</span>
              </label>
              <n-empty v-if="!filteredSources.length" size="small" description="没有匹配的测试内容" />
            </div>
            <n-button class="add-button" type="primary" secondary :disabled="!selectedSourceKeys.length" @click="addSelected">
              <template #icon><n-icon><PlusOutlined /></n-icon></template>添加到执行顺序
            </n-button>
          </aside>

          <main class="queue-panel">
            <div class="queue-head">
              <h3>执行顺序</h3>
              <n-button size="small" :disabled="!executionItems.length" @click="clearQueue">清空</n-button>
            </div>
            <draggable v-model="executionItems" item-key="key" handle=".drag-handle" class="queue-list" ghost-class="queue-ghost">
              <template #item="{ element: item, index }">
                <article class="queue-item">
                  <button type="button" class="drag-handle" title="拖拽排序"><n-icon><MenuOutlined /></n-icon></button>
                  <span class="sequence">{{ String(index + 1).padStart(2, '0') }}</span>
                  <span class="type-badge" :class="item.type">
                    <n-icon><component :is="item.type === 'api' ? CodeOutlined : DesktopOutlined" /></n-icon>
                    {{ item.type === 'api' ? '接口' : item.type === 'playwright_ui' ? '智能 UI' : 'UI' }}
                  </span>
                  <div class="queue-copy">
                    <strong>{{ item.name }}</strong>
                    <span>{{ itemMeta(item) }}</span>
                  </div>
                  <div class="queue-actions">
                    <n-button text :disabled="index === 0" @click="moveItem(index, -1)">上移</n-button>
                    <n-button text :disabled="index === executionItems.length - 1" @click="moveItem(index, 1)">下移</n-button>
                    <n-button text type="error" title="移除" @click="removeItem(index)"><n-icon><DeleteOutlined /></n-icon></n-button>
                  </div>
                </article>
              </template>
            </draggable>
            <n-empty v-if="!executionItems.length" class="queue-empty" description="请从左侧添加接口场景或 UI 用例" />
            <div class="execution-rule">
              <n-icon><PlayCircleOutlined /></n-icon>
              <span><strong>执行规则：</strong>系统将从 01 开始串行执行；前一步失败时按用例配置决定继续或终止。</span>
            </div>
          </main>
        </div>
      </section>
    </n-form>

    <footer class="sticky-actions">
      <n-button size="large" @click="goBack">取消</n-button>
      <n-button type="primary" size="large" :loading="savingAndRunning" @click="save(true)">
        保存并执行
      </n-button>
    </footer>
  </div>
</template>

<script lang="ts" setup>
  import { computed, onMounted, reactive, ref } from 'vue';
  import { useMessage } from 'naive-ui';
  import { useRoute, useRouter } from 'vue-router';
  import draggable from 'vuedraggable';
  import {
    CodeOutlined, DeleteOutlined, DesktopOutlined, MenuOutlined,
    PlayCircleOutlined, PlusOutlined, SearchOutlined,
  } from '@vicons/antd';
  import { EnvironmentAPI } from '@/api/project/http';
  import { ScenarioAPI } from '@/api/case_api/http';
  import { UiCaseAPI } from '@/api/case_ui/http';
  import { SuiteAPI } from '@/api/suite/http';
  import type { SuiteExecutionItem } from '@/api/suite/models';
  import { useSubmitRedirect } from '@/hooks/web/useSubmitRedirect';

  type ItemType = 'api' | 'ui' | 'playwright_ui';
  interface SourceItem {
    key: string;
    type: ItemType;
    id: number;
    name: string;
    projectName: string;
    stepCount: number;
    browser?: string;
    runMode?: string;
  }

  const route = useRoute();
  const router = useRouter();
  const message = useMessage();
  const { redirectAfterSubmit } = useSubmitRedirect();
  const id = Number(route.params.id);
  const formRef = ref<any>();
  const saving = ref(false);
  const savingAndRunning = ref(false);
  const api = new SuiteAPI();
  const scenarioApi = new ScenarioAPI();
  const uiCaseApi = new UiCaseAPI();
  const playwrightCaseApi = new UiCaseAPI();
  playwrightCaseApi.base_url = '/case_ui/playwright-case/';
  const environmentApi = new EnvironmentAPI();

  const formValue = reactive<any>({
    name: '', description: '', environment: null, run_type: 'O', cron: '',
    hook_key: '', execution_timeout: 1800, enabled: true,
    schedule_kind: 'daily', schedule_config: { time: '09:00', weekdays: [1], days: [1] },
    schedule_timezone: 'Asia/Shanghai', next_run: null,
  });
  const onceAt = ref<number | null>(null);
  const rules = {
    name: { required: true, message: '请输入套件名称', trigger: 'blur' },
    environment: { required: true, type: 'number', message: '请选择执行环境', trigger: 'change' },
    run_type: { required: true, message: '请选择执行方式', trigger: 'change' },
  };
  const runTypeOptions = [
    { label: '手动执行', value: 'O' },
    { label: '定时任务', value: 'C' },
    { label: 'Webhook 触发', value: 'W' },
  ];
  const weekdayOptions = [
    { label: '周一', value: 1 }, { label: '周二', value: 2 }, { label: '周三', value: 3 },
    { label: '周四', value: 4 }, { label: '周五', value: 5 }, { label: '周六', value: 6 }, { label: '周日', value: 7 },
  ];
  const monthDayOptions = Array.from({ length: 31 }, (_, index) => ({
    label: `${index + 1} 日`,
    value: index + 1,
  }));
  const scheduleKindOptions = [
    { label: '一次性定时', value: 'once' },
    { label: '每日', value: 'daily' },
    { label: '每周', value: 'weekly' },
    { label: '每月', value: 'monthly' },
    { label: '自定义 Cron', value: 'custom' },
  ];
  const timezoneOptions = [
    { label: '中国标准时间（Asia/Shanghai）', value: 'Asia/Shanghai' },
    { label: 'UTC', value: 'UTC' },
    { label: '美国东部时间（America/New_York）', value: 'America/New_York' },
  ];
  const environmentNames = ['Dev', 'Test', 'Pre', 'Prod'];
  const environmentOptions = ref<any[]>([]);
  const apiSources = ref<SourceItem[]>([]);
  const uiSources = ref<SourceItem[]>([]);
  const playwrightSources = ref<SourceItem[]>([]);
  const executionItems = ref<SourceItem[]>([]);
  const activeType = ref<ItemType>('api');
  const projectFilter = ref<string | null>(null);
  const keyword = ref('');
  const selectedSourceKeys = ref<string[]>([]);

  const allSources = computed(() => [...apiSources.value, ...uiSources.value, ...playwrightSources.value]);
  const sourceMap = computed(() => new Map(allSources.value.map((item) => [item.key, item])));
  const queuedKeys = computed(() => new Set(executionItems.value.map((item) => item.key)));
  const apiCount = computed(() => executionItems.value.filter((item) => item.type === 'api').length);
  const uiCount = computed(() => executionItems.value.filter((item) => item.type === 'ui').length);
  const playwrightCount = computed(() => executionItems.value.filter((item) => item.type === 'playwright_ui').length);
  const projectOptions = computed(() => {
    const names = new Set(allSources.value.map((item) => item.projectName).filter(Boolean));
    return Array.from(names).sort().map((name) => ({ label: name, value: name }));
  });
  const filteredSources = computed(() => {
    const normalizedKeyword = keyword.value.trim().toLowerCase();
    const source = activeType.value === 'api' ? apiSources.value : activeType.value === 'ui' ? uiSources.value : playwrightSources.value;
    return source.filter((item) => {
      if (projectFilter.value && item.projectName !== projectFilter.value) return false;
      return !normalizedKeyword || `${item.name} ${item.projectName}`.toLowerCase().includes(normalizedKeyword);
    });
  });
  const scheduleCronPreview = computed(() => {
    const config = formValue.schedule_config || {};
    if (formValue.schedule_kind === 'custom') return String(formValue.cron || '').trim();
    if (formValue.schedule_kind === 'once') return '一次性任务';
    const [hour = '09', minute = '00'] = String(config.time || '09:00').split(':');
    if (formValue.schedule_kind === 'daily') return `${Number(minute)} ${Number(hour)} * * *`;
    if (formValue.schedule_kind === 'weekly') return `${Number(minute)} ${Number(hour)} * * ${(config.weekdays || []).join(',')}`;
    if (formValue.schedule_kind === 'monthly') return `${Number(minute)} ${Number(hour)} ${(config.days || []).join(',')} * *`;
    return '';
  });
  const scheduleSummary = computed(() => {
    const config = formValue.schedule_config || {};
    if (formValue.schedule_kind === 'once') return onceAt.value ? `一次性：${formatDateTime(new Date(onceAt.value).toISOString())}` : '请选择执行时间';
    const time = config.time || '09:00';
    if (formValue.schedule_kind === 'daily') return `每日 ${time}`;
    if (formValue.schedule_kind === 'weekly') return `每周 ${(config.weekdays || []).map((value: number) => weekdayOptions.find((item) => item.value === value)?.label).filter(Boolean).join('、') || '未选择'} ${time}`;
    if (formValue.schedule_kind === 'monthly') return `每月 ${(config.days || []).join('、') || '未选择'} 日 ${time}`;
    return '自定义 Cron';
  });
  const scheduleKindDescription = computed(() => {
    const descriptions: Record<string, string> = {
      once: '指定日期和时间仅执行一次',
      daily: '每天在指定时间执行',
      weekly: '选择星期和执行时间',
      monthly: '选择每月日期和执行时间',
      custom: '使用标准五段 Cron 表达式',
    };
    return descriptions[formValue.schedule_kind] || '';
  });

  const asList = (payload: any): any[] => {
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.list)) return payload.list;
    if (Array.isArray(payload?.results)) return payload.results;
    if (Array.isArray(payload?.data)) return payload.data;
    return [];
  };
  function formatDateTime(value: string) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
    }).format(date);
  }
  function changeScheduleKind() {
    formValue.next_run = null;
    const config = formValue.schedule_config || (formValue.schedule_config = {});
    if (!config.time) config.time = '09:00';
    if (!Array.isArray(config.weekdays)) config.weekdays = [1];
    if (!Array.isArray(config.days)) config.days = [1];
  }

  const toUniqueEnvironmentOptions = (payload: any) => {
    const byName = new Map<string, any>();
    asList(payload)
      .filter((item) => environmentNames.includes(item.name))
      .sort((a, b) => environmentNames.indexOf(a.name) - environmentNames.indexOf(b.name))
      .forEach((item) => { if (!byName.has(item.name)) byName.set(item.name, item); });
    return Array.from(byName.values()).map((item) => ({ label: item.name, value: item.id }));
  };

  function scenarioToSource(item: any): SourceItem {
    const projectNames = Array.isArray(item.project_names) ? item.project_names : [];
    return {
      key: `api-${item.id}`, type: 'api', id: item.id, name: item.name,
      projectName: projectNames.join(' / ') || item.project_name || '-',
      stepCount: Number(item.step_count || 0),
    };
  }
  function uiCaseToSource(item: any): SourceItem {
    return {
      key: `ui-${item.id}`, type: 'ui', id: item.id, name: item.name,
      projectName: item.project_name || '-', stepCount: Number(item.step_count || 0),
      browser: item.browser || 'chrome', runMode: item.run_mode || 'headless',
    };
  }
  function playwrightCaseToSource(item: any): SourceItem {
    return {
      key: `playwright_ui-${item.id}`, type: 'playwright_ui', id: item.id, name: item.name,
      projectName: item.project_name || '-', stepCount: Number(item.step_count || 0),
      browser: item.browser || 'chromium', runMode: item.run_mode || 'headless',
    };
  }
  function changeType(type: ItemType) {
    activeType.value = type;
    projectFilter.value = null;
    keyword.value = '';
    selectedSourceKeys.value = [];
  }
  function toggleSource(key: string, checked: boolean) {
    selectedSourceKeys.value = checked
      ? Array.from(new Set([...selectedSourceKeys.value, key]))
      : selectedSourceKeys.value.filter((item) => item !== key);
  }
  function addSelected() {
    selectedSourceKeys.value.forEach((key) => {
      const item = sourceMap.value.get(key);
      if (item && !queuedKeys.value.has(item.key)) executionItems.value.push({ ...item });
    });
    selectedSourceKeys.value = [];
  }
  function removeItem(index: number) { executionItems.value.splice(index, 1); }
  function clearQueue() { executionItems.value = []; selectedSourceKeys.value = []; }
  function moveItem(index: number, offset: number) {
    const target = index + offset;
    if (target < 0 || target >= executionItems.value.length) return;
    const [item] = executionItems.value.splice(index, 1);
    executionItems.value.splice(target, 0, item);
  }
  function itemMeta(item: SourceItem) {
    if (item.type === 'api') return `${item.projectName} · ${item.stepCount} 个步骤`;
    const mode = item.runMode === 'headed' ? '有界面' : '无头';
    return `${item.projectName} · ${item.browser || 'Chrome'} ${mode} · ${item.stepCount} 个步骤`;
  }
  function goBack() { router.push({ name: 'suite_suite' }); }

  async function load() {
    try {
      const [environments, scenarios, uiCases, playwrightCases] = await Promise.all([
        environmentApi.getDataList({ pageSize: 1000 }),
        scenarioApi.getDataList({ pageSize: 1000 }),
        uiCaseApi.getDataList({ enabled: true, pageSize: 1000 }),
        playwrightCaseApi.getDataList({ enabled: true, pageSize: 1000 }),
      ]);
      environmentOptions.value = toUniqueEnvironmentOptions(environments);
      apiSources.value = asList(scenarios).map(scenarioToSource);
      uiSources.value = asList(uiCases).map(uiCaseToSource);
      playwrightSources.value = asList(playwrightCases).map(playwrightCaseToSource);
      if (!id) return;
      const data: any = await api.getDataByID(id);
      Object.assign(formValue, data);
      formValue.schedule_kind = data.schedule_kind || 'daily';
      formValue.schedule_config = {
        time: '09:00', weekdays: [1], days: [1], ...(data.schedule_config || {}),
      };
      onceAt.value = formValue.schedule_config.run_at
        ? new Date(formValue.schedule_config.run_at).getTime()
        : null;
      const plan: SuiteExecutionItem[] = data.execution_items?.length
        ? data.execution_items
        : [
            ...(data.scenarios || []).map((itemId: number) => ({ type: 'api' as const, id: itemId })),
            ...(data.ui_cases || []).map((itemId: number) => ({ type: 'ui' as const, id: itemId })),
          ];
      executionItems.value = plan
        .map((item) => sourceMap.value.get(`${item.type}-${item.id}`))
        .filter(Boolean)
        .map((item) => ({ ...(item as SourceItem) }));
    } catch (error: any) {
      message.error(error?.message || '套件数据加载失败');
    }
  }

  async function save(shouldRun: boolean) {
    const loading = shouldRun ? savingAndRunning : saving;
    try {
      await formRef.value?.validate();
      if (!executionItems.value.length) throw new Error('请至少添加一个接口场景或 UI 用例');
      if (shouldRun && formValue.run_type !== 'O') throw new Error('仅“手动执行”套件可使用保存并执行');
      if (shouldRun && !formValue.enabled) throw new Error('请先启用套件再执行');
      if (formValue.run_type === 'C') {
        if (formValue.schedule_kind === 'once' && !onceAt.value) throw new Error('请选择一次性执行时间');
        if (formValue.schedule_kind === 'weekly' && !formValue.schedule_config?.weekdays?.length) throw new Error('请至少选择一个执行星期');
        if (formValue.schedule_kind === 'monthly' && !formValue.schedule_config?.days?.length) throw new Error('请至少选择一个执行日期');
      }
      loading.value = true;
      const payload = {
        name: formValue.name, description: formValue.description,
        environment: formValue.environment, run_type: formValue.run_type,
        cron: formValue.cron, hook_key: formValue.hook_key,
        schedule_kind: formValue.schedule_kind,
        schedule_config: {
          ...formValue.schedule_config,
          ...(formValue.schedule_kind === 'once' && onceAt.value
            ? { run_at: new Date(onceAt.value).toISOString() }
            : {}),
        },
        schedule_timezone: formValue.schedule_timezone,
        execution_timeout: formValue.execution_timeout, enabled: formValue.enabled,
      };
      const saved: any = id ? await api.update(id, payload as any) : await api.createData(payload as any);
      await api.syncExecutionItems(saved.id, executionItems.value.map((item) => ({ type: item.type, id: item.id })));
      if (shouldRun) {
        const result: any = await api.runById(saved.id);
        message.success(`套件已保存，执行任务 ${result.result_id} 已提交`);
        router.push({ name: 'suite_report', params: { id: result.result_id } });
        return;
      }
      message.success('套件保存成功');
      redirectAfterSubmit({ name: 'suite_suite' });
    } catch (error: any) {
      message.error(error?.message || '保存失败，请检查配置');
    } finally {
      loading.value = false;
    }
  }

  onMounted(load);
</script>

<style scoped lang="less">
  .suite-editor-page { min-height: 100%; padding: 18px 28px 92px; background: #f6f8fb; color: #1d2738; }
  .page-header { display: flex; align-items: flex-end; justify-content: space-between; max-width: 1540px; margin: 0 auto 16px; }
  .breadcrumb { display: flex; gap: 10px; align-items: center; margin-bottom: 14px; color: #7b8798; font-size: 13px; }
  .breadcrumb i { color: #aab3c0; font-style: normal; }.breadcrumb strong { color: #344054; }
  .title-line { display: flex; gap: 20px; align-items: baseline; }.title-line h1 { margin: 0; color: #172033; font-size: 25px; font-weight: 750; }
  .title-line p { margin: 0; color: #6f7d90; font-size: 14px; }
  .editor-form { max-width: 1540px; margin: 0 auto; }
  .basic-section, .orchestration-section { border: 1px solid #dfe5ed; border-radius: 11px; background: #fff; box-shadow: 0 2px 8px rgba(20, 38, 63, .025); }
  .basic-section { margin-bottom: 14px; padding: 18px 20px 8px; }.basic-section h2, .section-heading h2 { margin: 0; color: #1d2738; font-size: 18px; font-weight: 720; }
  .basic-grid { display: grid; grid-template-columns: 1.25fr 1.05fr .9fr 1.75fr 90px; gap: 16px 28px; margin-top: 15px; }
  .secondary-grid { display: flex; gap: 20px; align-items: flex-start; }.secondary-grid :deep(.n-form-item) { width: 260px; }
  .enabled-field :deep(.n-form-item-blank) { align-items: center; }.basic-section :deep(.n-form-item-label) { color: #3f4a5c; font-weight: 600; }
  .basic-section :deep(.n-input), .basic-section :deep(.n-base-selection), .basic-section :deep(.n-input-number) { min-height: 42px; }
  .schedule-config-card { margin: 12px 0 10px; border: 1px solid #dce5f1; border-radius: 9px; overflow: hidden; background: #fbfdff; }
  .schedule-heading { display: flex; align-items: center; justify-content: space-between; min-height: 66px; padding: 0 16px; border-bottom: 1px solid #e4ebf4; background: #fff; }
  .schedule-heading h3 { margin: 0 0 5px; color: #26344a; font-size: 15px; }.schedule-heading p { margin: 0; color: #8190a5; font-size: 12px; }
  .schedule-kind-row { display: flex; gap: 12px; align-items: center; padding: 16px; border-bottom: 1px solid #e8eef6; }.schedule-kind-row > span, .schedule-fields > label > span, .schedule-check-field > span { flex: none; color: #4e5e73; font-size: 13px; font-weight: 650; }.schedule-kind-select { width: 190px; }.schedule-kind-row p { margin: 0; color: #8190a5; font-size: 12px; }
  .schedule-fields { display: flex; flex-wrap: wrap; gap: 14px 24px; align-items: flex-start; padding: 16px; }.schedule-fields > label { display: flex; gap: 10px; align-items: center; }.schedule-fields > label :deep(.n-input), .schedule-fields > label :deep(.n-base-selection), .schedule-fields > label :deep(.n-date-picker) { width: 220px; }
  .schedule-fields .cron-input { min-width: 480px; }.schedule-fields .cron-input :deep(.n-input) { width: 360px; }.timezone-field { margin-left: auto; }.schedule-multi-field :deep(.n-base-selection) { width: 360px !important; }
  .schedule-tip { align-self: center; margin: 0; color: #8190a5; font-size: 12px; }.schedule-preview { display: flex; flex-wrap: wrap; gap: 8px 26px; align-items: center; min-height: 47px; padding: 0 16px; border-top: 1px solid #e4ebf4; color: #718097; font-size: 12px; background: #f4f8ff; }.schedule-preview strong { color: #455772; font-weight: 650; }.schedule-preview code { padding: 3px 6px; border-radius: 3px; color: #246ee1; background: #e6f0ff; }
  .orchestration-section { padding: 18px 20px 20px; }.section-heading { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 14px; }
  .heading-copy { display: flex; gap: 18px; align-items: baseline; }.heading-copy p { margin: 0; color: #7a8798; font-size: 13px; }
  .count-badges { display: flex; gap: 10px; }.count-badge { display: inline-flex; gap: 8px; align-items: center; height: 34px; padding: 0 13px; border: 1px solid; border-radius: 6px; font-size: 13px; font-weight: 650; }
  .count-badge b { min-width: 18px; text-align: center; }.count-badge.api { border-color: #bdd6ff; color: #1769e8; background: #f5f9ff; }.count-badge.ui { border-color: #dec8ff; color: #7638db; background: #fbf8ff; }.count-badge.playwright { border-color: #bce6d5; color: #0b8a58; background: #f2fcf7; }
  .orchestration-grid { display: grid; grid-template-columns: minmax(390px, 37%) minmax(0, 1fr); min-height: 475px; border: 1px solid #dde4ed; border-radius: 9px; overflow: hidden; }
  .source-panel { display: flex; min-width: 0; flex-direction: column; border-right: 1px solid #dde4ed; background: #fff; }.source-panel h3, .queue-head h3 { margin: 0; color: #273245; font-size: 16px; font-weight: 700; }
  .source-panel > h3 { padding: 17px 16px 9px; }.source-tabs { display: grid; grid-template-columns: repeat(3, 1fr); padding: 0 14px; border-bottom: 1px solid #e5e9f0; }
  .source-tabs button { display: flex; gap: 8px; align-items: center; justify-content: center; height: 46px; border: 0; border-bottom: 2px solid transparent; color: #344054; font-size: 14px; font-weight: 650; background: transparent; cursor: pointer; }
  .source-tabs button.active { border-bottom-color: #2475ef; color: #1769e8; }.source-filters { display: grid; grid-template-columns: .85fr 1.15fr; gap: 10px; padding: 13px 14px; }
  .source-table-head { display: grid; grid-template-columns: minmax(0, 1fr) 110px 52px; padding: 0 16px 8px 77px; color: #7d8999; font-size: 12px; }
  .source-list { min-height: 270px; max-height: 345px; overflow: auto; border-top: 1px solid #edf0f4; }.source-list :deep(.n-empty) { padding: 70px 0; }
  .source-row { display: grid; grid-template-columns: 22px 28px minmax(0, 1fr) 110px 38px; gap: 8px; align-items: center; min-height: 49px; padding: 0 14px; border-bottom: 1px solid #edf0f4; cursor: pointer; }
  .source-row:hover { background: #f8faff; }.source-row.added { color: #9ba5b3; background: #fafbfc; cursor: default; }.mini-type { display: grid; width: 24px; height: 24px; place-items: center; border-radius: 5px; }
  .mini-type.api { color: #1769e8; background: #edf5ff; }.mini-type.ui { color: #7638db; background: #f5edff; }.source-name, .source-project { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .source-name { color: #263246; font-size: 13px; font-weight: 600; }.source-row.added .source-name { color: #8e99a8; }.source-project { color: #66758a; font-size: 12px; }.source-count { color: #344054; font-size: 13px; text-align: center; }
  .add-button { height: 42px; margin: auto 14px 14px; }.queue-panel { display: flex; min-width: 0; flex-direction: column; padding: 12px 14px; background: #fbfcfe; }.queue-head { display: flex; align-items: center; justify-content: space-between; min-height: 40px; }
  .queue-list { display: flex; min-height: 0; flex-direction: column; gap: 8px; }.queue-item { display: grid; grid-template-columns: 30px 40px auto minmax(0, 1fr) auto; gap: 10px; align-items: center; min-height: 58px; padding: 0 13px 0 8px; border: 1px solid #dce3ec; border-radius: 7px; background: #fff; transition: border-color .15s, box-shadow .15s; }
  .queue-item:hover { border-color: #a9c9fb; box-shadow: 0 3px 10px rgba(40, 104, 205, .07); }.queue-ghost { border: 1px dashed #2475ef; background: #edf5ff; opacity: .7; }.drag-handle { display: grid; width: 30px; height: 40px; place-items: center; border: 0; color: #909cac; font-size: 18px; background: transparent; cursor: grab; }.drag-handle:active { cursor: grabbing; }
  .sequence { color: #253044; font-size: 16px; font-weight: 720; }.type-badge { display: inline-flex; gap: 6px; align-items: center; height: 30px; padding: 0 10px; border: 1px solid; border-radius: 6px; font-size: 13px; font-weight: 650; }.type-badge.api { border-color: #bfd6ff; color: #1769e8; background: #f4f8ff; }.type-badge.ui { border-color: #dec8ff; color: #7638db; background: #fbf8ff; }
  .queue-copy { display: flex; min-width: 0; gap: 18px; align-items: baseline; }.queue-copy strong { overflow: hidden; color: #202b3d; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }.queue-copy span { overflow: hidden; color: #738096; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }.queue-actions { display: flex; gap: 8px; align-items: center; white-space: nowrap; }.queue-empty { padding: 100px 0; }
  .execution-rule { display: flex; gap: 10px; align-items: center; min-height: 48px; margin-top: auto; padding: 0 14px; border: 1px solid #d8e8ff; border-radius: 7px; color: #3672c8; font-size: 12px; background: #eff6ff; }.execution-rule > .n-icon { flex: none; color: #1769e8; font-size: 22px; }
  .sticky-actions { position: fixed; z-index: 12; right: 0; bottom: 0; left: 0; display: flex; gap: 12px; align-items: center; justify-content: flex-end; padding: 12px 34px; border-top: 1px solid #dfe5ed; background: rgba(255, 255, 255, .96); box-shadow: 0 -4px 18px rgba(31, 48, 73, .05); backdrop-filter: blur(8px); }.sticky-actions .n-button { min-width: 140px; }
  @media (max-width: 1180px) { .basic-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.enabled-field { grid-column: span 2; }.orchestration-grid { grid-template-columns: 1fr; }.source-panel { border-right: 0; border-bottom: 1px solid #dde4ed; }.source-list { max-height: 260px; }.queue-panel { min-height: 440px; } }
  @media (max-width: 720px) { .suite-editor-page { padding: 14px 14px 90px; }.page-header, .title-line, .section-heading, .heading-copy { align-items: flex-start; flex-direction: column; }.page-header { gap: 14px; }.basic-grid { grid-template-columns: 1fr; }.enabled-field { grid-column: auto; }.secondary-grid { flex-direction: column; }.secondary-grid :deep(.n-form-item) { width: 100%; }.schedule-kind-row, .schedule-fields, .schedule-fields > label { align-items: flex-start; flex-direction: column; }.schedule-kind-row { gap: 10px; }.schedule-kind-select { width: 100%; }.schedule-fields .cron-input, .schedule-fields .cron-input :deep(.n-input), .schedule-fields > label :deep(.n-input), .schedule-fields > label :deep(.n-base-selection), .schedule-fields > label :deep(.n-date-picker), .schedule-multi-field :deep(.n-base-selection) { width: 100% !important; min-width: 0; }.timezone-field { margin-left: 0; }.orchestration-grid { grid-template-columns: minmax(0, 1fr); }.queue-item { grid-template-columns: 28px 34px auto minmax(0, 1fr); }.queue-actions { grid-column: 4; }.queue-copy { flex-direction: column; gap: 2px; }.sticky-actions { padding: 10px 14px; } }
</style>
