<template>
  <n-card :bordered="true" class="proCard">
    <BasicTable ref="tableRef" :columns="columns" :request="load" :row-key="(row) => row.id">
      <template #tableTitle>
        <div class="list-filter-bar">
          <span>场景名称</span>
          <n-input v-model:value="searchName" clearable placeholder="请输入场景名称" class="name-filter" @keyup.enter="reloadTable" @clear="reloadTable" />
          <span>所属项目</span>
          <n-select v-model:value="selectedProject" :options="projectOptions" clearable filterable placeholder="全部项目" class="project-filter" @update:value="reloadTable" />
          <n-button type="primary" secondary @click="reloadTable">查询</n-button>
        </div>
      </template>
      <template #toolbar>
        <n-button type="primary" @click="router.push({ name: 'case_api_scenario_edit', params: { id: 0 } })">新建场景</n-button>
      </template>
    </BasicTable>
  </n-card>
</template>

<script lang="ts" setup>
import { h, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { NButton, NInput, NSelect, useDialog, useMessage } from 'naive-ui';
import { BasicTable } from '@/components/Table';
import { ScenarioAPI } from '@/api/case_api/http';
import { ProjectAPI } from '@/api/project/http';

const router = useRouter();
const dialog = useDialog();
const message = useMessage();
const api = new ScenarioAPI();
const projectApi = new ProjectAPI();
const tableRef = ref<any>();
const searchName = ref('');
const selectedProject = ref<number | null>(null);
const projectOptions = ref<Array<{ label: string; value: number }>>([]);

const asList = (payload: any): any[] => Array.isArray(payload) ? payload : payload?.results || payload?.list || payload?.data || [];

const columns = [
  {
    title: '场景名称',
    key: 'name',
    width: 220,
    render: (row: any) => h('span', { style: 'font-size:14px;font-weight:500;color:#111827' }, row.name),
  },
  {
    title: '所属项目',
    key: 'project_names',
    width: 200,
    render: (row: any) => row.project_names?.join('/') || row.project_name || h('span', { style: 'color:#D1D5DB' }, '-'),
  },
  {
    title: '步骤数',
    key: 'step_count',
    width: 90,
    render: (row: any) => h('span', { style: 'font-size:13px;font-weight:500;color:#5B6AF0' }, row.step_count ?? 0),
  },
  {
    title: '创建人',
    key: 'creator_name',
    width: 120,
    render: (row: any) => row.creator_name || h('span', { style: 'color:#94A3B8' }, '-'),
  },
  {
    title: '描述',
    key: 'description',
    width: 280,
    ellipsis: { tooltip: true },
  },
  {
    title: '操作',
    key: 'action',
    width: 140,
    render: (row: any) =>
      h('div', { style: 'display:flex;gap:10px' }, [
        h(NButton, { text: true, type: 'primary', onClick: () => router.push({ name: 'case_api_scenario_edit', params: { id: row.id } }) }, { default: () => '编辑' }),
        h(NButton, { text: true, type: 'error', onClick: () => remove(row) }, { default: () => '删除' }),
      ]),
  },
];

const load = (params: any) => api.getDataList({
  ...params,
  name: searchName.value.trim() || undefined,
  project: selectedProject.value || undefined,
});

function reloadTable() {
  tableRef.value?.reload?.();
}

function remove(row: any) {
  dialog.warning({
    title: '删除场景',
    content: `确认删除「${row.name}」及其步骤吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      await api.DeleteDataByID(row.id);
      message.success('删除成功');
      await tableRef.value?.removeRowByKey(row.id);
    },
  });
}

onMounted(async () => {
  projectOptions.value = asList(await projectApi.getDataList({ pageSize: 1000 }))
    .map((project: any) => ({ label: project.name, value: Number(project.id) }));
});
</script>

<style scoped>
.proCard :deep(.table-toolbar-left) { min-width: 0; flex: 0 1 auto; }
.proCard :deep(.table-toolbar-right) { flex: none; margin-left: auto; }
.list-filter-bar { display: flex; flex-wrap: nowrap; align-items: center; gap: 10px; color: #475569; font-size: 14px; font-weight: 600; white-space: nowrap; }
.name-filter, .project-filter { width: 220px; font-weight: 400; }
@media (max-width: 1100px) {
  .proCard :deep(.table-toolbar) { align-items: flex-start; flex-direction: column; gap: 12px; }
  .proCard :deep(.table-toolbar-right) { width: 100%; margin-left: 0; }
  .list-filter-bar { flex-wrap: wrap; }
}
</style>
