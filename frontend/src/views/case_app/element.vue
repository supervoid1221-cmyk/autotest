<template>
  <div class="element-management">
    <aside class="element-tree-panel">
      <header class="tree-heading">
        <div><h3>元素目录</h3><p>目录与接口、UI 元素共用，按项目维护</p></div>
      </header>
      <n-spin :show="treeLoading">
        <div v-if="projects.length" class="tree-content">
          <section v-for="item in projects" :key="item.id" class="project-tree-group">
            <div class="tree-project-row">
              <button
                type="button"
                class="tree-project-node"
                :class="{ active: selectedProjectId === item.id && !selectedModuleId }"
                @click="toggleProject(item)"
              >
                <span class="tree-icon">▣</span><span class="tree-label">{{ item.name }}</span>
                <span class="tree-arrow">{{ expandedProjectIds.includes(item.id) ? '−' : '＋' }}</span>
              </button>
              <button type="button" class="tree-node-add" title="新增模块" @click.stop="openModuleModal(item.id)">＋</button>
            </div>
            <template v-if="expandedProjectIds.includes(item.id)">
              <div v-for="module in projectModules(item.id)" :key="module.id" class="tree-module-row" :class="{ active: selectedModuleId === module.id }">
                <button type="button" class="tree-module-node" @click="selectModule(item, module)">
                  <span>└</span><span class="tree-label">{{ module.name }}</span><span class="tree-count">{{ module.app_element_count || 0 }}</span>
                </button>
                <button type="button" title="编辑模块" @click.stop="openModuleModal(item.id, module)">✎</button>
                <button type="button" title="删除模块" @click.stop="removeModule(module)">×</button>
              </div>
              <div v-if="!projectModules(item.id).length" class="tree-empty module-empty">暂无模块</div>
            </template>
          </section>
        </div>
        <n-empty v-else description="暂无可访问项目" class="tree-empty-state" />
      </n-spin>
    </aside>

    <section class="element-table-panel">
      <n-card :bordered="true" class="proCard element-table-card">
        <header class="element-list-header">
          <div class="list-title-block"><h3>{{ tableTitle }}</h3><span>共 {{ elementTotal }} 个元素</span></div>
          <n-space>
            <n-button @click="router.push({ name: 'case_app_inspector' })">元素检查</n-button>
            <n-button :disabled="!selectedProjectId" @click="openModuleModal(selectedProjectId)">新增模块</n-button>
            <n-button type="primary" :disabled="!selectedProjectId" @click="addElement">添加元素</n-button>
          </n-space>
        </header>
        <div class="element-list-toolbar">
          <n-input v-model:value="keyword" clearable placeholder="搜索元素名称、页面或定位表达式" class="element-search" @keyup.enter="applyFilters" @clear="applyFilters" />
          <n-select v-model:value="applicationFilter" :options="applicationOptions" class="application-filter" placeholder="全部应用" clearable @update:value="applyFilters" />
          <n-select v-model:value="locatorFilter" :options="locatorOptions" class="locator-filter" @update:value="applyFilters" />
          <div class="selection-actions"><span>已选择 {{ checkedRowKeys.length }} 项</span><n-button text type="primary" :disabled="!checkedRowKeys.length" @click="checkedRowKeys = []">清空选择</n-button></div>
        </div>
        <BasicTable
          ref="tableRef"
          :columns="columns"
          :request="loadTable"
          :row-key="(row) => row.id"
          :action-column="actionColumn"
          :checked-row-keys="checkedRowKeys"
          :scroll-x="1460"
          @update:checked-row-keys="checkedRowKeys = $event"
        />
      </n-card>
    </section>

    <n-modal
      v-model:show="moduleModalVisible"
      preset="dialog"
      :title="moduleForm.id ? '重命名模块' : '添加模块'"
      positive-text="确定"
      negative-text="取消"
      :positive-button-props="{ loading: moduleSaving }"
      @positive-click="saveModule"
    >
      <n-form label-placement="top"><n-form-item label="模块名称" required><n-input v-model:value="moduleForm.name" maxlength="64" placeholder="例如：登录模块" @keyup.enter="saveModule" /></n-form-item></n-form>
    </n-modal>

    <ModuleDeleteDialog v-model:show="deleteModuleVisible" :module="deletingModule" @deleted="handleModuleDeleted" />
  </div>
</template>

<script setup lang="ts">
import { asList } from '@/utils/list';

import { computed, h, onMounted, reactive, ref } from 'vue';
import { NButton, NTag, useDialog, useMessage } from 'naive-ui';
import { useRouter } from 'vue-router';
import { BasicTable } from '@/components/Table';
import { ModuleAPI, ProjectAPI } from '@/api/project/http';
import type { Module } from '@/api/project/models';
import { AppTestAPI, type AppApplication, type AppElement } from '@/api/case_app/http';
import ModuleDeleteDialog from '@/views/case_shared/ModuleDeleteDialog.vue';

const router = useRouter();
const dialog = useDialog();
const message = useMessage();
const projectApi = new ProjectAPI();
const moduleApi = new ModuleAPI();
const tableRef = ref<any>();
const projects = ref<any[]>([]);
const applications = ref<AppApplication[]>([]);
// 模块与接口管理、UI 元素管理共用同一份数据，不再按应用隔离。
const modules = ref<Module[]>([]);
const treeLoading = ref(false);
const selectedProjectId = ref<number | null>(null);
const selectedModuleId = ref<number | null>(null);
const expandedProjectIds = ref<number[]>([]);
const moduleModalVisible = ref(false);
const moduleSaving = ref(false);
const moduleForm = reactive<{ id?: number; project: number | null; name: string }>({ project: null, name: '' });
const deleteModuleVisible = ref(false);
const deletingModule = ref<Module | null>(null);
const keyword = ref('');
const applicationFilter = ref<number | null>(null);
const locatorFilter = ref('');
const elementTotal = ref(0);
const checkedRowKeys = ref<number[]>([]);

const locatorOptions = [
  { label: '全部定位方式', value: '' },
  { label: 'Accessibility ID', value: 'accessibility id' },
  { label: 'Resource ID', value: 'id' },
  { label: '文本', value: 'text' },
  { label: 'UIAutomator', value: '-android uiautomator' },
  { label: 'XPath', value: 'xpath' },
  { label: '坐标', value: 'coordinate' },
  { label: 'OCR 文字', value: 'ocr_text' },
  { label: '图像文字', value: 'image_text' },
];
const locatorLabels: Record<string, string> = Object.fromEntries(locatorOptions.map((item) => [item.value, item.label]));
const locatorTones: Record<string, string> = {
  'accessibility id': 'blue',
  id: 'green',
  text: 'amber',
  '-android uiautomator': 'teal',
  xpath: 'purple',
  coordinate: 'neutral',
  ocr_text: 'green',
  image_text: 'pink',
};
const selectedProject = computed(() => projects.value.find((item) => item.id === selectedProjectId.value));
const selectedModule = computed(() => modules.value.find((item) => item.id === selectedModuleId.value));
const selectedApplication = computed(() => applications.value.find((item) => item.id === applicationFilter.value));
const tableTitle = computed(() => {
  const parts = [selectedProject.value?.name, selectedApplication.value?.name, selectedModule.value?.name].filter(Boolean);
  return parts.length ? `元素列表 · ${parts.join(' / ')}` : '元素列表';
});

const columns: any[] = [
  { type: 'selection', width: 44 },
  { title: '元素名称', key: 'name', width: 210, render: (row: AppElement) => h('button', { class: 'element-name-link', type: 'button', onClick: () => editElement(row) }, row.name) },
  { title: '所属应用', key: 'application_name', width: 170, render: (row: AppElement) => row.application_name || '项目通用' },
  { title: '模块', key: 'module_name', width: 140, render: (row: AppElement) => row.module_name || '未分组' },
  { title: '页面', key: 'page_name', width: 150, render: (row: AppElement) => row.page_name || '-' },
  { title: 'Activity', key: 'activity', width: 220, ellipsis: { tooltip: true }, render: (row: AppElement) => row.activity || '-' },
  { title: '定位方式', key: 'locator_type', width: 176, render: (row: AppElement) => { const label = locatorLabels[row.locator_type] || row.locator_type; return h(NTag, { bordered: false, class: ['locator-type-tag', `tone-${locatorTones[row.locator_type] || 'neutral'}`], title: label }, { default: () => label }); } },
  { title: '定位表达式', key: 'locator_value', width: 310, ellipsis: { tooltip: true }, render: (row: AppElement) => h('code', { class: 'locator-expression' }, row.locator_value || '-') },
  { title: '创建人', key: 'created_by_name', width: 110, render: (row: any) => row.created_by_name || '-' },
];
const actionColumn = reactive({
  width: 164, title: '操作', key: 'action', fixed: 'right', align: 'center',
  render: (row: AppElement) => h('div', { class: 'row-actions' }, [
    h(NButton, { text: true, type: 'primary', onClick: () => editElement(row) }, { default: () => '编辑' }),
    h(NButton, { text: true, onClick: () => copyElement(row) }, { default: () => '复制' }),
    h(NButton, { text: true, type: 'error', onClick: () => removeElement(row) }, { default: () => '删除' }),
  ]),
});

const projectModules = (projectId: number) => modules.value.filter((item) => item.project === projectId);
const applicationOptions = computed(() =>
  applications.value
    .filter((item) => item.project === selectedProjectId.value)
    .map((item) => ({ label: item.name, value: Number(item.id) }))
);
function reloadTable() { checkedRowKeys.value = []; tableRef.value?.reload?.(); }
function applyFilters() { reloadTable(); }
function toggleProject(project: any) {
  selectedProjectId.value = project.id; selectedModuleId.value = null; applicationFilter.value = null;
  expandedProjectIds.value = expandedProjectIds.value.includes(project.id)
    ? expandedProjectIds.value.filter((id) => id !== project.id) : [...expandedProjectIds.value, project.id];
  reloadTable();
}
function selectModule(project: any, module: Module) { selectedProjectId.value = project.id; selectedModuleId.value = Number(module.id); reloadTable(); }
function addElement() { router.push({ name: 'case_app_element_edit', params: { id: 0 }, query: { project: selectedProjectId.value, application: applicationFilter.value || undefined, module: selectedModuleId.value || undefined } }); }
function editElement(row: AppElement) { router.push({ name: 'case_app_element_edit', params: { id: row.id } }); }
async function loadTable(params: any) {
  const result: any = await AppTestAPI.elements({ ...params, project: selectedProjectId.value || undefined, application: applicationFilter.value || undefined, module: selectedModuleId.value || undefined, search: keyword.value.trim() || undefined, locator_type: locatorFilter.value || undefined });
  elementTotal.value = Number(result?.itemCount ?? result?.total ?? result?.count ?? (Array.isArray(result) ? result.length : result?.list?.length || 0));
  return result;
}
function openModuleModal(projectId: number | null, module?: Module) {
  Object.assign(moduleForm, { id: module?.id, project: projectId, name: module?.name || '' });
  moduleModalVisible.value = true;
}
async function saveModule() {
  const name = moduleForm.name.trim();
  if (!moduleForm.project || !name) { message.error('请输入模块名称。'); return false; }
  moduleSaving.value = true;
  try {
    const payload = { project: Number(moduleForm.project), name };
    if (moduleForm.id) await moduleApi.update(moduleForm.id, payload);
    else await moduleApi.createData(payload);
    message.success(moduleForm.id ? '模块名称已更新。' : '模块添加成功。');
    moduleModalVisible.value = false;
    await loadTree();
    return true;
  } catch (error: any) { message.error(error?.message || '模块保存失败。'); return false; }
  finally { moduleSaving.value = false; }
}
function removeModule(module: Module) {
  deletingModule.value = module;
  deleteModuleVisible.value = true;
}
async function handleModuleDeleted() {
  if (selectedModuleId.value === deletingModule.value?.id) selectedModuleId.value = null;
  await loadTree(); reloadTable();
}
async function copyElement(row: AppElement) {
  const source = await AppTestAPI.element(Number(row.id));
  const { id: _id, created_at: _created, updated_at: _updated, created_by: _creator, created_by_name: _creatorName, project_name: _projectName, application_name: _applicationName, ...payload } = source as any;
  await AppTestAPI.saveElement({ ...payload, name: `${source.name} 副本` });
  message.success('元素已复制'); await loadTree(); reloadTable();
}
function removeElement(row: AppElement) {
  dialog.warning({ title: '删除元素', content: `确定删除元素「${row.name}」吗？`, positiveText: '删除', negativeText: '取消', onPositiveClick: async () => { await AppTestAPI.deleteElement(Number(row.id)); message.success('元素已删除'); await loadTree(); reloadTable(); } });
}
async function loadTree() {
  treeLoading.value = true;
  try {
    const [projectResult, appResult, moduleResult] = await Promise.all([projectApi.getDataList({ pageSize: 1000 }), AppTestAPI.applications({ pageSize: 1000 }), moduleApi.getDataList({ pageSize: 1000 })]);
    projects.value = asList(projectResult); applications.value = asList(appResult); modules.value = asList(moduleResult);
    if (!selectedProjectId.value && projects.value.length) selectedProjectId.value = projects.value[0].id;
    if (selectedProjectId.value && !expandedProjectIds.value.includes(selectedProjectId.value)) expandedProjectIds.value.push(selectedProjectId.value);
  } finally { treeLoading.value = false; }
}
onMounted(async () => { await loadTree(); reloadTable(); });
</script>

<style scoped lang="less">
.element-management {display:grid;grid-template-columns:248px minmax(0,1fr);align-items:start;gap:16px;padding:20px 28px 36px;background:#f6f8fb;min-height:100%}
.element-tree-panel {min-height:570px;overflow:hidden;border:1px solid #e5eaf1;border-radius:8px;background:#fff}
.tree-heading {padding:17px 16px 13px;border-bottom:1px solid #edf1f5}
.tree-heading h3 {margin:0;color:#26344a;font-size:16px;font-weight:650}
.tree-heading p {margin:6px 0 0;color:#94a0b1;font-size:12px;line-height:1.5}
.tree-content {padding:10px 8px 14px}
.project-tree-group+.project-tree-group {margin-top:8px}
.tree-project-node {display:flex;width:100%;gap:6px;align-items:center;min-height:36px;padding:0 8px;border:0;border-radius:5px;color:#334155;background:transparent;text-align:left;cursor:pointer;transition:background .16s,color .16s}
.tree-project-node {font-size:13px;font-weight:600;background:#f7faff}
.tree-project-node:hover {background:#f4f8fc}
.tree-project-node.active {color:#2578dc;background:#eaf3ff}
.tree-node-add {display:grid;flex:none;width:24px;height:28px;padding:0;border:0;border-radius:4px;color:#8190a4;background:transparent;cursor:pointer;place-items:center}
.tree-node-add:hover {color:#2475ef;background:#eaf3ff}
.tree-icon, .tree-branch {width:15px;color:#8da0b7;text-align:center}
.tree-label {overflow:hidden;flex:1;text-overflow:ellipsis;white-space:nowrap}
.tree-arrow, .tree-count {color:#9ba8b9;font-size:12px}
.tree-module-row {display:flex;align-items:center;margin-left:32px;border-radius:5px}
.tree-module-row.active {color:#2578dc;background:#eef5ff}
.tree-module-node {display:flex;min-width:0;flex:1;gap:7px;align-items:center;height:32px;padding:0 5px;border:0;color:inherit;background:transparent;text-align:left;cursor:pointer;font-size:12px}
.tree-module-row>button:not(.tree-module-node) {width:23px;height:27px;padding:0;border:0;color:#9aa6b6;background:transparent;cursor:pointer}
.tree-module-row>button:not(.tree-module-node):hover {color:#2475ef}
.tree-empty {margin:7px 10px 7px 39px;color:#a2adbb;font-size:12px}
.module-empty {margin-left:54px}
.tree-empty-state {padding:76px 0}
.element-table-panel {min-width:0}
.element-table-card {min-height:570px;overflow:hidden}
.element-list-header {display:flex;gap:16px;align-items:center;justify-content:space-between;margin:-4px -4px 0;padding:4px 4px 16px;border-bottom:1px solid #edf1f5}
.list-title-block {display:flex;gap:10px;align-items:baseline;min-width:0}
.list-title-block h3 {overflow:hidden;margin:0;color:#26344a;font-size:16px;font-weight:650;text-overflow:ellipsis;white-space:nowrap}
.list-title-block span {color:#95a1b1;font-size:12px;white-space:nowrap}
.element-list-toolbar {display:flex;gap:10px;align-items:center;padding:14px 0 12px}
.element-search {width:min(390px,48%)}
.application-filter {width:150px}
.locator-filter {width:180px}
.selection-actions {display:flex;gap:10px;align-items:center;margin-left:auto;color:#8a96a7;font-size:12px}
.element-table-card :deep(.table-toolbar) {display:none}
.element-table-card :deep(.n-data-table) {overflow:hidden;border:1px solid #e5eaf1;border-radius:7px}
.element-table-card :deep(.n-data-table-th) {height:44px;color:#536174;background:#f7f9fc;font-size:12px;font-weight:600}
.element-table-card :deep(.n-data-table-td) {height:52px;border-color:#edf1f5}
.element-table-card :deep(.element-name-link) {max-width:100%;overflow:hidden;padding:0;border:0;color:#246fd1;background:transparent;font:inherit;font-size:14px;font-weight:550;text-align:left;text-overflow:ellipsis;white-space:nowrap;cursor:pointer}
.element-table-card :deep(.element-name-link:hover) {color:#1757a6;text-decoration:underline;text-underline-offset:3px}
.element-table-card :deep(.locator-expression) {color:#374151;font:13px ui-monospace,SFMono-Regular,Menlo,monospace}
.element-table-card :deep(.locator-type-tag) {max-width:100%;padding:0 9px;border:1px solid transparent;border-radius:5px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;font-weight:650;white-space:nowrap}
.element-table-card :deep(.locator-type-tag .n-tag__content) {overflow:hidden;text-overflow:ellipsis}
.element-table-card :deep(.locator-type-tag.tone-blue) {color:#1769e8;background:#eff6ff}
.element-table-card :deep(.locator-type-tag.tone-green) {color:#087f5b;background:#ecfdf5}
.element-table-card :deep(.locator-type-tag.tone-amber) {color:#b45309;background:#fffbeb}
.element-table-card :deep(.locator-type-tag.tone-teal) {color:#0e7490;background:#ecfeff}
.element-table-card :deep(.locator-type-tag.tone-purple) {color:#7c3aed;background:#f5f3ff}
.element-table-card :deep(.locator-type-tag.tone-neutral) {color:#526075;background:#f1f5f9}
.element-table-card :deep(.locator-type-tag.tone-pink) {color:#be185d;background:#fdf2f8}
.element-table-card :deep(.row-actions) {display:flex;justify-content:center;gap:12px;white-space:nowrap}
.tree-project-row {display:flex;align-items:center}
@media (max-width:800px) {
  .element-management {grid-template-columns:1fr;padding:16px}
  .element-tree-panel {min-height:auto}
  .element-list-header, .element-list-toolbar {align-items:stretch;flex-direction:column}
  .element-search, .application-filter, .locator-filter {width:100%}
  .selection-actions {margin-left:0}
}
</style>
