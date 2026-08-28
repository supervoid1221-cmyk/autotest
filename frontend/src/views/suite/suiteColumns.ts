import { h } from 'vue';

const formatNextRun = (value: unknown): string => {
  if (!value) return '-';
  const date = new Date(value as string);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const columns = [
  {
    title: '套件名称',
    key: 'name',
    width: 100,
  },
  {
    title: '所属项目',
    key: 'project_name',
    width: 140,
    render: (row: any) => row.project_name || '-',
  },
  { title: '执行环境', key: 'environment_name', width: 140 },
  {
    title: '运行模式',
    key: 'run_type_display',
    width: 100,
  },
  {
    title: '下次执行时间',
    key: 'next_run',
    width: 170,
    render: (row: any) => h('span', {}, formatNextRun(row.next_run)),
  },
  {
    title: '场景步骤数',
    key: 'case_api_count',
    width: 100,
  },
  {
    title: 'UI 用例数',
    key: 'case_ui_count',
    width: 100,
  },
  {
    title: '描述',
    key: 'description',
    width: 160,
    ellipsis: { tooltip: true },
  },
];
