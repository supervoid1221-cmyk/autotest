<template>
  <n-card class="proCard" title="Playwright 智能 UI 用例">
    <template #header-extra><n-button type="primary" @click="router.push({ name: 'case_ui_playwright_case_edit', params: { id: 0 } })">新建智能用例</n-button></template>
    <BasicTable :columns="columns" :request="load" :row-key="(row) => row.id" />
  </n-card>
</template>
<script lang="ts" setup>
import { h } from 'vue';
import { NButton, NTag, useDialog, useMessage } from 'naive-ui';
import { useRouter } from 'vue-router';
import { BasicTable } from '@/components/Table';
import { PlaywrightCaseAPI } from '@/api/case_ui/http';
const router = useRouter(); const message = useMessage(); const dialog = useDialog(); const api = new PlaywrightCaseAPI();
const columns = [
  { title: '用例名称', key: 'name', width: 220 }, { title: '所属项目', key: 'project_name', width: 160 },
  { title: '浏览器', key: 'browser', width: 110 }, { title: '运行模式', key: 'run_mode', width: 110, render: (r: any) => r.run_mode === 'headed' ? '有界面' : '无头' },
  { title: '步骤数', key: 'step_count', width: 80 }, { title: '创建人', key: 'creator_name', width: 120, render: (r: any) => r.creator_name || '-' }, { title: '状态', key: 'enabled', width: 90, render: (r: any) => h(NTag, { type: r.enabled ? 'success' : 'default', bordered: false }, { default: () => r.enabled ? '已启用' : '已停用' }) },
  { title: '操作', key: 'action', width: 220, render: (r: any) => h('div', { style: 'display:flex;gap:12px' }, [
    h(NButton, { text: true, type: 'primary', onClick: () => router.push({ name: 'case_ui_playwright_case_edit', params: { id: r.id } }) }, { default: () => '编辑' }),
    h(NButton, { text: true, type: 'success', onClick: async () => { try { const result = await api.run(r.id); message.success(result?.passed ? '执行成功' : '执行失败'); } catch {} } }, { default: () => '运行' }),
    h(NButton, { text: true, type: 'error', onClick: () => dialog.warning({ title: '删除智能用例', content: `确认删除「${r.name}」？`, positiveText: '删除', negativeText: '取消', onPositiveClick: async () => { await api.DeleteDataByID(r.id); message.success('删除成功'); location.reload(); } }) }, { default: () => '删除' }),
  ]) },
];
const load = (params: any) => api.getDataList(params);
</script>
