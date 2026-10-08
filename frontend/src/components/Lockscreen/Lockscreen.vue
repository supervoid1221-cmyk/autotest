<template>
  <div
    :class="{ onLockLogin: showLogin }"
    class="lockscreen"
    ref="lockscreenRef"
    tabindex="-1"
    @keydown="handleLockKeydown"
    @mousedown.stop
    @contextmenu.prevent
  >
    <template v-if="!showLogin">
      <div class="lock-box">
        <div class="lock">
          <span class="lock-icon" title="前往登录页面" @click="goLogin">
            <n-icon>
              <lock-outlined />
            </n-icon>
          </span>
        </div>
      </div>
      <!--充电-->
      <recharge
        :battery="battery"
        :battery-status="batteryStatus"
        :calc-discharging-time="calcDischargingTime"
        :calc-charging-time="calcChargingTime"
      />

      <div class="local-time">
        <div class="time">{{ hour }}:{{ minute }}</div>
        <div class="date">{{ month }}月{{ day }}号，星期{{ week }}</div>
        <div v-if="isExpired" class="expired-hint">会话已过期，点击顶部锁图标重新登录激活</div>
      </div>
      <div class="computer-status">
        <span :class="{ offline: !online }" class="network">
          <wifi-outlined class="network" />
        </span>
        <api-outlined />
      </div>
    </template>

    <!--登录-->
    <template v-if="showLogin">
      <form class="login-box" @submit.prevent="onLogin">
        <n-avatar :size="128">
          <n-icon>
            <user-outlined />
          </n-icon>
        </n-avatar>
        <div class="username">{{ lockedUsername || '解锁屏幕' }}</div>
        <div v-if="isExpired" class="session-expired-tip">会话已过期，请重新登录激活</div>
        <n-input
          ref="usernameInputRef"
          v-model:value="loginParams.username"
          placeholder="请输入用户名"
          :input-props="{ name: 'username', autocomplete: 'username', 'aria-label': '解锁用户名' }"
        />
        <n-input
          ref="passwordInputRef"
          type="password"
          v-model:value="loginParams.password"
          placeholder="请输入登录密码"
          :input-props="{ name: 'password', autocomplete: 'current-password', 'aria-label': '解锁密码' }"
        >
          <template #suffix>
            <n-icon @click="onLogin" style="cursor: pointer">
              <LoadingOutlined v-if="loginLoading" />
              <arrow-right-outlined v-else />
            </n-icon>
          </template>
        </n-input>

        <div class="flex w-full" v-if="isLoginError">
          <span class="text-red-500">{{ errorMsg }}</span>
        </div>

        <div class="flex justify-around w-full mt-1">
          <div><a @click="showLogin = false">返回</a></div>
          <div><a @click="goLogin">重新登录</a></div>
          <div><a @click="onLogin">进入系统</a></div>
        </div>
      </form>
    </template>
  </div>
</template>

<script lang="ts">
  import { computed, defineComponent, nextTick, onMounted, reactive, ref, toRefs, watch } from 'vue';
  import type { InputInst } from 'naive-ui';
  import { ResultEnum } from '@/enums/httpEnum';
  import recharge from './Recharge.vue';
  import {
    LockOutlined,
    LoadingOutlined,
    UserOutlined,
    ApiOutlined,
    ArrowRightOutlined,
    WifiOutlined,
  } from '@vicons/antd';

  import { useRouter, useRoute } from 'vue-router';
  import { resolveLoginRedirect } from '@/router/loginRedirect';
  import { useOnline } from '@/hooks/useOnline';
  import { useTime } from '@/hooks/useTime';
  import { useBattery } from '@/hooks/useBattery';
  import { useScreenLockStore } from '@/store/modules/screenLock';
  import { UserInfoType, useUserStore } from '@/store/modules/user';

  export default defineComponent({
    name: 'ScreenLock',
    components: {
      LockOutlined,
      LoadingOutlined,
      UserOutlined,
      ArrowRightOutlined,
      ApiOutlined,
      WifiOutlined,
      recharge,
    },
    setup() {
      const useScreenLock = useScreenLockStore();
      const userStore = useUserStore();

      // 获取时间
      const { month, day, hour, minute, second, week } = useTime();
      const { online } = useOnline();

      const router = useRouter();
      const route = useRoute();

      const { battery, batteryStatus, calcDischargingTime, calcChargingTime } = useBattery();
      const userInfo: UserInfoType = userStore.getUserInfo || {};
      const username = userInfo['username'] || '';
      const lockedUsername = username;
      const lockscreenRef = ref<HTMLElement | null>(null);
      const usernameInputRef = ref<InputInst | null>(null);
      const passwordInputRef = ref<InputInst | null>(null);
      const state = reactive({
        // 无论手动锁屏还是会话过期，都先保留原来的时间屏保。
        // 用户点击锁图标或按任意键后，直接进入统一登录页面。
        showLogin: false,
        loginLoading: false, // 正在登录
        isLoginError: false, //密码错误
        errorMsg: '密码错误',
        loginParams: {
          username: username || '',
          password: '',
        },
      });
      const isExpired = computed(() => useScreenLock.reason === 'expired');

      // 已处于手动锁屏时若会话随后过期，也回到时间屏保作为统一入口。
      watch(isExpired, (expired) => {
        if (expired) state.showLogin = false;
      });

      onMounted(() => {
        // 锁屏时旧页面可能仍有聚焦的搜索框，必须先把键盘焦点移进遮罩。
        lockscreenRef.value?.focus();
      });

      watch(() => state.showLogin, async (visible) => {
        await nextTick();
        if (visible) {
          if (state.loginParams.username) passwordInputRef.value?.focus();
          else usernameInputRef.value?.focus();
        } else {
          lockscreenRef.value?.focus();
        }
      });

      // 解锁登录
      const onLockLogin = (value: boolean) => (state.showLogin = value);
      const handleLockKeydown = (event: KeyboardEvent) => {
        if (state.showLogin || event.altKey || event.ctrlKey || event.metaKey ||
            ['Shift', 'Control', 'Alt', 'Meta'].includes(event.key)) return;
        event.preventDefault();
        goLogin();
      };

      // 登录
      const onLogin = async () => {
        if (state.loginLoading) return;
        if (!lockedUsername) {
          state.errorMsg = '无法确认锁定前的账号，请点“重新登录”。';
          state.isLoginError = true;
          return;
        }
        if (state.loginParams.username.trim() !== lockedUsername) {
          state.errorMsg = '屏保只能解锁当前账号；切换账号请点“重新登录”。';
          state.isLoginError = true;
          return;
        }
        if (!state.loginParams.username.trim() || !state.loginParams.password.trim()) {
          state.errorMsg = '请输入用户名和密码';
          state.isLoginError = true;
          return;
        }
        const params = {
          isLock: true,
          ...state.loginParams,
        };
        state.loginLoading = true;
        state.isLoginError = false;
        try {
          const { code, message } = await userStore.login(params);
          if (code === ResultEnum.SUCCESS) {
            // 先用新令牌完成一次服务端验证，再解锁页面，
            // 避免旧请求的 401 与解锁过程竞态。
            await userStore.getInfo();
            const resumePath = useScreenLock.resumePath;
            if (resumePath && resumePath !== '/login' && route.fullPath !== resumePath) {
              await router.replace(resumePath);
            }
            // 路由恢复成功后才移除屏保，避免导航被旧会话拦截时
            // 提前露出登录页。
            state.loginParams.password = '';
            onLockLogin(false);
            useScreenLock.setLock(false);
            useScreenLock.clearResumePath();
          } else {
            state.errorMsg = message || '登录失败';
            state.isLoginError = true;
          }
        } catch (error: any) {
          state.errorMsg = error?.message || error?.msg || '用户名或密码不正确';
          state.isLoginError = true;
        } finally {
          state.loginLoading = false;
        }
      };

      //重新登录
      const goLogin = async () => {
        const currentRedirect = route.path === '/login' ? route.query.redirect : route.fullPath;
        const redirect = resolveLoginRedirect(useScreenLock.resumePath || currentRedirect);
        onLockLogin(false);
        await router.replace({
          path: '/login',
          query: {
            redirect,
          },
        });
        // 先切到登录路由，再解除屏保；否则旧令牌的到期定时器会立即重新锁屏。
        if (router.currentRoute.value.path === '/login') {
          useScreenLock.setLock(false);
          useScreenLock.clearResumePath();
        }
      };

      return {
        ...toRefs(state),
        online,
        month,
        day,
        hour,
        minute,
        second,
        week,
        battery,
        batteryStatus,
        calcDischargingTime,
        calcChargingTime,
        onLockLogin,
        onLogin,
        goLogin,
        isExpired,
        lockedUsername,
        lockscreenRef,
        usernameInputRef,
        passwordInputRef,
        handleLockKeydown,
      };
    },
  });
</script>

<style lang="less" scoped>
  .lockscreen {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    right: 0;
    display: flex;
    background: #000;
    color: white;
    overflow: hidden;
    z-index: 9999;

    &.onLockLogin {
      background-color: rgba(25, 28, 34, 0.88);
      backdrop-filter: blur(7px);
    }

    .login-box {
      position: absolute;
      top: 45%;
      left: 50%;
      transform: translate(-50%, -50%);
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      width: min(360px, calc(100vw - 40px));

      > * {
        margin-bottom: 14px;
      }

      .username {
        font-size: 30px;
      }

      :deep(.n-input) {
        width: 100%;
      }

      .session-expired-tip {
        color: rgba(255, 255, 255, 0.78);
        font-size: 14px;
      }
    }

    .lock-box {
      position: absolute;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      font-size: 34px;
      z-index: 100;

      .tips {
        color: white;
        cursor: text;
      }

      .lock {
        display: flex;
        justify-content: center;

        .lock-icon {
          cursor: pointer;

          .anticon-unlock {
            display: none;
          }

          &:hover .anticon-unlock {
            display: initial;
          }

          &:hover .anticon-lock {
            display: none;
          }
        }
      }
    }

    .local-time {
      position: absolute;
      bottom: 60px;
      left: 60px;
      font-family: helvetica;

      .time {
        font-size: 70px;
      }

      .date {
        font-size: 40px;
      }

      .expired-hint {
        margin-top: 12px;
        color: rgba(255, 255, 255, 0.72);
        font-size: 15px;
        letter-spacing: 0.02em;
      }
    }

    .computer-status {
      position: absolute;
      bottom: 60px;
      right: 60px;
      font-size: 24px;

      > * {
        margin-left: 14px;
      }

      .network {
        position: relative;

        &.offline::before {
          content: '';
          position: absolute;
          left: 50%;
          top: 50%;
          width: 2px;
          height: 28px;
          transform: translate(-50%, -50%) rotate(45deg);
          background-color: red;
          z-index: 10;
        }
      }
    }
  }
</style>
