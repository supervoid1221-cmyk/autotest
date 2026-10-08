import { h } from 'vue';
import { formatDateTime } from '@/utils/time';

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
    render: (row: any) =>
      h(
        'span',
        {},
        row.run_type === 'C' || row.run_type_display === 'Cron'
          ? '定时任务'
          : row.run_type_display || '-'
      ),
  },
  {
    title: '下次执行时间',
    key: 'next_run',
    width: 170,
    render: (row: any) => h('span', {}, formatDateTime(row.next_run, { includeSeconds: false })),
  },
  {
    title: '场景步骤数',
    key: 'case_api_count',
    width: 100,
  },
  {
    title: 'UI 步骤数',
    key: 'ui_step_count',
    width: 100,
  },
  {
    title: 'App 步骤数',
    key: 'app_step_count',
    width: 100,
  },
  {
    title: '描述',
    key: 'description',
    width: 160,
    ellipsis: { tooltip: true },
  },
];
