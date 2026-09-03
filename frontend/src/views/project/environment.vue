<template>
  <n-card :bordered="false" class="proCard" title="项目环境与认证">
    <BasicTable v-if="!isMobile" ref="tableRef" :columns="columns" :request="loadDataTable" :row-key="(row) => row.id">
      <template #toolbar>
        <n-button type="primary" @click="router.push({ name: 'project_environment_edit', params: { id: 0 } })">
          添加环境
        </n-button>
      </template>
    </BasicTable>

    <section v-else class="mobile-environment-view">
      <div class="mobile-environment-toolbar">
        <span>共 {{ mobileRows.length }} 个环境</span>
        <n-button type="primary" @click="router.push({ name: 'project_environment_edit', params: { id: 0 } })">
          添加环境
        </n-button>
      </div>

      <n-spin :show="mobileLoading">
        <div v-if="mobileRows.length" class="mobile-environment-list">
          <article v-for="row in mobileRows" :key="row.id" class="mobile-environment-card">
            <header>
              <div class="mobile-environment-name">
                <small>{{ row.project_name || '未关联项目' }}</small>
                <strong>{{ row.name || '-' }}</strong>
              </div>
              <n-tag size="small" :type="row.auth_enabled ? 'success' : 'default'">
                {{ row.auth_enabled ? '自动登录已启用' : '自动登录未启用' }}
              </n-tag>
            </header>

            <div class="mobile-environment-field">
              <span>Base URL</span>
              <code>{{ row.base_url || '-' }}</code>
            </div>

            <footer>
              <n-button text type="primary" @click="router.push({ name: 'project_environment_edit', params: { id: row.id } })">
                编辑
              </n-button>
              <n-button text type="error" @click="remove(row)">删除</n-button>
            </footer>
          </article>
        </div>
        <n-empty v-else-if="!mobileLoading" description="暂无环境配置" class="mobile-environment-empty" />
      </n-spin>
    </section>
  </n-card>
</template>

<script lang="ts" setup>
  import { computed, h, ref, watch } from 'vue';
  import { useRouter } from 'vue-router';
  import { NButton, NTag, useDialog, useMessage } from 'naive-ui';
  import { BasicTable } from '@/components/Table';
  import { EnvironmentAPI } from '@/api/project/http';
  import { useProjectSettingStore } from '@/store/modules/projectSetting';

  const router = useRouter();
  const message = useMessage();
  const dialog = useDialog();
  const api = new EnvironmentAPI();
  const settingStore = useProjectSettingStore();
  const tableRef = ref<any>();
  const mobileRows = ref<any[]>([]);
  const mobileLoading = ref(false);
  const mobileLoaded = ref(false);
  const isMobile = computed(() => settingStore.getIsMobile);
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
  const asList = (payload: any) => Array.isArray(payload)
    ? payload
    : payload?.list || payload?.results || payload?.data || [];

  async function loadMobileRows() {
    try {
      mobileLoading.value = true;
      const result = await api.getDataList({ page: 1, pageSize: 999 });
      mobileRows.value = asList(result);
      mobileLoaded.value = true;
    } finally {
      mobileLoading.value = false;
    }
  }

  watch(isMobile, (mobile) => {
    if (mobile && !mobileLoaded.value) loadMobileRows();
  }, { immediate: true });

  function remove(row) {
    dialog.warning({
      title: '删除环境', content: `确认删除环境「${row.name}」吗？`, positiveText: '删除', negativeText: '取消',
      onPositiveClick: async () => {
        await api.DeleteDataByID(row.id);
        mobileRows.value = mobileRows.value.filter((item) => item.id !== row.id);
        await tableRef.value?.removeRowByKey(row.id);
        message.success('删除成功');
      },
    });
  }
</script>

<style lang="less" scoped>
  .mobile-environment-view { min-width: 0; }
  .mobile-environment-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; color: #8793a5; font-size: 13px; }
  .mobile-environment-list { display: grid; gap: 12px; }
  .mobile-environment-card { overflow: hidden; border: 1px solid #e5eaf1; border-radius: 10px; background: #fff; }
  .mobile-environment-card header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 15px 14px 13px; border-bottom: 1px solid #edf1f5; }
  .mobile-environment-name { display: grid; min-width: 0; gap: 4px; }
  .mobile-environment-name small { overflow: hidden; color: #8a96a8; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
  .mobile-environment-name strong { overflow: hidden; color: #26344a; font-size: 16px; text-overflow: ellipsis; white-space: nowrap; }
  .mobile-environment-field { display: grid; gap: 7px; padding: 13px 14px; }
  .mobile-environment-field span { color: #8a96a8; font-size: 12px; }
  .mobile-environment-field code { overflow-wrap: anywhere; color: #46566d; font: 13px/1.55 'JetBrains Mono', monospace; }
  .mobile-environment-card footer { display: flex; justify-content: flex-end; gap: 18px; padding: 10px 14px; border-top: 1px solid #edf1f5; background: #fafbfd; }
  .mobile-environment-empty { padding: 48px 0; }

  @media (max-width: 640px) {
    .proCard :deep(.n-card-header) { padding: 18px 16px 12px; }
    .proCard :deep(.n-card__content) { padding: 12px 16px 18px; }
    .mobile-environment-toolbar .n-button { flex: 0 0 auto; }
    .mobile-environment-card header { flex-direction: column; }
  }
</style>
