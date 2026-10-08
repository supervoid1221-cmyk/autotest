import { RouteRecordRaw } from 'vue-router';
import { Layout } from '@/router/constant';

// 保留旧监控地址的跳转兼容；实际菜单已迁移至“监控中心”和“服务器配置”。
const routes: Array<RouteRecordRaw> = [
  {
    path: '/monitor',
    name: 'LegacyMonitorCenter',
    component: Layout,
    redirect: '/server-configuration/monitor-config',
    meta: { title: '监控', hidden: true, sort: 0 },
    children: [
      { path: 'overview', name: 'legacy_monitor_overview', redirect: '/dashboard/monitor', meta: { title: '监控台', hidden: true } },
      { path: 'config', name: 'legacy_monitor_config', redirect: '/server-configuration/monitor-config', meta: { title: '监控配置', hidden: true } },
      { path: 'service', name: 'legacy_monitor_service', redirect: '/server-configuration/service-monitor', meta: { title: '服务监控', hidden: true } },
      { path: 'notification', name: 'legacy_monitor_notification', redirect: '/server-configuration/notification', meta: { title: '告警通知', hidden: true } },
      { path: 'alerts', name: 'legacy_monitor_alerts', redirect: '/server-configuration/alerts', meta: { title: '告警事件', hidden: true } },
    ],
  },
];

export default routes;
