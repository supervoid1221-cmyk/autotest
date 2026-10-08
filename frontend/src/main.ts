import './styles/tailwind.css';
import { createApp } from 'vue';
import { setupNaiveDiscreteApi, setupNaive, setupDirectives } from '@/plugins';
import App from './App.vue';
import router, { setupRouter } from './router';
import { setupStore } from '@/store';
import { initializeBranding } from '@/config/website.config';

// 页面在发布前已打开时，懒加载路由可能仍引用旧版资源。只自动刷新一次，
// 重新读取最新 index.html；一分钟内再次失败则保留错误，避免刷新循环。
window.addEventListener('vite:preloadError', (event) => {
  event.preventDefault();
  const key = 'frontend-preload-reload-at';
  const lastReload = Number(sessionStorage.getItem(key) || 0);
  if (Date.now() - lastReload < 60_000) return;
  sessionStorage.setItem(key, String(Date.now()));
  window.location.reload();
});

async function bootstrap() {
  await initializeBranding();
  const app = createApp(App);

  // 挂载状态管理
  setupStore(app);

  // 注册全局常用的 naive-ui 组件
  setupNaive(app);

  // 挂载 naive-ui 脱离上下文的 Api
  setupNaiveDiscreteApi();

  // 注册全局自定义指令，如：v-permission权限指令
  setupDirectives(app);

  // 挂载路由
  setupRouter(app);

  // 路由准备就绪后挂载 APP 实例
  // https://router.vuejs.org/api/interfaces/router.html#isready
  await router.isReady();

  // https://www.naiveui.com/en-US/os-theme/docs/style-conflict#About-Tailwind's-Preflight-Style-Override
  const meta = document.createElement('meta');
  meta.name = 'naive-ui-style';
  document.head.appendChild(meta);

  app.mount('#app', true);
}

void bootstrap();
