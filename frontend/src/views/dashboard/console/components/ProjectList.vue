<template>
  <div class="project-list">
    <div v-if="loading" class="skeleton-list">
      <n-skeleton v-for="i in 4" :key="i" height="52" class="mb-3" />
    </div>
    <div v-else>
      <div v-for="item in projects" :key="item.id" class="project-item">
        <div class="project-item__info">
          <span class="text-avatar text-avatar-sm" :class="avatarColor(item.id || item.name)">
            {{ (item.name || '?').charAt(0) }}
          </span>
          <div>
            <p class="project-item__name">{{ item.name }}</p>
            <p class="project-item__meta">{{ item.api_count ?? item.endpoint_count ?? 0 }} 接口 · {{ item.scenario_count ?? 0 }} 场景</p>
          </div>
        </div>
        <span class="status-badge" :class="statusClass(item)">
          {{ statusLabel(item) }}
        </span>
      </div>
      <div v-if="!projects.length" class="empty-state">
        <p>暂无项目数据</p>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted } from 'vue';

interface ProjectItem {
  id: number | string;
  name: string;
  api_count?: number;
  endpoint_count?: number;
  scenario_count?: number;
  status?: string;
}

defineProps<{
  projects?: ProjectItem[];
  loading?: boolean;
}>();

const avatarColors = ['text-avatar-purple', 'text-avatar-teal', 'text-avatar-blue', 'text-avatar-coral'];

function avatarColor(id: string | number): string {
  const index = typeof id === 'string' ? id.length : Number(id);
  return avatarColors[index % avatarColors.length];
}

function statusClass(item: ProjectItem): string {
  const s = item.status || 'active';
  if (s === 'paused') return 'status-badge-paused';
  if (s === 'draft') return 'status-badge-draft';
  return 'status-badge-active';
}

function statusLabel(item: ProjectItem): string {
  const s = item.status || 'active';
  const map: Record<string, string> = { active: '运行中', paused: '已暂停', draft: '草稿' };
  return map[s] || '运行中';
}
</script>

<style lang="less" scoped>
.project-list {
  min-height: 100px;
}

.project-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 0;
  border-bottom: 0.5px solid var(--color-border-tertiary);

  &:last-child { border-bottom: none; }

  &__info {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  &__name {
    font-size: 13px;
    font-weight: 500;
    margin: 0;
    color: var(--color-text-primary);
  }

  &__meta {
    font-size: 12px;
    color: var(--color-text-secondary);
    margin: 2px 0 0 0;
  }
}

.skeleton-list { padding: 8px 0; }
.empty-state { text-align: center; padding: 32px 0; color: var(--color-text-tertiary); font-size: 13px; }
</style>
