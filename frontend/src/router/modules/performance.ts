import { RouteRecordRaw } from 'vue-router';
import { Layout } from '@/router/constant';
import { PhLightning } from '@phosphor-icons/vue';
import { renderIcon } from '@/utils/index';

const routes: Array<RouteRecordRaw> = [{
  path: '/performance', name: 'Performance', component: Layout, redirect: '/performance/scenario',
  meta: { title: '性能测试', icon: renderIcon(PhLightning), sort: 20, group: '测试资产', alwaysShow: true },
  children: [
    { path: 'scenario', name: 'performance_scenario', meta: { title: '性能场景' }, component: () => import('@/views/performance/scenario.vue') },
    { path: 'run', name: 'performance_run', meta: { title: '执行任务', hidden: true, activeMenu: 'execution_control' }, component: () => import('@/views/performance/run.vue') },
    { path: 'report/:id', name: 'performance_report', meta: { title: '性能报告', hidden: true, activeMenu: 'execution_control' }, component: () => import('@/views/performance/report.vue') },
    { path: 'compare', name: 'performance_compare', meta: { title: '报告对比', hidden: true, activeMenu: 'execution_control' }, component: () => import('@/views/performance/compare.vue') },
  ],
}];

export default routes;
