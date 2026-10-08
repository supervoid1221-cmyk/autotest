<template>
  <div class="project-page">
    <header class="project-page-header">
      <div>
        <h1>项目信息</h1>
        <p>集中管理测试项目、成员与项目级测试资产</p>
      </div>
      <n-button v-if="isAdmin" class="create-project-button" type="primary" @click="addData">
        <template #icon><PhPlus :size="17" weight="light" /></template>
        新建项目
      </n-button>
    </header>

    <section class="project-guide" aria-label="项目管理能力">
      <div><span><PhFolderSimple :size="20" /></span><strong>资产隔离</strong><small>接口、场景与变量按项目管理</small></div>
      <div><span><PhGlobeHemisphereWest :size="20" /></span><strong>独立环境</strong><small>为每个项目配置环境与认证</small></div>
      <div><span><PhUsersThree :size="20" /></span><strong>成员协作</strong><small>统一管理负责人与项目成员</small></div>
    </section>

    <n-card :bordered="true" class="proCard">
      <BasicTable
        title="项目列表"
        :columns="columns"
        :request="loadDataTable"
        :row-key="(row) => row.id"
        ref="actionRef"
        :actionColumn="actionColumn"
        :scroll-x="1040"
        @update:checked-row-keys="onCheckedRow"
      />
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
  import { PhFolderSimple, PhGlobeHemisphereWest, PhPlus, PhUsersThree } from '@phosphor-icons/vue';

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
      return h('div', { class: 'project-row-actions' }, children);
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
    gap: 14px;
    padding: 18px 24px 30px;
  }
  .project-page-header { display: flex; min-height: 62px; align-items: center; justify-content: space-between; gap: 24px; }
  .project-page-header h1 { margin: 0; color: #18243a; font-size: 26px; font-weight: 750; line-height: 1.2; letter-spacing: -.03em; }
  .project-page-header p { margin: 7px 0 0; color: #7b899d; font-size: 13px; }
  .create-project-button { min-width: 116px; height: 38px; border-radius: 7px; }
  .project-guide { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); overflow: hidden; border: 1px solid #dfe6ef; border-radius: 10px; background: #fff; }
  .project-guide > div { display: grid; min-width: 0; grid-template-columns: 38px minmax(0, 1fr); grid-template-rows: auto auto; column-gap: 12px; padding: 15px 18px; border-right: 1px solid #e8edf3; }
  .project-guide > div:last-child { border-right: 0; }
  .project-guide > div > span { display: grid; grid-row: 1 / 3; width: 38px; height: 38px; place-items: center; border-radius: 8px; color: #3565e8; background: #edf3ff; }
  .project-guide strong { overflow: hidden; color: #26344a; font-size: 13px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
  .project-guide small { margin-top: 3px; overflow: hidden; color: #8290a4; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
  .proCard {
    overflow: hidden;
    border-radius: 10px;
    :deep(.n-card-header) {
      padding: 17px 20px 13px;
      font-size: 15px;
      font-weight: 650;
      color: #1f2937;
    }
    :deep(.n-card__content) {
      padding: 0 0 12px;
    }
    :deep(.table-toolbar) {
      min-height: 60px;
      box-sizing: border-box;
      padding: 0 20px;
      border-bottom: 1px solid #e8edf3;
    }
    :deep(.table-toolbar-left-title) {
      color: #26344a;
      font-size: 16px;
      font-weight: 650;
    }
    :deep(.s-table) {
      padding: 0 20px;
    }
    :deep(.n-data-table-th) { height: 44px; font-size: 12px; font-weight: 600; }
    :deep(.n-data-table-td) { height: 64px; }
    :deep(.n-data-table-tr) { transition: background-color .18s ease; }
    :deep(.n-pagination) { padding-top: 14px; }
  }

  :deep(.project-name-cell) { display: flex; align-items: center; gap: 12px; min-width: 0; }
  :deep(.project-list-avatar) { display: inline-flex; flex: 0 0 38px; width: 38px; height: 38px; align-items: center; justify-content: center; border-radius: 9px; color: #fff; font-size: 14px; font-weight: 650; }
  :deep(.project-name-copy) { display: grid; min-width: 0; gap: 3px; }
  :deep(.project-name-copy strong) { overflow: hidden; color: #26344a; font-size: 14px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
  :deep(.project-name-copy small) { color: #98a3b4; font-size: 11px; font-variant-numeric: tabular-nums; }
  :deep(.project-owner), :deep(.project-intro-text) { color: #536176; font-size: 13px; }
  :deep(.project-empty-value) { color: #9aa5b5; font-size: 12px; }
  :deep(.project-member-count) { display: inline-grid; min-width: 30px; height: 25px; place-items: center; padding: 0 7px; border-radius: 6px; color: #5267dc; background: #edf1ff; font-size: 12px; font-weight: 650; font-variant-numeric: tabular-nums; }
  :deep(.project-row-actions) { display: flex; justify-content: center; gap: 14px; }

  @media (max-width: 680px) {
    .project-page {
      padding: 14px;
    }
    .project-page-header { align-items: flex-start; flex-direction: column; gap: 14px; }
    .create-project-button { width: 100%; }
    .project-guide { grid-template-columns: 1fr; }
    .project-guide > div { border-right: 0; border-bottom: 1px solid #e8edf3; }
    .project-guide > div:last-child { border-bottom: 0; }
    .proCard :deep(.table-toolbar),
    .proCard :deep(.s-table) {
      padding-right: 14px;
      padding-left: 14px;
    }
  }
</style>
