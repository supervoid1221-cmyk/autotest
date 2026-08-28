import { h } from 'vue';

const locatorColors: Record<string, { color: string; background: string }> = {
  XPATH: { color: '#7c3aed', background: '#f5f3ff' },
  CSS_SELECTOR: { color: '#1769e8', background: '#eff6ff' },
  ID: { color: '#087f5b', background: '#ecfdf5' },
  NAME: { color: '#b45309', background: '#fffbeb' },
  LINK_TEXT: { color: '#0e7490', background: '#ecfeff' },
  PARTIAL_LINK_TEXT: { color: '#0e7490', background: '#ecfeff' },
};

export function createElementColumns(onNameClick: (row: any) => void) {
  return [
    { type: 'selection', width: 44 },
    {
      title: '元素名称', key: 'name', width: 210,
      render: (row: any) => h('button', {
        type: 'button', class: 'element-name-link', title: `编辑元素「${row.name}」`,
        onClick: () => onNameClick(row),
      }, row.name),
    },
    {
      title: '创建人', key: 'creator_name', width: 120,
      render: (row: any) => row.creator_name || h('span', { style: 'color:#94a3b8' }, '-'),
    },
    {
      title: '定位方式', key: 'by', width: 150,
      render: (row: any) => {
        const style = locatorColors[row.by] || { color: '#526075', background: '#f1f5f9' };
        return h('span', {
          style: `display:inline-block;padding:3px 9px;border-radius:4px;color:${style.color};background:${style.background};font:600 12px 'JetBrains Mono',monospace`,
        }, row.by || '-');
      },
    },
    {
      title: '定位表达式', key: 'value', width: 330, ellipsis: { tooltip: true },
      render: (row: any) => h('span', { class: 'locator-expression' }, row.value || '-'),
    },
    {
      title: '所属模块', key: 'module_name', width: 150,
      render: (row: any) => row.module_name || h('span', { style: 'color:#94a3b8' }, '未分组'),
    },
    {
      title: '所属项目', key: 'project_name', width: 160,
      render: (row: any) => row.project_name || row.project_info?.name || '-',
    },
  ];
}
