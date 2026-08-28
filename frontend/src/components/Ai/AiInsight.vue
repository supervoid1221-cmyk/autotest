<template>
  <div class="ai-insight">
    <h4 class="ai-insight__title">{{ title }}</h4>
    <p class="ai-insight__content">{{ content }}</p>
    <slot name="extra" />
  </div>
</template>

<script lang="ts" setup>
defineProps<{ title: string; content: string }>();
</script>

<style lang="less" scoped>
.ai-insight {
  background: #F3F4FF;
  border: 1px solid #DFE3FF;
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 14px;

  &__title {
    font-size: 13px;
    font-weight: 600;
    color: #4338CA;
    margin: 0 0 8px 0;
  }
  &__content {
    font-size: 13px;
    color: #4F46E5;
    line-height: 1.6;
    margin: 0;
  }
}
</style>
