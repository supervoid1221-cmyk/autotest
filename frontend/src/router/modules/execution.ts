import { RouteRecordRaw } from 'vue-router';
import { PhPlayCircle } from '@phosphor-icons/vue';
import { Layout } from '@/router/constant';
import { renderIcon } from '@/utils/index';

const routes: Array<RouteRecordRaw> = [{
  path: '/execution',
  name: 'Execution',
  component: Layout,
  redirect: '/execution/tasks',
  meta: {
    title: '执行与报告',
    icon: renderIcon(PhPlayCircle),
    sort: 22,
    group: '执行与报告',
  },
  children: [
    {
      path: 'tasks',
      name: 'execution_control',
      meta: { title: '执行与报告' },
      component: () => import('@/views/suite/execution_control.vue'),
    },
    {
      path: 'report/:sourceType/:id',
      name: 'execution_report',
      meta: { title: '执行报告', hidden: true, activeMenu: 'execution_control' },
      component: () => import('@/views/suite/execution_report.vue'),
    },
  ],
}];

export default routes;
