import { warn } from '@/utils/log';
import pkg from '../../package.json';

export function getCommonStoragePrefix() {
  const { VITE_GLOB_APP_SHORT_NAME } = getAppEnvConfig();
  return `${VITE_GLOB_APP_SHORT_NAME}__${getEnv()}`.toUpperCase();
}

// Generate cache key according to version
export function getStorageShortName() {
  return `${getCommonStoragePrefix()}${`__${pkg.version}`}__`.toUpperCase();
}

export function getAppEnvConfig() {
  // 当前项目不再依赖模板的 build/ 配置生成脚本；Vite 会在构建时注入环境变量。
  // 使用静态属性访问，确保 Vite 在生产构建时能够可靠替换这些变量。
  const VITE_GLOB_APP_TITLE = import.meta.env.VITE_GLOB_APP_TITLE;
  const VITE_GLOB_API_URL = import.meta.env.VITE_GLOB_API_URL;
  const VITE_GLOB_APP_SHORT_NAME = import.meta.env.VITE_GLOB_APP_SHORT_NAME;
  const VITE_GLOB_API_URL_PREFIX = import.meta.env.VITE_GLOB_API_URL_PREFIX;
  const VITE_GLOB_UPLOAD_URL = import.meta.env.VITE_GLOB_UPLOAD_URL;
  const VITE_GLOB_PROD_MOCK = import.meta.env.VITE_GLOB_PROD_MOCK;
  const VITE_GLOB_IMG_URL = import.meta.env.VITE_GLOB_IMG_URL;

  if (!/^[a-zA-Z\_]*$/.test(VITE_GLOB_APP_SHORT_NAME)) {
    warn(
      `VITE_GLOB_APP_SHORT_NAME Variables can only be characters/underscores, please modify in the environment variables and re-running.`
    );
  }

  return {
    VITE_GLOB_APP_TITLE,
    VITE_GLOB_API_URL,
    VITE_GLOB_APP_SHORT_NAME,
    VITE_GLOB_API_URL_PREFIX,
    VITE_GLOB_UPLOAD_URL,
    VITE_GLOB_PROD_MOCK,
    VITE_GLOB_IMG_URL,
  };
}

/**
 * @description: Development model
 */
export const devMode = 'development';

/**
 * @description: Production mode
 */
export const prodMode = 'production';

/**
 * @description: Get environment variables
 * @returns:
 * @example:
 */
export function getEnv(): string {
  return import.meta.env.MODE;
}

/**
 * @description: Is it a development mode
 * @returns:
 * @example:
 */
export function isDevMode(): boolean {
  return import.meta.env.DEV;
}

/**
 * @description: Is it a production mode
 * @returns:
 * @example:
 */
export function isProdMode(): boolean {
  return import.meta.env.PROD;
}
