<template>
  <div class="element-management">
    <aside class="element-tree-panel">
      <div class="tree-heading">
        <div><h3>元素目录</h3><p>项目名称固定，可在项目下管理模块与元素</p></div>
      </div>
      <n-spin :show="treeLoading">
        <div v-if="projects.length" class="tree-content">
          <section v-for="project in projects" :key="project.id" class="project-tree-group">
            <div class="tree-project-node" :class="{ active: selectedProjectId === project.id && !selectedModuleId }" @click="toggleProject(project)">
              <span class="tree-icon">▣</span><span class="tree-label">{{ project.name }}</span>
              <n-button text type="primary" size="tiny" @click.stop="openModuleModal(project.id)">＋ 模块</n-button>
            </div>
            <template v-if="expandedProjectIds.includes(project.id)">
              <div
                v-for="module in projectModules(project.id)"
                :key="module.id"
                class="tree-module-node"
                :class="{ active: selectedModuleId === module.id }"
                @click="selectModule(project, module)"
              >
                <span class="tree-branch">└</span><span class="tree-icon">▱</span><span class="tree-label">{{ module.name }}</span>
                <span class="tree-count">{{ module.element_count || 0 }}</span>
                <n-button text type="primary" size="tiny" class="module-add-element" @click.stop="addElementForModule(project.id, module.id)">＋ 元素</n-button>
                <n-dropdown trigger="click" placement="bottom-end" :options="moduleActionOptions" @select="(key) => handleModuleAction(key, module)">
                  <n-button text size="tiny" class="module-more" title="模块操作" @click.stop>•••</n-button>
                </n-dropdown>
              </div>
              <div v-if="!projectModules(project.id).length" class="tree-empty">暂无模块，请先添加模块</div>
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
          <n-button type="primary" :disabled="!selectedModuleId" @click="addData">添加元素</n-button>
        </header>
        <div class="element-list-toolbar">
          <n-input v-model:value="elementSearch" clearable placeholder="搜索元素名称或定位表达式" class="element-search" @keyup.enter="applyFilters" @clear="applyFilters" />
          <n-select v-model:value="locatorFilter" :options="locatorOptions" class="locator-filter" @update:value="applyFilters" />
          <div class="selection-actions">
            <span>已选择 {{ checkedRowKeys.length }} 项</span>
            <n-button text type="primary" :disabled="!checkedRowKeys.length" @click="checkedRowKeys = []">清空选择</n-button>
          </div>
        </div>
        <BasicTable
          :columns="columns"
          :request="loadDataTable"
          :row-key="(row) => row.id"
          ref="actionRef"
          :actionColumn="actionColumn"
          :checked-row-keys="checkedRowKeys"
          :scroll-x="1340"
          @update:checked-row-keys="onCheckedRow"
        />
      </n-card>
    </section>

    <n-modal
      v-model:show="moduleModalVisible"
      preset="dialog"
      :title="editingModuleId ? '重命名模块' : '添加模块'"
      positive-text="确定"
      negative-text="取消"
      :positive-button-props="{ loading: moduleSaving }"
      @positive-click="saveModule"
    >
      <n-form label-placement="top">
        <n-form-item label="模块名称" required><n-input v-model:value="moduleForm.name" placeholder="例如：登录页" maxlength="64" /></n-form-item>
      </n-form>
    </n-modal>

    <n-modal v-model:show="deleteModuleVisible" :mask-closable="false">
      <section class="delete-module-dialog">
        <header class="delete-dialog-header">
          <div><h3>删除模块</h3><p>确定删除模块「{{ deletingModule?.name }}」吗？</p></div>
          <n-button text class="dialog-close" @click="deleteModuleVisible = false">×</n-button>
        </header>
        <div class="delete-dialog-body">
          <div class="element-risk-count">该模块下共有 <strong>{{ deletingModule?.element_count || 0 }}</strong> 个元素。</div>
          <n-radio-group v-model:value="deleteMode" class="delete-mode-list">
            <label class="delete-mode-item" :class="{ selected: deleteMode === 'unassign' }">
              <n-radio value="unassign" />
              <span><strong>仅删除模块，元素移至未分组</strong><small>推荐选择，元素数据将保留，可稍后重新分配模块。</small></span>
            </label>
            <label class="delete-mode-item danger" :class="{ selected: deleteMode === 'cascade' }">
              <n-radio value="cascade" />
              <span><strong>删除模块及模块下全部元素</strong><small>元素及相关引用将被永久删除，此操作不可恢复。</small></span>
            </label>
          </n-radio-group>
          <div v-if="deleteMode === 'cascade'" class="danger-confirm-area">
            <span>请输入 <strong>确认删除</strong> 继续</span>
            <n-input v-model:value="deleteConfirmText" placeholder="确认删除" />
          </div>
        </div>
        <footer class="delete-dialog-footer">
          <n-button @click="deleteModuleVisible = false">取消</n-button>
          <n-button type="error" :loading="moduleDeleting" :disabled="deleteMode === 'cascade' && deleteConfirmText !== '确认删除'" @click="confirmDeleteModule">确认删除</n-button>
        </footer>
      </section>
    </n-modal>
  </div>
</template>

<script lang="ts" setup>
import { computed, h, onMounted, reactive, ref } from 'vue';
import { NButton, useDialog, useMessage } from 'naive-ui';
import { useRouter } from 'vue-router';
import { BasicTable } from '@/components/Table';
import { ElementAPI, ElementModuleAPI } from '@/api/case_ui/http';
import { ProjectAPI } from '@/api/project/http';
import { createElementColumns } from './elementColumns';

const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const actionRef = ref<any>();
const api = new ElementAPI();
const moduleApi = new ElementModuleAPI();
const projectApi = new ProjectAPI();
const projects = ref<any[]>([]);
const modules = ref<any[]>([]);
const treeLoading = ref(false);
const selectedProjectId = ref<number | null>(null);
const selectedModuleId = ref<number | null>(null);
const expandedProjectIds = ref<number[]>([]);
const elementSearch = ref('');
const locatorFilter = ref('');
const elementTotal = ref(0);
const checkedRowKeys = ref<number[]>([]);
const moduleModalVisible = ref(false);
const moduleSaving = ref(false);
const editingModuleId = ref<number | null>(null);
const moduleForm = reactive({ project: null as number | null, name: '' });
const deleteModuleVisible = ref(false);
const moduleDeleting = ref(false);
const deletingModule = ref<any>(null);
const deleteMode = ref<'unassign' | 'cascade'>('unassign');
const deleteConfirmText = ref('');
const moduleActionOptions = [
  { label: '重命名模块', key: 'rename' },
  { label: '删除模块', key: 'delete', props: { style: 'color:#d03050' } },
];
const locatorOptions = [
  { label: '全部定位方式', value: '' },
  ...['XPATH', 'CSS_SELECTOR', 'ID', 'NAME', 'LINK_TEXT', 'PARTIAL_LINK_TEXT', 'TAG_NAME'].map((value) => ({ label: value, value })),
];
const columns = createElementColumns((record) => handleEdit(record));
const selectedProject = computed(() => projects.value.find((item) => item.id === selectedProjectId.value));
const selectedModule = computed(() => modules.value.find((item) => item.id === selectedModuleId.value));
const tableTitle = computed(() => selectedModule.value
  ? `元素列表 · ${selectedProject.value?.name || ''} / ${selectedModule.value.name}`
  : selectedProject.value ? `元素列表 · ${selectedProject.value.name}` : '元素列表');

const actionColumn = reactive({
  width: 164, title: '操作', key: 'action', fixed: 'right', align: 'center',
  render(record) {
    return h('div', { style: 'display:flex;justify-content:center;gap:12px;white-space:nowrap' }, [
      h(NButton, { text: true, type: 'primary', onClick: () => handleEdit(record) }, { default: () => '编辑' }),
      h(NButton, { text: true, type: 'default', onClick: () => handleCopy(record) }, { default: () => '复制' }),
      h(NButton, { text: true, type: 'error', onClick: () => handleDelete(record) }, { default: () => '删除' }),
    ]);
  },
});

function asList(payload: any): any[] {
  if (Array.isArray(payload)) return payload;
  return payload?.list || payload?.results || payload?.data || [];
}
function projectModules(projectId: number) { return modules.value.filter((item) => item.project === projectId); }
function reloadTable() { actionRef.value?.reload(); }
function onCheckedRow(keys: number[]) { checkedRowKeys.value = keys; }
function applyFilters() { checkedRowKeys.value = []; reloadTable(); }
async function loadDataTable(res: any) {
  const params: Record<string, unknown> = { ...res };
  if (selectedProjectId.value) params.project = selectedProjectId.value;
  if (selectedModuleId.value) params.module = selectedModuleId.value;
  if (elementSearch.value.trim()) params.search = elementSearch.value.trim();
  if (locatorFilter.value) params.by = locatorFilter.value;
  const result: any = await api.getDataList(params);
  elementTotal.value = Number(result?.itemCount ?? result?.total ?? result?.count ?? (Array.isArray(result) ? result.length : result?.list?.length || 0));
  return result;
}
function toggleProject(project: any) {
  selectedProjectId.value = project.id; selectedModuleId.value = null;
  expandedProjectIds.value = expandedProjectIds.value.includes(project.id)
    ? expandedProjectIds.value.filter((id) => id !== project.id)
    : [...expandedProjectIds.value, project.id];
  reloadTable();
}
function selectModule(project: any, module: any) { selectedProjectId.value = project.id; selectedModuleId.value = module.id; reloadTable(); }
function addData() {
  if (!selectedProjectId.value || !selectedModuleId.value) { message.info('请先在左侧选择一个模块'); return; }
  addElementForModule(selectedProjectId.value, selectedModuleId.value);
}
function addElementForModule(projectId: number, moduleId: number) {
  router.push({ name: 'case_ui_element_edit', params: { id: 0 }, query: { project: projectId, module: moduleId } });
}
function handleEdit(record: any) { router.push({ name: 'case_ui_element_edit', params: { id: record.id } }); }
function handleDelete(record: any) {
  dialog.warning({
    title: '删除元素', content: `确定删除元素「${record.name}」吗？`, positiveText: '删除', negativeText: '取消',
    onPositiveClick: async () => { await api.DeleteDataByID(record.id); message.success('元素已删除'); await loadTree(); reloadTable(); },
  });
}
async function handleCopy(record: any) {
  try {
    const source: any = await api.getDataByID(record.id);
    await api.createData({ project: source.project, module: source.module, name: `${source.name} 副本`, by: source.by, value: source.value } as any);
    message.success('元素已复制'); await loadTree(); reloadTable();
  } catch (error: any) { message.error(error?.message || '复制失败'); }
}
function openModuleModal(projectId: number) { editingModuleId.value = null; moduleForm.project = projectId; moduleForm.name = ''; moduleModalVisible.value = true; }
function handleModuleAction(key: string, module: any) {
  if (key === 'rename') {
    editingModuleId.value = module.id; moduleForm.project = module.project; moduleForm.name = module.name; moduleModalVisible.value = true; return;
  }
  deletingModule.value = module; deleteMode.value = 'unassign'; deleteConfirmText.value = ''; deleteModuleVisible.value = true;
}
async function saveModule() {
  if (!moduleForm.project || !moduleForm.name.trim()) { message.error('请输入模块名称'); return false; }
  try {
    moduleSaving.value = true;
    const saved: any = editingModuleId.value
      ? await moduleApi.update(editingModuleId.value, { project: moduleForm.project, name: moduleForm.name.trim() })
      : await moduleApi.createData({ project: moduleForm.project, name: moduleForm.name.trim() });
    await loadTree();
    const target = modules.value.find((item) => item.id === saved.id) || saved;
    const project = projects.value.find((item) => item.id === moduleForm.project);
    selectModule(project, target); message.success(editingModuleId.value ? '模块名称已更新' : '模块已添加'); return true;
  } catch (error: any) { message.error(error?.message || '模块保存失败'); return false; }
  finally { moduleSaving.value = false; }
}
async function confirmDeleteModule() {
  if (!deletingModule.value?.id) return false;
  try {
    moduleDeleting.value = true;
    const result = await moduleApi.deleteModule(deletingModule.value.id, deleteMode.value === 'cascade');
    if (selectedModuleId.value === deletingModule.value.id) { selectedModuleId.value = null; selectedProjectId.value = deletingModule.value.project; }
    deleteModuleVisible.value = false; await loadTree(); reloadTable(); message.success(result?.detail || '模块已删除'); return true;
  } catch (error: any) { message.error(error?.message || '模块删除失败'); return false; }
  finally { moduleDeleting.value = false; }
}
async function loadTree() {
  try {
    treeLoading.value = true;
    const [projectResponse, moduleResponse] = await Promise.all([
      projectApi.getDataList({ pageSize: 1000 }), moduleApi.getDataList({ pageSize: 1000 }),
    ]);
    projects.value = asList(projectResponse); modules.value = asList(moduleResponse);
    if (!selectedProjectId.value && projects.value.length) selectedProjectId.value = projects.value[0].id;
    if (selectedProjectId.value && !expandedProjectIds.value.includes(selectedProjectId.value)) expandedProjectIds.value.push(selectedProjectId.value);
  } finally { treeLoading.value = false; }
}
onMounted(async () => { await loadTree(); reloadTable(); });
</script>

<style scoped lang="less">
.element-management { display: grid; grid-template-columns: 248px minmax(0, 1fr); align-items: start; gap: 16px; }
.element-tree-panel { min-height: 540px; overflow: hidden; border: 1px solid #e5eaf1; border-radius: 8px; background: #fff; }.tree-heading { padding: 17px 16px 13px; border-bottom: 1px solid #edf1f5; }.tree-heading h3 { margin: 0; color: #26344a; font-size: 16px; font-weight: 650; }.tree-heading p { margin: 6px 0 0; color: #94a0b1; font-size: 12px; line-height: 1.5; }
.tree-content { padding: 10px 8px 14px; }.project-tree-group + .project-tree-group { margin-top: 8px; }.tree-project-node, .tree-module-node { display: flex; gap: 6px; align-items: center; min-height: 36px; padding: 0 8px; border-radius: 5px; cursor: pointer; transition: background .16s, color .16s; }.tree-project-node { color: #334155; font-size: 13px; font-weight: 600; background: #f7faff; }.tree-module-node { margin-left: 15px; color: #536276; font-size: 13px; }.tree-project-node:hover, .tree-module-node:hover { background: #f4f8fc; }.tree-project-node.active, .tree-module-node.active { color: #2578dc; background: #eaf3ff; }
.tree-icon, .tree-branch { width: 15px; color: #8da0b7; text-align: center; }.tree-label { overflow: hidden; flex: 1; text-overflow: ellipsis; white-space: nowrap; }.tree-count { min-width: 16px; color: #9ba8b9; font-size: 11px; text-align: center; }.module-add-element { white-space: nowrap; }.module-more { width: 24px; min-width: 24px; color: #8593a6; letter-spacing: -1px; }.tree-empty { margin: 6px 10px 6px 39px; color: #a2adbb; font-size: 12px; }.tree-empty-state { padding: 76px 0; }
.element-table-panel { min-width: 0; }.element-table-card { min-height: 540px; overflow: hidden; }.element-list-header { display: flex; gap: 16px; align-items: center; justify-content: space-between; margin: -4px -4px 0; padding: 4px 4px 16px; border-bottom: 1px solid #edf1f5; }.list-title-block { display: flex; gap: 10px; align-items: baseline; min-width: 0; }.list-title-block h3 { overflow: hidden; margin: 0; color: #26344a; font-size: 16px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }.list-title-block span { color: #95a1b1; font-size: 12px; white-space: nowrap; }
.element-list-toolbar { display: flex; gap: 10px; align-items: center; padding: 14px 0 12px; }.element-search { width: min(380px, 48%); }.locator-filter { width: 180px; }.selection-actions { display: flex; gap: 10px; align-items: center; margin-left: auto; color: #8a96a7; font-size: 12px; }.element-table-card :deep(.table-toolbar) { display: none; }.element-table-card :deep(.n-data-table) { overflow: hidden; border: 1px solid #e5eaf1; border-radius: 7px; }.element-table-card :deep(.n-data-table-th) { height: 44px; color: #536174; background: #f7f9fc; font-size: 12px; font-weight: 600; }.element-table-card :deep(.n-data-table-td) { height: 52px; border-color: #edf1f5; }.element-table-card :deep(.element-name-link) { max-width: 100%; overflow: hidden; padding: 0; border: 0; color: #246fd1; background: transparent; font: inherit; font-size: 14px; font-weight: 550; text-align: left; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }.element-table-card :deep(.element-name-link:hover) { color: #1757a6; text-decoration: underline; text-underline-offset: 3px; }.element-table-card :deep(.locator-expression) { color: #374151; font: 13px 'JetBrains Mono', monospace; }
.delete-module-dialog { width: min(520px, calc(100vw - 32px)); overflow: hidden; border-radius: 9px; background: #fff; box-shadow: 0 18px 50px rgba(20, 32, 50, .18); }.delete-dialog-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 20px 22px 16px; border-bottom: 1px solid #edf1f5; }.delete-dialog-header h3 { margin: 0; color: #202b3d; font-size: 18px; }.delete-dialog-header p { margin: 6px 0 0; color: #7e8a9b; font-size: 13px; }.dialog-close { color: #7b8797; font-size: 24px; line-height: 1; }.delete-dialog-body { padding: 20px 22px; }.element-risk-count { margin-bottom: 14px; color: #5f6c7e; font-size: 13px; }.delete-mode-list { display: grid; gap: 10px; width: 100%; }.delete-mode-item { display: flex; gap: 10px; align-items: flex-start; padding: 13px; border: 1px solid #e2e7ee; border-radius: 7px; cursor: pointer; }.delete-mode-item.selected { border-color: #91baf0; background: #f7fbff; }.delete-mode-item.danger.selected { border-color: #efb3b9; background: #fff8f8; }.delete-mode-item > span { display: grid; gap: 4px; }.delete-mode-item strong { color: #303b4b; font-size: 13px; }.delete-mode-item small { color: #8995a5; font-size: 12px; line-height: 1.5; }.delete-mode-item.danger strong { color: #c13f4b; }.danger-confirm-area { display: grid; gap: 7px; margin-top: 14px; color: #788496; font-size: 12px; }.danger-confirm-area strong { color: #c13f4b; }.delete-dialog-footer { display: flex; gap: 10px; justify-content: flex-end; padding: 14px 22px 18px; border-top: 1px solid #edf1f5; }
@media (max-width: 800px) { .element-management { grid-template-columns: 1fr; }.element-tree-panel { min-height: auto; }.element-list-header, .element-list-toolbar { align-items: stretch; flex-direction: column; }.element-search, .locator-filter { width: 100%; }.selection-actions { margin-left: 0; } }
</style>
