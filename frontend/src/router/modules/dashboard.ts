import { RouteRecordRaw } from 'vue-router';
import { Layout } from '@/router/constant';
import { PhGauge } from '@phosphor-icons/vue';
import { renderIcon } from '@/utils/index';

const routes: Array<RouteRecordRaw> = [
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: Layout,
    redirect: '/dashboard/console',
    meta: {
      title: '仪表盘',
      icon: renderIcon(PhGauge),
      sort: 0,
    },
    children: [
      {
        path: 'console',
        name: 'dashboard_console',
        meta: { title: '主控台' },
        component: () => import('@/views/dashboard/console/console.vue'),
      },
      {
        path: 'monitor',
        name: 'dashboard_monitor',
        meta: { title: '监控台' },
        component: () => import('@/views/dashboard/monitor/monitor.vue'),
      },
    ],
  },
];

export default routes;
