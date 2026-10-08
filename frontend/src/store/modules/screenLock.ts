import { defineStore } from 'pinia';
import { IS_SCREENLOCKED } from '@/store/mutation-types';
import { storage } from '@/utils/Storage';

const isLocked = storage.get(IS_SCREENLOCKED, false);

export type IScreenLockState = {
  isLocked: boolean; // 是否锁屏
  reason: 'manual' | 'idle' | 'expired';
  resumePath: string;
};

export const useScreenLockStore = defineStore({
  id: 'app-screen-lock',
  state: (): IScreenLockState => ({
    isLocked: isLocked === true, // 是否锁屏
    reason: 'manual',
    resumePath: '',
  }),
  getters: {},
  actions: {
    setLock(payload: boolean, reason: 'manual' | 'idle' | 'expired' = 'manual', resumePath = '') {
      this.isLocked = payload;
      this.reason = payload ? reason : 'manual';
      if (payload && resumePath) this.resumePath = resumePath;
      storage.set(IS_SCREENLOCKED, this.isLocked);
    },
    clearResumePath() {
      this.resumePath = '';
    },
  },
});
