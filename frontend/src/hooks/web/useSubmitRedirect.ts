import type { RouteLocationRaw } from 'vue-router';
import { useRoute, useRouter } from 'vue-router';
import { useAsyncRouteStore } from '@/store/modules/asyncRoute';
import { useTabsViewStore } from '@/store/modules/tabsView';

/** 保存成功后关闭当前详情标签，并回到对应的列表页。 */
export function useSubmitRedirect() {
  const route = useRoute();
  const router = useRouter();
  const asyncRouteStore = useAsyncRouteStore();
  const tabsViewStore = useTabsViewStore();

  function redirectAfterSubmit(destination: RouteLocationRaw) {
    if (route.meta.keepAlive && route.name) {
      asyncRouteStore.setKeepAliveComponents(
        asyncRouteStore.keepAliveComponents.filter((name) => name !== String(route.name))
      );
    }
    tabsViewStore.closeCurrentTab(route as any);
    router.push(destination);
  }

  return { redirectAfterSubmit };
}
