import { RouteRecordRaw } from 'vue-router';
import { Layout } from '@/router/constant';
import { PhGearSix, PhHardDrives } from '@phosphor-icons/vue';
import { renderIcon } from '@/utils/index';

/**
 * @param name 路由名称, 必须设置,且不能重名
 * @param meta 路由元信息（路由附带扩展信息）
 * @param redirect 重定向地址, 访问这个路由时,自定进行重定向
 * @param meta.disabled 禁用整个菜单
 * @param meta.title 菜单名称
 * @param meta.icon 菜单图标
 * @param meta.keepAlive 缓存该路由
 * @param meta.sort 排序越小越排前
 *
 * */
const routes: Array<RouteRecordRaw> = [
  {
    path: '/server-configuration',
    name: 'ServerConfiguration',
    redirect: '/server-configuration/connection',
    component: Layout,
    meta: {
      title: '服务器配置',
      icon: renderIcon(PhHardDrives),
      sort: 22,
      group: '系统',
      // 即使当前只有“服务器连接”一个子项，也保留一级菜单层级。
      alwaysShow: true,
    },
    children: [
      {
        path: 'connection', alias: '/system/server', name: 'system_server', meta: { title: '服务器连接' },
        component: () => import('@/views/system/server.vue'),
      },
      {
        path: 'monitor-settings', name: 'monitor_check_settings', meta: { title: '监控设置', hidden: true, activeMenu: 'monitor_config' },
        component: () => import('@/views/monitor/settings.vue'),
      },
      {
        path: 'monitor-config', name: 'monitor_config', meta: { title: '监控配置' },
        component: () => import('@/views/monitor/config.vue'),
      },
      {
        path: 'service-monitor', name: 'monitor_service', meta: { title: '服务监控' },
        component: () => import('@/views/monitor/config.vue'),
        props: { defaultTab: 'services' },
      },
      {
        path: 'notification', name: 'monitor_notification', meta: { title: '告警通知' },
        component: () => import('@/views/monitor/notification.vue'),
      },
      {
        path: 'alerts', name: 'monitor_alerts', meta: { title: '告警事件' },
        component: () => import('@/views/monitor/alerts.vue'),
      },
    ],
  },
  {
    path: '/system',
    name: 'System',
    redirect: '/system/configuration',
    component: Layout,
    meta: {
      title: '系统管理',
      icon: renderIcon(PhGearSix),
      sort: 23,
      group: '系统',
      alwaysShow: true,
    },
    children: [
      {
        path: 'tenant', name: 'system_tenant', meta: { title: '租户管理' },
        component: () => import('@/views/system/tenant.vue'),
      },
      {
        path: 'configuration', name: 'system_configuration', meta: { title: '系统配置' },
        component: () => import('@/views/system/configuration.vue'),
      },
      {
        path: 'user', name: 'system_user', meta: { title: '用户管理' },
        component: () => import('@/views/system/user.vue'),
      },
      {
        path: 'user/:id?', name: 'system_user_edit', meta: { title: '用户详情', hidden: true, activeMenu: 'system_user' },
        component: () => import('@/views/system/user_edit.vue'),
      },
      {
        path: 'notifications', name: 'suite_notifications', meta: { title: '通知管理' },
        component: () => import('@/views/suite/notifications.vue'),
      },
    ],
  },
];

export default routes;
