import { NTag } from 'naive-ui';
import { h } from 'vue';
import { formatDateTime, formatElapsedDuration } from '@/utils/time';

const formatDuration = (row: any): string => {
  return formatElapsedDuration(row.started_at, row.finished_at, { showMilliseconds: false });
};

export const columns = [
  {
    title: '执行编号',
    key: 'id',
    width: 130,
  },
  {
    title: '套件名称',
    key: 'suite_name',
    width: 100,
  },
  {
    title: '所属项目',
    key: 'project_names',
    width: 180,
  },
  {
    title: '执行环境',
    key: 'environment_name',
    width: 120,
    render: (row: any) => h('span', {}, row.environment_name || '-'),
  },
  {
    title: '运行模式',
    key: 'run_type',
    width: 100,
  },
  {
    title: '执行人',
    key: 'executor_name',
    width: 120,
    render: (row: any) => h('span', {}, row.executor_name || '-'),
  },
  {
    title: '执行状态',
    key: 'status',
    width: 100,
  },
  {
    title: '是否通过',
    key: 'is_pass',
    width: 100,
    render(row) {
      if (row.status !== '执行完毕' && row.status !== '执行出错') {
        return h(NTag, { type: 'default' }, { default: () => '-' });
      }

      return h(
        NTag,
        {
          type: row.is_pass ? 'success' : 'error',
        },
        {
          default: () => (row.is_pass ? '通过' : '失败'),
        }
      );
    },
  },
  {
    title: '耗时',
    key: 'duration',
    width: 120,
    render: (row: any) => h('span', {}, formatDuration(row)),
  },
  {
    title: '执行时间',
    key: 'started_at',
    width: 170,
    render: (row: any) => h('span', {}, formatDateTime(row.started_at ?? row.create_datetime)),
  },
];
