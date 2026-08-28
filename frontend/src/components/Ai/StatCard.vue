<template>
  <div class="stat-card" :class="`stat-card--${color}`">
    <p class="stat-card__label">{{ label }}</p>
    <p class="stat-card__value">{{ value }}</p>
    <p v-if="change" class="stat-card__change" :class="trend === 'down' ? 'is-down' : 'is-up'">
      {{ change }}
    </p>
  </div>
</template>

<script lang="ts" setup>
defineProps<{
  label: string;
  value: number | string;
  change?: string;
  trend?: 'up' | 'down';
  color?: 'indigo' | 'teal' | 'blue' | 'coral';
}>();
</script>

<style lang="less" scoped>
.stat-card {
  background: #fff;
  border: 1px solid #E5E7EB;
  border-radius: 10px;
  padding: 18px 20px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;

  &:hover {
    border-color: #D1D5DB;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  }

  &--indigo { border-top: 3px solid #5B6AF0; }
  &--teal   { border-top: 3px solid #10B981; }
  &--blue   { border-top: 3px solid #3B82F6; }
  &--coral  { border-top: 3px solid #F43F5E; }

  &__label {
    font-size: 12px;
    font-weight: 500;
    color: #6B7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0 0 8px 0;
  }

  &__value {
    font-size: 28px;
    font-weight: 700;
    color: #111827;
    margin: 0;
    line-height: 1.15;
    letter-spacing: -0.02em;
  }

  &__change {
    font-size: 13px;
    margin: 6px 0 0 0;
    font-weight: 500;

    &.is-up   { color: #059669; }
    &.is-down { color: #E11D48; }
  }
}
</style>
