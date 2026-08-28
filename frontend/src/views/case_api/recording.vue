<template>
  <div class="recording-page">
    <header class="recording-header">
      <div><h2>接口录制</h2><p>导入 Chrome DevTools 录制数据或 HAR 文件，确认后批量保存为接口或业务场景。</p></div>
      <div class="header-actions"><n-button @click="downloadExtensionGuide">下载录制插件</n-button><n-button type="primary" @click="parseInput">解析录制数据</n-button></div>
    </header>

    <n-card class="source-card" :bordered="false">
      <div class="source-grid">
        <n-form-item label="所属项目" required><n-select v-model:value="form.project" :options="projectOptions" placeholder="选择项目" @update:value="loadModules" /></n-form-item>
        <n-form-item label="保存模块" required><n-select v-model:value="form.module" :options="moduleOptions" :disabled="!form.project" placeholder="选择模块" /></n-form-item>
        <n-form-item label="重复接口处理"><n-select v-model:value="form.conflict_mode" :options="conflictOptions" /></n-form-item>
      </div>
      <div class="import-row">
        <n-input v-model:value="rawInput" type="textarea" :autosize="{ minRows: 4, maxRows: 7 }" placeholder="粘贴录制插件导出的 JSON 或 HAR 内容。插件推送至当前页面后也会自动填入。" />
        <div class="import-actions"><input ref="fileInput" type="file" accept=".har,.json,application/json" hidden @change="readHarFile" /><n-button @click="fileInput?.click()">导入 HAR</n-button><n-button :disabled="!rawInput" @click="rawInput = ''">清空</n-button></div>
      </div>
    </n-card>

    <n-card class="record-list-card" :bordered="false">
      <template #header><span class="card-title">录制请求</span><span class="record-count">已解析 {{ records.length }} 条，已选择 {{ selectedCount }} 条</span></template>
      <template #header-extra><div class="table-actions"><n-input v-model:value="keyword" size="small" clearable placeholder="搜索名称或路径" /><n-select v-model:value="methodFilter" size="small" :options="methodOptions" class="method-filter" /><n-button size="small" @click="toggleVisible(true)">全选</n-button><n-button size="small" @click="toggleVisible(false)">清空选择</n-button></div></template>
      <n-data-table :columns="columns" :data="filteredRecords" :row-key="(row: RecordedRequest) => row.record_id" :checked-row-keys="selectedKeys" :pagination="false" @update:checked-row-keys="updateSelection" />
      <n-empty v-if="!records.length" description="暂无录制数据。请粘贴插件导出的数据或导入 HAR 文件。" class="record-empty" />
    </n-card>

    <n-card class="save-card" :bordered="false">
      <div class="save-actions">
        <n-checkbox v-model:checked="form.create_scenario">同时生成场景</n-checkbox>
        <n-input v-if="form.create_scenario" v-model:value="form.scenario_name" placeholder="场景名称" class="scenario-name" />
        <n-checkbox v-model:checked="form.apply_assertions">应用建议的状态码断言</n-checkbox>
        <span class="save-tip">认证头中的 Token、Cookie、密码等敏感信息已遮罩；认证建议由项目“环境与认证”统一维护。</span>
        <n-button :disabled="!records.length" @click="exportHar">导出 HAR</n-button>
        <n-button type="primary" :loading="saving" :disabled="!selectedCount" @click="saveRecords">保存{{ form.create_scenario ? '并生成场景' : '接口' }}</n-button>
      </div>
    </n-card>
  </div>
</template>

<script lang="ts" setup>
  import { computed, h, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
  import { NButton, NTag, useMessage } from 'naive-ui';
  import { useRoute } from 'vue-router';
  import { EndpointModuleAPI, RecordedRequest, RecordingAPI } from '@/api/case_api/http';
  import { ProjectAPI } from '@/api/project/http';

  defineOptions({ name: 'case_api_recording' });
  const message = useMessage();
  const route = useRoute();
  const recordingApi = new RecordingAPI();
  const projectApi = new ProjectAPI();
  const moduleApi = new EndpointModuleAPI();
  const fileInput = ref<HTMLInputElement | null>(null);
  const rawInput = ref(''); const records = ref<RecordedRequest[]>([]); const keyword = ref(''); const methodFilter = ref('all'); const saving = ref(false);
  const projectOptions = ref<any[]>([]); const moduleOptions = ref<any[]>([]);
  function asList(payload: any) { return Array.isArray(payload) ? payload : payload?.list || payload?.results || payload?.data || []; }
  const form = reactive({ project: null as number | null, module: null as number | null, conflict_mode: 'skip', create_scenario: false, scenario_name: '录制场景', apply_assertions: true });
  const conflictOptions = [{ label: '忽略已存在接口', value: 'skip' }, { label: '覆盖已存在接口', value: 'overwrite' }, { label: '创建接口副本', value: 'copy' }];
  const methodOptions = [{ label: '全部方法', value: 'all' }, ...['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((value) => ({ label: value, value }))];
  const methodType = (method: string) => ({ GET: 'info', POST: 'success', PUT: 'warning', PATCH: 'warning', DELETE: 'error' }[method] || 'default') as any;
  const filteredRecords = computed(() => records.value.filter((item) => (methodFilter.value === 'all' || item.method === methodFilter.value) && (!keyword.value.trim() || `${item.name} ${item.url}`.toLowerCase().includes(keyword.value.trim().toLowerCase()))));
  const selectedKeys = computed(() => records.value.filter((item) => item.selected).map((item) => item.record_id));
  const selectedCount = computed(() => selectedKeys.value.length);
  const columns = [
    { type: 'selection' as const },
    { title: '接口名称', key: 'name', minWidth: 150, ellipsis: { tooltip: true } },
    { title: '方法', key: 'method', width: 92, render: (row: RecordedRequest) => h(NTag, { size: 'small', type: methodType(row.method), bordered: false }, { default: () => row.method }) },
    { title: '路径', key: 'url', minWidth: 260, ellipsis: { tooltip: true }, render: (row: RecordedRequest) => h('code', { class: 'record-url' }, row.url) },
    { title: '状态', key: 'status_code', width: 84, render: (row: RecordedRequest) => row.status_code || '-' },
    { title: '耗时', key: 'duration_ms', width: 84, render: (row: RecordedRequest) => row.duration_ms ? `${row.duration_ms} ms` : '-' },
    { title: '提示', key: 'auth_suggestion', minWidth: 190, ellipsis: { tooltip: true }, render: (row: RecordedRequest) => row.auth_suggestion || '—' },
    { title: '操作', key: 'action', width: 70, render: (row: RecordedRequest) => h(NButton, { text: true, type: 'error', onClick: () => records.value = records.value.filter((item) => item.record_id !== row.record_id) }, { default: () => '移除' }) },
  ];
  const queryNumber = (value: unknown) => {
    const parsed = Number(Array.isArray(value) ? value[0] : value);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  };
  async function loadProjects() { projectOptions.value = asList(await projectApi.getDataList({ pageSize: 999 })).map((item: any) => ({ label: item.name, value: item.id })); }
  async function loadModules(resetModule = true) {
    if (resetModule) form.module = null;
    moduleOptions.value = asList(await moduleApi.getDataList({ project: form.project, pageSize: 999 })).map((item: any) => ({ label: item.name, value: item.id }));
    if (!moduleOptions.value.some((item) => item.value === form.module)) form.module = null;
  }
  async function parseInput() { try { const parsed = JSON.parse(rawInput.value); const result = await recordingApi.parse(Array.isArray(parsed) ? { records: parsed } : parsed); records.value = result.records || []; message.success(`已解析 ${records.value.length} 条请求`); } catch { message.error('录制内容不是合法 JSON / HAR 文件。'); } }
  function updateSelection(keys: Array<string | number>) { const selected = new Set(keys.map(String)); records.value.forEach((item) => item.selected = selected.has(item.record_id)); }
  function toggleVisible(selected: boolean) { const visible = new Set(filteredRecords.value.map((item) => item.record_id)); records.value.forEach((item) => { if (visible.has(item.record_id)) item.selected = selected; }); }
  function readHarFile(event: Event) { const file = (event.target as HTMLInputElement).files?.[0]; if (!file) return; const reader = new FileReader(); reader.onload = () => { rawInput.value = String(reader.result || ''); parseInput(); }; reader.readAsText(file); }
  function exportHar() { const content = JSON.stringify({ log: { version: '1.2', creator: { name: 'Automation Test Platform', version: '1.0' }, entries: records.value.map((item) => ({ request: { method: item.method, url: item.original_url || item.url, headers: Object.entries(item.headers || {}).map(([name, value]) => ({ name, value })) }, response: { status: item.status_code, content: { text: item.response_preview || '' } }, time: item.duration_ms })) } }, null, 2); const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([content], { type: 'application/json' })); link.download = 'api-recording.har'; link.click(); URL.revokeObjectURL(link.href); }
  async function saveRecords() { if (!form.project || !form.module) return message.error('请选择项目和保存模块。'); try { saving.value = true; const data = await recordingApi.importRecords({ ...form, records: records.value.map((item) => ({ ...item, recommended_assertions: form.apply_assertions ? item.recommended_assertions : {} })) }); message.success(`已新增 ${data.created} 个、更新 ${data.updated} 个接口${data.skipped ? `，跳过 ${data.skipped} 个` : ''}`); if (data.scenario_id) message.success('场景已生成，可前往场景管理继续编排。'); } finally { saving.value = false; } }
  function receiveExtension(event: MessageEvent) { if (event.data?.type !== 'AUTOTEST_RECORDER_EXPORT') return; rawInput.value = JSON.stringify({ records: event.data.records || [] }); parseInput(); }
  function downloadExtensionGuide() { message.info('录制插件位于前端项目的 recorder-extension 目录，请在 Chrome 扩展程序中开启开发者模式后加载该目录。'); }
  onMounted(async () => {
    await loadProjects();
    const project = queryNumber(route.query.project);
    const module = queryNumber(route.query.module);
    if (project && projectOptions.value.some((item) => item.value === project)) {
      form.project = project;
      form.module = module;
      await loadModules(false);
    }
    window.addEventListener('message', receiveExtension);
  }); onBeforeUnmount(() => window.removeEventListener('message', receiveExtension));
</script>

<style lang="less" scoped>
  .recording-page { max-width: 1320px; margin: 18px auto 32px; } .recording-header { display:flex; align-items:flex-start; justify-content:space-between; gap:20px; margin-bottom:16px; } .recording-header h2 { margin:0; color:#1f2937; font-size:22px; } .recording-header p { margin:6px 0 0; color:#8491a3; font-size:13px; } .header-actions,.import-actions,.table-actions,.save-actions { display:flex; align-items:center; gap:10px; } .source-card,.record-list-card,.save-card { margin-bottom:16px; border:1px solid #e6ebf2; box-shadow:0 2px 8px rgb(31 45 61 / 4%); } .source-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; } .source-grid :deep(.n-form-item) { margin:0; } .import-row { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:12px; margin-top:16px; } .import-actions { align-items:flex-start; } .card-title { font-size:16px; font-weight:700; color:#263244; } .record-count { margin-left:10px; color:#7c8797; font-size:12px; } .table-actions :deep(.n-input) { width:190px; } .method-filter { width:120px; } .record-empty { padding:56px 0; } .record-url { color:#536276; font-size:12px; } .save-actions { flex-wrap:wrap; justify-content:flex-end; } .scenario-name { width:200px; } .save-tip { flex:1; min-width:260px; color:#8a96a6; font-size:12px; } @media (max-width:800px) { .recording-header,.import-row { display:block; } .header-actions,.import-actions { margin-top:12px; } .source-grid { grid-template-columns:1fr; } .table-actions { flex-wrap:wrap; } }
</style>
