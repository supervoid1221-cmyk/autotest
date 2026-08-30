<template>
  <n-card :bordered="false" class="proCard" title="项目环境与认证">
    <BasicTable ref="tableRef" :columns="columns" :request="loadDataTable" :row-key="(row) => row.id">
      <template #toolbar>
        <n-button type="primary" @click="router.push({ name: 'project_environment_edit', params: { id: 0 } })">
          添加环境
        </n-button>
      </template>
    </BasicTable>
  </n-card>
</template>

<script lang="ts" setup>
  import { h, ref } from 'vue';
  import { useRouter } from 'vue-router';
  import { NButton, NTag, useDialog, useMessage } from 'naive-ui';
  import { BasicTable } from '@/components/Table';
  import { EnvironmentAPI } from '@/api/project/http';

  const router = useRouter();
  const message = useMessage();
  const dialog = useDialog();
  const api = new EnvironmentAPI();
  const tableRef = ref<any>();
  const columns = [
    { title: '项目', key: 'project_name' },
    { title: '环境名称', key: 'name' },
    { title: 'Base URL', key: 'base_url' },
    {
      title: '自动登录', key: 'auth_enabled', render: (row) =>
        h(NTag, { type: row.auth_enabled ? 'success' : 'default' }, { default: () => row.auth_enabled ? '已启用' : '未启用' }),
    },
    {
      title: '操作', key: 'action', render: (row) => h('div', { style: 'display:flex;gap:8px' }, [
        h(NButton, { text: true, type: 'primary', onClick: () => router.push({ name: 'project_environment_edit', params: { id: row.id } }) }, { default: () => '编辑' }),
        h(NButton, { text: true, type: 'error', onClick: () => remove(row) }, { default: () => '删除' }),
      ]),
    },
  ];
  const loadDataTable = async (params) => api.getDataList(params);
  function remove(row) {
    dialog.warning({
      title: '删除环境', content: `确认删除环境「${row.name}」吗？`, positiveText: '删除', negativeText: '取消',
      onPositiveClick: async () => { await api.DeleteDataByID(row.id); await tableRef.value?.removeRowByKey(row.id); message.success('删除成功'); },
    });
  }
</script>
