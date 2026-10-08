<template>
  <div class="aside-menu" :class="{ 'aside-menu-collapsed': collapsed }">
    <div v-show="!collapsed" class="menu-search">
      <NInput
        ref="searchRef"
        v-model:value="keyword"
        size="small"
        clearable
        placeholder="搜索菜单…"
        @keydown.esc="keyword = ''"
      >
        <template #prefix>
          <svg
            class="menu-search-icon"
            viewBox="0 0 24 24"
            width="15"
            height="15"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </template>
        <template #suffix>
          <span class="menu-search-shortcut">⌘K</span>
        </template>
      </NInput>
    </div>
    <NMenu
      :options="displayMenus"
      :inverted="inverted"
      :mode="mode"
      :collapsed="collapsed"
      :collapsed-width="68"
      :collapsed-icon-size="18"
      :indent="24"
      :node-props="menuNodeProps"
      :expanded-keys="isSearching ? searchOpenKeys : openKeys"
      :value="getSelectedKeys"
      @update:value="clickMenuItem"
      @update:expanded-keys="menuExpanded"
    />
  </div>
</template>

<script lang="ts">
  import {
    defineComponent,
    ref,
    computed,
    onMounted,
    onBeforeUnmount,
    reactive,
    watch,
    nextTick,
    toRefs,
    unref,
  } from 'vue';
  import { NInput, NMenu } from 'naive-ui';
  import { useRoute, useRouter } from 'vue-router';
  import { useAsyncRouteStore } from '@/store/modules/asyncRoute';
  import { generatorMenu, generatorMenuGroup, generatorMenuMix } from '@/utils';
  import { useProjectSettingStore } from '@/store/modules/projectSetting';
  import { useProjectSetting } from '@/hooks/setting/useProjectSetting';

  export default defineComponent({
    name: 'AppMenu',
    components: { NInput, NMenu },
    props: {
      mode: {
        // 菜单模式
        type: String,
        default: 'vertical',
      },
      collapsed: {
        // 侧边栏菜单是否收起
        type: Boolean,
      },
      //位置
      location: {
        type: String,
        default: 'left',
      },
    },
    emits: ['update:collapsed', 'clickMenuItem'],
    setup(props, { emit }) {
      // 当前路由
      const currentRoute = useRoute();
      const router = useRouter();
      const asyncRouteStore = useAsyncRouteStore();
      const settingStore = useProjectSettingStore();
      const menus = ref<any[]>([]);
      const selectedKeys = ref<string>(currentRoute.name as string);
      const headerMenuSelectKey = ref<string>('');
      // 菜单项 key -> 其所属父级 submenu 的 key，用于稳定计算需要展开的父菜单
      const menuParentMap: Record<string, string> = {};
      // 菜单搜索关键词
      const keyword = ref<string>('');
      const searchRef = ref<any>(null);

      const { navMode } = useProjectSetting();

      // 获取当前打开的子菜单
      const matched = currentRoute.matched;

      const getOpenKeys = matched && matched.length ? matched.map((item) => item.name) : [];

      const state = reactive({
        openKeys: getOpenKeys,
      });

      const inverted = computed(() => {
        return ['dark', 'header-dark'].includes(settingStore.navTheme);
      });

      const isSearching = computed(() => keyword.value.trim().length > 0);

      // 关键词命中：自身标题包含，或任一子项标题包含
      function hit(item: any, kw: string) {
        const label = typeof item.label === 'string' ? item.label : '';
        return label.toLowerCase().includes(kw);
      }

      // 按关键词过滤菜单。分组节点内没有命中项时整组隐藏。
      const displayMenus = computed(() => {
        const kw = keyword.value.trim().toLowerCase();
        if (!kw) return menus.value;

        const walk = (list: any[]): any[] =>
          list
            .map((item) => {
              if (item.type === 'group') {
                const children = walk(item.children || []);
                return children.length ? { ...item, children } : null;
              }
              const children: any[] = item.children || [];
              if (children.length) {
                // 父菜单：自身命中则保留全部子项，否则只保留命中的子项
                if (hit(item, kw)) return { ...item };
                const matchedChildren = children.filter((child) => hit(child, kw));
                return matchedChildren.length ? { ...item, children: matchedChildren } : null;
              }
              return hit(item, kw) ? { ...item } : null;
            })
            .filter(Boolean) as any[];

        return walk(menus.value);
      });

      // 搜索时自动展开所有命中结果的父级
      const searchOpenKeys = computed(() => {
        if (!isSearching.value) return [];
        const keys: string[] = [];
        displayMenus.value.forEach((node: any) => {
          const list = node.type === 'group' ? node.children || [] : [node];
          list.forEach((item: any) => {
            if (item && item.children && item.children.length) keys.push(item.key);
          });
        });
        return keys;
      });

      const getSelectedKeys = computed(() => {
        let location = props.location;
        return location === 'left' || (location === 'header' && unref(navMode) === 'horizontal')
          ? unref(selectedKeys)
          : unref(headerMenuSelectKey);
      });

      // 监听分割菜单
      watch(
        () => settingStore.menuSetting.mixMenu,
        () => {
          buildMenus();
          if (props.collapsed) {
            emit('update:collapsed', !props.collapsed);
          }
        }
      );

      // 跟随页面路由变化，切换菜单选中状态
      // 非混合菜单下只更新选中态，不重建菜单结构，避免上一个选中项"闪一下"
      watch(
        () => currentRoute.fullPath,
        () => {
          if (!settingStore.menuSetting.mixMenu) {
            updateSelectedKeys();
          } else {
            buildMenus();
          }
        }
      );

      function updateSelectedKeys() {
        const activeMenu: string = (currentRoute.meta?.activeMenu as string) || '';
        const key: string = activeMenu ? (activeMenu as string) : (currentRoute.name as string);
        // 展开当前项所属的父级 submenu，同时保留已展开的其他分组（可多组并存）
        const parentKey = menuParentMap[key];
        if (parentKey && state.openKeys.indexOf(parentKey) === -1) {
          state.openKeys = [...state.openKeys, parentKey];
        }
        selectedKeys.value = key;
      }

      // 仅（重新）构建菜单结构。菜单项本身是静态的，路由切换不应重建，否则会闪。
      function buildMenus() {
        if (!settingStore.menuSetting.mixMenu) {
          menus.value = generatorMenuGroup(asyncRouteStore.getMenus);
        } else {
          //混合菜单
          const firstRouteName: string = (currentRoute.matched[0].name as string) || '';
          menus.value = generatorMenuMix(asyncRouteStore.getMenus, firstRouteName, props.location);
          const activeMenu: string = currentRoute?.matched[0].meta?.activeMenu as string;
          headerMenuSelectKey.value = (activeMenu ? activeMenu : firstRouteName) || '';
        }
        // 重建菜单结构后重算父级映射，保证切换子项时展开键稳定
        buildMenuParentMap(menus.value);
        updateSelectedKeys();
      }

      // 递归构建 菜单项 key -> 父级 submenu key 的映射。
      // 分组节点（type === 'group'）本身不可展开，不能作为父级 key。
      function buildMenuParentMap(items: any[], parentKey: string | null = null) {
        for (const item of items) {
          if (item.type === 'group') {
            if (item.children && item.children.length) {
              buildMenuParentMap(item.children, parentKey);
            }
            continue;
          }
          if (parentKey) menuParentMap[item.key] = parentKey;
          if (item.children && item.children.length) {
            buildMenuParentMap(item.children, item.key);
          }
        }
      }

      // 点击菜单
      function clickMenuItem(key: string) {
        if (/http(s)?:/.test(key)) {
          window.open(key);
        } else {
          // NMenu 的 value 受 selectedKeys 控制。先同步选中态，再发起路由跳转，
          // 否则在路由响应式更新前会短暂回绘为上一个菜单项，造成闪烁。
          const parentKey = menuParentMap[key];
          if (parentKey && state.openKeys.indexOf(parentKey) === -1) {
            state.openKeys = [...state.openKeys, parentKey];
          }
          selectedKeys.value = key;
          router.push({ name: key });
        }
        emit('clickMenuItem' as any, key);
      }

      // 展开/收起菜单：允许多个分组同时展开，不再强制手风琴
      function menuExpanded(openKeys: string[]) {
        if (!openKeys) return;
        // 搜索态下的展开由 searchOpenKeys 计算得出，不写回常驻展开状态
        if (isSearching.value) return;
        state.openKeys = openKeys;

        // Naive UI 在折叠模式下点击多级菜单只会更新展开键，
        // 但侧栏仍保持折叠，用户会感觉点击没有响应。
        // 有新的父级节点被展开时，同步展开整个侧栏。
        if (props.collapsed && openKeys.length > 0) {
          emit('update:collapsed', false);
        }
      }

      // 折叠态下 Naive UI 的父级菜单默认只支持悬停弹出，点击不会展开。
      // 为多层级节点补充明确的点击行为：展开侧栏并打开完整父级链路。
      function menuNodeProps(option: any) {
        if (!option?.children?.length || option.disabled) return {};
        return {
          class: 'menu-parent-node',
          onClick: () => {
            if (!props.collapsed) return;

            const keysToOpen: string[] = [];
            let currentKey = String(option.key);
            while (currentKey) {
              keysToOpen.unshift(currentKey);
              currentKey = menuParentMap[currentKey] || '';
            }
            state.openKeys = Array.from(new Set([...state.openKeys, ...keysToOpen]));
            emit('update:collapsed', false);
          },
        };
      }

      function focusSearch() {
        nextTick(() => {
          const el = searchRef.value?.$el || searchRef.value;
          const input = el?.querySelector?.('input');
          if (input) input.focus();
          else emit('update:collapsed', false);
        });
      }

      // ⌘K / Ctrl+K 聚焦菜单搜索
      function onKeydown(e: KeyboardEvent) {
        if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
          e.preventDefault();
          if (props.collapsed) emit('update:collapsed', false);
          focusSearch();
        }
      }

      onMounted(() => {
        buildMenus();
        window.addEventListener('keydown', onKeydown);
      });

      onBeforeUnmount(() => {
        window.removeEventListener('keydown', onKeydown);
      });

      return {
        ...toRefs(state),
        inverted,
        menus,
        keyword,
        searchRef,
        isSearching,
        displayMenus,
        searchOpenKeys,
        selectedKeys,
        headerMenuSelectKey,
        getSelectedKeys,
        clickMenuItem,
        menuExpanded,
        menuNodeProps,
      };
    },
  });
</script>

<style lang="less" scoped>
  .aside-menu {
    display: flex;
    flex-direction: column;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
      'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  }

  .menu-search {
    padding: 10px 10px 2px;
  }

  .menu-search :deep(.n-input) {
    height: 34px;
    background: #f1f4f8;
    border-radius: 9px;
  }

  .menu-search :deep(.n-input .n-input__input-el),
  .menu-search :deep(.n-input .n-input__placeholder) {
    font-size: 13px;
  }

  .menu-search-icon {
    display: block;
    color: #94a3b8;
  }

  .menu-search-shortcut {
    padding: 2px 5px;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    color: #94a3b8;
    background: #fff;
    font-size: 10px;
    line-height: 1.2;
  }

  /* 折叠态只保留图标和轻量分隔，避免分组文字被压成竖排单字。 */
  .aside-menu-collapsed :deep(.n-menu) {
    padding: 8px 8px 150px !important;
  }

  .aside-menu-collapsed :deep(.n-menu-item-group-title) {
    width: 32px !important;
    min-width: 32px !important;
    height: 1px !important;
    min-height: 1px !important;
    margin: 9px auto !important;
    padding: 0 !important;
    overflow: hidden !important;
    border: 0 !important;
    background: #e5e9ef !important;
    color: transparent !important;
    font-size: 0 !important;
    line-height: 0 !important;
    letter-spacing: 0 !important;
    pointer-events: none;
  }

  .aside-menu-collapsed :deep(.n-menu-item-content) {
    width: 44px;
    margin: 2px auto !important;
    border-radius: 9px !important;
  }

  .aside-menu-collapsed :deep(.n-menu-item-content__icon) {
    margin-right: 0 !important;
  }

  html[data-theme='dark'] &.aside-menu-collapsed :deep(.n-menu-item-group-title) {
    background: #353535 !important;
  }
</style>
