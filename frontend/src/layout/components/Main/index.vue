<template>
  <RouterView v-slot="{ Component, route }">
    <!-- KeepAlive must stay mounted across route changes. Switching between a cached
         and uncached wrapper inside an out-in transition can leave the outlet empty. -->
    <KeepAlive :include="keepAliveComponents">
      <component :is="Component" :key="route.fullPath" />
    </KeepAlive>
  </RouterView>
</template>

<script>
  import { defineComponent, computed } from 'vue';
  import { useAsyncRouteStore } from '@/store/modules/asyncRoute';

  export default defineComponent({
    name: 'MainView',
    components: {},
    props: {
      notNeedKey: {
        type: Boolean,
        default: false,
      },
      animate: {
        type: Boolean,
        default: true,
      },
    },
    setup() {
      const asyncRouteStore = useAsyncRouteStore();
      // 需要缓存的路由组件
      const keepAliveComponents = computed(() => asyncRouteStore.keepAliveComponents);
      return {
        keepAliveComponents,
      };
    },
  });
</script>

<style lang="less" scoped></style>
