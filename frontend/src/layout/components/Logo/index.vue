<template>
  <div class="logo">
    <img :src="websiteConfig.logo" alt="" :class="{ 'mr-2': !collapsed }" />
    <div v-show="!collapsed" class="logo-text">
      <span class="logo-en">{{ websiteConfig.enTitle }}</span>
      <span class="logo-cn">{{ websiteConfig.title }}</span>
    </div>
  </div>
</template>

<script lang="ts">
  import { websiteConfig } from '@/config/website.config';
  export default {
    name: 'Index',
    props: {
      collapsed: {
        type: Boolean,
      },
    },
    data() {
      return {
        websiteConfig,
      };
    },
  };
</script>

<style lang="less" scoped>
  .logo {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    height: 60px;
    padding: 0 20px;
    overflow: hidden;
    white-space: nowrap;
    border-bottom: 1px solid #f1f5f9;

    img {
      width: 42px;
      height: 42px;
      object-fit: contain;
      flex-shrink: 0;
    }

    .logo-text {
      display: flex;
      flex-direction: column;
      margin-left: 12px;
      line-height: 1.15;
    }

    .logo-en {
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.14em;
      color: #94a3b8;
      text-transform: uppercase;
    }

    .logo-cn {
      margin-top: 3px;
      color: #0f172a;
      font-size: 15px;
      font-weight: 500;
      letter-spacing: -0.01em;
    }
  }
</style>
