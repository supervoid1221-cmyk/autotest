import { NTag } from 'naive-ui';
import { h } from 'vue';

const formatDateTime = (value: unknown): string => {
  if (!value) return '-';
  const date = new Date(value as string);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

const formatDuration = (row: any): string => {
  const start = row.started_at;
  const end = row.finished_at;
  if (!start || !end) return '-';
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (Number.isNaN(ms) || ms < 0) return '-';
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}秒`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}分${seconds % 60}秒`;
  const hours = Math.floor(minutes / 60);
  return `${hours}时${minutes % 60}分`;
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
        return h(
          NTag,
          { type: 'default' },
          { default: () => '-' }
        );
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
