import type { RouteLocationRaw } from 'vue-router';
import { useRoute, useRouter } from 'vue-router';
import { useTabsViewStore } from '@/store/modules/tabsView';

/** 保存成功后关闭当前详情标签，并回到对应的列表页。 */
export function useSubmitRedirect() {
  const route = useRoute();
  const router = useRouter();
  const tabsViewStore = useTabsViewStore();

  function redirectAfterSubmit(destination: RouteLocationRaw) {
    tabsViewStore.closeCurrentTab(route as any);
    router.push(destination);
  }

  return { redirectAfterSubmit };
}
