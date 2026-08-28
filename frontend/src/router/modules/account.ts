import { RouteRecordRaw } from 'vue-router';
import { Layout } from '@/router/constant';
import { PhUserCircle } from '@phosphor-icons/vue';
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
    path: '/account',
    name: 'Account',
    redirect: '/account/403',
    component: Layout,
    meta: {
      title: '个人中心',
      icon: renderIcon(PhUserCircle),
      sort: 20,
      hidden: true,
    },
    children: [
      {
        path: 'reset_password',
        name: 'account_reset_password',
        meta: {
          title: '修改密码',
        },
        component: () => import('@/views/account/reset_password.vue'),
      },
    ],
  },
];

export default routes;
