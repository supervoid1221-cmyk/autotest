import type { RouteLocationRaw, Router } from 'vue-router';

import { PageEnum } from '@/enums/pageEnum';
import { RedirectName } from '@/router/constant';

import { useRouter } from 'vue-router';
import { isString } from '@/utils/is';
import { unref } from 'vue';

export type RouteLocationRawEx = Omit<RouteLocationRaw, 'path'> & { path: PageEnum };

function handleError(e: Error) {
  console.error(e);
}

/**
 * 页面切换
 */
export function useGo(_router?: Router) {
  let router;
  if (!_router) {
    router = useRouter();
  }
  const { push, replace } = _router || router;
  function go(opt: PageEnum | RouteLocationRawEx | string = PageEnum.BASE_HOME, isReplace = false) {
    if (!opt) {
      return;
    }
    if (isString(opt)) {
      isReplace ? replace(opt).catch(handleError) : push(opt).catch(handleError);
    } else {
      const o = opt as RouteLocationRaw;
      isReplace ? replace(o).catch(handleError) : push(o).catch(handleError);
    }
  }
  return go;
}

/**
 * 重做当前页面
 */
export const useRedo = (_router?: Router) => {
  const { push, currentRoute } = _router || useRouter();
  const { name, fullPath, path } = unref(currentRoute.value);
  function redo(): Promise<boolean> {
    return new Promise((resolve) => {
      if (name === RedirectName) {
        resolve(false);
        return;
      }
      push({
        name: RedirectName,
        params: { path: path.replace(/^\/+/, '') },
        query: { __redirect: fullPath },
      }).then(() => resolve(true));
    });
  }
  return redo;
};
