<template>
  <n-card :bordered="true" class="proCard">
    <BasicTable ref="tableRef" title="业务场景" :columns="columns" :request="load" :row-key="(row) => row.id">
      <template #toolbar>
        <n-button type="primary" @click="router.push({ name: 'case_api_scenario_edit', params: { id: 0 } })">新建场景</n-button>
      </template>
    </BasicTable>
  </n-card>
</template>

<script lang="ts" setup>
import { h, ref } from 'vue';
import { useRouter } from 'vue-router';
import { NButton, useDialog, useMessage } from 'naive-ui';
import { BasicTable } from '@/components/Table';
import { ScenarioAPI } from '@/api/case_api/http';

const router = useRouter();
const dialog = useDialog();
const message = useMessage();
const api = new ScenarioAPI();
const tableRef = ref<any>();

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

const load = (params: any) => api.getDataList(params);

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
</script>
