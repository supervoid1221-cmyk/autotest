<template>
  <div class="project-page">
    <AiBanner message="管理所有测试项目，每个项目可独立配置接口、环境和测试场景" />
    <n-card :bordered="true" class="proCard">
      <BasicTable
        title="项目列表"
        :columns="columns"
        :request="loadDataTable"
        :row-key="(row) => row.id"
        ref="actionRef"
        :actionColumn="actionColumn"
        :scroll-x="1360"
        @update:checked-row-keys="onCheckedRow"
      >
        <template #toolbar>
          <n-button v-if="isAdmin" type="primary" @click="addData">
            <template #icon><PhPlus :size="16" weight="light" /></template>
            添加数据
          </n-button>
        </template>
      </BasicTable>
    </n-card>
  </div>
</template>

<script lang="ts" setup>
  import { reactive, ref, h, computed, onActivated } from 'vue';
  import { BasicTable } from '@/components/Table';
  import { columns } from './projectColumns';
  import { NButton, useDialog, useMessage } from 'naive-ui';
  import { useRouter } from 'vue-router';
  import { ProjectAPI } from '@/api/project/http';
  import { useUserStore } from '@/store/modules/user';
  import { AiBanner } from '@/components/Ai';
  import { PhPlus } from '@phosphor-icons/vue';

  const message = useMessage();
  const dialog = useDialog();
  const actionRef = ref();
  const deletingIds = new Set<number>();
  const router = useRouter();

  const api = new ProjectAPI();
  const userStore = useUserStore();
  const isAdmin = computed(() => Boolean((userStore.info as any)?.is_admin));

  const params = reactive({
    pageSize: 5,
    // 列表初始不带名称过滤，避免新建项目因遗留的固定关键字被隐藏。
    name: '',
  });

  const actionColumn = reactive({
    width: 150,
    title: '操作',
    key: 'action',
    fixed: 'right',
    align: 'center',
    render(record) {
      const children = [
        h(
          NButton,
          { text: true, type: 'primary', onClick: () => handleEdit(record) },
          { default: () => '编辑' }
        ),
      ];
      if (isAdmin.value) {
        children.push(
          h(
            NButton,
            { text: true, type: 'error', onClick: () => handleDelete(record) },
            { default: () => '删除' }
          )
        );
      }
      return h('div', { style: 'display:flex;gap:12px' }, children);
    },
  });

  const loadDataTable = async (res) => {
    return await api.getDataList({ ...params, ...res });
  };

  function onCheckedRow(rowKeys) {
    console.log(rowKeys);
  }

  function reloadTable() {
    actionRef.value.reload();
  }

  // 多页签返回时该页面可能被缓存；重新激活后刷新，确保能立即看到刚新建的项目。
  onActivated(() => {
    reloadTable();
  });

  function handleDelete(record) {
    console.log(record);
    dialog.info({
      title: '提示',
      content: `您想删除${record.name}`,
      positiveText: '确定',
      negativeText: '取消',
      onPositiveClick: async () => {
        if (deletingIds.has(record.id)) return;
        deletingIds.add(record.id);
        try {
          await api.DeleteDataByID(record.id);
          message.success('删除成功');
          reloadTable();
        } finally {
          deletingIds.delete(record.id);
        }
      },
      onNegativeClick: () => {},
    });
  }

  function handleEdit(record) {
    console.log(record);
    router.push({ name: 'project_project_edit', params: { id: record.id } });
  }

  function addData() {
    if (!isAdmin.value) return message.error('仅管理员可以创建项目并设置项目负责人');
    router.push({ name: 'project_project_edit', params: { id: 0 } });
  }
</script>

<style lang="less" scoped>
  .project-page {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .proCard {
    border-radius: 12px;
    :deep(.n-card-header) {
      padding: 16px 20px 12px;
      font-size: 15px;
      font-weight: 500;
      color: #1f2937;
    }
    :deep(.n-card__content) {
      padding: 0 0 12px;
    }
  }
</style>
