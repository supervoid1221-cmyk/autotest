import type { RouteRecordRaw } from 'vue-router';
import { isNavigationFailure, Router } from 'vue-router';
import { useUser } from '@/store/modules/user';
import { useAsyncRoute } from '@/store/modules/asyncRoute';
import { ACCESS_TOKEN, ACCESS_TOKEN_EXPIRES_AT } from '@/store/mutation-types';
import { storage } from '@/utils/Storage';
import { PageEnum } from '@/enums/pageEnum';
import { ErrorPageRoute } from '@/router/base';
import { useScreenLockStore } from '@/store/modules/screenLock';
import { resolveLoginRedirect } from '@/router/loginRedirect';

const LOGIN_PATH = PageEnum.BASE_LOGIN;

const whitePathList = [LOGIN_PATH]; // no redirect whitelist

export function createRouterGuards(router: Router) {
  const userStore = useUser();
  const asyncRouteStore = useAsyncRoute();
  const screenLockStore = useScreenLockStore();
  router.beforeEach(async (to, from, next) => {
    const Loading = window['$loading'] || null;
    Loading && Loading.start();
    if (from.path === LOGIN_PATH && to.name === 'errorPage') {
      next(PageEnum.BASE_HOME);
      return;
    }

    // Whitelist can be directly entered
    if (whitePathList.includes(to.path as PageEnum)) {
      next();
      return;
    }

    // 公开页面必须在读取、校验本地 Token 之前放行。否则浏览器中残留过期
    // Token 时仍会请求用户信息，导致 ignoreAuth 页面被 401 阻断。
    if (to.meta.ignoreAuth) {
      next();
      return;
    }

    const token = storage.get(ACCESS_TOKEN);

    if (!token) {
      if (screenLockStore.isLocked) {
        // 锁屏仍可通过账号密码重新激活；不要让后台发起的路由跳转
        // 把屏保层清掉并导航到登录页。
        screenLockStore.setLock(true, 'expired', to.fullPath);
        Loading && Loading.finish();
        if (from.matched.length === 0) {
          next({ path: LOGIN_PATH, replace: true, query: { redirect: to.fullPath } });
          return;
        }
        next(false);
        return;
      }
      // redirect login page
      const redirectData: { path: string; replace: boolean; query?: Recordable<string> } = {
        path: LOGIN_PATH,
        replace: true,
      };
      if (to.path) {
        redirectData.query = {
          ...redirectData.query,
          redirect: to.path,
        };
      }
      next(redirectData);
      return;
    }

    const tokenExpiresAt = Number(storage.get(ACCESS_TOKEN_EXPIRES_AT, 0)) || 0;
    if (tokenExpiresAt && tokenExpiresAt <= Date.now()) {
      if (screenLockStore.isLocked) {
        screenLockStore.setLock(true, 'expired', to.fullPath);
        Loading && Loading.finish();
        if (from.matched.length === 0) {
          next({ path: LOGIN_PATH, replace: true, query: { redirect: to.fullPath } });
          return;
        }
        next(false);
        return;
      }
      // 非锁屏状态下首次进入仍走完整登录，避免拿已过期令牌请求 profile。
      next({
        path: LOGIN_PATH,
        replace: true,
        query: { redirect: to.fullPath, expired: '1' },
      });
      return;
    }

    if (asyncRouteStore.getIsDynamicRouteAdded) {
      next();
      return;
    }

    let userInfo;
    try {
      userInfo = await userStore.getInfo();
    } catch (error: any) {
      if (error?.staleAuthResponse) {
        try {
          userInfo = await userStore.getInfo();
        } catch (retryError: any) {
          error = retryError;
        }
      }

      if (!userInfo) {
        Loading && Loading.finish();
        if (screenLockStore.isLocked) {
          screenLockStore.setLock(true, 'expired', to.fullPath);
          if (from.matched.length === 0) {
            next({ path: LOGIN_PATH, replace: true, query: { redirect: to.fullPath } });
            return;
          }
          next(false);
          return;
        }
        if (error?.httpStatus === 401) {
          // 保留当前页面，由屏保层重新认证；不再与统一 401 处理
          // 重复竞争并导航到登录页。
          screenLockStore.setLock(true, 'expired', to.fullPath);
          if (from.matched.length === 0) {
            next({ path: LOGIN_PATH, replace: true, query: { redirect: to.fullPath } });
            return;
          }
          next(false);
          return;
        }

        next({
          path: LOGIN_PATH,
          replace: true,
          query: { redirect: to.fullPath },
        });
        return;
      }
    }

    const routes = await asyncRouteStore.generateRoutes(userInfo);

    // 动态添加可访问路由表
    routes.forEach((item) => {
      router.addRoute(item as unknown as RouteRecordRaw);
    });

    //添加404
    const isErrorPage = router.getRoutes().findIndex((item) => item.name === ErrorPageRoute.name);
    if (isErrorPage === -1) {
      router.addRoute(ErrorPageRoute as unknown as RouteRecordRaw);
    }

    const redirect = resolveLoginRedirect(from.query.redirect || to.fullPath);
    const nextData = to.path === redirect ? { ...to, replace: true } : { path: redirect };
    asyncRouteStore.setDynamicRouteAdded(true);
    next(nextData);
    Loading && Loading.finish();
  });

  router.afterEach((to, _, failure) => {
    document.title = (to?.meta?.title as string) || document.title;
    if (isNavigationFailure(failure)) {
      //console.log('failed navigation', failure)
    }
    const asyncRouteStore = useAsyncRoute();
    // 在这里设置需要缓存的组件名称
    const keepAliveComponents = asyncRouteStore.keepAliveComponents;
    const currentComName: any = to.matched.find((item) => item.name == to.name)?.name;
    if (currentComName && !keepAliveComponents.includes(currentComName) && to.meta?.keepAlive) {
      // 需要缓存的组件
      keepAliveComponents.push(currentComName);
    } else if (!to.meta?.keepAlive || to.name == 'Redirect') {
      // 不需要缓存的组件
      const index = asyncRouteStore.keepAliveComponents.findIndex((name) => name == currentComName);
      if (index != -1) {
        keepAliveComponents.splice(index, 1);
      }
    }
    asyncRouteStore.setKeepAliveComponents(keepAliveComponents);
    const Loading = window['$loading'] || null;
    Loading && Loading.finish();
  });

  router.onError((error) => {
    console.log(error, '路由错误');
  });
}
