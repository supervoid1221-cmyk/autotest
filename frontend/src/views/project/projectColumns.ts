import { h } from 'vue';

const avatarColors = ['#5B6AF0', '#10B981', '#3B82F6', '#F43F5E', '#8B5CF6', '#F59E0B'];

function nameRender(row: any) {
  const char = (row.name || '?').charAt(0);
  const idx = (row.id || 0) % avatarColors.length;
  return h('div', { class: 'project-name-cell' }, [
    h('span', {
      class: 'project-list-avatar',
      style: `background:${avatarColors[idx]}`,
    }, char),
    h('span', { class: 'project-name-copy' }, [
      h('strong', row.name || '未命名项目'),
      h('small', `ID ${row.id || '-'}`),
    ]),
  ]);
}

export const columns = [
  {
    title: '项目名称',
    key: 'name',
    width: 260,
    render: nameRender,
  },
  {
    title: '项目负责人',
    key: 'pm_name',
    width: 160,
    render: (row: any) => h('span', { class: row.pm_name ? 'project-owner' : 'project-empty-value' }, row.pm_name || '未设置'),
  },
  {
    title: '成员数',
    key: 'user_list',
    width: 100,
    render: (row: any) => h('span', { class: 'project-member-count' }, Array.isArray(row.user_list) ? row.user_list.length : '-'),
  },
  {
    title: '项目简介',
    key: 'intro',
    width: 360,
    ellipsis: { tooltip: true },
    render: (row: any) => h('span', { class: row.intro ? 'project-intro-text' : 'project-empty-value' }, row.intro || '暂无项目说明'),
  },
];
