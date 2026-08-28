<template>
  <div class="endpoint-management">
    <aside class="endpoint-tree-panel">
      <div class="tree-heading">
        <div><h3>接口目录</h3><p>项目名称固定，可在项目下管理模块与接口</p></div>
      </div>
      <n-spin :show="treeLoading">
        <div v-if="projects.length" class="tree-content">
          <section v-for="project in projects" :key="project.id" class="project-tree-group">
            <div class="tree-project-node" :class="{ active: selectedProjectId === project.id && !selectedModuleId }" @click="toggleProject(project)">
              <span class="tree-icon">▣</span><span class="tree-label">{{ project.name }}</span>
              <n-button text type="primary" size="tiny" @click.stop="openModuleModal(project.id)">＋ 模块</n-button>
            </div>
            <template v-if="expandedProjectIds.includes(project.id)">
              <div v-for="module in projectModules(project.id)" :key="module.id" class="tree-module-node" :class="{ active: selectedModuleId === module.id }" @click="selectModule(project, module)">
                <span class="tree-branch">└</span><span class="tree-icon">▱</span><span class="tree-label">{{ module.name }}</span><span class="tree-count">{{ module.endpoint_count || 0 }}</span>
                <n-button text type="primary" size="tiny" class="module-add-endpoint" @click.stop="addEndpointForModule(project.id, module.id)">＋ 接口</n-button>
                <n-dropdown trigger="click" placement="bottom-end" :options="moduleActionOptions" @select="(key) => handleModuleAction(key, module)">
                  <n-button text size="tiny" class="module-more" title="模块操作" @click.stop>•••</n-button>
                </n-dropdown>
              </div>
              <div v-if="!projectModules(project.id).length" class="tree-empty">暂无模块，请先添加模块</div>
            </template>
          </section>
        </div>
        <n-empty v-else description="暂无可访问项目" class="tree-empty-state" />
      </n-spin>
    </aside>

    <section class="endpoint-table-panel">
      <n-card :bordered="true" class="proCard endpoint-table-card">
        <header class="endpoint-list-header">
          <div class="list-title-block"><h3>{{ tableTitle }}</h3><span>共 {{ endpointTotal }} 个接口</span></div>
          <div class="list-primary-actions">
            <n-button @click="openRecording">接口录制</n-button>
            <n-button @click="openImport">Import</n-button>
            <n-button type="primary" :disabled="!selectedModuleId" @click="addData">添加接口</n-button>
          </div>
        </header>
        <div class="endpoint-list-toolbar">
          <n-input v-model:value="endpointSearch" clearable placeholder="搜索接口名称或路径" class="endpoint-search" @keyup.enter="applyEndpointFilters" @clear="applyEndpointFilters" />
          <n-select v-model:value="endpointMethod" :options="endpointMethodOptions" class="method-filter" @update:value="applyEndpointFilters" />
          <div class="selection-actions">
            <span>已选择 {{ checkedRowKeys.length }} 项</span>
            <n-button text type="primary" :disabled="!checkedRowKeys.length" @click="checkedRowKeys = []">清空选择</n-button>
          </div>
        </div>
        <BasicTable
          :columns="columns"
          :request="loadDataTable"
          :row-key="(row) => row.id"
          ref="actionRef"
          :actionColumn="actionColumn"
          :checked-row-keys="checkedRowKeys"
          :scroll-x="1300"
          @update:checked-row-keys="onCheckedRow"
        />
      </n-card>
    </section>

    <n-modal v-model:show="moduleModalVisible" preset="dialog" :title="editingModuleId ? '重命名模块' : '添加模块'" positive-text="确定" negative-text="取消" :positive-button-props="{ loading: moduleSaving }" @positive-click="saveModule">
      <n-form label-placement="top"><n-form-item label="模块名称" required><n-input v-model:value="moduleForm.name" placeholder="例如：订单管理" maxlength="64" /></n-form-item></n-form>
    </n-modal>

    <n-modal v-model:show="deleteModuleVisible" :mask-closable="false">
      <section class="delete-module-dialog">
        <header class="delete-dialog-header">
          <div><h3>删除模块</h3><p>确定删除模块「{{ deletingModule?.name }}」吗？</p></div>
          <n-button text class="dialog-close" @click="deleteModuleVisible = false">×</n-button>
        </header>
        <div class="delete-dialog-body">
          <div class="endpoint-risk-count">该模块下共有 <strong>{{ deletingModule?.endpoint_count || 0 }}</strong> 个接口。</div>
          <n-radio-group v-model:value="deleteMode" class="delete-mode-list">
            <label class="delete-mode-item" :class="{ selected: deleteMode === 'unassign' }">
              <n-radio value="unassign" />
              <span><strong>仅删除模块，接口移至未分组</strong><small>推荐选择，接口数据将保留，可稍后重新分配模块。</small></span>
            </label>
            <label class="delete-mode-item danger" :class="{ selected: deleteMode === 'cascade' }">
              <n-radio value="cascade" />
              <span><strong>删除模块及模块下全部接口</strong><small>接口及相关引用将被永久删除，此操作不可恢复。</small></span>
            </label>
          </n-radio-group>
          <div v-if="deleteMode === 'cascade'" class="danger-confirm-area">
            <span>请输入 <strong>确认删除</strong> 继续</span>
            <n-input v-model:value="deleteConfirmText" placeholder="确认删除" />
          </div>
        </div>
        <footer class="delete-dialog-footer">
          <n-button @click="deleteModuleVisible = false">取消</n-button>
          <n-button type="error" :loading="moduleDeleting" :disabled="deleteMode === 'cascade' && deleteConfirmText !== '确认删除'" @click="confirmDeleteModule">确认删除</n-button>
        </footer>
      </section>
    </n-modal>

    <n-modal v-model:show="importVisible" preset="card" title="导入 cURL" class="curl-import-modal" :style="{ width: 'min(1100px, calc(100vw - 48px))' }" :mask-closable="false">
      <div class="curl-import-layout">
        <section class="curl-source-panel">
          <div class="panel-heading">粘贴请求</div>
          <div class="panel-description">支持 Postman、浏览器开发者工具复制的 cURL。</div>
          <n-form label-placement="top" :model="importForm">
            <n-form-item label="所属项目" required>
              <n-select v-model:value="importForm.project" :options="projectOptions" placeholder="请选择接口所属项目" @update:value="handleImportProjectChange" />
            </n-form-item>
            <n-form-item label="所属模块" required>
              <n-select v-model:value="importForm.module" :options="importModuleOptions" :disabled="!importForm.project" placeholder="请选择模块" />
            </n-form-item>
            <n-form-item label="cURL 内容" required>
              <n-input v-model:value="importForm.curl" class="curl-textarea" type="textarea" :autosize="{ minRows: 13, maxRows: 18 }" :input-props="{ wrap: 'off', spellcheck: false }" placeholder="粘贴 Postman 或浏览器复制的 cURL 命令" />
            </n-form-item>
            <n-button type="primary" block @click="parseCurl">{{ importParsed ? '重新解析 cURL' : '解析 cURL' }}</n-button>
            <div class="curl-tip">将导入请求方法、地址、请求头和请求数据；Cookie 不会导入。</div>
          </n-form>
        </section>

        <section class="import-preview-panel">
          <div class="preview-heading">
            <div><div class="panel-heading">解析结果</div><div class="panel-description">确认后可直接保存为接口。</div></div>
            <span v-if="importParsed" class="parse-success">✓ 已解析</span>
          </div>
          <n-empty v-if="!importParsed" description="粘贴 cURL 并点击“解析 cURL”后，在此确认导入内容" class="parse-empty" />
          <template v-else>
            <n-form label-placement="top" :model="importForm">
              <div class="result-top-fields">
                <n-form-item label="接口名称"><n-input v-model:value="importForm.name" /></n-form-item>
                <n-form-item label="请求方法"><n-select v-model:value="importForm.method" :options="methodOptions" /></n-form-item>
              </div>
              <n-form-item label="接口地址"><n-input v-model:value="importForm.url" /></n-form-item>
              <n-form-item>
                <template #label>
                  <div class="header-field-label">
                    <span>请求头</span>
                    <n-button v-if="hasSensitiveHeaders" text type="primary" size="tiny" @click="sensitiveHeadersVisible = !sensitiveHeadersVisible">
                      {{ sensitiveHeadersVisible ? '隐藏敏感信息' : '显示敏感信息' }}
                    </n-button>
                  </div>
                </template>
                <n-input
                  v-if="sensitiveHeadersVisible || !hasSensitiveHeaders"
                  v-model:value="importForm.headersText"
                  type="textarea"
                  :autosize="{ minRows: 4, maxRows: 7 }"
                  placeholder="{}"
                />
                <n-input
                  v-else
                  :value="maskedHeadersText"
                  type="textarea"
                  readonly
                  :autosize="{ minRows: 4, maxRows: 7 }"
                  class="masked-header-editor"
                />
              </n-form-item>
              <n-form-item label="请求数据">
                <div class="request-data-editor">
                  <n-select v-model:value="importForm.bodyType" :options="bodyTypeOptions" class="body-type" />
                  <n-input v-model:value="importForm.bodyText" type="textarea" :autosize="{ minRows: 5, maxRows: 9 }" placeholder="{}" />
                </div>
              </n-form-item>
            </n-form>
            <n-alert type="warning" :show-icon="false">请求头可能包含 Authorization、Token 等敏感信息，请确认后再保存。</n-alert>
          </template>
        </section>
      </div>

      <template #footer>
        <n-space justify="end">
          <n-button @click="importVisible = false">取消</n-button>
          <n-button type="primary" :disabled="!importParsed" :loading="importing" @click="saveImportedEndpoint">保存接口</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script lang="ts" setup>
  import { computed, reactive, ref, h, onMounted } from 'vue';
  import { BasicTable } from '@/components/Table';
  import { createEndpointColumns } from './endpointColumns';
  import { NButton, useDialog, useMessage } from 'naive-ui';
  import { useRouter } from 'vue-router';
  import { EndpointAPI, EndpointModuleAPI } from '@/api/case_api/http';
  import { EnvironmentAPI, ProjectAPI } from '@/api/project/http';

  const message = useMessage();
  const dialog = useDialog();
  const actionRef = ref();
  const router = useRouter();
  const api = new EndpointAPI();
  const moduleApi = new EndpointModuleAPI();
  const projectApi = new ProjectAPI();
  const environmentApi = new EnvironmentAPI();
  const columns = createEndpointColumns((record) => handleEdit(record));
  const importVisible = ref(false);
  const importParsed = ref(false);
  const importing = ref(false);
  const sensitiveHeadersVisible = ref(false);
  const treeLoading = ref(false);
  const projects = ref<any[]>([]);
  const modules = ref<any[]>([]);
  const selectedProjectId = ref<number | null>(null);
  const selectedModuleId = ref<number | null>(null);
  const expandedProjectIds = ref<number[]>([]);
  const moduleModalVisible = ref(false);
  const moduleSaving = ref(false);
  const editingModuleId = ref<number | null>(null);
  const moduleForm = reactive({ project: null as number | null, name: '' });
  const deleteModuleVisible = ref(false);
  const moduleDeleting = ref(false);
  const deletingModule = ref<any>(null);
  const deleteMode = ref<'unassign' | 'cascade'>('unassign');
  const deleteConfirmText = ref('');
  const moduleActionOptions = [
    { label: '重命名模块', key: 'rename' },
    { label: '删除模块', key: 'delete', props: { style: 'color: #d03050;' } },
  ];
  const projectOptions = ref<any[]>([]);
  const environments = ref<any[]>([]);
  const methodOptions = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((value) => ({ label: value, value }));
  const endpointMethodOptions = [{ label: '所有方法', value: '' }, ...methodOptions];
  const endpointSearch = ref('');
  const endpointMethod = ref('');
  const checkedRowKeys = ref<number[]>([]);
  const endpointTotal = ref(0);
  const bodyTypeOptions = [{ label: 'JSON', value: 'json' }, { label: 'Data（表单）', value: 'data' }, { label: 'Params（查询）', value: 'params' }];
  const createImportForm = () => ({ project: null as number | null, module: null as number | null, curl: '', name: '', method: 'GET', url: '', originalUrl: '', headersText: '{}', bodyText: '{}', bodyType: 'json' as 'json' | 'data' | 'params' });
  const importForm = reactive(createImportForm());
  const sensitiveHeaderNames = new Set([
    'authorization', 'token', 'x-token', 'x-auth-token', 'access-token',
    'access_token', 'x-access-token', 'bearer-token', 'api-key', 'x-api-key',
  ]);
  const parsedImportHeaders = computed<Record<string, unknown>>(() => {
    try { return JSON.parse(importForm.headersText || '{}'); }
    catch { return {}; }
  });
  const hasSensitiveHeaders = computed(() => Object.keys(parsedImportHeaders.value).some((key) => sensitiveHeaderNames.has(key.trim().toLowerCase())));
  const maskedHeadersText = computed(() => JSON.stringify(
    Object.fromEntries(Object.entries(parsedImportHeaders.value).map(([key, value]) => [
      key,
      sensitiveHeaderNames.has(key.trim().toLowerCase()) && value ? '••••••••••••' : value,
    ])),
    null,
    2
  ));

  const importModuleOptions = computed(() => modules.value
    .filter((module) => module.project === importForm.project)
    .map((module) => ({ label: module.name, value: module.id })));
  const selectedProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value));
  const selectedModule = computed(() => modules.value.find((module) => module.id === selectedModuleId.value));
  const tableTitle = computed(() => {
    if (selectedModule.value) return `接口列表 · ${selectedProject.value?.name || ''} / ${selectedModule.value.name}`;
    return selectedProject.value ? `接口列表 · ${selectedProject.value.name}` : '接口列表';
  });

  const params = reactive({ pageSize: 10, name: 'xiaoMa' });
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
    const filter: Record<string, unknown> = { ...params, ...res };
    if (selectedProjectId.value) filter.project = selectedProjectId.value;
    if (typeof selectedModuleId.value === 'number') filter.module = selectedModuleId.value;
    if (endpointSearch.value.trim()) filter.search = endpointSearch.value.trim();
    if (endpointMethod.value) filter.method = endpointMethod.value;
    const result: any = await api.getDataList(filter);
    endpointTotal.value = Number(result?.itemCount ?? result?.total ?? result?.count ?? (Array.isArray(result) ? result.length : result?.list?.length || 0));
    return result;
  };
  function onCheckedRow(rowKeys) { checkedRowKeys.value = rowKeys as number[]; }
  function reloadTable() { actionRef.value?.reload(); }
  function applyEndpointFilters() { checkedRowKeys.value = []; reloadTable(); }
  function handleDelete(record) {
    dialog.info({
      title: '提示', content: `您想删除【${record.name}】`, positiveText: '确定', negativeText: '取消',
      onPositiveClick: async () => { await api.DeleteDataByID(record.id); message.success('删除成功'); reloadTable(); },
    });
  }
  function handleEdit(record) { router.push({ name: 'case_api_endpoint_edit', params: { id: record.id } }); }
  function addData() {
    if (!selectedProjectId.value || typeof selectedModuleId.value !== 'number') {
      message.info('请先在左侧选择一个模块。');
      return;
    }
    addEndpointForModule(selectedProjectId.value, selectedModuleId.value);
  }

  function addEndpointForModule(projectId: number, moduleId: number) {
    router.push({ name: 'case_api_endpoint_edit', params: { id: 0 }, query: { project: projectId, module: moduleId } });
  }

  function openRecording() {
    const query: Record<string, string> = {};
    if (selectedProjectId.value) query.project = String(selectedProjectId.value);
    if (typeof selectedModuleId.value === 'number') query.module = String(selectedModuleId.value);
    router.push({ name: 'case_api_recording', query });
  }

  function projectModules(projectId: number) {
    return modules.value.filter((module) => module.project === projectId);
  }

  function toggleProject(project: any) {
    selectedProjectId.value = project.id;
    selectedModuleId.value = null;
    expandedProjectIds.value = expandedProjectIds.value.includes(project.id)
      ? expandedProjectIds.value.filter((projectId) => projectId !== project.id)
      : [...expandedProjectIds.value, project.id];
    reloadTable();
  }

  function selectModule(project: any, module: any) {
    selectedProjectId.value = project.id;
    selectedModuleId.value = module.id;
    reloadTable();
  }

  function openModuleModal(projectId: number) {
    editingModuleId.value = null;
    moduleForm.project = projectId;
    moduleForm.name = '';
    moduleModalVisible.value = true;
  }

  function handleModuleAction(key: string, module: any) {
    if (key === 'rename') {
      editingModuleId.value = module.id;
      moduleForm.project = module.project;
      moduleForm.name = module.name;
      moduleModalVisible.value = true;
      return;
    }
    if (key === 'delete') {
      deletingModule.value = module;
      deleteMode.value = 'unassign';
      deleteConfirmText.value = '';
      deleteModuleVisible.value = true;
    }
  }

  async function saveModule() {
    if (!moduleForm.project || !moduleForm.name.trim()) {
      message.error('请输入模块名称。');
      return false;
    }
    try {
      moduleSaving.value = true;
      const module = editingModuleId.value
        ? await moduleApi.update(editingModuleId.value, { project: moduleForm.project, name: moduleForm.name.trim() })
        : await moduleApi.createData({ project: moduleForm.project, name: moduleForm.name.trim() });
      await loadTree();
      const created = modules.value.find((item) => item.id === module.id) || module;
      selectModule(projects.value.find((item) => item.id === moduleForm.project), created);
      message.success(editingModuleId.value ? '模块名称已更新。' : '模块添加成功。');
      return true;
    } catch (error: any) {
      message.error(error.message || '模块添加失败。');
      return false;
    } finally {
      moduleSaving.value = false;
    }
  }

  async function confirmDeleteModule() {
    const module = deletingModule.value;
    if (!module?.id) return;
    if (deleteMode.value === 'cascade' && deleteConfirmText.value !== '确认删除') {
      message.warning('请输入“确认删除”。');
      return;
    }
    try {
      moduleDeleting.value = true;
      const result = await moduleApi.deleteModule(module.id, deleteMode.value === 'cascade');
      if (selectedModuleId.value === module.id) {
        selectedModuleId.value = null;
        selectedProjectId.value = module.project;
      }
      deleteModuleVisible.value = false;
      await loadTree();
      reloadTable();
      message.success(result?.detail || (deleteMode.value === 'cascade' ? '模块及接口已删除。' : '模块已删除，接口已移至未分组。'));
    } catch (error: any) {
      message.error(error.message || '模块删除失败。');
    } finally {
      moduleDeleting.value = false;
    }
  }

  async function openImport() {
    Object.assign(importForm, createImportForm(), {
      project: selectedProjectId.value,
      module: typeof selectedModuleId.value === 'number' ? selectedModuleId.value : null,
    });
    importParsed.value = false;
    sensitiveHeadersVisible.value = false;
    importVisible.value = true;
    const environmentList = await environmentApi.getDataList({});
    projectOptions.value = projects.value.map((project: any) => ({ label: project.name, value: project.id }));
    environments.value = environmentList;
  }

  function handleImportProjectChange() {
    importForm.module = null;
    applyImportedUrl();
  }

  function shellTokens(command: string) {
    const tokens: string[] = [];
    let current = '';
    let quote = '';
    for (let index = 0; index < command.length; index += 1) {
      const char = command[index];
      if (char === '\\' && quote !== "'") {
        if (index + 1 < command.length) current += command[++index];
      } else if (char === "'" || char === '"') {
        if (!quote) quote = char;
        else if (quote === char) quote = '';
        else current += char;
      } else if (/\s/.test(char) && !quote) {
        if (current) { tokens.push(current); current = ''; }
      } else current += char;
    }
    if (current) tokens.push(current);
    return tokens;
  }

  function toObject(value: string, fieldName: string) {
    try {
      const result = value.trim() ? JSON.parse(value) : {};
      if (!result || Array.isArray(result) || typeof result !== 'object') throw new Error();
      return result;
    } catch { throw new Error(`${fieldName}不是合法的 JSON 对象`); }
  }

  function applyImportedUrl() {
    if (!importForm.originalUrl) return;
    try {
      const importedUrl = new URL(importForm.originalUrl);
      const candidates = environments.value
        .filter((environment: any) => environment.project === importForm.project && environment.base_url)
        .sort((left: any, right: any) => right.base_url.length - left.base_url.length);
      const matched = candidates.find((environment: any) => {
        const base = environment.base_url.replace(/\/$/, '');
        return importedUrl.href === base || importedUrl.href.startsWith(`${base}/`);
      });
      importForm.url = matched ? `${importedUrl.pathname}${importedUrl.search}` : importedUrl.href;
    } catch { importForm.url = importForm.originalUrl; }
  }

  function parseCurl() {
    try {
      const tokens = shellTokens(importForm.curl.replace(/\\\r?\n/g, ' ').trim());
      if (!tokens.length || tokens[0].toLowerCase() !== 'curl') throw new Error('请输入以 curl 开头的命令');
      const headers: Record<string, string> = {};
      const dataParts: string[] = [];
      let method = '';
      let rawUrl = '';
      const valueOptions = new Set(['-X', '--request', '-H', '--header', '-d', '--data', '--data-raw', '--data-binary', '--data-ascii', '--data-urlencode', '-b', '--cookie', '-u', '--user', '--url']);
      for (let index = 1; index < tokens.length; index += 1) {
        const token = tokens[index];
        const equalsAt = token.indexOf('=');
        const option = equalsAt > 0 ? token.slice(0, equalsAt) : token;
        const inlineValue = equalsAt > 0 ? token.slice(equalsAt + 1) : undefined;
        const value = inlineValue === undefined && valueOptions.has(option) ? tokens[++index] : inlineValue;
        if (option === '-X' || option === '--request') method = (value || '').toUpperCase();
        else if (option === '-H' || option === '--header') {
          const separator = (value || '').indexOf(':');
          if (separator > 0) headers[(value || '').slice(0, separator).trim()] = (value || '').slice(separator + 1).trim();
        } else if (['-d', '--data', '--data-raw', '--data-binary', '--data-ascii', '--data-urlencode'].includes(option)) dataParts.push(value || '');
        else if (option === '--url') rawUrl = value || rawUrl;
        else if (!token.startsWith('-') && !rawUrl) rawUrl = token;
      }
      if (!rawUrl) throw new Error('未识别到请求 URL');
      const parsedUrl = new URL(rawUrl);
      const bodyText = dataParts.join('&');
      const queryParams: Record<string, unknown> = {};
      parsedUrl.searchParams.forEach((value, key) => {
        queryParams[key] = key in queryParams ? ([] as string[]).concat(queryParams[key] as any, value) : value;
      });
      // 查询参数独立保存到 Params；接口地址只保留路径，避免执行时重复拼接 ?a=1&a=1。
      parsedUrl.search = '';
      const contentType = Object.entries(headers).find(([key]) => key.toLowerCase() === 'content-type')?.[1]?.toLowerCase() || '';
      let bodyType: 'json' | 'data' | 'params' = contentType.includes('application/x-www-form-urlencoded') ? 'data' : 'json';
      let body: Record<string, unknown> = {};
      if (bodyText) {
        try { body = toObject(bodyText, '请求数据'); bodyType = 'json'; }
        catch { body = Object.fromEntries(new URLSearchParams(bodyText).entries()); bodyType = contentType.includes('application/json') ? 'json' : 'data'; }
      }
      importForm.method = method || (bodyText ? 'POST' : 'GET');
      importForm.originalUrl = parsedUrl.href;
      importForm.name = decodeURIComponent(parsedUrl.pathname.split('/').filter(Boolean).pop() || parsedUrl.hostname);
      importForm.headersText = JSON.stringify(headers, null, 2);
      // 解析后默认隐藏 Authorization、Token 等认证值；真实值仍保存在
      // headersText 中，仅在用户主动点击“显示敏感信息”时展示。
      sensitiveHeadersVisible.value = false;
      importForm.bodyType = bodyType;
      importForm.bodyText = JSON.stringify(body, null, 2);
      if (!bodyText && Object.keys(queryParams).length) {
        importForm.bodyType = 'params';
        importForm.bodyText = JSON.stringify(queryParams, null, 2);
      }
      applyImportedUrl();
      importParsed.value = true;
      message.success('cURL 解析成功，请确认结果后保存');
    } catch (error: any) {
      importParsed.value = false;
      message.error(error.message || 'cURL 解析失败');
    }
  }

  async function saveImportedEndpoint() {
    if (!importForm.project || !importForm.module || !importForm.name.trim() || !importForm.url.trim()) { message.error('请补充项目、模块、接口名称和接口地址'); return; }
    try {
      importing.value = true;
      const body = toObject(importForm.bodyText, '请求数据');
      await api.createData({
        project: importForm.project, module: importForm.module, name: importForm.name.trim(), method: importForm.method, url: importForm.url.trim(), headers: toObject(importForm.headersText, '请求头'),
        params: importForm.bodyType === 'params' ? body : {}, data: importForm.bodyType === 'data' ? body : {}, json: importForm.bodyType === 'json' ? body : {}, cookies: {},
      } as any);
      message.success('接口导入成功');
      importVisible.value = false;
      reloadTable();
    } catch (error: any) { message.error(error.message || '接口导入失败'); }
    finally { importing.value = false; }
  }

  async function loadTree() {
    try {
      treeLoading.value = true;
      const [projectData, moduleData] = await Promise.all([
        projectApi.getDataList({ pageSize: 999 }),
        moduleApi.getDataList({ pageSize: 999 }),
      ]);
      const asList = (data: any) => Array.isArray(data) ? data : data?.list || data?.results || [];
      projects.value = asList(projectData);
      modules.value = asList(moduleData);
      if (!selectedProjectId.value && projects.value.length) selectedProjectId.value = projects.value[0].id;
    } finally {
      treeLoading.value = false;
    }
  }

  onMounted(async () => {
    await loadTree();
    reloadTable();
  });
</script>

<style lang="less" scoped>
  .endpoint-management { display: grid; grid-template-columns: 248px minmax(0, 1fr); align-items: start; gap: 16px; }
  .endpoint-tree-panel { min-height: 520px; overflow: hidden; border: 1px solid #e5eaf1; border-radius: 8px; background: #fff; }
  .tree-heading { padding: 17px 16px 13px; border-bottom: 1px solid #edf1f5; }
  .tree-heading h3 { margin: 0; color: #26344a; font-size: 16px; font-weight: 600; }
  .tree-heading p { margin: 6px 0 0; color: #94a0b1; font-size: 12px; line-height: 1.5; }
  .tree-content { padding: 10px 8px 14px; }
  .project-tree-group + .project-tree-group { margin-top: 8px; }
  .tree-project-node, .tree-module-node { display: flex; align-items: center; min-height: 36px; gap: 6px; padding: 0 8px; border-radius: 5px; cursor: pointer; }
  .tree-project-node { color: #334155; font-size: 13px; font-weight: 600; background: #f7faff; }
  .tree-module-node { margin-left: 15px; color: #536276; font-size: 13px; }
  .tree-project-node:hover, .tree-module-node:hover { background: #f4f8fc; }
  .tree-project-node.active, .tree-module-node.active { color: #2578dc; background: #eaf3ff; }
  .tree-icon, .tree-branch { width: 15px; color: #8da0b7; text-align: center; font-size: 14px; }
  .tree-label { overflow: hidden; flex: 1; text-overflow: ellipsis; white-space: nowrap; }
  .tree-count { min-width: 16px; color: #9ba8b9; font-size: 11px; text-align: center; }
  .module-add-endpoint { white-space: nowrap; }
  .module-more { width: 24px; min-width: 24px; color: #8593a6; letter-spacing: -1px; }
  .module-more:hover { color: #256fd1; }
  .tree-empty { margin: 6px 10px 6px 39px; color: #a2adbb; font-size: 12px; }
  .tree-empty-state { padding: 76px 0; }
  .endpoint-table-panel { min-width: 0; }
  .endpoint-table-card { min-height: 520px; overflow: hidden; }
  .endpoint-list-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: -4px -4px 0; padding: 4px 4px 16px; border-bottom: 1px solid #edf1f5; }
  .list-title-block { display: flex; align-items: baseline; gap: 10px; min-width: 0; }
  .list-title-block h3 { overflow: hidden; margin: 0; color: #26344a; font-size: 16px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
  .list-title-block span { flex: 0 0 auto; color: #95a1b1; font-size: 12px; }
  .list-primary-actions { display: flex; align-items: center; gap: 9px; flex: 0 0 auto; }
  .endpoint-list-toolbar { display: flex; align-items: center; gap: 10px; padding: 14px 0 12px; }
  .endpoint-search { width: min(360px, 45%); }
  .method-filter { width: 138px; }
  .selection-actions { display: flex; align-items: center; gap: 10px; margin-left: auto; color: #8a96a7; font-size: 12px; }
  .endpoint-table-card :deep(.table-toolbar) { display: none; }
  .endpoint-table-card :deep(.n-data-table) { border: 1px solid #e5eaf1; border-radius: 7px; overflow: hidden; }
  .endpoint-table-card :deep(.n-data-table-th) { height: 44px; color: #536174; background: #f7f9fc; font-size: 12px; font-weight: 600; }
  .endpoint-table-card :deep(.n-data-table-td) { height: 52px; border-color: #edf1f5; }
  .endpoint-table-card :deep(.endpoint-name-link) { max-width: 100%; overflow: hidden; padding: 0; border: 0; color: #246fd1; background: transparent; font: inherit; font-size: 14px; font-weight: 550; text-align: left; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }
  .endpoint-table-card :deep(.endpoint-name-link:hover) { color: #1757a6; text-decoration: underline; text-underline-offset: 3px; }
  .endpoint-table-card :deep(.endpoint-name-link:focus-visible) { border-radius: 3px; outline: 2px solid rgba(37, 111, 209, .28); outline-offset: 2px; }
  :global(.curl-import-modal.n-card) { max-height: calc(100vh - 48px); overflow: auto; }
  .curl-import-layout { display: grid; grid-template-columns: minmax(340px, .9fr) minmax(420px, 1.1fr); margin: -12px -16px; }
  .curl-source-panel { padding: 20px 22px 22px; border-right: 1px solid #e8ecf1; background: #fafbfd; }
  .import-preview-panel { min-width: 0; padding: 20px 22px 22px; }
  .panel-heading { color: #303844; font-size: 16px; font-weight: 600; }
  .panel-description { margin-top: 5px; color: #8b95a7; font-size: 12px; }
  .preview-heading { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
  .result-top-fields { display: grid; grid-template-columns: minmax(0, 1fr) 132px; gap: 14px; }
  .parse-success { color: #3c9a5f; font-size: 12px; }
  .parse-empty { padding: 105px 0; }
  .curl-tip { margin-top: 10px; color: #8b95a7; font-size: 12px; line-height: 1.55; }
  .curl-textarea :deep(textarea) { overflow-x: auto !important; overflow-wrap: normal; white-space: pre; word-break: normal; }
  .curl-textarea :deep(.n-input-wrapper) { overflow: hidden; }
  .request-data-editor { display: grid; grid-template-columns: 132px minmax(0, 1fr); width: 100%; gap: 10px; }
  .body-type { width: 132px; }
  .header-field-label { display: flex; align-items: center; justify-content: space-between; width: 100%; gap: 12px; }
  .masked-header-editor :deep(textarea) { color: #6f7d90; letter-spacing: .02em; }
  .delete-module-dialog { width: min(520px, calc(100vw - 32px)); overflow: hidden; border-radius: 8px; background: #fff; box-shadow: 0 18px 50px rgba(30, 43, 63, .2); }
  .delete-dialog-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 20px 22px 16px; border-bottom: 1px solid #edf0f4; }
  .delete-dialog-header h3 { margin: 0; color: #202b3c; font-size: 18px; font-weight: 650; }
  .delete-dialog-header p { margin: 7px 0 0; color: #5f6c7e; font-size: 13px; }
  .dialog-close { width: 28px; color: #7c8796; font-size: 22px; line-height: 1; }
  .delete-dialog-body { padding: 18px 22px 20px; }
  .endpoint-risk-count { padding: 11px 13px; border: 1px solid #f1d49a; border-radius: 6px; color: #76551c; background: #fffaf0; font-size: 13px; }
  .endpoint-risk-count strong { color: #a86500; }
  .delete-mode-list { display: grid; gap: 10px; width: 100%; margin-top: 14px; }
  .delete-mode-item { display: flex; align-items: flex-start; gap: 10px; padding: 13px; border: 1px solid #e2e7ee; border-radius: 7px; cursor: pointer; transition: border-color .16s, background .16s; }
  .delete-mode-item:hover, .delete-mode-item.selected { border-color: #91baf0; background: #f7fbff; }
  .delete-mode-item.danger:hover, .delete-mode-item.danger.selected { border-color: #efb3b9; background: #fff8f8; }
  .delete-mode-item > span { display: grid; gap: 4px; }
  .delete-mode-item strong { color: #303b4b; font-size: 13px; font-weight: 600; }
  .delete-mode-item small { color: #8995a5; font-size: 12px; line-height: 1.5; }
  .delete-mode-item.danger strong { color: #c13f4b; }
  .danger-confirm-area { display: grid; gap: 7px; margin-top: 12px; padding: 12px 13px; border-radius: 6px; background: #fff2f3; color: #b83b46; font-size: 12px; }
  .delete-dialog-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 14px 22px; border-top: 1px solid #edf0f4; background: #fafbfc; }
  @media (max-width: 760px) {
    .endpoint-management { grid-template-columns: 1fr; }
    .endpoint-tree-panel { min-height: auto; }
    .curl-import-layout { grid-template-columns: 1fr; }
    .curl-source-panel { border-right: 0; border-bottom: 1px solid #e8ecf1; }
    .result-top-fields { grid-template-columns: 1fr; gap: 0; }
    .endpoint-list-header, .endpoint-list-toolbar { align-items: stretch; flex-direction: column; }
    .list-primary-actions { flex-wrap: wrap; }
    .endpoint-search, .method-filter { width: 100%; }
    .selection-actions { margin-left: 0; }
  }
</style>
