import { defineStore } from 'pinia';
import { store } from '@/store';
import designSetting from '@/settings/designSetting';
import { storage } from '@/utils/Storage';
import { DESIGN_SETTING } from '@/store/mutation-types';

const { darkTheme, appTheme, appThemeList } = designSetting;

interface PersistedDesignSetting {
  darkTheme?: boolean;
  appTheme?: string;
}

const persistedSetting = storage.get(DESIGN_SETTING, {}) as PersistedDesignSetting;
const initialDarkTheme =
  typeof persistedSetting.darkTheme === 'boolean' ? persistedSetting.darkTheme : darkTheme;
const initialAppTheme = appThemeList.includes(persistedSetting.appTheme || '')
  ? persistedSetting.appTheme!
  : appTheme;

interface DesignSettingState {
  //深色主题
  darkTheme: boolean;
  //系统风格
  appTheme: string;
  //系统内置风格
  appThemeList: string[];
}

export const useDesignSettingStore = defineStore({
  id: 'app-design-setting',
  state: (): DesignSettingState => ({
    darkTheme: initialDarkTheme,
    appTheme: initialAppTheme,
    appThemeList,
  }),
  getters: {
    getDarkTheme(): boolean {
      return this.darkTheme;
    },
    getAppTheme(): string {
      return this.appTheme;
    },
    getAppThemeList(): string[] {
      return this.appThemeList;
    },
  },
  actions: {
    persistSetting(): void {
      storage.set(
        DESIGN_SETTING,
        { darkTheme: this.darkTheme, appTheme: this.appTheme },
        null
      );
    },
    setDarkTheme(value: boolean): void {
      this.darkTheme = value;
      this.persistSetting();
    },
    setAppTheme(value: string): void {
      if (!this.appThemeList.includes(value)) return;
      this.appTheme = value;
      this.persistSetting();
    },
  },
});

// Need to be used outside the setup
export function useDesignSetting() {
  return useDesignSettingStore(store);
}
