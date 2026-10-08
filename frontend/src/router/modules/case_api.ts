import { RouteRecordRaw } from 'vue-router';
import { Layout } from '@/router/constant';
import { PhGlobe } from '@phosphor-icons/vue';
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
    path: '/case_api',
    name: 'CaseApi',
    redirect: '/case_api/endpoint',
    component: Layout,
    meta: {
      title: 'API测试',
      icon: renderIcon(PhGlobe),
      sort: 17,
      group: '测试资产',
    },
    children: [
      {
        path: 'endpoint',
        name: 'case_api_endpoint',
        meta: {
          title: '接口管理',
        },
        component: () => import('@/views/case_api/endpoint.vue'),
      },
      {
        path: 'endpoint/:id?',
        name: 'case_api_endpoint_edit',
        meta: {
          title: '接口详情',
          hidden: true,
          activeMenu: 'case_api_endpoint',
          // 执行结果和未提交的请求配置在切换平台多页签时需要保留。
          keepAlive: true,
        },
        component: () => import('@/views/case_api/endpoint_edit.vue'),
      },
      {
        path: 'recording',
        name: 'case_api_recording',
        // 录制页仅从“接口管理”的工具按钮进入，不单独展示在侧边菜单。
        meta: { title: '接口录制', activeMenu: 'case_api_endpoint', hidden: true },
        component: () => import('@/views/case_api/recording.vue'),
      },
      {
        path: 'scenario', name: 'case_api_scenario', meta: { title: '场景管理' }, component: () => import('@/views/case_api/scenario.vue'),
      },
      {
        path: 'scenario/:id?', name: 'case_api_scenario_edit', meta: { title: '场景详情', hidden: true, activeMenu: 'case_api_scenario', keepAlive: true }, component: () => import('@/views/case_api/scenario_edit.vue'),
      },
    ],
  },
];

export default routes;
