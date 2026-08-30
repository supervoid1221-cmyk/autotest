<template>
  <n-card :bordered="true" class="proCard">
    <BasicTable ref="tableRef" title="UI 用例" :columns="columns" :request="load" :row-key="(row) => row.id">
      <template #toolbar>
        <n-button type="primary" @click="router.push({ name: 'case_ui_case_edit', params: { id: 0 } })">新建 UI 用例</n-button>
      </template>
    </BasicTable>
  </n-card>
</template>

<script lang="ts" setup>
import { h, ref } from 'vue';
import { NButton, NTag, useDialog, useMessage } from 'naive-ui';
import { useRouter } from 'vue-router';
import { BasicTable } from '@/components/Table';
import { UiCaseAPI } from '@/api/case_ui/http';

const router = useRouter();
const dialog = useDialog();
const message = useMessage();
const api = new UiCaseAPI();
const tableRef = ref<any>();
const columns = [
  { title: '用例名称', key: 'name', width: 220 },
  { title: '所属项目', key: 'project_name', width: 180 },
  { title: '浏览器', key: 'browser', width: 100, render: () => 'Chrome' },
  { title: '运行模式', key: 'run_mode', width: 130, render: (row: any) => row.run_mode === 'headed' ? '有界面' : '无头' },
  { title: '步骤数', key: 'step_count', width: 90 },
  { title: '创建人', key: 'creator_name', width: 120, render: (row: any) => row.creator_name || '-' },
  { title: '状态', key: 'enabled', width: 90, render: (row: any) => h(NTag, { type: row.enabled ? 'success' : 'default', bordered: false }, { default: () => row.enabled ? '已启用' : '已停用' }) },
  { title: '描述', key: 'description', ellipsis: { tooltip: true } },
  { title: '操作', key: 'action', width: 140, render: (row: any) => h('div', { style: 'display:flex;gap:12px' }, [
    h(NButton, { text: true, type: 'primary', onClick: () => router.push({ name: 'case_ui_case_edit', params: { id: row.id } }) }, { default: () => '编辑' }),
    h(NButton, { text: true, type: 'error', onClick: () => remove(row) }, { default: () => '删除' }),
  ]) },
];
const load = (params: any) => api.getDataList(params);
function remove(row: any) {
  dialog.warning({ title: '删除 UI 用例', content: `确认删除「${row.name}」及全部步骤吗？`, positiveText: '删除', negativeText: '取消', onPositiveClick: async () => { await api.DeleteDataByID(row.id); await tableRef.value?.removeRowByKey(row.id); message.success('删除成功'); } });
}
</script>
