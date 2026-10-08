<template>
  <n-card :bordered="false" class="proCard">
    <BasicTable
      :columns="columns"
      :request="loadDataTable"
      :row-key="(row) => row.id"
      ref="actionRef"
      :actionColumn="actionColumn"
      :scroll-x="1480"
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
            @update:value="handleProjectChange"
          />
          <span>执行环境</span>
          <n-select
            v-model:value="selectedEnvironment"
            :options="environmentOptions"
            placeholder="全部环境"
            clearable
            filterable
            class="environment-filter"
            @update:value="reloadTable"
          />
        </div>
      </template>
    </BasicTable>
  </n-card>
</template>

<script lang="ts" setup>
import { asList } from '@/utils/list';

  import { computed, reactive, ref, h, onActivated, onMounted, nextTick } from 'vue';
  import { BasicTable } from '@/components/Table';
  import { NButton, NSelect, useDialog, useMessage } from 'naive-ui';
  import { useRouter } from 'vue-router';
  import { RunResultAPI } from '@/api/suite/http';
  import { EnvironmentAPI, ProjectAPI } from '@/api/project/http';
  import { columns } from './resultColumns';

  const message = useMessage();
  const dialog = useDialog();
  const actionRef = ref();
  const router = useRouter();

  const api = new RunResultAPI();
  const projectApi = new ProjectAPI();
  const environmentApi = new EnvironmentAPI();
  const selectedProject = ref<number | null>(null);
  const selectedEnvironment = ref<string | null>(null);
  const projectOptions = ref<Array<{ label: string; value: number }>>([]);
  const environments = ref<any[]>([]);
  const environmentOptions = computed(() => {
    const names = environments.value
      .filter((environment) => !selectedProject.value || Number(environment.project) === selectedProject.value)
      .map((environment) => String(environment.name || '').trim())
      .filter(Boolean);
    return Array.from(new Set(names)).map((name) => ({ label: name, value: name }));
  });

  

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
            onClick: () => router.push({ name: 'execution_report', params: { sourceType: 'suite', id: record.id } }),
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
    return await api.getDataList({
      ...res,
      project: selectedProject.value || undefined,
      environment: selectedEnvironment.value || undefined,
      _t: Date.now(),
    });
  };

  const refreshWhenVisible = async () => {
    await nextTick();
    actionRef.value?.reload?.();
  };

  // 本页面由多标签/keep-alive 缓存。每次重新进入执行报告时主动请求第一页，
  // 否则 BasicTable 会继续展示上次离开页面时缓存的列表数据。
  onMounted(async () => {
    const [projectPayload, environmentPayload] = await Promise.all([
      projectApi.getDataList({ pageSize: 1000 }),
      environmentApi.getDataList({ pageSize: 1000 }),
    ]);
    const projects = asList(projectPayload);
    projectOptions.value = projects.map((project: any) => ({ label: project.name, value: project.id }));
    environments.value = asList(environmentPayload);
    await refreshWhenVisible();
  });
  onActivated(refreshWhenVisible);

  function onCheckedRow(rowKeys) {
    console.log(rowKeys);
  }

  function reloadTable() {
    actionRef.value.reload();
  }

  function handleProjectChange() {
    if (selectedEnvironment.value && !environmentOptions.value.some((item) => item.value === selectedEnvironment.value)) {
      selectedEnvironment.value = null;
    }
    reloadTable();
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

<style lang="less" scoped>
  .project-filter-wrap { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; color: #475569; font-size: 14px; font-weight: 600; }
  .project-filter { width: 220px; font-weight: 400; }
  .environment-filter { width: 220px; font-weight: 400; }
</style>
