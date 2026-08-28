import { RouteRecordRaw } from 'vue-router';
import { Layout } from '@/router/constant';
import { BankOutlined } from '@vicons/antd';
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
    redirect: '/project/403',
    component: Layout,
    meta: {
      title: '项目管理',
      icon: renderIcon(BankOutlined),
      sort: 16,
    },
    children: [
      {
        path: 'project',
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
          title: '部门详情',
          hidden: true,
          activeMenu: 'project_project',
        },
        component: () => import('@/views/system/project_edit.vue'),
      },
    ],
  },
];

export default routes;
