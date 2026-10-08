<template>
  <div class="logo" :class="{ 'logo-collapsed': collapsed }">
    <img
      v-if="websiteConfig.platformIcon"
      class="logo-image"
      :class="{ 'logo-image--contrast': websiteConfig.logoNeedsContrastPlate }"
      :src="websiteConfig.platformIcon"
      alt="平台图标"
    />
    <span v-else class="logo-mark" aria-hidden="true">TP</span>
    <div v-show="!collapsed" class="logo-text">
      <span class="logo-cn">{{ websiteConfig.title }}</span>
      <span class="logo-en">{{ websiteConfig.enTitle }}</span>
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
    gap: 11px;
    padding: 0 16px;
    overflow: hidden;
    white-space: nowrap;
    border-bottom: 1px solid #eef2f7;

    .logo-mark {
      display: inline-grid;
      width: 32px;
      height: 32px;
      place-items: center;
      flex-shrink: 0;
      border-radius: 9px;
      color: #fff;
      background: linear-gradient(135deg, #2563eb, #4f8ef7);
      font-size: 14px;
      font-weight: 700;
    }

    .logo-image {
      width: 32px;
      height: 32px;
      box-sizing: border-box;
      flex-shrink: 0;
      border-radius: 8px;
      object-fit: contain;
    }

    .logo-image--contrast {
      padding: 4px;
      border: 1px solid #cfd5dc;
      background: #eef1f3;
    }

    .logo-text {
      display: flex;
      flex-direction: column;
      min-width: 0;
      line-height: 1.2;
    }

    .logo-en {
      margin-top: 2px;
      font-size: 10px;
      font-weight: 400;
      letter-spacing: 0.1em;
      color: #94a3b8;
      text-transform: uppercase;
    }

    .logo-cn {
      color: #0f172a;
      font-size: 14px;
      font-weight: 600;
    }
  }

  .logo-collapsed {
    justify-content: center;
    gap: 0;
    padding-right: 0;
    padding-left: 0;

    .logo-image,
    .logo-mark {
      width: 34px;
      height: 34px;
    }
  }
</style>
