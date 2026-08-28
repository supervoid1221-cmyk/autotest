<script lang="tsx">
  import { defineComponent, onBeforeMount } from 'vue';
  import { useRoute, useRouter } from 'vue-router';
  import { NEmpty } from 'naive-ui';

  export default defineComponent({
    name: 'Redirect',
    setup() {
      const route = useRoute();
      const router = useRouter();
      onBeforeMount(() => {
        const { params, query } = route;
        const { path } = params;
        const redirect = query.__redirect;
        // 刷新时优先使用保存的完整地址，以保留原页面的 query 与 hash。
        // 未使用新版刷新逻辑的旧地址仍按原来的 path 参数兼容处理。
        const target = typeof redirect === 'string'
          ? redirect
          : '/' + (Array.isArray(path) ? path.join('/') : (path || ''));
        router.replace(target.startsWith('/') ? target : '/project');
      });
      return () => <NEmpty />;
    },
  });
</script>
