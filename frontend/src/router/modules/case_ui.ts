import { RouteRecordRaw } from 'vue-router';
import { Layout } from '@/router/constant';
import { PhMonitor } from '@phosphor-icons/vue';
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
    path: '/case_ui',
    name: 'CaseUi',
    redirect: '/case_ui/case',
    component: Layout,
    meta: {
      title: 'UI测试',
      icon: renderIcon(PhMonitor),
      sort: 18,
      group: '测试资产',
    },
    children: [
      {
        path: 'element',
        name: 'case_ui_element',
        meta: {
          title: '元素管理',
        },
        component: () => import('@/views/case_ui/element.vue'),
      },
      {
        path: 'element/:id?',
        name: 'case_ui_element_edit',
        meta: {
          title: '元素详情',
          hidden: true,
          activeMenu: 'case_ui_element',
        },
        component: () => import('@/views/case_ui/element_edit.vue'),
      },
      {
        path: 'case',
        name: 'case_ui_case',
        meta: {
          title: 'UI用例',
        },
        component: () => import('@/views/case_ui/ui_case.vue'),
      },
      {
        path: 'case/:id?',
        name: 'case_ui_case_edit',
        meta: {
          title: 'UI用例详情',
          hidden: true,
          activeMenu: 'case_ui_case',
        },
        component: () => import('@/views/case_ui/ui_case_edit.vue'),
      },
      {
        path: 'playwright-case',
        name: 'case_ui_playwright_case',
        meta: { title: '智能用例' },
        component: () => import('@/views/case_ui/playwright_case.vue'),
      },
      {
        path: 'playwright-case/:id?',
        name: 'case_ui_playwright_case_edit',
        meta: {
          title: '智能用例详情',
          hidden: true,
          activeMenu: 'case_ui_playwright_case',
          // 编辑器中存在未提交的 Tab/步骤草稿；切换平台多页签时必须保留组件状态。
          keepAlive: true,
        },
        component: () => import('@/views/case_ui/ui_case_edit.vue'),
      },
      {
        path: 'yaml-case',
        name: 'case_ui_yaml_case',
        meta: { title: 'YAML用例', keepAlive: true },
        component: () => import('@/views/case_ui/yaml_case.vue'),
      },
    ],
  },
];

export default routes;
