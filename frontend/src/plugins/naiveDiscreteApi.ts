import * as NaiveUI from 'naive-ui';
import { computed } from 'vue';
import { useDesignSetting } from '@/store/modules/designSetting';
import { lighten } from '@/utils/index';

export function setupNaiveDiscreteApi() {
  const designStore = useDesignSetting();

  const configProviderPropsRef = computed(() => ({
    theme: designStore.darkTheme ? NaiveUI.darkTheme : undefined,
    themeOverrides: {
      common: {
        primaryColor: designStore.appTheme,
        primaryColorHover: lighten(designStore.appTheme, 6),
        primaryColorPressed: lighten(designStore.appTheme, 6),
        primaryColorSuppl: designStore.appTheme,
        borderRadius: '6px',
        fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
        fontFamilyMono: "'JetBrains Mono', monospace",
      },
      LoadingBar: { colorLoading: designStore.appTheme },
      Card: {
        borderRadius: '10px',
        borderColor: '#E5E7EB',
        titleTextColor: '#1F2937',
        titleFontWeight: '600',
      },
      Tag: { borderRadius: '4px' },
      Button: {
        borderRadiusMedium: '6px',
        // 与 App.vue 的 NConfigProvider 保持一致，否则弹窗里的按钮配色和页面对不上：
        //   ① 深色下实心主按钮用白字（naive 默认给亮底配黑字）
        //   ② 深色下文字形态主按钮用提亮主色（#2563EB 在深色面上只有 3.16）
        ...(designStore.darkTheme
          ? {
              textColorPrimary: '#FFFFFF',
              textColorHoverPrimary: '#FFFFFF',
              textColorPressedPrimary: '#FFFFFF',
              textColorFocusPrimary: '#FFFFFF',
              textColorTextPrimary: '#79b8e8',
              textColorTextHoverPrimary: '#9ccbf0',
              textColorTextPressedPrimary: '#9ccbf0',
              textColorTextFocusPrimary: '#9ccbf0',
              textColorGhostPrimary: '#79b8e8',
              textColorGhostHoverPrimary: '#9ccbf0',
              textColorGhostPressedPrimary: '#9ccbf0',
              textColorGhostFocusPrimary: '#9ccbf0',
            }
          : {}),
      },
      Pagination: designStore.darkTheme
        ? { itemTextColorActive: '#79b8e8', itemTextColorActiveHover: '#9ccbf0' }
        : {},
      DataTable: {
        thColor: '#F9FAFB',
        thFontWeight: '600',
        tdColorHover: '#F3F4FF',
      },
    },
  }));
  const { message, dialog, notification, loadingBar } = NaiveUI.createDiscreteApi(
    ['message', 'dialog', 'notification', 'loadingBar'],
    { configProviderProps: configProviderPropsRef }
  );

  window['$message'] = message;
  window['$dialog'] = dialog;
  window['$notification'] = notification;
  window['$loading'] = loadingBar;
}
