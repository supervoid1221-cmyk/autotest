import { RouteRecordRaw } from 'vue-router';
import { Layout } from '@/router/constant';
import { PhSquaresFour } from '@phosphor-icons/vue';
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
    path: '/project',
    name: 'Project',
    component: Layout,
    meta: {
      title: '项目管理',
      icon: renderIcon(PhSquaresFour),
      sort: 16,
    },
    children: [
      {
        // 项目列表作为模块首页，避免出现 /project/project 的重复路径。
        path: '',
        name: 'project_project',
        meta: {
          title: '项目信息',
        },
        component: () => import('@/views/project/project.vue'),
      },
      {
        path: 'project/:id?',
        name: 'project_project_edit',
        meta: {
          title: '项目详情',
          hidden: true,
          activeMenu: 'project_project',
        },
        component: () => import('@/views/project/project_edit.vue'),
      },
      {
        path: 'environment',
        name: 'project_environment',
        meta: { title: '环境与认证' },
        component: () => import('@/views/project/environment.vue'),
      },
      {
        path: 'environment/:id?',
        name: 'project_environment_edit',
        meta: { title: '环境详情', hidden: true, activeMenu: 'project_environment' },
        component: () => import('@/views/project/environment_edit.vue'),
      },
      {
        path: 'database',
        name: 'project_database',
        meta: { title: '数据库连接' },
        component: () => import('@/views/project/database.vue'),
      },
      {
        path: 'database/:id?',
        name: 'project_database_edit',
        meta: { title: '数据库连接详情', hidden: true, activeMenu: 'project_database' },
        component: () => import('@/views/project/database_edit.vue'),
      },
      {
        path: 'dynamic-function',
        name: 'project_dynamic_function',
        meta: { title: '动态函数' },
        component: () => import('@/views/project/dynamic_function.vue'),
      },
      {
        path: 'dynamic-function/:id?',
        name: 'project_dynamic_function_edit',
        meta: { title: '动态函数详情', hidden: true, activeMenu: 'project_dynamic_function' },
        component: () => import('@/views/project/dynamic_function_edit.vue'),
      },
    ],
  },
];

export default routes;
