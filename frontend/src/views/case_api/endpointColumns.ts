import { h } from 'vue';

function methodRender(row: any) {
  const m = String(row.method || 'GET').toUpperCase();
  return h('span', {
    class: ['endpoint-method-tag', `method-${m.toLowerCase()}`],
  }, m);
}

export function createEndpointColumns(onNameClick: (row: any) => void) {
  return [
  {
    type: 'selection',
    width: 44,
  },
  {
    title: '接口名称',
    key: 'name',
    width: 200,
    render: (row: any) => h('button', {
      type: 'button',
      class: 'endpoint-name-link',
      title: `查看接口「${row.name}」详情`,
      onClick: () => onNameClick(row),
    }, row.name),
  },
  {
    title: '创建人',
    key: 'creator_name',
    width: 120,
    render: (row: any) => row.creator_name || h('span', { class: 'endpoint-empty-value' }, '-'),
  },
  {
    title: '方法',
    key: 'method',
    width: 100,
    render: methodRender,
  },
  {
    title: '路径',
    key: 'url',
    width: 280,
    render: (row: any) => h('span', { class: 'endpoint-path' }, row.url || '-'),
  },
  {
    title: '所属模块',
    key: 'module_name',
    width: 150,
    render: (row: any) => row.module_name || h('span', { class: 'endpoint-empty-value' }, '未分组'),
  },
  {
    title: '所属项目',
    key: 'project_name',
    width: 160,
    render: (row: any) => row.project_name || h('span', { class: 'endpoint-empty-value' }, '-'),
  },
  ];
}
