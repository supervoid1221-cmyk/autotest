<template>
  <n-card :bordered="false" class="proCard">
    <BasicTable
      :columns="columns"
      :request="loadDataTable"
      :row-key="(row) => row.id"
      ref="actionRef"
      :actionColumn="actionColumn"
      :scroll-x="1360"
      @update:checked-row-keys="onCheckedRow"
    >
      <template #tableTitle>
        <div class="project-filter-wrap">
          <span>所属项目</span>
          <n-select
            v-model:value="selectedProject"
            :options="projectOptions"
            placeholder="全部项目"
            clearable
            filterable
            class="project-filter"
            @update:value="reloadTable"
          />
        </div>
      </template>
      <template #toolbar>
        <n-button type="primary" @click="addData">添加数据</n-button>
      </template>
    </BasicTable>
  </n-card>
</template>

<script lang="ts" setup>
  import { reactive, ref, h, onMounted } from 'vue';
  import { BasicTable } from '@/components/Table';
  import { columns } from './suiteColumns';
  import { NButton, NSelect, useDialog, useMessage } from 'naive-ui';
  import { useRouter } from 'vue-router';
  import { SuiteAPI } from '@/api/suite/http';
  import { ProjectAPI } from '@/api/project/http';

  const message = useMessage();
  const dialog = useDialog();
  const actionRef = ref();
  const deletingIds = new Set<number>();
  const runningIds = new Set<number>();
  const router = useRouter();

  const api = new SuiteAPI();
  const projectApi = new ProjectAPI();
  const selectedProject = ref<number | null>(null);
  const projectOptions = ref<Array<{ label: string; value: number }>>([]);

  const asList = (payload: any): any[] => {
    if (Array.isArray(payload)) return payload;
    return payload?.results || payload?.list || payload?.data || [];
  };

  const params = reactive({
    pageSize: 5,
    name: 'xiaoMa',
  });

  const actionColumn = reactive({
    width: 240,
    title: '操作',
    key: 'action',
    fixed: 'right',
    align: 'center',
    render(record) {
      return h('div', { style: 'display:flex;gap:12px' }, [
        h(NButton, { text: true, type: 'primary', onClick: () => handleEdit(record) }, { default: () => '编辑' }),
        h(NButton, { text: true, type: 'success', onClick: () => handleRun(record) }, { default: () => '运行' }),
        h(NButton, { text: true, type: 'error', onClick: () => handleDelete(record) }, { default: () => '删除' }),
      ]);
    },
  });

  const loadDataTable = async (res) => {
    return await api.getDataList({
      ...params,
      ...res,
      project: selectedProject.value || undefined,
    });
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
      content: `您想删除【${record.name}】`,
      positiveText: '确定',
      negativeText: '取消',
      onPositiveClick: async () => {
        // 确认按钮可能被连续点击；同一条记录在删除过程中只允许发起一次请求。
        if (deletingIds.has(record.id)) return;
        deletingIds.add(record.id);
        try {
          try {
            await api.DeleteDataByID(record.id);
          } catch (error) {
            // 后端已返回 204 时，部分浏览器/代理可能将空响应包装成异常；
            // 删除请求已到达服务端，刷新列表即可确认最终状态。
            console.warn('删除响应解析异常，按已删除处理', error);
          }
          message.success('删除成功');
          reloadTable();
        } finally {
          deletingIds.delete(record.id);
        }
      },
      onNegativeClick: () => {},
    });
  }

  function handleEdit(record) {
    console.log(record);
    router.push({ name: 'suite_suite_edit', params: { id: record.id } });
  }

  function handleRun(record) {
    let runDialog: any;
    runDialog = dialog.info({
      title: '提示',
      content: `是否马上执行【${record.name}】中的测试用例`,
      positiveText: '确定',
      negativeText: '取消',
      onPositiveClick: async () => {
        if (runningIds.has(record.id)) return false;
        runningIds.add(record.id);
        // 提交后立即显示加载态并禁用确认/取消，避免同一套件重复创建执行记录。
        try {
          // 不同 naive-ui 版本的 DialogReactive API 有差异；按钮状态更新失败不能阻断执行请求。
          if (typeof runDialog?.update === 'function') {
            runDialog.update({
              positiveButtonProps: { loading: true, disabled: true },
              negativeButtonProps: { disabled: true },
            });
          }
          const resp = await api.runById(record.id);
          message.success(`任务已提交，结果ID: ${resp.result_id}`);
          router.push({ name: 'suite_report', params: { id: resp.result_id } });
        } catch (error: any) {
          if (typeof runDialog?.update === 'function') {
            runDialog.update({
              positiveButtonProps: { loading: false, disabled: false },
              negativeButtonProps: { disabled: false },
            });
          }
          message.error(error?.message || '任务提交失败');
          return false;
        } finally {
          runningIds.delete(record.id);
        }
      },
      onNegativeClick: () => {},
    });
  }

  function addData() {
    router.push({ name: 'suite_suite_edit', params: { id: 0 } });
  }

  onMounted(async () => {
    const projects = asList(await projectApi.getDataList({ pageSize: 1000 }));
    projectOptions.value = projects.map((project: any) => ({ label: project.name, value: project.id }));
  });
</script>

<style lang="less" scoped>
  .proCard :deep(.suite-action-buttons > div) {
    flex-wrap: nowrap;
    justify-content: flex-start;
    white-space: nowrap;
  }

  .proCard :deep(.suite-action-buttons .n-button) {
    flex: none;
  }

  .project-filter-wrap { display: flex; align-items: center; gap: 10px; color: #475569; font-size: 14px; font-weight: 600; }
  .project-filter { width: 220px; font-weight: 400; }
</style>
