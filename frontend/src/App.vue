<template>
  <NConfigProvider
    v-if="!isLock"
    :locale="zhCN"
    :theme="getDarkTheme"
    :theme-overrides="getThemeOverrides"
    :date-locale="dateZhCN"
  >
    <AppProvider>
      <RouterView />
    </AppProvider>
  </NConfigProvider>

  <transition v-if="isLock && $route.name !== 'login'" name="slide-up">
    <LockScreen />
  </transition>
</template>

<script lang="ts" setup>
  import { computed, onMounted, onUnmounted } from 'vue';
  import { zhCN, dateZhCN, darkTheme } from 'naive-ui';
  import { LockScreen } from '@/components/Lockscreen';
  import { AppProvider } from '@/components/Application';
  import { useScreenLockStore } from '@/store/modules/screenLock.js';
  import { useRoute } from 'vue-router';
  import { useDesignSettingStore } from '@/store/modules/designSetting';
  import { lighten } from '@/utils/index';

  const route = useRoute();
  const useScreenLock = useScreenLockStore();
  const designStore = useDesignSettingStore();
  const isLock = computed(() => useScreenLock.isLocked);
  const lockTime = computed(() => useScreenLock.lockTime);

  /**
   * @type import('naive-ui').GlobalThemeOverrides
   */
  const getThemeOverrides = computed(() => {
    const appTheme = designStore.appTheme;
    const lightenStr = lighten(designStore.appTheme, 6);
    return {
      common: {
        primaryColor: appTheme,
        primaryColorHover: lightenStr,
        primaryColorPressed: lightenStr,
        primaryColorSuppl: appTheme,
        borderRadius: '6px',
        fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
        fontFamilyMono: "'JetBrains Mono', monospace",
      },
      LoadingBar: { colorLoading: appTheme },
      Card: {
        borderRadius: '10px',
        borderColor: '#E5E7EB',
        titleTextColor: '#1F2937',
        titleFontWeight: '600',
      },
      Tag: { borderRadius: '4px' },
      Button: { borderRadiusMedium: '6px' },
      DataTable: {
        thColor: '#F9FAFB',
        thFontWeight: '600',
        tdColorHover: '#F3F4FF',
      },
      // 左侧菜单视觉规范：slate 字阶 + 蓝色激活态 + 浅蓝底
      Menu: {
        // 形态
        itemHeight: '42px',
        itemBorderRadius: '8px',
        fontSize: '14px',
        itemMargin: '2px 0',
        groupLabelPadding: '10px 12px 6px 12px',
        // 默认态（弱化 slate 色阶）
        itemColor: 'transparent',
        itemTextColor: '#475569',
        itemIconColor: '#94A3B8',
        itemTextColorHover: '#0F172A',
        itemIconColorHover: '#475569',
        itemColorHover: '#F1F5F9',
        arrowColor: '#94A3B8',
        arrowColorHover: '#475569',
        groupTextColor: '#94A3B8',
        // 激活态（主色 #2563EB + 浅蓝底 #EFF6FF）
        itemTextColorActive: '#2563EB',
        itemIconColorActive: '#2563EB',
        itemColorActive: '#EFF6FF',
        itemColorActiveHover: '#EFF6FF',
        itemTextColorChildActive: '#2563EB',
        itemIconColorChildActive: '#2563EB',
        itemColorActiveCollapsed: '#EFF6FF',
        arrowColorActive: '#2563EB',
        arrowColorChildActive: '#2563EB',
        // 暗色侧边栏（navTheme=dark/header-dark）下的协调配色
        itemTextColorInverted: '#CBD5E1',
        itemIconColorInverted: '#94A3B8',
        itemTextColorHoverInverted: '#F1F5F9',
        itemIconColorHoverInverted: '#CBD5E1',
        itemColorHoverInverted: 'rgba(255,255,255,0.06)',
        itemTextColorActiveInverted: '#60A5FA',
        itemIconColorActiveInverted: '#60A5FA',
        itemColorActiveInverted: 'rgba(37,99,235,0.20)',
        itemColorActiveHoverInverted: 'rgba(37,99,235,0.20)',
        itemTextColorChildActiveInverted: '#60A5FA',
        itemIconColorChildActiveInverted: '#60A5FA',
        arrowColorInverted: '#94A3B8',
        arrowColorActiveInverted: '#60A5FA',
        arrowColorChildActiveInverted: '#60A5FA',
        groupTextColorInverted: '#64748B',
      },
    };
  });

  const getDarkTheme = computed(() => (designStore.darkTheme ? darkTheme : undefined));

  let timer: NodeJS.Timer;

  const timekeeping = () => {
    clearInterval(timer);
    if (route.name == 'login' || isLock.value) return;
    // 设置不锁屏
    useScreenLock.setLock(false);
    // 重置锁屏时间
    useScreenLock.setLockTime();
    timer = setInterval(() => {
      // 锁屏倒计时递减
      useScreenLock.setLockTime(lockTime.value - 1);
      if (lockTime.value <= 0) {
        // 设置锁屏
        useScreenLock.setLock(true);
        return clearInterval(timer);
      }
    }, 1000);
  };

  onMounted(() => {
    document.addEventListener('mousedown', timekeeping);
  });

  onUnmounted(() => {
    document.removeEventListener('mousedown', timekeeping);
  });
</script>

<style lang="less">
  @import 'styles/index.less';
</style>
