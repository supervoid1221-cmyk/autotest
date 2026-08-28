import type { UserConfig, ConfigEnv } from 'vite';
import { loadEnv } from 'vite';
import { resolve } from 'path';
import vue from '@vitejs/plugin-vue';
import vueJsx from '@vitejs/plugin-vue-jsx';
import pkg from './package.json';
import { format } from 'date-fns';
const { dependencies, devDependencies, name, version } = pkg;

const __APP_INFO__ = {
  pkg: { dependencies, devDependencies, name, version },
  lastBuildTime: format(new Date(), 'yyyy-MM-dd HH:mm:ss'),
};

function pathResolve(dir: string) {
  return resolve(process.cwd(), '.', dir);
}

function createProxy(proxyValue?: string) {
  if (!proxyValue) return undefined;

  try {
    return JSON.parse(proxyValue).reduce((proxy, [prefix, target]) => {
      proxy[prefix] = {
        target,
        changeOrigin: true,
        rewrite: (path: string) => path.replace(new RegExp(`^${prefix}`), ''),
      };
      return proxy;
    }, {} as Record<string, object>);
  } catch {
    throw new Error('VITE_PROXY 必须是有效的 JSON 数组。');
  }
}

export default ({ command, mode }: ConfigEnv): UserConfig => {
  const root = process.cwd();
  const env = loadEnv(mode, root);
  const { VITE_PUBLIC_PATH = '/', VITE_PORT = '8001', VITE_PROXY } = env;
  return {
    base: VITE_PUBLIC_PATH,
    resolve: {
      alias: [
        {
          find: /\/#\//,
          replacement: pathResolve('types') + '/',
        },
        {
          find: '@',
          replacement: pathResolve('src') + '/',
        },
      ],
      dedupe: ['vue'],
    },
    plugins: [vue(), vueJsx()],
    define: {
      __APP_INFO__: JSON.stringify(__APP_INFO__),
    },
    server: {
      host: true,
      port: Number(VITE_PORT),
      proxy: createProxy(VITE_PROXY),
    },
    optimizeDeps: {
      include: [],
      exclude: ['vue-demi'],
    },
    build: {
      target: 'es2020',
      cssTarget: 'chrome80',
      outDir: 'dist',
      reportCompressedSize: false,
      chunkSizeWarningLimit: 2000,
    },
  };
};
