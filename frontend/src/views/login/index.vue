<template>
  <main
    class="login-page"
    :class="{
      'is-username': focusedField === 'username',
      'is-password': focusedField === 'password',
      'is-loading': loading,
      'is-error': loginError,
    }"
    :style="gazeStyle"
    @pointermove="handlePointerMove"
    @pointerleave="resetPointerGaze"
  >
    <section class="mascot-panel" aria-hidden="true">
      <div class="brand-lockup">
        <img :class="{ 'logo-image--contrast': websiteConfig.logoNeedsContrastPlate }" :src="websiteConfig.logo" alt="" />
        <div><span>{{ websiteConfig.enTitle }}</span><strong>{{ websiteConfig.title }}</strong></div>
      </div>

      <div class="mascot-copy">
        <span class="eyebrow">WELCOME BACK</span>
        <h1>每一次执行，<br />都值得被认真看见。</h1>
        <p>登录后继续管理用例、执行任务与监控服务。</p>
      </div>

      <div class="character-stage">
        <div class="character character-tall">
          <div class="face face-tall">
            <span class="eye"><i /></span><span class="eye"><i /></span>
            <b class="mouth" />
          </div>
          <span class="arm arm-left" /><span class="arm arm-right" />
        </div>
        <div class="character character-coral">
          <div class="face"><span class="eye"><i /></span><span class="eye"><i /></span><b class="mouth" /></div>
        </div>
        <div class="character character-orbit">
          <div class="face"><span class="eye"><i /></span><span class="eye"><i /></span><b class="mouth" /></div>
        </div>
        <div class="character character-gold">
          <div class="face"><span class="eye"><i /></span><span class="eye"><i /></span><b class="mouth" /></div>
        </div>
        <span class="stage-line" />
      </div>

    </section>

    <section class="login-panel">
      <div class="login-card">
        <header class="login-header">
          <div class="mobile-logo"><img :class="{ 'logo-image--contrast': websiteConfig.logoNeedsContrastPlate }" :src="websiteConfig.logo" alt="" /><span>{{ websiteConfig.title }}</span></div>
          <span class="login-kicker">{{ isExpiredSession ? '会话已锁定' : '账号登录' }}</span>
          <h2>{{ isExpiredSession ? '重新登录激活' : '欢迎回来' }}</h2>
          <p>{{ isExpiredSession ? '登录令牌已过期，请重新输入账号密码' : '请输入你的平台账号信息' }}</p>
        </header>

        <n-form
          ref="formRef"
          class="login-form"
          label-placement="left"
          size="large"
          :model="formInline"
          :rules="rules"
          @submit.prevent="handleSubmit"
          @keydown.enter.prevent="handleEnter"
        >
          <n-form-item path="username">
            <n-input
              v-model:value="formInline.username"
              placeholder="请输入用户名"
              autocomplete="username"
              @focus="focusedField = 'username'"
              @blur="focusedField = null"
            >
              <template #prefix><n-icon size="19"><PersonOutline /></n-icon></template>
            </n-input>
          </n-form-item>
          <n-form-item path="password">
            <n-input
              v-model:value="formInline.password"
              type="password"
              show-password-on="click"
              placeholder="请输入密码"
              autocomplete="current-password"
              @focus="focusedField = 'password'"
              @blur="focusedField = null"
            >
              <template #prefix><n-icon size="19"><LockClosedOutline /></n-icon></template>
            </n-input>
          </n-form-item>
          <div class="form-options">
            <n-checkbox v-model:checked="autoLogin">自动登录</n-checkbox>
            <a href="javascript:void(0)">忘记密码</a>
          </div>
          <n-button class="login-button" type="primary" attr-type="submit" size="large" :loading="loading" block>登录平台</n-button>
        </n-form>

        <footer class="login-footer"><span>安全访问</span><i />Django · Vue · Naive UI</footer>
      </div>
    </section>
  </main>
</template>

<script lang="ts" setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useMessage } from 'naive-ui';
import { PersonOutline, LockClosedOutline } from '@vicons/ionicons5';
import { useUserStore } from '@/store/modules/user';
import { ResultEnum } from '@/enums/httpEnum';
import { websiteConfig } from '@/config/website.config';
import { resolveLoginRedirect } from '@/router/loginRedirect';

interface FormState {
  username: string;
  password: string;
}

const formRef = ref();
const message = useMessage();
const loading = ref(false);
const loginError = ref(false);
const focusedField = ref<'username' | 'password' | null>(null);
const pointerActive = ref(false);
const pointerGaze = reactive({ x: 0, y: 0 });
const autoLogin = ref(true);
let errorTimer: number | undefined;
let pointerFrame: number | undefined;
let pendingPointer = { x: 0, y: 0 };

const formInline = reactive({ username: '', password: '', isCaptcha: true });
const rules = {
  username: { required: true, message: '请输入用户名', trigger: 'blur' },
  password: { required: true, message: '请输入密码', trigger: 'blur' },
};

const gazeStyle = computed(() => {
  if (focusedField.value === 'password') return { '--gaze-x': '-5px', '--gaze-y': '-1px' };
  if (pointerActive.value) return { '--gaze-x': `${pointerGaze.x}px`, '--gaze-y': `${pointerGaze.y}px` };
  if (focusedField.value !== 'username') return { '--gaze-x': '0px', '--gaze-y': '0px' };
  const progress = Math.min(1, formInline.username.length / 14);
  return { '--gaze-x': `${2 + progress * 5}px`, '--gaze-y': `${1 + progress * 2}px` };
});

const updatePointerGaze = () => {
  const normalizedX = (pendingPointer.x / Math.max(1, window.innerWidth) - 0.5) * 2;
  const normalizedY = (pendingPointer.y / Math.max(1, window.innerHeight) - 0.5) * 2;
  pointerGaze.x = Math.round(Math.max(-1, Math.min(1, normalizedX)) * 5.5 * 10) / 10;
  pointerGaze.y = Math.round(Math.max(-1, Math.min(1, normalizedY)) * 3.5 * 10) / 10;
  pointerActive.value = true;
  pointerFrame = undefined;
};

const handlePointerMove = (event: PointerEvent) => {
  if (event.pointerType && event.pointerType !== 'mouse') return;
  pendingPointer = { x: event.clientX, y: event.clientY };
  if (pointerFrame === undefined) pointerFrame = window.requestAnimationFrame(updatePointerGaze);
};

const resetPointerGaze = () => {
  pointerActive.value = false;
  pointerGaze.x = 0;
  pointerGaze.y = 0;
};

const userStore = useUserStore();
const router = useRouter();
const route = useRoute();
const isExpiredSession = computed(() => route.query?.expired === '1');

const showLoginError = () => {
  loginError.value = false;
  window.clearTimeout(errorTimer);
  requestAnimationFrame(() => {
    loginError.value = true;
    errorTimer = window.setTimeout(() => { loginError.value = false; }, 700);
  });
};

const handleEnter = (event: KeyboardEvent) => {
  if (event.isComposing || loading.value) return;
  handleSubmit(event);
};

const handleSubmit = (event?: Event) => {
  event?.preventDefault();
  if (loading.value) return;
  formRef.value.validate(async (errors) => {
    if (errors) {
      showLoginError();
      message.error('请填写用户名和密码');
      return;
    }
    const params: FormState = { username: formInline.username, password: formInline.password };
    message.loading('登录中...');
    loading.value = true;
    try {
      const { code, message: msg } = await userStore.login(params);
      message.destroyAll();
      if (code == ResultEnum.SUCCESS) {
        const toPath = resolveLoginRedirect(route.query?.redirect);
        message.success('登录成功，即将进入系统');
        await router.replace(toPath);
      } else {
        showLoginError();
        message.info(msg || '登录失败');
      }
    } catch (error) {
      showLoginError();
      throw error;
    } finally {
      loading.value = false;
    }
  });
};

onBeforeUnmount(() => {
  window.clearTimeout(errorTimer);
  if (pointerFrame !== undefined) window.cancelAnimationFrame(pointerFrame);
});
</script>

<style lang="less" scoped>
.login-page {
  --ink: #17243a;
  --muted: #718198;
  --accent: #2769e8;
  --gaze-x: 0px;
  --gaze-y: 0px;
  display: grid;
  grid-template-columns: minmax(30rem, 1.08fr) minmax(30rem, .92fr);
  min-height: 100dvh;
  overflow: hidden;
  color: var(--ink);
  background: #f7f9fc;
}

.mascot-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 100dvh;
  padding: clamp(2rem, 4vw, 4.25rem) clamp(2rem, 5vw, 5.75rem) 2rem;
  overflow: hidden;
  background:
    radial-gradient(circle at 18% 16%, rgba(54, 123, 237, .16), transparent 28%),
    radial-gradient(circle at 82% 72%, rgba(14, 167, 139, .12), transparent 31%),
    #eef3fa;
}

.mascot-panel:after {
  position: absolute;
  inset: 0;
  opacity: .28;
  pointer-events: none;
  background-image: radial-gradient(rgba(54, 78, 113, .22) .7px, transparent .7px);
  background-size: 18px 18px;
  content: '';
}

.brand-lockup, .mascot-copy, .character-stage { position: relative; z-index: 1; }
.brand-lockup { display: flex; align-items: center; gap: .8rem; }
.brand-lockup img { width: 2.75rem; height: 2.75rem; object-fit: contain; }
.brand-lockup img.logo-image--contrast, .mobile-logo img.logo-image--contrast { box-sizing: border-box; padding: .32rem; border: 1px solid #cfd5dc; border-radius: .6rem; background: #eef1f3; }
.brand-lockup span { display: block; color: #8290a5; font-size: .7rem; font-weight: 700; letter-spacing: .14em; }
.brand-lockup strong { display: block; margin-top: .18rem; font-size: 1.1rem; font-weight: 700; letter-spacing: -.02em; }
.mascot-copy { margin-top: clamp(3.2rem, 8vh, 6.5rem); max-width: 37rem; }
.eyebrow { color: var(--accent); font-size: .72rem; font-weight: 700; letter-spacing: .18em; }
.mascot-copy h1 { margin: 1rem 0 1.2rem; font-size: clamp(2.35rem, 4.1vw, 4.8rem); line-height: 1.04; letter-spacing: -.06em; text-wrap: balance; }
.mascot-copy p { max-width: 32rem; margin: 0; color: var(--muted); font-size: 1rem; line-height: 1.75; }

.character-stage { flex: 1; min-height: 18rem; margin: 2rem 0 0; }
.stage-line { position: absolute; right: 2%; bottom: 2.5rem; left: 1%; height: 1px; background: rgba(75, 101, 139, .2); }
.character { position: absolute; bottom: 2.55rem; transform-origin: 50% 100%; transition: transform .48s cubic-bezier(.2,.8,.2,1), filter .3s ease; }
.character-tall { left: 8%; width: 9.4rem; height: 15.5rem; border-radius: 5.5rem 5.5rem 1.4rem 1.4rem; background: #2869e7; box-shadow: 0 1.8rem 3.8rem rgba(40, 105, 231, .22); }
.character-coral { left: 36%; width: 7rem; height: 10rem; border-radius: 3.5rem 3.5rem 1.2rem 1.2rem; background: #e9685b; }
.character-orbit { left: 59%; width: 8.5rem; height: 8.5rem; border-radius: 50%; background: #17a78c; }
.character-gold { left: 79%; width: 5.7rem; height: 12rem; border-radius: 3rem 3rem 1rem 1rem; background: #e9ad36; }
.face { position: absolute; top: 25%; left: 50%; display: flex; gap: 1rem; transform: translateX(-50%); }
.face-tall { top: 22%; }
.eye { position: relative; display: block; width: 1.25rem; height: 1.25rem; overflow: hidden; border-radius: 50%; background: #fff; transition: height .25s ease, transform .25s ease; }
.eye i { position: absolute; top: .37rem; left: .37rem; width: .52rem; height: .52rem; border-radius: 50%; background: #17243a; transform: translate(var(--gaze-x), var(--gaze-y)); transition: transform .11s cubic-bezier(.2,.8,.2,1); will-change: transform; }
.mouth { position: absolute; top: 2.25rem; left: 50%; width: 1.35rem; height: .5rem; border-bottom: 2px solid rgba(20, 36, 58, .74); border-radius: 0 0 1rem 1rem; transform: translateX(-50%); transition: transform .25s ease, width .25s ease; }
.arm { position: absolute; top: 56%; width: 5.4rem; height: 1.65rem; border-radius: 2rem; background: #1f58c7; opacity: 0; transition: opacity .25s ease, transform .48s cubic-bezier(.2,.8,.2,1); }
.arm-left { left: -3.2rem; transform: rotate(22deg) translate(-1rem, 2rem); }
.arm-right { right: -3.2rem; transform: rotate(-22deg) translate(1rem, 2rem); }

.is-username .character-tall { transform: rotate(3deg) translateX(.7rem); }
.is-username .character-coral { transform: rotate(5deg) translateX(.45rem); }
.is-username .character-orbit { transform: translateY(-.45rem) rotate(4deg); }
.is-username .character-gold { transform: rotate(6deg); }
.is-username .mouth { width: 1.7rem; transform: translateX(-50%) scaleY(1.3); }
.is-password .character-tall { transform: rotate(-7deg) translateX(-.75rem); }
.is-password .character-coral { transform: rotate(-8deg); }
.is-password .character-orbit { transform: rotate(-12deg) translateX(-.5rem); }
.is-password .character-gold { transform: rotate(-9deg); }
.is-password .character:not(.character-tall) .eye { height: .18rem; transform: translateY(.48rem); }
.is-password .character:not(.character-tall) .eye i { opacity: 0; }
.is-password .arm { opacity: 1; }
.is-password .arm-left { transform: rotate(-28deg) translate(1.8rem, -2.2rem); }
.is-password .arm-right { transform: rotate(28deg) translate(-1.8rem, -2.2rem); }
.is-loading .character { animation: attentive 1.1s ease-in-out infinite alternate; }
.is-error .character-stage { animation: stage-shake .48s ease; }

.login-panel { display: grid; place-items: center; min-height: 100dvh; padding: clamp(2rem, 5vw, 6rem); background: rgba(255, 255, 255, .82); }
.login-card { width: min(100%, 27.5rem); }
.mobile-logo { display: none; }
.login-kicker { color: var(--accent); font-size: .76rem; font-weight: 700; letter-spacing: .12em; }
.login-header h2 { margin: .8rem 0 .5rem; font-size: 2.55rem; line-height: 1.1; letter-spacing: -.055em; }
.login-header p { margin: 0; color: var(--muted); font-size: .95rem; }
.login-form { margin-top: 2.25rem; }
.login-form :deep(.n-form-item) { margin-bottom: .5rem; }
.login-form :deep(.n-input) { --n-border: 1px solid #dce3ed !important; --n-border-hover: 1px solid #9db8ed !important; --n-border-focus: 1px solid #2769e8 !important; --n-box-shadow-focus: 0 0 0 3px rgba(39, 105, 232, .1) !important; min-height: 3.25rem; border-radius: .7rem; background: #fff; transition: transform .2s ease, box-shadow .2s ease; }
.login-form :deep(.n-input--focus) { transform: translateY(-1px); }
.login-form :deep(.n-input__prefix) { margin-right: .65rem; color: #7a8da9; }
.form-options { display: flex; align-items: center; justify-content: space-between; margin: .3rem 0 1.35rem; color: #607089; font-size: .88rem; }
.form-options a { color: #466587; text-decoration: none; transition: color .2s ease; }
.form-options a:hover { color: var(--accent); }
.login-button { height: 3.3rem; border-radius: .7rem; font-size: .95rem; font-weight: 650; box-shadow: 0 .75rem 1.7rem rgba(39, 105, 232, .2); transition: transform .2s ease, box-shadow .2s ease; }
.login-button:hover { transform: translateY(-1px); box-shadow: 0 1rem 2rem rgba(39, 105, 232, .25); }
.login-button:active { transform: translateY(1px) scale(.995); }
.login-footer { display: flex; align-items: center; justify-content: center; gap: .55rem; margin-top: 2rem; color: #9aa6b6; font-size: .72rem; }
.login-footer span { color: #6f7f95; }
.login-footer i { width: 3px; height: 3px; border-radius: 50%; background: #b7c0cc; }

@keyframes attentive { to { transform: translateY(-.35rem); } }
@keyframes stage-shake { 20%, 60% { transform: translateX(-.5rem); } 40%, 80% { transform: translateX(.5rem); } }

@media (max-width: 980px) {
  .login-page { grid-template-columns: minmax(21rem, .85fr) minmax(25rem, 1.15fr); }
  .mascot-panel { padding-right: 2rem; padding-left: 2rem; }
  .mascot-copy h1 { font-size: clamp(2.2rem, 5vw, 3.5rem); }
  .character-stage { transform: scale(.82); transform-origin: 0 100%; width: 118%; }
}

@media (max-width: 760px) {
  .login-page { display: block; min-height: 100dvh; overflow: auto; }
  .mascot-panel { display: none; }
  .login-panel { min-height: 100dvh; padding: 2rem 1.35rem 3rem; background: radial-gradient(circle at 50% 0, rgba(39, 105, 232, .1), transparent 34%), #f7f9fc; }
  .mobile-logo { display: flex; align-items: center; gap: .65rem; margin-bottom: 3.5rem; }
  .mobile-logo img { width: 2.35rem; height: 2.35rem; object-fit: contain; }
  .mobile-logo span { font-size: 1rem; font-weight: 700; }
  .login-header h2 { font-size: 2.2rem; }
}

@media (prefers-reduced-motion: reduce) {
  .character, .eye, .eye i, .arm, .mouth, .login-button { transition: none !important; animation: none !important; }
}
</style>
