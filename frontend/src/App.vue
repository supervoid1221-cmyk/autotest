<template>
  <NConfigProvider
    :locale="zhCN"
    :theme="getDarkTheme"
    :theme-overrides="getThemeOverrides"
    :date-locale="dateZhCN"
  >
    <AppProvider>
      <RouterView />
      <transition name="slide-up">
        <LockScreen v-if="isLock" />
      </transition>
    </AppProvider>
  </NConfigProvider>
</template>

<script lang="ts" setup>
  import { computed, onMounted, onUnmounted, watch } from 'vue';
  import { zhCN, dateZhCN, darkTheme } from 'naive-ui';
  import { LockScreen } from '@/components/Lockscreen';
  import { AppProvider } from '@/components/Application';
  import { useScreenLockStore } from '@/store/modules/screenLock.js';
  import { useRoute } from 'vue-router';
  import { useDesignSettingStore } from '@/store/modules/designSetting';
  import { useUserStore } from '@/store/modules/user';
  import { storage } from '@/utils/Storage';
  import {
    ACCESS_TOKEN,
    ACCESS_TOKEN_EXPIRES_AT,
    LAST_SESSION_ACTIVITY_AT,
  } from '@/store/mutation-types';
  import { syncBrandingTheme } from '@/config/website.config';
  import { PageEnum } from '@/enums/pageEnum';
  import { lighten } from '@/utils/index';

  const route = useRoute();
  const useScreenLock = useScreenLockStore();
  const designStore = useDesignSettingStore();
  const userStore = useUserStore();
  const isLock = computed(() => useScreenLock.isLocked);

  /**
   * 深色下的「主色文字」用色。
   * 主色 #2563EB 是给「当底色」设计的，直接当文字色放在深色面上太暗：
   * 在 #202020 上只有 3.16，在全局选中态的 #3b3b3b 上只有 2.17。
   * 这里统一提亮成同一色相（和 dark-theme.less 里链接/图标用的深色强调色一致）。
   */
  const DARK_ACCENT_TEXT = '#79b8e8';
  const DARK_ACCENT_TEXT_HOVER = '#9ccbf0';

  /**
   * @type import('naive-ui').GlobalThemeOverrides
   */
  const getThemeOverrides = computed(() => {
    const appTheme = designStore.appTheme;
    const lightenStr = lighten(designStore.appTheme, 6);
    const isDark = designStore.darkTheme;
    return {
      common: {
        primaryColor: appTheme,
        primaryColorHover: lightenStr,
        primaryColorPressed: lightenStr,
        primaryColorSuppl: appTheme,
        borderRadius: '6px',
        fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
        fontFamilyMono: "'JetBrains Mono', monospace",
        bodyColor: isDark ? '#181818' : '#FFFFFF',
        cardColor: isDark ? '#202020' : '#FFFFFF',
        modalColor: isDark ? '#202020' : '#FFFFFF',
        popoverColor: isDark ? '#252525' : '#FFFFFF',
        tableColor: isDark ? '#202020' : '#FFFFFF',
        inputColor: isDark ? '#1C1C1C' : '#FFFFFF',
        actionColor: isDark ? '#292929' : '#F9FAFB',
        textColorBase: isDark ? '#D6D6D6' : '#1F2937',
        textColor1: isDark ? '#D6D6D6' : '#1F2937',
        textColor2: isDark ? '#D6D6D6' : '#4B5563',
        textColor3: isDark ? '#8996A8' : '#6B7280',
        borderColor: isDark ? '#353535' : '#E5E7EB',
        dividerColor: isDark ? '#303030' : '#E5E7EB',
      },
      LoadingBar: { colorLoading: appTheme },
      Card: {
        borderRadius: '10px',
        borderColor: isDark ? '#353535' : '#E5E7EB',
        titleTextColor: isDark ? '#D6D6D6' : '#1F2937',
        titleFontWeight: '600',
      },
      Tag: { borderRadius: '4px' },
      Button: {
        borderRadiusMedium: '6px',
        // 深色下主色 #2563EB 和 naive 深色主题的两个默认假设都对不上，必须成对改：
        //   ① 实心主按钮：naive 默认给「亮底」配黑字（它的默认深色主色是很亮的薄荷绿）。
        //      我们换成中深蓝后就成了蓝底黑字，对比度 4.08，低于正文 4.5，观感也脏 → 改白字。
        //   ② 文字形态主按钮（`text` / `ghost`，透明底 + 主色文字）：#2563EB 落在
        //      #202020 上只有 3.16，落在全局选中态的 #3b3b3b 上只有 2.17 → 用提亮主色。
        ...(isDark
          ? {
              textColorPrimary: '#FFFFFF',
              textColorHoverPrimary: '#FFFFFF',
              textColorPressedPrimary: '#FFFFFF',
              textColorFocusPrimary: '#FFFFFF',
              textColorTextPrimary: DARK_ACCENT_TEXT,
              textColorTextHoverPrimary: DARK_ACCENT_TEXT_HOVER,
              textColorTextPressedPrimary: DARK_ACCENT_TEXT_HOVER,
              textColorTextFocusPrimary: DARK_ACCENT_TEXT_HOVER,
              textColorGhostPrimary: DARK_ACCENT_TEXT,
              textColorGhostHoverPrimary: DARK_ACCENT_TEXT_HOVER,
              textColorGhostPressedPrimary: DARK_ACCENT_TEXT_HOVER,
              textColorGhostFocusPrimary: DARK_ACCENT_TEXT_HOVER,
            }
          : {}),
      },
      // 分页器「当前页」的文字色同样吃主色。深色下底色是全局选中态的 #3b3b3b，
      // #2563EB 落在上面只有 2.17，等于看不清页码。
      Pagination: isDark
        ? { itemTextColorActive: DARK_ACCENT_TEXT, itemTextColorActiveHover: DARK_ACCENT_TEXT_HOVER }
        : {},
      DataTable: {
        thColor: isDark ? '#252525' : '#F9FAFB',
        tdColor: isDark ? '#202020' : '#FFFFFF',
        borderColor: isDark ? '#353535' : '#E5E7EB',
        thTextColor: isDark ? '#8996A8' : '#374151',
        tdTextColor: isDark ? '#D6D6D6' : '#374151',
        thFontWeight: '600',
        tdColorHover: isDark ? '#292929' : '#F3F4FF',
      },
      // 左侧菜单视觉规范：slate 字阶 + 蓝色激活态 + 浅蓝底
      Menu: {
        // 形态
        itemHeight: '40px',
        itemBorderRadius: '9px',
        fontSize: '13.5px',
        itemMargin: '1px 0',
        groupLabelPadding: '10px 12px 6px 12px',
        // 默认态（弱化 slate 色阶）
        itemColor: 'transparent',
        itemTextColor: isDark ? '#D6D6D6' : '#475569',
        itemIconColor: isDark ? '#8996A8' : '#94A3B8',
        itemTextColorHover: isDark ? '#D6D6D6' : '#0F172A',
        itemIconColorHover: isDark ? '#D6D6D6' : '#475569',
        itemColorHover: isDark ? 'rgba(255,255,255,0.06)' : '#F1F5F9',
        arrowColor: isDark ? '#8996A8' : '#94A3B8',
        arrowColorHover: isDark ? '#D6D6D6' : '#475569',
        groupTextColor: isDark ? '#8996A8' : '#94A3B8',
        // 激活态（主色 #2563EB + 浅蓝底 #EFF6FF）
        itemTextColorActive: isDark ? '#60A5FA' : '#2563EB',
        itemIconColorActive: isDark ? '#60A5FA' : '#2563EB',
        itemColorActive: isDark ? 'rgba(37,99,235,0.20)' : '#EFF6FF',
        itemColorActiveHover: isDark ? 'rgba(37,99,235,0.24)' : '#EFF6FF',
        itemTextColorChildActive: isDark ? '#60A5FA' : '#2563EB',
        itemIconColorChildActive: isDark ? '#60A5FA' : '#2563EB',
        itemColorActiveCollapsed: isDark ? 'rgba(37,99,235,0.20)' : '#EFF6FF',
        arrowColorActive: isDark ? '#60A5FA' : '#2563EB',
        arrowColorChildActive: isDark ? '#60A5FA' : '#2563EB',
        // 暗色侧边栏（navTheme=dark/header-dark）下的协调配色
        itemTextColorInverted: '#D6D6D6',
        itemIconColorInverted: '#8996A8',
        itemTextColorHoverInverted: '#D6D6D6',
        itemIconColorHoverInverted: '#D6D6D6',
        itemColorHoverInverted: 'rgba(255,255,255,0.06)',
        itemTextColorActiveInverted: '#60A5FA',
        itemIconColorActiveInverted: '#60A5FA',
        itemColorActiveInverted: 'rgba(37,99,235,0.20)',
        itemColorActiveHoverInverted: 'rgba(37,99,235,0.20)',
        itemTextColorChildActiveInverted: '#60A5FA',
        itemIconColorChildActiveInverted: '#60A5FA',
        arrowColorInverted: '#8996A8',
        arrowColorActiveInverted: '#60A5FA',
        arrowColorChildActiveInverted: '#60A5FA',
        groupTextColorInverted: '#8996A8',
      },
    };
  });

  const getDarkTheme = computed(() => (designStore.darkTheme ? darkTheme : undefined));

  watch(
    () => designStore.darkTheme,
    (isDark) => {
      document.documentElement.dataset.theme = isDark ? 'dark' : 'light';
      document.documentElement.style.colorScheme = isDark ? 'dark' : 'light';
      syncBrandingTheme(isDark);
    },
    { immediate: true }
  );

  const SESSION_IDLE_TIMEOUT = 60 * 60 * 1000;
  const SESSION_RENEW_CHECK_INTERVAL = 10 * 60 * 1000;
  const SESSION_RENEW_THRESHOLD = 30 * 60 * 1000;
  const SESSION_RENEW_RETRY_INTERVAL = 60 * 1000;
  const ACTIVITY_THROTTLE = 1000;
  const STORAGE_MEMORY_SECONDS = 7 * 24 * 60 * 60;

  let tokenExpiryTimer: ReturnType<typeof setTimeout> | undefined;
  let idleTimer: ReturnType<typeof setTimeout> | undefined;
  let renewalTimer: ReturnType<typeof setInterval> | undefined;
  let lastActivityHandledAt = 0;
  let lastRenewalAttemptAt = 0;
  let renewalPromise: Promise<number> | undefined;

  const storedActivityAt = () =>
    Number(storage.get(LAST_SESSION_ACTIVITY_AT, 0)) || Date.now();

  const lockExpiredSession = () => {
    // 旧定时器可能恰好在解锁换发新令牌时触发。只依据当前令牌
    // 的到期时间锁屏，不能让旧定时器再次覆盖刚完成的认证。
    if (route.name !== PageEnum.BASE_LOGIN_NAME && userStore.getToken &&
        userStore.getTokenExpiresAt && userStore.getTokenExpiresAt <= Date.now()) {
      useScreenLock.setLock(true, 'expired', route.fullPath);
    }
  };

  const scheduleTokenExpiry = () => {
    if (tokenExpiryTimer) clearTimeout(tokenExpiryTimer);
    tokenExpiryTimer = undefined;
    if (route.name === PageEnum.BASE_LOGIN_NAME || !userStore.getToken || !userStore.getTokenExpiresAt) return;

    const remaining = userStore.getTokenExpiresAt - Date.now();
    if (remaining <= 0) {
      lockExpiredSession();
      return;
    }
    tokenExpiryTimer = setTimeout(lockExpiredSession, remaining);
  };

  const scheduleIdleLock = () => {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = undefined;
    if (route.name === PageEnum.BASE_LOGIN_NAME || !userStore.getToken || useScreenLock.isLocked) return;
    const remaining = storedActivityAt() + SESSION_IDLE_TIMEOUT - Date.now();
    if (remaining <= 0) {
      useScreenLock.setLock(true, 'idle', route.fullPath);
      return;
    }
    idleTimer = setTimeout(scheduleIdleLock, remaining);
  };

  const renewActiveSession = async () => {
    const now = Date.now();
    if (
      renewalPromise ||
      now - lastRenewalAttemptAt < SESSION_RENEW_RETRY_INTERVAL ||
      route.name === PageEnum.BASE_LOGIN_NAME ||
      !userStore.getToken ||
      useScreenLock.isLocked ||
      now - storedActivityAt() >= SESSION_IDLE_TIMEOUT ||
      userStore.getTokenExpiresAt - now > SESSION_RENEW_THRESHOLD
    ) return;
    lastRenewalAttemptAt = now;
    renewalPromise = userStore.renewSession();
    try {
      await renewalPromise;
    } catch {
      // 续期失败由统一 401 处理进入屏保，网络短暂失败则交给下一轮重试。
    } finally {
      renewalPromise = undefined;
    }
  };

  const recordActivity = () => {
    const now = Date.now();
    if (
      now - lastActivityHandledAt < ACTIVITY_THROTTLE ||
      route.name === PageEnum.BASE_LOGIN_NAME ||
      !userStore.getToken ||
      useScreenLock.isLocked
    ) return;
    lastActivityHandledAt = now;
    storage.set(LAST_SESSION_ACTIVITY_AT, now, STORAGE_MEMORY_SECONDS);
    scheduleIdleLock();
    if (userStore.getTokenExpiresAt - now <= SESSION_RENEW_THRESHOLD) {
      void renewActiveSession();
    }
  };

  const verifyTokenExpiry = () => {
    if (document.visibilityState === 'visible') {
      scheduleIdleLock();
      if (!useScreenLock.isLocked) recordActivity();
      scheduleTokenExpiry();
      void renewActiveSession();
    }
  };

  const syncSessionFromStorage = (event: StorageEvent) => {
    if (![ACCESS_TOKEN, ACCESS_TOKEN_EXPIRES_AT, LAST_SESSION_ACTIVITY_AT].includes(event.key || '')) {
      return;
    }
    const token = storage.get(ACCESS_TOKEN, '');
    const expiresAt = Number(storage.get(ACCESS_TOKEN_EXPIRES_AT, 0)) || 0;
    if (token !== userStore.getToken) userStore.setToken(token);
    if (expiresAt !== userStore.getTokenExpiresAt) userStore.setTokenExpiresAt(expiresAt);
    scheduleTokenExpiry();
    scheduleIdleLock();
  };

  watch(
    [
      () => route.name,
      () => userStore.getToken,
      () => userStore.getTokenExpiresAt,
      () => useScreenLock.isLocked,
    ],
    () => {
      scheduleTokenExpiry();
      scheduleIdleLock();
    },
    { immediate: true }
  );

  onMounted(() => {
    document.addEventListener('visibilitychange', verifyTokenExpiry);
    for (const eventName of ['pointermove', 'pointerdown', 'keydown', 'scroll', 'touchstart']) {
      window.addEventListener(eventName, recordActivity, { passive: true });
    }
    window.addEventListener('storage', syncSessionFromStorage);
    renewalTimer = setInterval(() => void renewActiveSession(), SESSION_RENEW_CHECK_INTERVAL);
    recordActivity();
  });

  onUnmounted(() => {
    if (tokenExpiryTimer) clearTimeout(tokenExpiryTimer);
    if (idleTimer) clearTimeout(idleTimer);
    if (renewalTimer) clearInterval(renewalTimer);
    document.removeEventListener('visibilitychange', verifyTokenExpiry);
    for (const eventName of ['pointermove', 'pointerdown', 'keydown', 'scroll', 'touchstart']) {
      window.removeEventListener(eventName, recordActivity);
    }
    window.removeEventListener('storage', syncSessionFromStorage);
  });
</script>

<style lang="less">
  @import 'styles/index.less';
</style>
