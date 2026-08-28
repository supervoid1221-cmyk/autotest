<template>
  <n-layout class="layout" :position="fixedMenu" has-sider>
    <n-layout-sider
      v-if="
        !isMobile && isMixMenuNoneSub && (navMode === 'vertical' || navMode === 'horizontal-mix')
      "
      show-trigger="bar"
      @collapse="collapsed = true"
      :position="fixedMenu"
      @expand="collapsed = false"
      :collapsed="collapsed"
      collapse-mode="width"
      :collapsed-width="64"
      :width="leftMenuWidth"
      :native-scrollbar="false"
      :inverted="inverted"
      class="layout-sider"
      :class="{ 'layout-sider-collapsed': collapsed }"
    >
      <Logo :collapsed="collapsed" />
      <AsideMenu v-model:collapsed="collapsed" v-model:location="getMenuLocation" />
      <SidebarAccount v-model:collapsed="collapsed" />
    </n-layout-sider>

    <n-drawer
      v-model:show="showSideDrawer"
      :width="menuWidth"
      :placement="'left'"
      class="layout-side-drawer"
    >
      <n-layout-sider
        :position="fixedMenu"
        :collapsed="false"
        :width="menuWidth"
        :native-scrollbar="false"
        :inverted="inverted"
        class="layout-sider"
      >
        <Logo :collapsed="collapsed" />
        <AsideMenu v-model:location="getMenuLocation" />
        <SidebarAccount :collapsed="false" />
      </n-layout-sider>
    </n-drawer>

    <n-layout :inverted="inverted">
      <n-layout-content
        ref="contentRef"
        class="layout-content"
        :class="{ 'layout-default-background': getDarkTheme === false }"
      >
        <div
          class="layout-content-main"
          :class="{
            'layout-content-main-fix': fixedMulti,
            'fluid-header': fixedHeader === 'static',
          }"
        >
          <TabsView v-if="isMultiTabs" v-model:collapsed="collapsed" />
          <div
            class="main-view"
            :class="{
              'main-view-fix': fixedMulti,
              noMultiTabs: !isMultiTabs,
            }"
          >
            <MainView />
          </div>
        </div>
        <!--1.15废弃，没啥用，占用操作空间-->
        <!--        <NLayoutFooter v-if="getShowFooter">-->
        <!--          <PageFooter />-->
        <!--        </NLayoutFooter>-->
      </n-layout-content>
      <n-back-top :right="100" />
    </n-layout>
  </n-layout>
</template>

<script lang="ts" setup>
  import { ref, unref, computed, onMounted, watch, nextTick } from 'vue';
  import { Logo } from './components/Logo';
  import { TabsView } from './components/TagsView';
  import { MainView } from './components/Main';
  import { AsideMenu } from './components/Menu';
  import { SidebarAccount } from './components/SidebarAccount';
  import { useProjectSetting } from '@/hooks/setting/useProjectSetting';
  import { useDesignSetting } from '@/hooks/setting/useDesignSetting';
  import { useRoute } from 'vue-router';
  import { useProjectSettingStore } from '@/store/modules/projectSetting';

  const { getDarkTheme } = useDesignSetting();
  const {
    // showFooter,
    navMode,
    navTheme,
    headerSetting,
    menuSetting,
    multiTabsSetting,
  } = useProjectSetting();

  const settingStore = useProjectSettingStore();
  const route = useRoute();

  const collapsed = ref<boolean>(false);
  const contentRef = ref<any>(null);

  const { mobileWidth, menuWidth } = unref(menuSetting);

  const isMobile = computed<boolean>({
    get: () => settingStore.getIsMobile,
    set: (val) => settingStore.setIsMobile(val),
  });

  const isMixMenuNoneSub = computed(() => {
    const mixMenu = unref(menuSetting).mixMenu;
    if (unref(navMode) != 'horizontal-mix') return true;
    if (unref(navMode) === 'horizontal-mix' && mixMenu && route.meta.isRoot) {
      return false;
    }
    return true;
  });

  const fixedMenu = computed(() => {
    const { fixed } = unref(headerSetting);
    return fixed ? 'absolute' : 'static';
  });

  const isMultiTabs = computed(() => {
    return unref(multiTabsSetting).show;
  });

  const fixedMulti = computed(() => {
    return unref(multiTabsSetting).fixed;
  });

  const inverted = computed(() => {
    return ['dark', 'header-dark'].includes(unref(navTheme));
  });

  const leftMenuWidth = computed(() => {
    const { minMenuWidth, menuWidth } = unref(menuSetting);
    return collapsed.value ? minMenuWidth : menuWidth;
  });

  const getMenuLocation = computed(() => {
    return 'left';
  });

  // 控制显示或隐藏移动端侧边栏
  const showSideDrawer = computed({
    get: () => isMobile.value && collapsed.value,
    set: (val) => (collapsed.value = val),
  });

  //判断是否触发移动端模式
  const checkMobileMode = () => {
    if (document.body.clientWidth <= mobileWidth) {
      isMobile.value = true;
    } else {
      isMobile.value = false;
    }
    collapsed.value = false;
  };

  const watchWidth = () => {
    const Width = document.body.clientWidth;
    if (Width <= 950) {
      collapsed.value = true;
    } else collapsed.value = false;

    checkMobileMode();
  };

  onMounted(() => {
    checkMobileMode();
    window.addEventListener('resize', watchWidth);
  });

  // n-layout-content 使用独立滚动容器；切页后显式回到顶部，避免新表单显示在视口外。
  watch(
    () => route.fullPath,
    async () => {
      await nextTick();
      const element = contentRef.value?.$el || contentRef.value;
      element?.scrollTo?.({ top: 0 });
    },
    { flush: 'post' }
  );
</script>

<style lang="less">
  .layout-side-drawer {
    background-color: rgb(0, 20, 40);

    .layout-sider {
      min-height: 100vh;
      box-shadow: 2px 0 8px 0 rgb(29 35 41 / 5%);
      position: relative;
      z-index: 13;
      transition: all 0.2s ease-in-out;
    }
  }
</style>
<style lang="less" scoped>
  .layout {
    display: flex;
    flex-direction: row;
    flex: auto;

    &-default-background {
      background: #f8f9fa;
    }

    .layout-sider {
      min-height: 100vh;
      box-shadow: 1px 0 0 0 #ededee, 0 0 0 0 transparent;
      position: relative;
      z-index: 13;
      transition: all 0.15s ease;
      border-right: none;
      background: #fafafc;
    }

    .layout-sider-fix {
      position: fixed;
      top: 0;
      left: 0;
    }

    .ant-layout {
      overflow: hidden;
    }

    .layout-right-fix {
      overflow-x: hidden;
      padding-left: 200px;
      min-height: 100vh;
      transition: all 0.2s ease-in-out;
    }

    .layout-content {
      flex: auto;
      min-height: 100vh;
    }

    .n-layout-header.n-layout-header--absolute-positioned {
      z-index: 11;
    }

    .n-layout-footer {
      background: none;
    }
  }

  .layout-content-main {
    margin: 0 12px 12px;
    position: relative;
    padding-top: 0;
  }

  .layout-content-main-fix {
    padding-top: 0;
  }

  .main-view-fix {
    padding-top: 44px;
  }

  .noMultiTabs {
    padding-top: 0;
  }

  /* ===== 侧边栏菜单视觉优化（仅布局/间距，配色交给主题） ===== */
  .layout-sider {
    :deep(.n-layout-sider-scroll-container) {
      position: relative;
      min-height: 100vh;
    }

    /* 菜单容器左右留白，菜单项形成"胶囊"观感 */
    :deep(.n-menu) {
      padding: 6px 10px 88px;
    }

    /* 菜单项：圆角 + 行高 */
    :deep(.n-menu .n-menu-item-content) {
      position: relative;
      border-radius: 8px;
      height: 42px;
      margin: 2px 0;
      transition: none;
    }

    /* Naive UI 的选中背景与左侧蓝色标记共用 ::before。
       默认 300ms 淡出会让旧菜单项在同级切换后继续闪现一帧。 */
    :deep(.n-menu .n-menu-item-content::before) {
      transition: none !important;
    }

    /* 激活态左侧 3px 蓝色指示条 */
    :deep(.n-menu .n-menu-item-content--selected)::before {
      content: '';
      position: absolute;
      left: 0;
      top: 50%;
      transform: translateY(-50%);
      width: 3px;
      height: 22px;
      border-radius: 0 3px 3px 0;
      background-color: #2563eb;
    }

    /* 图标与文字的间距更透气 */
    :deep(.n-menu .n-menu-item-content .n-menu-item-content__icon) {
      font-size: 18px;
    }

    /* 子菜单项缩进后的左侧对齐线 */
    :deep(.n-menu .n-submenu-children .n-menu-item-content) {
      padding-left: 44px;
    }

    /* 菜单文字字号微调，层级更清晰 */
    :deep(.n-menu .n-menu-item-content-header) {
      font-size: 13.5px;
    }
  }

  .layout-sider-collapsed :deep(.n-menu) {
    padding-bottom: 142px;
  }
</style>
