<template>
  <div class="sidebar-account" :class="{ 'sidebar-account-collapsed': collapsed }">
    <div class="account-row">
      <n-dropdown
        trigger="click"
        placement="top-start"
        :options="avatarOptions"
        @select="avatarSelect"
      >
        <button type="button" class="account-trigger" :title="displayName">
          <n-avatar round color="#2563eb" :size="34">{{ usernameInitial }}</n-avatar>
          <span v-if="!collapsed" class="account-copy">
            <strong>{{ displayName }}</strong>
            <small>{{ accountCaption }}</small>
          </span>
        </button>
      </n-dropdown>

      <div class="account-actions">
        <n-tooltip placement="top">
          <template #trigger>
            <button
              type="button"
              class="account-icon-button"
              title="平台设置"
              aria-label="平台设置"
              @click="openSetting"
            >
              <PhGearSix :size="18" />
            </button>
          </template>
          <span>平台设置</span>
        </n-tooltip>
        <n-tooltip placement="top">
          <template #trigger>
            <button
              type="button"
              class="account-icon-button"
              :title="collapsed ? '展开菜单' : '收起菜单'"
              :aria-label="collapsed ? '展开菜单' : '收起菜单'"
              @click="$emit('update:collapsed', !collapsed)"
            >
              <PhSidebarSimple :size="18" :weight="collapsed ? 'fill' : 'regular'" />
            </button>
          </template>
          <span>{{ collapsed ? '展开菜单' : '收起菜单' }}</span>
        </n-tooltip>
      </div>
    </div>
    <ProjectSetting ref="drawerSetting" />
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref } from 'vue';
  import { useDialog, useMessage } from 'naive-ui';
  import { PhGearSix, PhSidebarSimple } from '@phosphor-icons/vue';
  import { useRoute, useRouter } from 'vue-router';
  import { useUserStore } from '@/store/modules/user';
  import { TABS_ROUTES } from '@/store/mutation-types';
  import ProjectSetting from '@/layout/components/Header/ProjectSetting.vue';

  defineProps<{
    collapsed?: boolean;
  }>();

  defineEmits<{
    (event: 'update:collapsed', value: boolean): void;
  }>();

  const userStore = useUserStore();
  const router = useRouter();
  const route = useRoute();
  const dialog = useDialog();
  const message = useMessage();
  const drawerSetting = ref<InstanceType<typeof ProjectSetting>>();

  const userInfo = computed<any>(() => userStore.info || {});
  const displayName = computed(
    () =>
      String(
        userInfo.value.username ||
          userInfo.value.name ||
          userInfo.value.email ||
          userStore.username ||
          '当前用户'
      ).trim() || '当前用户'
  );
  const usernameInitial = computed(() => displayName.value.charAt(0).toUpperCase());
  const accountCaption = computed(() => {
    if (userInfo.value.is_admin || userInfo.value.is_superuser || userInfo.value.is_staff) return '系统管理员';
    return userInfo.value.role_name || userInfo.value.role || '已登录';
  });

  const avatarOptions = [
    { label: '修改密码', key: 'password' },
    { label: '退出登录', key: 'logout' },
  ];

  function avatarSelect(key: string) {
    if (key === 'password') {
      router.push({ name: 'account_reset_password' });
      return;
    }
    if (key === 'logout') doLogout();
  }

  function doLogout() {
    dialog.info({
      title: '提示',
      content: '您确定要退出登录吗',
      positiveText: '确定',
      negativeText: '取消',
      onPositiveClick: async () => {
        await userStore.logout();
        message.success('成功退出登录');
        localStorage.removeItem(TABS_ROUTES);
        await router.replace({ name: 'Login', query: { redirect: route.fullPath } });
        location.reload();
      },
    });
  }

  function openSetting() {
    drawerSetting.value?.openDrawer();
  }
</script>

<style lang="less" scoped>
  .sidebar-account {
    position: absolute;
    z-index: 4;
    right: 0;
    bottom: 0;
    left: 0;
    padding: 10px;
    border-top: 1px solid #e8edf3;
    background: rgb(250 250 252 / 96%);
    backdrop-filter: blur(10px);
  }

  .account-row,
  .account-trigger,
  .account-actions {
    display: flex;
    align-items: center;
  }

  .account-row {
    gap: 8px;
  }

  .account-trigger {
    min-width: 0;
    flex: 1;
    gap: 10px;
    padding: 5px;
    border: 0;
    border-radius: 7px;
    color: #263449;
    background: transparent;
    text-align: left;
    cursor: pointer;
    transition: background-color 160ms ease;
  }

  .account-trigger:hover,
  .account-icon-button:hover {
    background: #eef2f7;
  }

  .account-trigger:focus-visible,
  .account-icon-button:focus-visible {
    outline: 2px solid #8bb8ff;
    outline-offset: 1px;
  }

  .account-copy {
    display: grid;
    min-width: 0;
    line-height: 1.15;
  }

  .account-copy strong,
  .account-copy small {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .account-copy strong {
    font-size: 13px;
    font-weight: 600;
  }

  .account-copy small {
    margin-top: 4px;
    color: #8a96a8;
    font-size: 11px;
  }

  .account-actions {
    gap: 3px;
  }

  .account-icon-button {
    display: inline-grid;
    width: 32px;
    height: 32px;
    padding: 0;
    place-items: center;
    border: 0;
    border-radius: 7px;
    color: #657286;
    background: transparent;
    cursor: pointer;
    transition: background-color 160ms ease, color 160ms ease;
  }

  .sidebar-account-collapsed {
    padding: 8px;
  }

  .sidebar-account-collapsed .account-row,
  .sidebar-account-collapsed .account-actions {
    flex-direction: column;
  }

  .sidebar-account-collapsed .account-trigger {
    flex: none;
    padding: 5px;
  }
</style>
