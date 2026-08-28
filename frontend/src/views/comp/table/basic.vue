<template>
  <n-card :bordered="false" class="proCard">
    <BasicTable
      title="表格列表"
      titleTooltip="这是一个提示"
      :columns="columns"
      :request="loadDataTable"
      :row-key="(row) => row.id"
      ref="actionRef"
      :actionColumn="actionColumn"
      :scroll-x="1360"
      @update:checked-row-keys="onCheckedRow"
    >
      <template #toolbar>
        <n-button type="primary" @click="reloadTable">刷新数据</n-button>
      </template>
    </BasicTable>
  </n-card>
</template>

<script lang="ts" setup>
  import { reactive, ref, h } from 'vue';
  import { BasicTable } from '@/components/Table';
  import { getTableList } from '@/api/table/list';
  import { columns } from './basicColumns';
  import { NButton, useDialog, useMessage } from 'naive-ui';

  const message = useMessage();
  const dialog = useDialog();
  const actionRef = ref();

  const params = reactive({
    pageSize: 5,
    name: 'xiaoMa',
  });

  const actionColumn = reactive({
    width: 150,
    title: '操作',
    key: 'action',
    fixed: 'right',
    align: 'center',
    render(record) {
      return h('div', { style: 'display:flex;gap:12px' }, [
        h(NButton, { text: true, type: 'primary', onClick: () => handleEdit(record) }, { default: () => '编辑' }),
        h(NButton, { text: true, type: 'error', onClick: () => handleDelete(record) }, { default: () => '删除' }),
      ]);
    },
  });

  const loadDataTable = async (res) => {
    return await getTableList({ ...params, ...res });
  };

  function onCheckedRow(rowKeys) {
    console.log(rowKeys);
  }

  function reloadTable() {
    actionRef.value.reload();
  }

  function handleDelete(record) {
    console.log(record);
    dialog.info({
      title: '提示',
      content: `您想删除${record.name}`,
      positiveText: '确定',
      negativeText: '取消',
      onPositiveClick: () => {
        message.success('删除成功');
      },
      onNegativeClick: () => {},
    });
  }

  function handleEdit(record) {
    console.log(record);
    message.success('您点击了编辑按钮');
  }
</script>

<style lang="less" scoped></style>
