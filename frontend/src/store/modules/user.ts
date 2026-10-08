import { defineStore } from 'pinia';
import { store } from '@/store';
import {
  ACCESS_TOKEN,
  ACCESS_TOKEN_EXPIRES_AT,
  LAST_SESSION_ACTIVITY_AT,
  CURRENT_TENANT,
  CURRENT_USER,
} from '@/store/mutation-types';
import { ResultEnum } from '@/enums/httpEnum';

import { login, profile, renewSession as renewSessionRequest } from '@/api/account/http';
import { storage } from '@/utils/Storage';
import { useScreenLockStore } from '@/store/modules/screenLock';

export type UserInfoType = {
  name?: string;
  email?: string;
  username?: string;
  token?: string;
  token_expires_at?: string;
};

export interface IUserState {
  token: string;
  tokenExpiresAt: number;
  username: string;
  welcome: string;
  avatar: string;
  permissions: any[];
  info: UserInfoType;
}

export const useUserStore = defineStore({
  id: 'app-user',
  state: (): IUserState => ({
    token: storage.get(ACCESS_TOKEN, ''),
    tokenExpiresAt: Number(storage.get(ACCESS_TOKEN_EXPIRES_AT, 0)) || 0,
    username: '',
    welcome: '',
    avatar: '',
    permissions: [],
    info: storage.get(CURRENT_USER, {}),
  }),
  getters: {
    getToken(): string {
      return this.token;
    },
    getTokenExpiresAt(): number {
      return this.tokenExpiresAt;
    },
    getAvatar(): string {
      return this.avatar;
    },
    getNickname(): string {
      return this.username;
    },
    getPermissions(): [any][] {
      return this.permissions;
    },
    getUserInfo(): UserInfoType {
      return this.info;
    },
  },
  actions: {
    setToken(token: string) {
      this.token = token;
    },
    setTokenExpiresAt(expiresAt: number) {
      this.tokenExpiresAt = expiresAt;
    },
    setAvatar(avatar: string) {
      this.avatar = avatar;
    },
    setPermissions(permissions) {
      this.permissions = permissions;
    },
    setUserInfo(info: UserInfoType) {
      this.info = info;
    },
    // 登录
    async login(params: any) {
      const response = await login(params); // 调用API
      const { result, code } = response;
      if (code === ResultEnum.SUCCESS) {
        const expiresAt = Date.parse(result.token_expires_at || '');
        const normalizedExpiresAt = Number.isFinite(expiresAt)
          ? expiresAt
          : Date.now() + 60 * 60 * 1000;
        // 服务端每次签发/续期后有效 1 小时。本地保留过期令牌只为了
        // 刷新页面后仍能进入屏保重新激活，过期令牌无法通过后端认证。
        const localSessionMemory = 7 * 24 * 60 * 60;
        // 先写到期时间再写 Token，避免其他标签页收到 Token 变更时
        // 短暂读到“新 Token + 旧过期时间”并误触发锁屏。
        storage.set(ACCESS_TOKEN_EXPIRES_AT, normalizedExpiresAt, localSessionMemory);
        storage.set(ACCESS_TOKEN, result.token, localSessionMemory);
        storage.set(CURRENT_USER, result, localSessionMemory);
        storage.set(LAST_SESSION_ACTIVITY_AT, Date.now(), localSessionMemory);
        // 屏保重新认证时由 Lockscreen 在恢复原路由后再解锁。
        if (!params?.isLock) useScreenLockStore().setLock(false);
        if (!params?.isLock) storage.remove(CURRENT_TENANT);
        this.setToken(result.token);
        this.setTokenExpiresAt(normalizedExpiresAt);
        this.setUserInfo(result);
      }
      return response;
    },

    async renewSession() {
      const result = await renewSessionRequest();
      const expiresAt = Date.parse(result.token_expires_at || '');
      if (!Number.isFinite(expiresAt)) throw new Error('会话续期响应缺少有效过期时间。');
      const localSessionMemory = 7 * 24 * 60 * 60;
      storage.set(ACCESS_TOKEN_EXPIRES_AT, expiresAt, localSessionMemory);
      this.setTokenExpiresAt(expiresAt);
      return expiresAt;
    },

    // 获取用户信息
    async getInfo() {
      const result = await profile();
      this.setAvatar(result.avatar);
      this.setUserInfo(result);
      return result;
    },

    // 登出
    async logout() {
      this.setPermissions([]);
      this.setUserInfo({ name: '', email: '' });
      storage.remove(ACCESS_TOKEN);
      storage.remove(ACCESS_TOKEN_EXPIRES_AT);
      storage.remove(LAST_SESSION_ACTIVITY_AT);
      storage.remove(CURRENT_USER);
      storage.remove(CURRENT_TENANT);
      this.setToken('');
      this.setTokenExpiresAt(0);
    },
  },
});

// Need to be used outside the setup
export function useUser() {
  return useUserStore(store);
}
