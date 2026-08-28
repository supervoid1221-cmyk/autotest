<template>
  <div class="template-page">
    <div class="template-shell">
      <section class="filter-toolbar" aria-label="模板筛选">
        <n-input
          v-model:value="keyword"
          class="template-search"
          clearable
          placeholder="搜索模板名称或描述"
        >
          <template #prefix><PhMagnifyingGlass :size="19" /></template>
        </n-input>
        <n-select
          v-model:value="projectFilter"
          class="filter-select project-filter"
          :options="projectOptions"
          placeholder="全部项目"
        />
        <n-select
          v-model:value="typeFilter"
          class="filter-select type-filter"
          :options="typeOptions"
          placeholder="全部类型"
        />
        <span class="template-total">共 {{ filteredList.length }} 个模板</span>
        <n-button v-if="isAdmin" class="create-button" type="primary" @click="addTemplate">
          ＋ 新建模板
        </n-button>
      </section>

      <n-spin :show="loading">
        <section v-if="pageList.length" class="template-grid" aria-label="模板列表">
          <article
            v-for="(item, index) in pageList"
            :key="item.id"
            class="template-card"
            :class="{ deleting: deletingId === item.id }"
          >
            <button class="template-card-content" type="button" @click="openDetail(item)">
              <span class="template-icon" :class="`tone-${cardToneIndex(item, index)}`">
                <component :is="cardIcon(item, index)" :size="29" weight="regular" />
              </span>
              <span class="template-name">{{ item.name }}</span>
              <span class="template-description">{{ item.description || '暂未填写模板说明' }}</span>
            </button>

            <n-dropdown
              v-if="isAdmin"
              trigger="click"
              placement="bottom-end"
              :options="adminMenuOptions"
              @select="(key) => handleAdminAction(key, item)"
            >
              <button
                class="template-menu"
                type="button"
                :disabled="deletingId !== null"
                :aria-label="`${item.name}管理操作`"
                @click.stop
              >
                <PhDotsThree :size="22" weight="bold" />
              </button>
            </n-dropdown>
          </article>
        </section>

        <n-empty
          v-else-if="!loading"
          class="empty-state"
          :description="list.length ? '没有匹配的模板' : '暂无可查看的模板'"
        >
          <template #extra>
            <n-button v-if="list.length && hasActiveFilter" @click="clearFilters"
              >清空筛选</n-button
            >
            <n-button v-else-if="isAdmin" type="primary" @click="addTemplate">新建模板</n-button>
          </template>
        </n-empty>
      </n-spin>

      <footer v-if="filteredList.length" class="template-footer">
        <span>{{ pageStart }}–{{ pageEnd }} / 共 {{ filteredList.length }} 个模板</span>
        <n-pagination v-model:page="currentPage" :page-count="pageCount" :page-slot="5" />
      </footer>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, h, onMounted, ref, watch } from 'vue';
  import { useRouter } from 'vue-router';
  import {
    PhBracketsCurly,
    PhClipboardText,
    PhCode,
    PhDotsThree,
    PhFlask,
    PhIdentificationCard,
    PhMagnifyingGlass,
    PhPencilSimple,
    PhShieldCheck,
    PhTrash,
    PhUserCircleCheck,
    PhUserPlus,
    PhWallet,
  } from '@phosphor-icons/vue';
  import { NIcon, useDialog, useMessage } from 'naive-ui';
  import { ExecutionTemplateAPI, type ExecutionTemplate } from '@/api/execution_template/http';
  import { useUserStore } from '@/store/modules/user';

  const router = useRouter();
  const message = useMessage();
  const dialog = useDialog();
  const userStore = useUserStore();
  const api = new ExecutionTemplateAPI();
  const list = ref<ExecutionTemplate[]>([]);
  const loading = ref(false);
  const deletingId = ref<number | null>(null);
  const keyword = ref('');
  const projectFilter = ref<number | null>(null);
  const typeFilter = ref<string | null>(null);
  const currentPage = ref(1);
  const pageSize = 8;
  const isAdmin = computed(() => Boolean((userStore.info as any)?.is_admin));

  const cardIcons = [
    PhWallet,
    PhUserPlus,
    PhUserCircleCheck,
    PhIdentificationCard,
    PhShieldCheck,
    PhClipboardText,
    PhFlask,
    PhCode,
  ];

  const typeOptions = [
    { label: '全部类型', value: null },
    { label: '接口模板', value: 'api' },
    { label: 'UI 模板', value: 'ui' },
    { label: '混合模板', value: 'mixed' },
    { label: '空模板', value: 'empty' },
  ];

  const projectOptions = computed(() => {
    const projects = new Map<number, string>();
    list.value.forEach((item) => {
      if (item.project)
        projects.set(Number(item.project), item.project_name || `项目 ${item.project}`);
    });
    return [
      { label: '全部项目', value: null },
      ...Array.from(projects, ([value, label]) => ({ value, label })),
    ];
  });

  const filteredList = computed(() => {
    const search = keyword.value.trim().toLocaleLowerCase();
    return list.value.filter((item) => {
      const matchesKeyword =
        !search ||
        String(item.name || '')
          .toLocaleLowerCase()
          .includes(search) ||
        String(item.description || '')
          .toLocaleLowerCase()
          .includes(search);
      const matchesProject =
        projectFilter.value === null || Number(item.project) === Number(projectFilter.value);
      const matchesType = typeFilter.value === null || item.template_type === typeFilter.value;
      return matchesKeyword && matchesProject && matchesType;
    });
  });

  const pageCount = computed(() => Math.max(1, Math.ceil(filteredList.value.length / pageSize)));
  const pageList = computed(() => {
    const start = (currentPage.value - 1) * pageSize;
    return filteredList.value.slice(start, start + pageSize);
  });
  const pageStart = computed(() => (currentPage.value - 1) * pageSize + 1);
  const pageEnd = computed(() => Math.min(currentPage.value * pageSize, filteredList.value.length));
  const hasActiveFilter = computed(() =>
    Boolean(keyword.value.trim() || projectFilter.value !== null || typeFilter.value !== null)
  );

  const renderIcon = (icon: any, color?: string) => () =>
    h(NIcon, { color }, { default: () => h(icon) });
  const adminMenuOptions = [
    { label: '编辑模板', key: 'edit', icon: renderIcon(PhPencilSimple) },
    { type: 'divider', key: 'divider' },
    { label: '删除模板', key: 'delete', icon: renderIcon(PhTrash, '#e5484d') },
  ];

  function asList(payload: any): ExecutionTemplate[] {
    if (Array.isArray(payload)) return payload;
    return payload?.list || payload?.results || payload?.data || [];
  }

  async function load() {
    loading.value = true;
    try {
      const result: any = await api.getDataList({ page: 1, pageSize: 999 });
      list.value = asList(result);
    } catch (error: any) {
      message.error(error?.message || '加载失败');
    } finally {
      loading.value = false;
    }
  }

  function addTemplate() {
    router.push({ name: 'template_edit', params: { id: 0 } });
  }

  function editTemplate(row: ExecutionTemplate) {
    router.push({ name: 'template_edit', params: { id: row.id } });
  }

  function openDetail(row: ExecutionTemplate) {
    router.push({ name: 'template_run', params: { id: row.id } });
  }

  function cardToneIndex(item: ExecutionTemplate, index: number) {
    const typeOffset = { api: 3, ui: 5, mixed: 1, empty: 7 }[item.template_type || 'empty'];
    return (index + typeOffset) % 8;
  }

  function cardIcon(item: ExecutionTemplate, index: number) {
    return cardIcons[cardToneIndex(item, index)];
  }

  function clearFilters() {
    keyword.value = '';
    projectFilter.value = null;
    typeFilter.value = null;
  }

  function handleAdminAction(key: string, row: ExecutionTemplate) {
    if (key === 'edit') editTemplate(row);
    if (key === 'delete') confirmDelete(row);
  }

  function confirmDelete(row: ExecutionTemplate) {
    if (!row?.id || deletingId.value !== null) return;
    dialog.warning({
      title: '删除模板',
      content: `确认删除模板「${row.name}」吗？删除后无法恢复。`,
      positiveText: '删除',
      negativeText: '取消',
      positiveButtonProps: { type: 'error' },
      onPositiveClick: async () => {
        if (deletingId.value !== null) return false;
        deletingId.value = Number(row.id);
        try {
          await api.DeleteDataByID(Number(row.id));
          list.value = list.value.filter((item) => item.id !== row.id);
          message.success('模板删除成功');
        } catch (error: any) {
          message.error(error?.response?.data?.detail || error?.message || '模板删除失败');
          return false;
        } finally {
          deletingId.value = null;
        }
        return true;
      },
    });
  }

  watch([keyword, projectFilter, typeFilter], () => {
    currentPage.value = 1;
  });

  watch(pageCount, (count) => {
    if (currentPage.value > count) currentPage.value = count;
  });

  onMounted(load);
</script>

<style lang="less" scoped>
  .template-page {
    min-height: 100%;
    padding: 30px 32px 34px;
    background: #f7f9fc;
  }

  .template-shell {
    width: 100%;
    max-width: 1440px;
    margin: 0 auto;
  }

  .create-button {
    min-width: 138px;
    height: 46px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 650;
    box-shadow: 0 8px 18px rgba(83, 109, 254, 0.18);
  }

  .filter-toolbar {
    display: flex;
    min-height: 84px;
    align-items: center;
    gap: 14px;
    padding: 14px;
    border: 1px solid #dfe5ee;
    border-radius: 8px;
    background: #fff;
    margin-bottom: 18px;
  }

  .template-search {
    width: min(392px, 42%);
  }

  .filter-select {
    width: 150px;
  }

  :deep(.filter-toolbar .n-input),
  :deep(.filter-toolbar .n-base-selection) {
    height: 46px;
    border-radius: 6px;
    background: #fff;
  }

  :deep(.filter-toolbar .n-input-wrapper) {
    padding: 0 14px;
  }

  :deep(.filter-toolbar .n-base-selection-label) {
    height: 44px;
    padding: 0 13px;
  }

  .template-total {
    margin-left: auto;
    padding-right: 6px;
    color: #536174;
    font-size: 14px;
    font-weight: 600;
    white-space: nowrap;
  }

  .template-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px;
    margin-top: 14px;
  }

  .template-card {
    position: relative;
    min-width: 0;
    min-height: 246px;
    overflow: hidden;
    border: 1px solid #dfe5ee;
    border-radius: 8px;
    color: inherit;
    background: #fff;
    transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease,
      background 0.18s ease;
  }

  .template-card-content {
    display: flex;
    width: 100%;
    min-height: 244px;
    flex-direction: column;
    align-items: flex-start;
    padding: 29px 26px 25px;
    border: 0;
    color: inherit;
    background: transparent;
    text-align: left;
    cursor: pointer;
  }

  .template-card:hover {
    border-color: #536dfe;
    background: #fbfcff;
    box-shadow: 0 8px 22px rgba(83, 109, 254, 0.1);
    transform: translateY(-2px);
  }

  .template-card:focus-within {
    border-color: #536dfe;
    outline: 2px solid rgba(83, 109, 254, 0.14);
    outline-offset: 1px;
  }

  .template-card:active {
    transform: translateY(0);
  }

  .template-card.deleting {
    pointer-events: none;
    opacity: 0.58;
  }

  .template-menu {
    position: absolute;
    z-index: 2;
    top: 18px;
    right: 18px;
    display: grid;
    width: 30px;
    height: 30px;
    place-items: center;
    padding: 0;
    border: 0;
    border-radius: 6px;
    color: #6780d9;
    background: transparent;
    cursor: pointer;
    opacity: 0.78;
  }

  .template-menu:hover {
    color: #4261e8;
    background: #eef2ff;
    opacity: 1;
  }

  .template-icon {
    display: inline-flex;
    width: 58px;
    height: 58px;
    align-items: center;
    justify-content: center;
    border-radius: 12px;
    color: #2b6fe8;
    background: #e9f1ff;
  }

  .tone-1 {
    color: #c48214;
    background: #fff2d8;
  }
  .tone-2 {
    color: #1d9b69;
    background: #e8f7ef;
  }
  .tone-3 {
    color: #7051d8;
    background: #f0ecff;
  }
  .tone-4 {
    color: #12a0ba;
    background: #e8f8fb;
  }
  .tone-5 {
    color: #da5365;
    background: #ffeaed;
  }
  .tone-6 {
    color: #3670d9;
    background: #eaf0ff;
  }
  .tone-7 {
    color: #7655d5;
    background: #f0ecff;
  }

  .template-name {
    width: 100%;
    margin-top: 26px;
    overflow: hidden;
    color: #1b2638;
    font-size: 17px;
    font-weight: 700;
    line-height: 1.4;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .template-description {
    display: -webkit-box;
    margin-top: 10px;
    overflow: hidden;
    color: #69778d;
    font-size: 14px;
    line-height: 1.75;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }

  .empty-state {
    min-height: 430px;
    padding: 100px 0;
  }

  .template-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 76px;
    color: #58667a;
    font-size: 14px;
  }

  :deep(.template-footer .n-pagination-item) {
    border-radius: 6px;
  }

  @media (max-width: 1180px) {
    .template-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .template-search {
      width: min(340px, 38%);
    }
  }

  @media (max-width: 900px) {
    .filter-toolbar {
      flex-wrap: wrap;
    }
    .template-search {
      width: 100%;
    }
    .template-total {
      margin-left: 0;
    }
    .template-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 600px) {
    .template-page {
      padding: 20px 16px 28px;
    }
    .create-button {
      width: 100%;
    }
    .filter-select {
      flex: 1;
      min-width: 130px;
    }
    .template-total {
      width: 100%;
    }
    .template-grid {
      grid-template-columns: 1fr;
    }
    .template-footer {
      align-items: flex-start;
      flex-direction: column;
      gap: 12px;
      padding: 18px 0;
    }
  }
</style>
