<template>
  <div class="app-case-page">
    <header class="page-header">
      <div class="heading-block">
        <div class="breadcrumb"><span>App 自动化</span><i>/</i><span>App 用例</span><i>/</i><strong>{{ form.id ? '编辑用例' : '新增用例' }}</strong></div>
        <div class="title-line"><h1>{{ form.id ? '编辑 App 用例' : '新增 App 用例' }}</h1><p>配置移动端操作步骤，严格按顺序执行</p></div>
      </div>
      <n-space><n-button size="large" @click="back">取消</n-button><n-button type="primary" size="large" :loading="saving" @click="saveAll">保存用例</n-button></n-space>
    </header>

    <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
      <section class="basic-section">
        <header class="basic-heading"><h2>基本信息</h2><n-button text type="primary" @click="basicEditing = !basicEditing">{{ basicEditing ? '完成' : '编辑' }}</n-button></header>
        <div v-if="!basicEditing" class="basic-summary">
          <div><span>用例名称</span><strong>{{ form.name || '未命名用例' }}</strong></div>
          <div><span>所属项目</span><strong>{{ projectName }}</strong></div>
          <div><span>执行环境</span><strong>{{ form.environment_name || '未选择' }}</strong></div>
          <div><span>测试应用</span><strong>{{ applicationName }}</strong></div>
          <div><span>默认设备</span><strong>{{ deviceName }}</strong></div>
          <div><span>默认超时</span><strong>{{ form.default_timeout }} ms</strong></div>
          <div><span>失败策略</span><strong>{{ form.stop_on_failure ? '失败后停止' : '继续执行' }}</strong></div>
          <div><span>状态</span><strong class="case-status" :class="{ enabled: form.enabled }">{{ form.enabled ? '已启用' : '已停用' }}</strong></div>
        </div>
        <div v-else class="basic-grid">
          <n-form-item label="用例名称" path="name"><n-input v-model:value="form.name" maxlength="96" placeholder="例如：登录并进入首页" /></n-form-item>
          <n-form-item label="所属项目" path="project"><n-select v-model:value="form.project" filterable :options="projectOptions" placeholder="请选择项目" @update:value="projectChanged" /></n-form-item>
          <n-form-item label="执行环境"><n-select v-model:value="form.environment_name" clearable :disabled="!form.project" :options="environmentNameOptions" placeholder="请选择环境" /></n-form-item>
          <n-form-item label="测试应用" path="application"><n-select v-model:value="form.application" filterable :disabled="!form.project" :options="applicationOptions" placeholder="请选择应用" @update:value="applicationChanged" /></n-form-item>
          <n-form-item label="默认设备"><n-select v-model:value="form.default_device" clearable filterable :disabled="!form.project" :options="deviceOptions" placeholder="执行时选择" /></n-form-item>
          <n-form-item label="默认超时"><n-input-number v-model:value="form.default_timeout" :min="500" :max="300000"><template #suffix>ms</template></n-input-number></n-form-item>
          <n-form-item label="失败重试"><n-input-number v-model:value="form.retry_count" :min="0" :max="10"><template #suffix>次</template></n-input-number></n-form-item>
          <n-form-item label="失败策略"><n-switch v-model:value="form.stop_on_failure" /><span class="switch-label">失败后停止</span></n-form-item>
          <n-form-item label="状态"><n-switch v-model:value="form.enabled" /><span class="switch-label">启用</span></n-form-item>
          <n-form-item label="用例描述" class="description-field"><n-input v-model:value="form.description" maxlength="500" show-count placeholder="请输入用例描述（选填）" /></n-form-item>
        </div>
      </section>
    </n-form>

    <section class="steps-section">
      <div class="section-heading">
        <div><h2>操作步骤</h2><p>按顺序执行，可拖拽调整</p></div>
        <n-space><n-button @click="router.push({ name: 'case_app_element' })">元素管理</n-button><n-button @click="router.push({ name: 'case_app_inspector' })">元素检查</n-button></n-space>
      </div>

      <div class="step-table-wrap">
        <div class="step-table-head"><span>顺序</span><span>操作方式</span><span>页面元素 / 坐标</span><span>操作值</span><span>操作</span></div>
        <draggable v-model="steps" item-key="__key" handle=".drag-handle" class="step-list" ghost-class="step-ghost">
          <template #item="{ element: step, index }">
            <div class="step-entry" :class="{ expanded: step.expanded }">
              <div class="step-row">
                <div class="order-cell">
                  <button class="drag-handle" title="拖拽调整顺序"><n-icon :component="MenuOutlined" /></button>
                  <button class="expand-button" :class="{ open: step.expanded }" title="展开高级配置" @click="step.expanded = !step.expanded"><n-icon :component="RightOutlined" /></button>
                  <strong>{{ String(index + 1).padStart(2, '0') }}</strong>
                </div>
                <div class="action-select" :class="actionTone(step.action)"><n-select v-model:value="step.action" :options="actionOptions" :consistent-menu-width="false" @update:value="actionChanged(step)" /></div>
                <n-popover v-if="needsElement(step.action)" placement="bottom-start" trigger="click" :show="activeElementPickerKey === step.__key" :style="{ width: '780px', maxWidth: 'calc(100vw - 32px)' }" @update:show="(visible) => pickerVisible(step, visible)">
                  <template #trigger><button type="button" class="element-picker-trigger" :class="{ empty: !step.element }"><span>{{ selectedElementLabel(step.element) || '选择页面元素' }}</span><span v-if="step.element" class="element-picker-clear" @click.stop="step.element = null">×</span></button></template>
                  <div class="element-picker-dropdown">
                    <header><strong>选择页面元素</strong><n-input v-model:value="elementKeyword" clearable placeholder="搜索元素名称、页面或表达式" /></header>
                    <div class="element-picker-body">
                      <aside class="element-module-sidebar">
                        <div class="module-sidebar-title">模块</div>
                        <button v-for="module in elementModuleItems" :key="String(module.value)" type="button" :class="{ active: elementModuleFilter === module.value }" @click="elementModuleFilter = module.value">
                          <span>{{ module.label }}</span><em>{{ module.count }}</em>
                        </button>
                      </aside>
                      <section class="element-results">
                        <div class="element-list-title"><strong>{{ activeModuleLabel }}</strong><span>共 {{ filteredElements.length }} 个元素</span></div>
                        <div class="element-option-list">
                          <button v-for="item in filteredElements" :key="item.id" type="button" class="element-option" :class="{ selected: step.element === item.id }" @click="selectElement(step, item)"><div><strong>{{ item.name }}</strong><span>{{ item.page_name || '未设置页面' }}</span></div><code>{{ locatorLabel(item.locator_type) }}</code><p>{{ item.locator_value }}</p></button>
                          <n-empty v-if="!filteredElements.length" size="small" description="当前模块暂无匹配元素" />
                        </div>
                      </section>
                    </div>
                  </div>
                </n-popover>
                <n-input v-else-if="step.action === 'swipe'" v-model:value="step.targetText" class="table-input" placeholder="起点x,起点y,终点x,终点y" />
                <span v-else class="empty-cell">——</span>
                <n-input v-if="needsValue(step.action)" v-model:value="step.value" :placeholder="valuePlaceholder(step.action)" class="table-input" />
                <span v-else class="empty-cell">——</span>
                <div class="row-actions"><n-button text title="复制步骤" @click="duplicateStep(index)"><n-icon :component="CopyOutlined" /></n-button><n-button text type="error" title="删除步骤" @click="removeStep(index)"><n-icon :component="DeleteOutlined" /></n-button></div>
              </div>
              <div v-if="step.expanded" class="advanced-row">
                <div class="advanced-title">高级配置<span>仅影响当前步骤</span></div>
                <label><span>查找超时</span><n-input-number v-model:value="step.options.timeout" :min="500" :max="300000" placeholder="跟随用例" /><em>ms</em></label>
                <n-checkbox v-model:checked="step.options.screenshot">执行后截图</n-checkbox>
                <n-checkbox v-model:checked="step.continue_on_failure">失败后继续执行</n-checkbox>
              </div>
            </div>
          </template>
        </draggable>
        <n-empty v-if="!steps.length" description="当前用例暂无操作步骤" class="step-empty" />
        <button class="add-step" @click="addStep"><n-icon :component="PlusOutlined" />添加操作步骤</button>
      </div>
      <div class="execution-rule"><n-icon :component="PlayCircleOutlined" /><span><strong>执行规则：</strong>步骤按从上到下的顺序执行；失败时按用例策略或当前步骤配置处理。</span></div>
    </section>

    <footer class="sticky-actions"><n-button size="large" @click="back">取消</n-button><n-button type="primary" size="large" :loading="starting" @click="saveAndRun">立即执行</n-button></footer>
  </div>
</template>

<script setup lang="ts">
import { asList } from '@/utils/list';

defineOptions({ name: 'case_app_case_edit' });

import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useMessage } from 'naive-ui';
import draggable from 'vuedraggable';
import { CopyOutlined, DeleteOutlined, MenuOutlined, PlusOutlined, PlayCircleOutlined, RightOutlined } from '@vicons/antd';
import { EnvironmentAPI, ModuleAPI, ProjectAPI } from '@/api/project/http';
import type { Module } from '@/api/project/models';
import { AppTestAPI, type AppApplication, type AppCase, type AppDevice, type AppElement, type AppStep } from '@/api/case_app/http';
import { useSubmitRedirect } from '@/hooks/web/useSubmitRedirect';
import { environmentOptionsForProject } from '@/views/case_shared/catalog';

const route = useRoute();
const router = useRouter();
const { redirectAfterSubmit } = useSubmitRedirect();
const message = useMessage();
const projectApi = new ProjectAPI();
const environmentApi = new EnvironmentAPI();
const moduleApi = new ModuleAPI();
const formRef = ref<any>();
const saving = ref(false);
const starting = ref(false);
const basicEditing = ref(!Number(route.params.id));
const projects = ref<any[]>([]);
const environments = ref<any[]>([]);
const applications = ref<AppApplication[]>([]);
const devices = ref<AppDevice[]>([]);
const elements = ref<AppElement[]>([]);
const elementModules = ref<Module[]>([]);
const steps = ref<any[]>([]);
const activeElementPickerKey = ref('');
const elementKeyword = ref('');
const elementModuleFilter = ref<number | 'unassigned' | null>(null);
const form = reactive<AppCase>({ project: null, application: null, default_device: null, name: '', description: '', environment_name: '', default_timeout: 10000, stop_on_failure: true, retry_count: 0, enabled: true });

const rules = { project: { required: true, type: 'number', message: '请选择项目', trigger: 'change' }, application: { required: true, type: 'number', message: '请选择测试应用', trigger: 'change' }, name: { required: true, message: '请输入用例名称', trigger: 'blur' } };
const projectOptions = computed(() => projects.value.map((item) => ({ label: item.name, value: Number(item.id) })));
const environmentNameOptions = computed(() => environmentOptionsForProject(environments.value, form.project).map((option) => ({ label: option.label, value: option.label })));
const applicationOptions = computed(() => applications.value.map((item) => ({ label: item.name, value: Number(item.id) })));
const deviceOptions = computed(() => devices.value.map((item) => ({ label: item.name, value: Number(item.id), disabled: item.state === 'offline' })));
const projectName = computed(() => projects.value.find((item) => item.id === form.project)?.name || '-');
const applicationName = computed(() => applications.value.find((item) => item.id === form.application)?.name || '-');
const deviceName = computed(() => devices.value.find((item) => item.id === form.default_device)?.name || '执行时选择');
const selectableElements = computed(() => elements.value.filter((item) => !item.application || item.application === form.application));
const elementModuleItems = computed(() => [
  { label: '全部元素', value: null as number | 'unassigned' | null, count: selectableElements.value.length },
  ...elementModules.value.filter((item) => item.project === form.project).map((item) => ({ label: item.name, value: Number(item.id) as number | 'unassigned' | null, count: selectableElements.value.filter((element) => element.module === item.id).length })),
  { label: '未分组', value: 'unassigned' as number | 'unassigned' | null, count: selectableElements.value.filter((item) => !item.module).length },
]);
const activeModuleLabel = computed(() => elementModuleItems.value.find((item) => item.value === elementModuleFilter.value)?.label || '全部元素');
const actionOptions = [['launch','启动应用'],['terminate','关闭应用'],['restart','重启应用'],['click','点击'],['input','输入文本'],['clear','清空输入'],['swipe','滑动'],['back','返回'],['home','Home'],['wait','固定等待'],['wait_element','等待元素'],['get_text','提取文本'],['assert_exists','断言元素存在'],['assert_text','断言文本'],['assert_attribute','断言属性'],['screenshot','截图'],['set_variable','设置变量']].map(([value, label]) => ({ value, label }));
const elementActions = ['click','input','clear','wait_element','get_text','assert_exists','assert_text','assert_attribute'];
const valueActions = ['input','wait','get_text','assert_text','assert_attribute','set_variable'];
const needsElement = (action: string) => elementActions.includes(action);
const needsValue = (action: string) => valueActions.includes(action);
const valuePlaceholder = (action: string) => action === 'wait' ? '等待秒数' : action === 'get_text' ? '保存变量名' : action === 'set_variable' ? '变量名=变量值' : action === 'assert_attribute' ? '属性名=期望值' : '操作值';
const filteredElements = computed(() => { const keyword = elementKeyword.value.trim().toLowerCase(); return selectableElements.value.filter((item) => (elementModuleFilter.value === null || (elementModuleFilter.value === 'unassigned' ? !item.module : item.module === elementModuleFilter.value)) && (!keyword || [item.name, item.module_name, item.page_name, item.locator_type, item.locator_value].some((value) => String(value || '').toLowerCase().includes(keyword)))); });
const locatorLabel = (value: string) => ({ 'accessibility id': 'A11Y', id: 'ID', text: 'TEXT', '-android uiautomator': 'UIA', xpath: 'XPATH', coordinate: 'XY', ocr_text: 'OCR', image_text: 'IMG' }[value] || value);
const selectedElementLabel = (id: number | null) => elements.value.find((item) => item.id === id)?.name || '';
const actionTone = (action: string) => ['click','input','clear'].includes(action) ? 'blue' : ['assert_exists','assert_text','assert_attribute'].includes(action) ? 'green' : ['wait','wait_element'].includes(action) ? 'orange' : ['get_text','set_variable'].includes(action) ? 'purple' : '';

function back() { router.push({ name: 'case_app_case' }); }
function actionChanged(step: any) { if (!needsElement(step.action)) step.element = null; if (step.action !== 'swipe') step.targetText = ''; if (!needsValue(step.action)) step.value = ''; }
function pickerVisible(step: any, visible: boolean) { activeElementPickerKey.value = visible ? step.__key : ''; if (visible) { elementKeyword.value = ''; elementModuleFilter.value = null; } }
function selectElement(step: any, item: AppElement) { step.element = Number(item.id); activeElementPickerKey.value = ''; }
function createStep(source: any = {}) { return { __key: source.__key || `step-${Date.now()}-${Math.random()}`, id: source.id, order: source.order || steps.value.length + 1, action: source.action || 'click', element: source.element || null, target: source.target || {}, targetText: source.targetText || '', value: source.value || '', options: { ...(source.options || {}) }, continue_on_failure: Boolean(source.continue_on_failure), expanded: Boolean(source.expanded) }; }
function addStep() { steps.value.push(createStep()); }
function removeStep(index: number) { steps.value.splice(index, 1); }
function duplicateStep(index: number) { const copy = createStep({ ...steps.value[index], id: undefined, __key: undefined, options: { ...steps.value[index].options } }); steps.value.splice(index + 1, 0, copy); }
const toEditableStep = (source: AppStep) => createStep({ ...source, targetText: source.action === 'swipe' ? [source.target?.start_x, source.target?.start_y, source.target?.end_x, source.target?.end_y].join(',') : '' });
async function loadOptions() {
  if (!form.project) { applications.value = []; devices.value = []; elements.value = []; elementModules.value = []; return; }
  const [applicationResult, deviceResult, elementResult, moduleResult] = await Promise.all([AppTestAPI.applications({ project: form.project, pageSize: 1000 }), AppTestAPI.devices({ project: form.project, pageSize: 1000 }), AppTestAPI.elements({ project: form.project, pageSize: 1000 }), moduleApi.getDataList({ project: form.project, pageSize: 1000 })]);
  applications.value = asList(applicationResult); devices.value = asList(deviceResult); elements.value = asList(elementResult); elementModules.value = asList(moduleResult);
}
function projectChanged() { form.environment_name = ''; form.application = null; form.default_device = null; steps.value.forEach((step) => step.element = null); void loadOptions(); }
function applicationChanged() { steps.value.forEach((step) => step.element = null); activeElementPickerKey.value = ''; elementModuleFilter.value = null; }
async function persistAppCase() {
  await formRef.value?.validate();
  if (!steps.value.length) throw new Error('请至少添加一个操作步骤');
  const saved = await AppTestAPI.saveCase({ ...form, name: form.name.trim() });
  const payload: AppStep[] = steps.value.map((step, index) => {
    let target = step.target || {};
    if (step.action === 'swipe' && step.targetText) {
      const values = step.targetText.split(',').map(Number);
      target = { start_x: values[0] || 0, start_y: values[1] || 0, end_x: values[2] || 0, end_y: values[3] || 0 };
    }
    return { id: typeof step.id === 'number' ? step.id : undefined, case: saved.id, order: index + 1, action: step.action, element: step.element || null, target, value: step.value || '', options: step.options || {}, continue_on_failure: Boolean(step.continue_on_failure) };
  });
  await AppTestAPI.syncSteps(Number(saved.id), payload);
  return saved;
}
async function saveAll() {
  try {
    saving.value = true;
    await persistAppCase();
    message.success('用例保存成功');
    redirectAfterSubmit({ name: 'case_app_case' });
  } catch (error: any) {
    message.error(error?.message || '保存失败');
  } finally {
    saving.value = false;
  }
}
async function saveAndRun() {
  if (!form.environment_name) return message.warning('请先选择执行环境');
  if (!form.default_device) return message.warning('请先选择默认设备');
  try {
    starting.value = true;
    const saved = await persistAppCase();
    const application = applications.value.find((item) => Number(item.id) === Number(saved.application));
    const run = await AppTestAPI.start(Number(saved.id), {
      device: saved.default_device,
      version: null,
      auto_install: Boolean(application?.auto_install),
      clear_data: Boolean(application?.clear_data),
    });
    message.success('用例已提交执行');
    router.push({ name: 'execution_report', params: { sourceType: 'app', id: run.id } });
  } catch (error: any) {
    message.error(error?.message || '用例执行失败');
  } finally {
    starting.value = false;
  }
}
onMounted(async () => { const [projectResponse, environmentResponse] = await Promise.all([projectApi.getDataList({ pageSize: 1000 }), environmentApi.getDataList({ page: 1, pageSize: 1000 })]); projects.value = asList(projectResponse); environments.value = asList(environmentResponse); const id = Number(route.params.id); if (id) { const data = await AppTestAPI.appCase(id); Object.assign(form, data); await loadOptions(); steps.value = (data.steps || []).map(toEditableStep); } });
</script>

<style scoped lang="less">
.app-case-page{min-height:100%;padding:20px 28px 92px;color:#1d2738;background:#f7f9fc}.page-header{display:flex;align-items:flex-end;justify-content:space-between;max-width:1540px;margin:0 auto 16px}.heading-block{min-width:0}.breadcrumb{display:flex;gap:10px;align-items:center;margin-bottom:14px;color:#748197;font-size:13px}.breadcrumb i{color:#aab3c0;font-style:normal}.breadcrumb strong{color:#273348}.title-line{display:flex;gap:22px;align-items:baseline}.title-line h1{margin:0;color:#172033;font-size:26px;font-weight:760}.title-line p{margin:0;color:#718096;font-size:14px}.page-header :deep(.n-button),.sticky-actions :deep(.n-button){min-width:112px;height:44px;border-radius:7px}.basic-section,.steps-section{max-width:1540px;margin:0 auto 14px;border:1px solid #dfe5ed;border-radius:9px;background:#fff;box-shadow:0 2px 8px rgba(24,43,72,.025)}.basic-section{padding:0;overflow:hidden}.basic-heading{display:flex;align-items:center;justify-content:space-between;min-height:54px;padding:0 22px;border-bottom:1px solid #e7ebf1}.basic-heading h2,.section-heading h2{margin:0;color:#1d2738;font-size:16px;font-weight:730}.basic-summary{display:grid;grid-template-columns:1.3fr 1fr 1fr 1.1fr .85fr 1fr .75fr;min-height:86px;padding:0 22px}.basic-summary>div{display:flex;min-width:0;flex-direction:column;justify-content:center;padding-right:20px}.basic-summary span,.basic-summary strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.basic-summary span{margin-bottom:8px;color:#8a95a6;font-size:11px}.basic-summary strong{color:#263247;font-size:13px;font-weight:650}.case-status{display:inline-flex!important;align-items:center;color:#7b8798}.case-status:before{width:7px;height:7px;margin-right:7px;border-radius:50%;background:#aab3c0;content:''}.case-status.enabled{color:#15975f}.case-status.enabled:before{background:#20b872}.basic-grid{display:grid;grid-template-columns:1.2fr 1fr 1fr 1fr .75fr .7fr .85fr .65fr;gap:0 18px;padding:18px 22px 8px}.description-field{grid-column:1/-1}.basic-section :deep(.n-form-item-label){color:#3d495a;font-size:13px;font-weight:600}.basic-section :deep(.n-input),.basic-section :deep(.n-base-selection),.basic-section :deep(.n-input-number){min-height:42px;width:100%}.switch-label{margin-left:8px;color:#64748b;font-size:13px}.steps-section{padding:18px 20px 20px;overflow-x:auto}.section-heading{display:flex;gap:20px;align-items:center;justify-content:space-between;margin-bottom:15px}.section-heading>div{display:flex;gap:18px;align-items:baseline}.section-heading p{margin:0;color:#7b8798;font-size:13px}.step-table-wrap{min-width:900px;overflow:hidden;border:1px solid #dfe5ed;border-radius:7px}.step-table-head,.step-row{display:grid;grid-template-columns:118px 160px minmax(240px,1.45fr) minmax(210px,1.25fr) 70px;gap:10px;align-items:center}.step-table-head{min-height:46px;padding:0 14px;border-bottom:1px solid #dfe5ed;color:#5e6b7e;font-size:13px;font-weight:650;background:#fafbfd}.step-table-head span:last-child{text-align:center}.step-entry{border-bottom:1px solid #e7ebf1;background:#fff}.step-entry:last-of-type{border-bottom:0}.step-entry.expanded{position:relative;z-index:1;box-shadow:inset 0 0 0 1px #7cacfb}.step-row{min-height:62px;padding:7px 14px}.step-row:hover{background:#fbfcff}.step-ghost{border:1px dashed #2475ef;background:#edf5ff;opacity:.7}.order-cell{display:flex;gap:8px;align-items:center}.order-cell strong{color:#253044;font-size:14px}.drag-handle,.expand-button{display:grid;width:25px;height:32px;padding:0;border:0;color:#98a3b2;background:transparent;cursor:pointer;place-items:center}.drag-handle{font-size:17px;cursor:grab}.expand-button{font-size:12px;transition:transform .18s}.expand-button.open{transform:rotate(90deg)}.action-select{--action-border:#d5dbe4;--action-color:#526075;--action-bg:#f7f9fb}.action-select.blue{--action-border:#b9d4ff;--action-color:#1769e8;--action-bg:#f3f8ff}.action-select.green{--action-border:#bde8d0;--action-color:#0c9b5d;--action-bg:#f1fbf6}.action-select.orange{--action-border:#ffd3ad;--action-color:#e56a16;--action-bg:#fff7ef}.action-select.purple{--action-border:#dbc7ff;--action-color:#7540d7;--action-bg:#f8f4ff}.action-select :deep(.n-base-selection){color:var(--action-color);background:var(--action-bg)}.action-select :deep(.n-base-selection__border),.action-select :deep(.n-base-selection__state-border){border-color:var(--action-border)!important}.action-select :deep(.n-base-selection-label){font-size:13px;font-weight:650}.table-input :deep(.n-input__border){border-color:transparent}.table-input:hover :deep(.n-input__border),.table-input.n-input--focus :deep(.n-input__border){border-color:#b8c8dd}.empty-cell{color:#a2adbb;text-align:center}.row-actions{display:flex;justify-content:center;gap:10px}.element-picker-trigger{display:flex;gap:8px;align-items:center;justify-content:space-between;width:100%;min-width:0;height:36px;padding:0 10px;overflow:hidden;border:1px solid transparent;border-radius:5px;color:#344054;background:transparent;cursor:pointer}.element-picker-trigger:hover{border-color:#b8c8dd;background:#f8fbff}.element-picker-trigger.empty{color:#9aa5b5}.element-picker-trigger>span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.element-picker-clear{flex:none;color:#8a96a8;font-size:18px}.element-picker-dropdown{overflow:hidden}.element-picker-dropdown header{display:flex;gap:16px;align-items:center;padding:13px 15px;border-bottom:1px solid #e8edf4}.element-picker-dropdown header strong{flex:none;color:#26344a;font-size:15px}.element-picker-dropdown header :deep(.n-input){flex:1}.element-list-title{margin:12px 15px 7px;color:#26344a;font-size:13px;font-weight:650}.element-list-title span{margin-left:7px;color:#93a0b1;font-size:11px;font-weight:400}.element-option-list{max-height:330px;overflow-y:auto;padding:0 10px 12px}.element-option{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:3px 12px;width:100%;padding:10px 11px;border:1px solid transparent;border-radius:6px;color:#344054;text-align:left;background:#fff;cursor:pointer}.element-option:hover,.element-option.selected{border-color:#b9d4ff;background:#f5f9ff}.element-option>div{display:flex;gap:8px;min-width:0;align-items:baseline}.element-option strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px}.element-option span{flex:none;color:#8d9aae;font-size:11px}.element-option code{padding:2px 5px;border-radius:3px;color:#1769e8;background:#eaf2ff;font-size:10px}.element-option p{grid-column:1/-1;margin:0;overflow:hidden;color:#7a8799;text-overflow:ellipsis;white-space:nowrap;font:11px ui-monospace,monospace}.advanced-row{display:flex;gap:24px;align-items:center;min-height:62px;padding:10px 18px 10px 132px;border-top:1px dashed #dfe5ed;background:#f9fbfd}.advanced-title{display:grid;color:#344054;font-size:13px;font-weight:650}.advanced-title span{color:#96a1b1;font-size:10px;font-weight:400}.advanced-row label{display:flex;gap:8px;align-items:center;color:#5d697b;font-size:12px}.advanced-row :deep(.n-input-number){width:140px}.advanced-row em{color:#8a96a8;font-style:normal}.step-empty{padding:44px 0}.add-step{display:flex;gap:7px;align-items:center;justify-content:center;width:100%;height:48px;border:0;border-top:1px solid #e7ebf1;color:#2475ef;background:#fafcff;cursor:pointer;font-size:13px;font-weight:650}.add-step:hover{background:#f2f7ff}.execution-rule{display:flex;gap:9px;align-items:center;margin-top:13px;padding:10px 13px;border-radius:6px;color:#66758a;background:#f6f8fb;font-size:12px}.execution-rule :deep(.n-icon){color:#2475ef;font-size:16px}.sticky-actions{position:fixed;z-index:20;right:0;bottom:0;left:0;display:flex;gap:12px;justify-content:flex-end;padding:12px 34px;border-top:1px solid #dfe5ed;background:rgba(255,255,255,.96);backdrop-filter:blur(12px)}@media(max-width:980px){.basic-summary,.basic-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.description-field{grid-column:1/-1}.title-line{display:block}.title-line p{margin-top:6px}}@media(max-width:640px){.app-case-page{padding:16px 16px 90px}.page-header{align-items:flex-start;gap:16px;flex-direction:column}.basic-summary,.basic-grid{grid-template-columns:1fr}.steps-section{padding:15px}.sticky-actions{padding:10px 16px}}
.element-picker-dropdown header{display:grid;grid-template-columns:auto minmax(240px,1fr);gap:20px;padding:15px 18px}.element-picker-dropdown header strong{flex:none}.element-picker-body{display:grid;grid-template-columns:180px minmax(0,1fr);height:390px;min-height:0}.element-module-sidebar{overflow-y:auto;padding:12px 10px;border-right:1px solid #e7ebf1;background:#f8fafc}.module-sidebar-title{padding:3px 10px 9px;color:#8a96a8;font-size:11px;font-weight:600}.element-module-sidebar button{display:flex;align-items:center;justify-content:space-between;width:100%;height:36px;padding:0 10px;border:0;border-radius:5px;color:#526075;background:transparent;cursor:pointer;font-size:13px;text-align:left;transition:background .16s,color .16s}.element-module-sidebar button:hover{background:#eef3f9}.element-module-sidebar button.active{color:#1769e8;background:#e9f2ff;font-weight:650}.element-module-sidebar button span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.element-module-sidebar button em{margin-left:8px;color:#98a4b4;font-size:11px;font-style:normal;font-variant-numeric:tabular-nums}.element-module-sidebar button.active em{color:#4f83d8}.element-results{display:flex;min-width:0;min-height:0;flex-direction:column;background:#fff}.element-results .element-list-title{display:flex;align-items:baseline;justify-content:space-between;flex:none;margin:0;padding:13px 16px 9px}.element-results .element-list-title strong{font-size:13px}.element-results .element-option-list{min-height:0;flex:1;max-height:none;padding:0 10px 12px}.element-results .element-option{padding:11px 12px}.element-results .element-option+.element-option{margin-top:2px}@media(max-width:640px){.element-picker-dropdown header{grid-template-columns:1fr;gap:10px}.element-picker-body{grid-template-columns:128px minmax(0,1fr);height:350px}.element-module-sidebar{padding:9px 6px}.element-module-sidebar button{padding:0 7px}.element-option span{max-width:110px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.basic-summary{grid-template-columns:1.3fr 1fr .9fr 1fr 1.1fr .85fr 1fr .75fr}
.basic-grid{grid-template-columns:1.2fr 1fr .9fr 1fr 1fr .75fr .7fr .85fr .65fr}
@media(max-width:980px){.basic-summary,.basic-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.basic-summary,.basic-grid{grid-template-columns:1fr}}
</style>
