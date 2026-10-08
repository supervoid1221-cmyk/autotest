<template>
  <footer class="pagination-footer">
    <span>共 {{ total }} 条 · 当前第 {{ pageStart }}–{{ pageEnd }} 条</span>
    <div class="pagination-actions">
      <n-pagination
        :page="page"
        :page-count="pageCount"
        :page-slot="pageSlot"
        @update:page="emit('update:page', $event)"
      />
      <n-select
        :value="pageSize"
        class="pagination-page-size"
        :options="pageSizeOptions"
        aria-label="每页数量"
        @update:value="emit('update:pageSize', $event)"
      />
    </div>
  </footer>
</template>

<script setup lang="ts">
  import { computed } from 'vue';

  const props = withDefaults(
    defineProps<{
      total: number;
      page: number;
      pageSize: number;
      pageSizes?: number[];
      pageSlot?: number;
    }>(),
    {
      pageSizes: () => [10, 20, 50],
      pageSlot: 5,
    }
  );

  const emit = defineEmits<{
    (event: 'update:page', value: number): void;
    (event: 'update:pageSize', value: number): void;
  }>();

  const pageCount = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)));
  const pageStart = computed(() => (props.total ? (props.page - 1) * props.pageSize + 1 : 0));
  const pageEnd = computed(() => Math.min(props.page * props.pageSize, props.total));
  const pageSizeOptions = computed(() =>
    props.pageSizes.map((value) => ({ label: `${value} 条 / 页`, value }))
  );
</script>

<style scoped>
  .pagination-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    min-height: 70px;
    box-sizing: border-box;
    padding: 0 20px;
    border-top: 1px solid var(--plan-line, var(--line, rgb(128 128 128 / 22%)));
    color: var(--plan-muted, #74839a);
    font-size: 13px;
  }

  .pagination-actions {
    display: flex;
    align-items: center;
    gap: 20px;
  }

  .pagination-page-size {
    width: 116px;
  }

  .pagination-footer :deep(.n-pagination-item--active) {
    color: var(--plan-primary, #2563eb) !important;
    border-color: var(--plan-primary, #2563eb) !important;
  }

  @media (max-width: 720px) {
    .pagination-footer {
      align-items: flex-start;
      flex-direction: column;
      padding: 14px 12px;
    }

    .pagination-actions {
      width: 100%;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
    }
  }
</style>
