import { RouteRecordRaw } from 'vue-router';
import { Layout } from '@/router/constant';
import { PhCube } from '@phosphor-icons/vue';
import { renderIcon } from '@/utils/index';

const routes: Array<RouteRecordRaw> = [
  {
    path: '/template',
    name: 'Template',
    component: Layout,
    meta: {
      title: '数据工厂',
      icon: renderIcon(PhCube),
      sort: 24,
      group: '测试资产',
    },
    children: [
      {
        path: '',
        name: 'template_list',
        meta: { title: '模块管理' },
        component: () => import('@/views/execution_template/template.vue'),
      },
      {
        path: 'tools',
        name: 'template_tools',
        meta: { title: '工具' },
        component: () => import('@/views/execution_template/tools.vue'),
      },
      {
        path: 'edit/:id?',
        name: 'template_edit',
        meta: { title: '模板详情', hidden: true, activeMenu: 'template_list' },
        component: () => import('@/views/execution_template/template_edit.vue'),
      },
      {
        path: 'run/:id',
        name: 'template_run',
        meta: { title: '执行', hidden: true, activeMenu: 'template_list' },
        component: () => import('@/views/execution_template/template_run.vue'),
      },
    ],
  },
];

export default routes;
