<template>
  <n-card :bordered="false" class="proCard" title="数据库连接">
    <BasicTable :columns="columns" :request="loadData" :row-key="(row) => row.id" ref="actionRef" :scroll-x="1120">
      <template #toolbar>
        <n-button type="primary" @click="openEdit(0)">添加连接</n-button>
      </template>
    </BasicTable>
  </n-card>
</template>

<script lang="ts" setup>
  import { h, ref } from 'vue';
  import { useRouter } from 'vue-router';
  import { NButton, NTag, useDialog, useMessage } from 'naive-ui';
  import { BasicTable } from '@/components/Table';
  import { DatabaseConnectionAPI } from '@/api/project/http';

  const router = useRouter();
  const dialog = useDialog();
  const message = useMessage();
  const api = new DatabaseConnectionAPI();
  const actionRef = ref<any>();
  const openEdit = (id: number) => router.push({ name: 'project_database_edit', params: { id } });
  const columns = [
    { title: '所属项目', key: 'project_names', width: 180, ellipsis: { tooltip: true }, render: (row: any) => (row.project_names || []).join(' / ') || '-' },
    { title: '执行环境', key: 'environment_name', width: 100 },
    { title: '数据库类型', key: 'database_type_display', width: 120 },
    { title: '调用函数', key: 'function_name', width: 210, ellipsis: { tooltip: true } },
    { title: '地址', key: 'host', width: 220, render: (row: any) => `${row.host}:${row.port}/${row.database}` },
    { title: '状态', key: 'enabled', width: 90, render: (row: any) => h(NTag, { type: row.enabled ? 'success' : 'default', bordered: false }, { default: () => row.enabled ? '启用' : '禁用' }) },
    { title: '操作', key: 'action', width: 150, fixed: 'right', render: (row: any) => h('div', { class: 'row-actions' }, [
      h(NButton, { text: true, type: 'primary', onClick: () => openEdit(row.id) }, { default: () => '编辑' }),
      h(NButton, { text: true, type: 'error', onClick: () => remove(row) }, { default: () => '删除' }),
    ]) },
  ];
  const loadData = (params: any) => api.getDataList(params);
  function remove(row: any) {
    dialog.warning({
      title: '删除数据库连接', content: `确认删除调用函数「${row.function_name}」吗？`,
      positiveText: '删除', negativeText: '取消',
      onPositiveClick: async () => { await api.DeleteDataByID(row.id); message.success('删除成功'); actionRef.value?.reload(); },
    });
  }
</script>

<style scoped>
  :deep(.row-actions) { display: flex; gap: 14px; }
</style>
