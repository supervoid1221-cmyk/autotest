<template>
  <n-card :bordered="false" class="proCard dynamic-function-page">
    <BasicTable
      title="动态函数"
      :columns="columns"
      :request="loadData"
      :row-key="(row) => row.id"
      ref="actionRef"
      :actionColumn="actionColumn"
      :scroll-x="920"
    >
      <template #toolbar>
        <div class="table-toolbar">
          <n-select
            v-model:value="selectedProjects"
            multiple
            filterable
            clearable
            max-tag-count="responsive"
            :options="projectOptions"
            placeholder="按项目筛选（可多选）"
            class="project-filter"
            @update:value="reload"
          />
          <n-button type="primary" @click="add">添加函数</n-button>
        </div>
      </template>
    </BasicTable>
  </n-card>
</template>

<script setup lang="ts">
import { asList } from '@/utils/list';

  import { computed, h, onMounted, reactive, ref } from 'vue';
  import { BasicTable } from '@/components/Table';
  import { NButton, NSelect, NTag, useDialog, useMessage } from 'naive-ui';
  import { useRouter } from 'vue-router';
  import { DynamicFunctionAPI, ProjectAPI } from '@/api/project/http';
  import { useUserStore } from '@/store/modules/user';

  const api = new DynamicFunctionAPI();
  const projectApi = new ProjectAPI();
  const router = useRouter();
  const dialog = useDialog();
  const message = useMessage();
  const actionRef = ref<any>();
  const projects = ref<any[]>([]);
  const selectedProjects = ref<number[]>([]);
  const userStore = useUserStore();
  const isAdmin = computed(() => Boolean((userStore.info as any)?.is_admin));

  
  const projectOptions = computed(() =>
    projects.value.map((project) => ({ label: project.name, value: project.id }))
  );
  const columns = [
    {
      title: '所属项目',
      key: 'project_names',
      width: 260,
      render: (row: any) =>
        h(
          'div',
          { class: 'tag-list' },
          (row.project_names || []).map((name: string) =>
            h(NTag, { size: 'small', bordered: false, type: 'info' }, { default: () => name })
          )
        ),
    },
    {
      title: '包含函数',
      key: 'function_names',
      width: 360,
      ellipsis: { tooltip: true },
      render: (row: any) => (row.function_names || []).join('、') || '-',
    },
    {
      title: '版本',
      key: 'version',
      width: 90,
      render: (row: any) => `v${row.version || 1}`,
    },
    {
      title: '审批',
      key: 'approval_status',
      width: 110,
      render: (row: any) => {
        const state: any = {
          draft: ['待审批', 'warning'], approved: ['已审批', 'success'], rejected: ['已驳回', 'error'],
        }[row.approval_status] || ['待审批', 'warning'];
        return h(NTag, { size: 'small', bordered: false, type: state[1] }, { default: () => state[0] });
      },
    },
    {
      title: '状态',
      key: 'enabled',
      width: 100,
      render: (row: any) =>
        h(
          NTag,
          { size: 'small', bordered: false, type: row.enabled ? 'success' : 'default' },
          { default: () => (row.enabled ? '启用' : '停用') }
        ),
    },
  ];
  const loadData = (params: any) =>
    api.getDataList({
      ...params,
      projects: selectedProjects.value.length ? selectedProjects.value.join(',') : undefined,
    });
  const actionColumn = reactive({
    width: 280,
    title: '操作',
    key: 'action',
    render: (row: any) =>
      h('div', { class: 'row-actions' }, [
        h(
          NButton,
          {
            text: true,
            type: 'primary',
            onClick: () =>
              router.push({ name: 'project_dynamic_function_edit', params: { id: row.id } }),
          },
          { default: () => '编辑' }
        ),
        ...(isAdmin.value && row.approval_status !== 'approved' ? [h(
          NButton,
          { text: true, type: 'success', onClick: async () => { await api.approve(row.id); message.success('审批通过'); reload(); } },
          { default: () => '审批' }
        )] : []),
        ...(isAdmin.value && row.approval_status !== 'rejected' ? [h(
          NButton,
          {
            text: true,
            type: 'warning',
            onClick: () => dialog.warning({
              title: '确认驳回',
              content: '驳回后该版本将立即停止用于正式执行。',
              positiveText: '确认驳回',
              negativeText: '取消',
              onPositiveClick: async () => {
                await api.reject(row.id);
                message.success('已驳回');
                reload();
              },
            }),
          },
          { default: () => '驳回' }
        )] : []),
        h(
          NButton,
          {
            text: true,
            type: 'error',
            onClick: () =>
              dialog.warning({
                title: '确认删除',
                content: '删除这组动态函数？',
                positiveText: '确定',
                negativeText: '取消',
                onPositiveClick: async () => {
                  await api.DeleteDataByID(row.id);
                  message.success('删除成功');
                  reload();
                },
              }),
          },
          { default: () => '删除' }
        ),
      ]),
  });

  function reload() {
    actionRef.value?.reload();
  }
  function add() {
    router.push({ name: 'project_dynamic_function_edit', params: { id: 0 } });
  }
  onMounted(async () => {
    projects.value = asList(await projectApi.getDataList({ pageSize: 1000 }));
  });
</script>

<style scoped lang="less">
  .table-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .project-filter {
    width: 320px;
  }
  :deep(.tag-list),
  :deep(.row-actions) {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  @media (max-width: 680px) {
    .table-toolbar {
      align-items: stretch;
      flex-direction: column;
    }
    .project-filter {
      width: 100%;
    }
  }
</style>
