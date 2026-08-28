import { h } from 'vue';

export const columns = [
  {
    title: 'id',
    key: 'id',
    width: 100,
  },
  {
    title: '用例名称',
    key: 'name',
    width: 100,
  },
  {
    title: '所属项目',
    key: 'project_name',
    width: 100,
  },
  {
    title: '接口名称',
    key: 'endpoint_info.name',
    width: 100,
    render(row) {
      return h('div', `${row.endpoint_info.name} （ID：${row.endpoint_info.id}）`);
    },
  },
];
