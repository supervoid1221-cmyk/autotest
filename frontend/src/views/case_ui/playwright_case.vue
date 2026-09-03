<template>
  <n-card class="proCard" title="Playwright 智能 UI 用例">
    <template #header-extra><n-space><n-button @click="recordingVisible = true">录制用例</n-button><n-button type="primary" @click="router.push({ name: 'case_ui_playwright_case_edit', params: { id: 0 } })">新建智能用例</n-button></n-space></template>
    <BasicTable ref="tableRef" :columns="columns" :request="load" :row-key="(row) => row.id">
      <template #tableTitle>
        <div class="list-filter-bar">
          <span>名称</span>
          <n-input v-model:value="searchName" clearable placeholder="请输入用例名称" class="name-filter" @keyup.enter="reloadTable" @clear="reloadTable" />
          <span>所属项目</span>
          <n-select v-model:value="selectedProject" :options="projectOptions" clearable filterable placeholder="全部项目" class="project-filter" @update:value="reloadTable" />
          <n-button type="primary" secondary @click="reloadTable">查询</n-button>
        </div>
      </template>
    </BasicTable>
    <n-modal
      v-model:show="recordingVisible"
      preset="card"
      title="导入 UI 录制"
      class="recording-modal"
      :style="{ width: 'min(1100px, calc(100vw - 48px))' }"
      :mask-closable="false"
    >
      <div class="recording-modal-body">
        <n-alert type="info" :bordered="false">在 Chrome 扩展管理页重新加载前端 recorder-extension，然后在 DevTools 的“自动化录制器”中可直接生成用例。也可将扩展下载的 JSON 粘贴到下方导入。</n-alert>
        <n-form label-placement="top" class="recording-form">
          <div class="recording-grid"><n-form-item label="所属项目"><n-select v-model:value="recordingForm.project" :options="projectOptions" :loading="projectLoading" filterable clearable placeholder="请选择项目" /></n-form-item><n-form-item label="用例名称"><n-input v-model:value="recordingForm.name" /></n-form-item><n-form-item label="执行环境"><n-select v-model:value="recordingForm.environment_name" :options="environmentOptions" :loading="environmentLoading" :disabled="!recordingForm.project" clearable placeholder="请先选择项目" /></n-form-item></div>
          <n-form-item label="录制 JSON"><n-input v-model:value="recordingText" type="textarea" :autosize="{ minRows: 7, maxRows: 11 }" placeholder="粘贴 { &quot;events&quot;: [...] }" /></n-form-item>
          <n-form-item v-if="codePreview" label="Playwright Python 代码预览"><pre class="code-preview">{{ codePreview }}</pre></n-form-item>
        </n-form>
      </div>
      <template #footer><n-space justify="end"><n-button @click="previewRecording">预览步骤</n-button><n-button type="primary" :loading="importing" @click="importRecording">生成智能用例</n-button></n-space></template>
    </n-modal>
  </n-card>
</template>
<script lang="ts" setup>
import { h, onMounted, reactive, ref, watch } from 'vue';
import { NButton, NTag, useDialog, useMessage } from 'naive-ui';
import { useRouter } from 'vue-router';
import { BasicTable } from '@/components/Table';
import { PlaywrightCaseAPI } from '@/api/case_ui/http';
import { EnvironmentAPI, ProjectAPI } from '@/api/project/http';
const router = useRouter(); const message = useMessage(); const dialog = useDialog(); const api = new PlaywrightCaseAPI();
const projectApi = new ProjectAPI(); const environmentApi = new EnvironmentAPI(); const recordingVisible = ref(false); const recordingText = ref(''); const codePreview = ref(''); const importing = ref(false); const projectOptions = ref<any[]>([]); const environmentOptions = ref<any[]>([]); const projectLoading = ref(false); const environmentLoading = ref(false);
const tableRef = ref<any>();
const searchName = ref('');
const selectedProject = ref<number | null>(null);
const recordingForm = reactive<{ project: number | null; name: string; environment_name: string | null }>({ project: null, name: '录制的智能 UI 用例', environment_name: null });
const listOf = (value: any): any[] => { if (Array.isArray(value)) return value; for (const key of ['list', 'items', 'results', 'data', 'result']) { const nested = value?.[key]; if (nested !== undefined && nested !== value) { const list = listOf(nested); if (list.length) return list; } } return []; };
function recordingEvents() { const value = JSON.parse(recordingText.value || '{}'); if (!Array.isArray(value.events)) throw new Error('录制 JSON 中缺少 events 数组'); return value.events; }
async function previewRecording() { try { const result = await api.previewRecording(recordingEvents()); codePreview.value = result.code || ''; message.success(`已识别 ${result.steps?.length || 0} 个步骤`); } catch (error: any) { message.error(error?.message || '录制数据解析失败'); } }
async function importRecording() { if (!recordingForm.project) return message.error('请选择所属项目'); try { importing.value = true; const result = await api.importRecording({ ...recordingForm, events: recordingEvents() }); message.success('智能 UI 用例已生成'); recordingVisible.value = false; router.push({ name: 'case_ui_playwright_case_edit', params: { id: result.id } }); } catch (error: any) { message.error(error?.message || '生成用例失败'); } finally { importing.value = false; } }
async function loadProjects() { projectLoading.value = true; try { projectOptions.value = listOf(await projectApi.getDataList({ page: 1, pageSize: 1000 })).map((item: any) => ({ label: item.name, value: Number(item.id) })).filter((item: any) => item.value); } catch (error: any) { projectOptions.value = []; message.error(error?.message || '项目列表加载失败'); } finally { projectLoading.value = false; } }
async function loadEnvironments(projectId: number | null) { environmentOptions.value = []; if (!projectId) return; environmentLoading.value = true; try { const environments = listOf(await environmentApi.getDataList({ project: projectId, page: 1, pageSize: 1000 })).filter((item: any) => Number(item.project) === Number(projectId)); const names = ['Dev', 'Test', 'Pre', 'Prod']; environmentOptions.value = environments.sort((a: any, b: any) => { const ai = names.indexOf(a.name); const bi = names.indexOf(b.name); return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi); }).map((item: any) => ({ label: item.name, value: item.name })); } catch (error: any) { environmentOptions.value = []; message.error(error?.message || '执行环境加载失败'); } finally { environmentLoading.value = false; } }
watch(() => recordingForm.project, async (projectId) => { recordingForm.environment_name = null; await loadEnvironments(projectId); });
watch(recordingVisible, (visible) => { if (visible && !projectOptions.value.length) loadProjects(); });
onMounted(loadProjects);
const columns = [
  { title: '用例名称', key: 'name', width: 220 }, { title: '所属项目', key: 'project_name', width: 160 },
  { title: '浏览器', key: 'browser', width: 110 }, { title: '运行模式', key: 'run_mode', width: 110, render: (r: any) => r.run_mode === 'headed' ? '有界面' : '无头' },
  { title: '步骤数', key: 'step_count', width: 80 }, { title: '创建人', key: 'creator_name', width: 120, render: (r: any) => r.creator_name || '-' }, { title: '状态', key: 'enabled', width: 90, render: (r: any) => h(NTag, { type: r.enabled ? 'success' : 'default', bordered: false }, { default: () => r.enabled ? '已启用' : '已停用' }) },
  { title: '操作', key: 'action', width: 220, render: (r: any) => h('div', { style: 'display:flex;gap:12px' }, [
    h(NButton, { text: true, type: 'primary', onClick: () => router.push({ name: 'case_ui_playwright_case_edit', params: { id: r.id } }) }, { default: () => '编辑' }),
    h(NButton, { text: true, type: 'success', onClick: async () => { try { const result = await api.run(r.id); message.success(result?.passed ? '执行成功' : '执行失败'); } catch {} } }, { default: () => '运行' }),
    h(NButton, { text: true, type: 'error', onClick: () => dialog.warning({ title: '删除智能用例', content: `确认删除「${r.name}」？`, positiveText: '删除', negativeText: '取消', onPositiveClick: async () => { await api.DeleteDataByID(r.id); await tableRef.value?.removeRowByKey(r.id); message.success('删除成功'); } }) }, { default: () => '删除' }),
  ]) },
];
const load = (params: any) => api.getDataList({ ...params, name: searchName.value.trim() || undefined, project: selectedProject.value || undefined });
function reloadTable() { tableRef.value?.reload?.(); }
</script>
<style scoped>
:global(.recording-modal.n-card){max-height:calc(100vh - 48px);overflow:auto}.recording-modal-body{min-height:460px}.recording-form{margin-top:16px}.recording-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.recording-grid :deep(.n-form-item){margin:0}.code-preview{width:100%;max-height:220px;overflow:auto;margin:0;padding:14px;border-radius:8px;color:#dbe7ff;background:#1f2937;font:12px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace}.proCard :deep(.table-toolbar-left){min-width:0;flex:0 1 auto}.proCard :deep(.table-toolbar-right){flex:none;margin-left:auto}.list-filter-bar{display:flex;flex-wrap:nowrap;align-items:center;gap:10px;color:#475569;font-size:14px;font-weight:600;white-space:nowrap}.name-filter,.project-filter{width:220px;font-weight:400}@media(max-width:1100px){.proCard :deep(.table-toolbar){align-items:flex-start;flex-direction:column;gap:12px}.proCard :deep(.table-toolbar-right){width:100%;margin-left:0}.list-filter-bar{flex-wrap:wrap}}@media(max-width:760px){.recording-modal-body{min-height:0}.recording-grid{grid-template-columns:1fr}}
</style>
