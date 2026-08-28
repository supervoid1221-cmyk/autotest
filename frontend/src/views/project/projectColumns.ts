import { h } from 'vue';

const avatarColors = ['#5B6AF0', '#10B981', '#3B82F6', '#F43F5E', '#8B5CF6', '#F59E0B'];

function nameRender(row: any) {
  const char = (row.name || '?').charAt(0);
  const idx = (row.id || 0) % avatarColors.length;
  return h('div', { style: 'display:flex;align-items:center;gap:12px' }, [
    h('span', {
      style: `display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:8px;font-size:14px;font-weight:500;color:#fff;background:${avatarColors[idx]};flex-shrink:0`
    }, char),
    h('span', { style: 'font-size:14px;font-weight:500;color:#1a1a1a' }, row.name),
  ]);
}

export const columns = [
  {
    title: '项目名称',
    key: 'name',
    width: 220,
    render: nameRender,
  },
  {
    title: '项目负责人',
    key: 'pm_name',
    width: 140,
    render: (row: any) => row.pm_name || h('span', { style: 'color:#B4B2A9;font-size:12px' }, '未设置'),
  },
  {
    title: '成员数',
    key: 'user_list',
    width: 80,
    render: (row: any) => h('span', { style: 'font-size:13px;font-weight:500;color:#7C3AED' }, Array.isArray(row.user_list) ? row.user_list.length : '-'),
  },
  {
    title: '项目简介',
    key: 'intro',
    width: 280,
    ellipsis: { tooltip: true },
  },
];
