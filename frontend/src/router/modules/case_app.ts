import { RouteRecordRaw } from 'vue-router';
import { PhDeviceMobile } from '@phosphor-icons/vue';
import { Layout } from '@/router/constant';
import { renderIcon } from '@/utils/index';

const routes: Array<RouteRecordRaw> = [{
  path: '/case_app', name: 'CaseApp', component: Layout, redirect: '/case_app/application',
  meta: { title: 'App测试', icon: renderIcon(PhDeviceMobile), sort: 19, group: '测试资产', alwaysShow: true },
  children: [
    { path: 'application', name: 'case_app_application', meta: { title: '应用管理' }, component: () => import('@/views/case_app/application.vue') },
    { path: 'device', name: 'case_app_device', meta: { title: '设备管理' }, component: () => import('@/views/case_app/device.vue') },
    { path: 'inspector', name: 'case_app_inspector', meta: { title: '元素检查', keepAlive: true }, component: () => import('@/views/case_app/inspector.vue') },
    { path: 'element', name: 'case_app_element', meta: { title: '元素管理' }, component: () => import('@/views/case_app/element.vue') },
    { path: 'element/:id?', name: 'case_app_element_edit', meta: { title: '元素详情', hidden: true, activeMenu: 'case_app_element' }, component: () => import('@/views/case_app/element_edit.vue') },
    { path: 'case', name: 'case_app_case', meta: { title: 'App用例' }, component: () => import('@/views/case_app/case.vue') },
    {
      path: 'case/:id?',
      name: 'case_app_case_edit',
      meta: {
        title: 'App用例详情',
        hidden: true,
        activeMenu: 'case_app_case',
        // 编辑中的基本信息和操作步骤在切换平台标签时需要保留。
        keepAlive: true,
      },
      component: () => import('@/views/case_app/case_edit.vue'),
    },
    { path: 'run', name: 'case_app_run', meta: { title: '执行任务', hidden: true, activeMenu: 'execution_control' }, component: () => import('@/views/case_app/run.vue') },
    { path: 'report/:id', name: 'case_app_report', meta: { title: '测试报告', hidden: true, activeMenu: 'execution_control' }, component: () => import('@/views/case_app/report.vue') },
  ],
}];

export default routes;
