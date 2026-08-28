import { h } from 'vue';

const methodColors: Record<string, { color: string; bg: string }> = {
  GET:    { color: '#065F46', bg: '#ECFDF5' },
  POST:   { color: '#1E40AF', bg: '#EFF6FF' },
  PUT:    { color: '#92400E', bg: '#FFFBEB' },
  PATCH:  { color: '#4338CA', bg: '#F3F4FF' },
  DELETE: { color: '#9F1239', bg: '#FFF1F2' },
};

function methodRender(row: any) {
  const m = String(row.method || 'GET').toUpperCase();
  const s = methodColors[m] || { color: '#374151', bg: '#F3F4F6' };
  return h('span', {
    style: `display:inline-block;min-width:56px;padding:2px 10px;border-radius:4px;color:${s.color};background:${s.bg};font-size:12px;font-weight:600;text-align:center;font-family:'JetBrains Mono',monospace`
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
    render: (row: any) => row.creator_name || h('span', { style: 'color:#94A3B8' }, '-'),
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
    render: (row: any) => h('span', { style: 'font-family:JetBrains Mono,monospace;font-size:13px;color:#374151' }, row.url || '-'),
  },
  {
    title: '所属模块',
    key: 'module_name',
    width: 150,
    render: (row: any) => row.module_name || h('span', { style: 'color:#94A3B8' }, '未分组'),
  },
  {
    title: '所属项目',
    key: 'project_name',
    width: 160,
    render: (row: any) => row.project_name || h('span', { style: 'color:#D1D5DB' }, '-'),
  },
  ];
}
