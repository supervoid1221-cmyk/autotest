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
      Button: { borderRadiusMedium: '6px' },
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
