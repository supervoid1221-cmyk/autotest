import { RouteRecordRaw } from 'vue-router';
import { Layout } from '@/router/constant';
import { PhChartLineUp } from '@phosphor-icons/vue';
import { renderIcon } from '@/utils/index';

const routes: Array<RouteRecordRaw> = [
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: Layout,
    redirect: '/dashboard/console',
    meta: {
      title: '监控中心',
      icon: renderIcon(PhChartLineUp),
      sort: 0,
      alwaysShow: true,
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
        component: () => import('@/views/monitor/overview.vue'),
      },
    ],
  },
];

export default routes;
