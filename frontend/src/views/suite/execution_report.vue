<template>
  <section class="unified-report">
    <header class="unified-report__bar">
      <div>
        <n-button text type="primary" @click="back">← 返回执行与报告中心</n-button>
        <n-tag size="small" :type="tagType">{{ typeName }}</n-tag>
      </div>
      <span>执行编号：{{ route.params.id }}</span>
    </header>
    <component
      :is="reportComponent"
      v-if="reportComponent"
      :key="`${sourceType}-${route.params.id}`"
      @report-type-change="reportTypeOverride = $event"
    />
    <n-result v-else status="404" title="报告类型不存在" description="请从执行与报告中心重新打开。">
      <template #footer><n-button @click="back">返回中心</n-button></template>
    </n-result>
  </section>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();
const sourceType = computed(() => String(route.params.sourceType || ''));
const reportTypeOverride = ref<string | null>(null);
const reports: Record<string, any> = {
  suite: defineAsyncComponent(() => import('@/views/suite/report.vue')),
  app: defineAsyncComponent(() => import('@/views/case_app/report.vue')),
  performance: defineAsyncComponent(() => import('@/views/performance/report.vue')),
};
const reportComponent = computed(() => reports[sourceType.value]);
const effectiveType = computed(() => reportTypeOverride.value || sourceType.value);
const typeName = computed(() => ({ suite: '测试计划报告', app: 'App 测试报告', performance: '性能测试报告' }[effectiveType.value] || '未知报告'));
const tagType = computed(() => effectiveType.value === 'performance' ? 'warning' : effectiveType.value === 'app' ? 'success' : 'info');
watch(sourceType, () => { reportTypeOverride.value = null; });
const back = () => router.push({ name: 'execution_control' });
</script>

<style scoped lang="less">
.unified-report{min-height:100%;background:#f5f7fb}.unified-report__bar{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 28px;border-bottom:1px solid #e2e8f0;background:#fff}.unified-report__bar>div{display:flex;align-items:center;gap:14px}.unified-report__bar>span{color:#7b8ba3;font-size:13px;font-variant-numeric:tabular-nums}@media(max-width:640px){.unified-report__bar{align-items:flex-start;flex-direction:column;padding:12px 16px}}
</style>
