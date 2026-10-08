import { RouteRecordRaw } from 'vue-router';
import { Layout } from '@/router/constant';
import { PhCheckSquare } from '@phosphor-icons/vue';
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
    path: '/suite',
    name: 'Suite',
    component: Layout,
    meta: {
      title: '测试计划',
      icon: renderIcon(PhCheckSquare),
      sort: 21,
      group: '执行与报告',
    },
    children: [
      {
        path: 'execution-control',
        name: 'legacy_execution_control',
        redirect: '/execution/tasks',
        meta: { title: '执行与报告中心', hidden: true, activeMenu: 'execution_control' },
      },
      {
        path: 'execution-report/:sourceType/:id',
        name: 'legacy_execution_report',
        redirect: to => `/execution/report/${to.params.sourceType}/${to.params.id}`,
        meta: { title: '执行报告', hidden: true, activeMenu: 'execution_control' },
      },
      {
        // 套件管理就是模块首页，避免出现 /suite/suite 的重复路径。
        path: '',
        name: 'suite_suite',
        meta: {
          title: '测试计划',
        },
        component: () => import('@/views/suite/suite.vue'),
      },
      {
        path: 'suite/:id?',
        name: 'suite_suite_edit',
        meta: {
          title: '套件详情',
          hidden: true,
          activeMenu: 'suite_suite',
        },
        component: () => import('@/views/suite/suite_edit.vue'),
      },
      {
        path: 'run_result',
        name: 'suite_run_result',
        meta: {
          title: '套件执行任务',
          hidden: true,
          activeMenu: 'execution_control',
        },
        component: () => import('@/views/suite/run_result.vue'),
      },
      {
        path: 'notifications',
        name: 'legacy_suite_notifications',
        redirect: '/system/notifications',
        meta: { title: '通知管理', hidden: true, activeMenu: 'suite_notifications' },
      },
      {
        path: 'report/:id(.*)',
        name: 'suite_report',
        meta: {
          title: '测试报告',
          hidden: true,
          activeMenu: 'execution_control',
        },
        component: () => import('@/views/suite/report.vue'),
      },
    ],
  },
];

export default routes;
