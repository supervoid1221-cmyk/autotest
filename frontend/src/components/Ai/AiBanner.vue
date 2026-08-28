<template>
  <div class="ai-banner">
    <span class="ai-banner__text">{{ message }}</span>
    <n-button v-if="buttonText" size="small" class="ai-banner__btn" @click="$emit('action')">
      {{ buttonText }}
    </n-button>
  </div>
</template>

<script lang="ts" setup>
defineProps<{ message: string; buttonText?: string }>();
defineEmits<{ action: [] }>();
</script>

<style lang="less" scoped>
.ai-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #F3F4FF;
  border: 1px solid #DFE3FF;
  border-radius: 10px;
  padding: 14px 20px;

  &__text { font-size: 13px; font-weight: 500; color: #4338CA; }
  &__btn { flex-shrink: 0; }
}
</style>
