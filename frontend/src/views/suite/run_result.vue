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
    />
  </n-card>
</template>

<script lang="ts" setup>
  import { reactive, ref, h, onActivated, onMounted, nextTick } from 'vue';
  import { BasicTable } from '@/components/Table';
  import { NButton, useDialog, useMessage } from 'naive-ui';
  import { useRouter } from 'vue-router';
  import { RunResultAPI } from '@/api/suite/http';
  import { columns } from './resultColumns';

  const message = useMessage();
  const dialog = useDialog();
  const actionRef = ref();
  const router = useRouter();

  const api = new RunResultAPI();

  const actionColumn = reactive({
    width: 240,
    title: '操作',
    key: 'action',
    fixed: 'right',
    align: 'center',
    render(record) {
      const actions: any[] = [];
      if (!record.is_pass) {
        actions.push(
          h(
            NButton,
            { text: true, type: 'primary', onClick: () => handleRetry(record) },
            { default: () => '重试' }
          )
        );
      }
      actions.push(
        h(
          NButton,
          {
            text: true,
            type: 'primary',
            onClick: () => router.push({ name: 'suite_report', params: { id: record.id } }),
          },
          { default: () => '查看报告' }
        )
      );
      actions.push(
        h(
          NButton,
          { text: true, type: 'error', onClick: () => handleDelete(record) },
          { default: () => '删除' }
        )
      );
      return h('div', { style: 'display:flex;gap:12px' }, actions);
    },
  });

  function handleRetry(record) {
    dialog.info({
      title: '提示',
      content: `是否重新执行【${record.suite_name}】的测试用例`,
      positiveText: '确定',
      negativeText: '取消',
      onPositiveClick: async () => {
        const resp = await api.retryById(record.id);
        message.success(`已重新提交原执行记录，执行编号: ${resp.result_id}`);
        reloadTable();
      },
      onNegativeClick: () => {},
    });
  }

  const loadDataTable = async (res) => {
    return await api.getDataList({ ...res, _t: Date.now() });
  };

  const refreshWhenVisible = async () => {
    await nextTick();
    actionRef.value?.reload?.();
  };

  // 本页面由多标签/keep-alive 缓存。每次重新进入执行报告时主动请求第一页，
  // 否则 BasicTable 会继续展示上次离开页面时缓存的列表数据。
  onMounted(refreshWhenVisible);
  onActivated(refreshWhenVisible);

  function onCheckedRow(rowKeys) {
    console.log(rowKeys);
  }

  function reloadTable() {
    actionRef.value.reload();
  }

  function handleDelete(record) {
    dialog.info({
      title: '提示',
      content: `您想删除【${record.suite_name}】的执行记录（执行编号: ${record.id}）`,
      positiveText: '确定',
      negativeText: '取消',
      onPositiveClick: async () => {
        await api.DeleteDataByID(record.id); // 调用删除接口
        message.success('删除成功'); // 提示操作成功
        reloadTable(); // 自动刷新表格
      },
      onNegativeClick: () => {},
    });
  }

  function addData() {
    router.push({ name: 'suite_suite_edit', params: { id: 0 } });
  }
</script>

<style lang="less" scoped></style>
