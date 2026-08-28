<template>
  <div class="activity-feed">
    <div v-if="loading" class="skeleton-list">
      <n-skeleton v-for="i in 4" :key="i" height="44" class="mb-3" />
    </div>
    <div v-else>
      <div v-for="(item, index) in items" :key="index" class="activity-item">
        <span class="activity-item__icon" :style="{ background: item.iconBg, color: item.iconColor }">
          {{ item.icon }}
        </span>
        <div class="activity-item__body">
          <p class="activity-item__desc" v-html="item.description"></p>
          <span class="activity-item__time">{{ item.time }}</span>
        </div>
      </div>
      <div v-if="!items.length" class="empty-state">
        <p>暂无活动记录</p>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
interface ActivityItem {
  icon: string;
  iconBg: string;
  iconColor: string;
  description: string;
  time: string;
}

defineProps<{
  items: ActivityItem[];
  loading?: boolean;
}>();
</script>

<style lang="less" scoped>
.activity-feed {
  min-height: 100px;
}

.activity-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 0;
  border-bottom: 0.5px solid var(--color-border-tertiary);

  &:last-child { border-bottom: none; }

  &__icon {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    flex-shrink: 0;
  }

  &__body {
    flex: 1;
    min-width: 0;
  }

  &__desc {
    font-size: 13px;
    color: var(--color-text-primary);
    margin: 0;
    line-height: 1.5;
  }

  &__time {
    font-size: 12px;
    color: var(--color-text-tertiary);
    display: block;
    margin-top: 2px;
  }
}

.skeleton-list { padding: 8px 0; }
.empty-state { text-align: center; padding: 32px 0; color: var(--color-text-tertiary); font-size: 13px; }
</style>
