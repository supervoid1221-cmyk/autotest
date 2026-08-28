<template>
  <div class="endpoint-page">
    <div class="endpoint-page-inner">
      <div class="page-toolbar">
        <div class="breadcrumb-row"
          ><span>接口测试</span><i>/</i><span>接口管理</span><i>/</i><b>接口详情</b></div
        >
        <div class="page-actions">
          <n-button @click="back">返回</n-button>
          <n-button
            class="save-button"
            :loading="submitMode === 'save'"
            :disabled="submitMode !== null"
            @click="formSubmit(false)"
            >保存</n-button
          >
        </div>
      </div>

      <n-form
        :model="formValue"
        :rules="rules"
        label-placement="left"
        :show-require-mark="false"
        ref="formRef"
        class="endpoint-form"
      >
        <section class="basic-card">
          <h2>基本信息</h2>
          <div class="basic-grid">
            <n-form-item label="接口名称" path="name"
              ><n-input v-model:value="formValue.name" size="small" placeholder="请输入接口名称"
            /></n-form-item>
            <n-form-item label="关联项目" path="project"
              ><n-select
                v-model:value="formValue.project"
                size="small"
                :options="project_list"
                @update:value="handleProjectChange"
            /></n-form-item>
            <n-form-item label="所属模块" path="module"
              ><n-select
                v-model:value="formValue.module"
                size="small"
                :options="module_list"
                :disabled="!formValue.project"
                placeholder="请先选择项目"
            /></n-form-item>
          </div>
        </section>

        <div class="endpoint-workspace">
          <main class="workspace-main">
            <section class="request-card">
              <div class="request-card-head">
                <h2>请求配置</h2>
                <n-button
                  type="primary"
                  class="request-debug-button"
                  :loading="submitMode === 'debug'"
                  :disabled="submitMode !== null"
                  @click="formSubmit(true)"
                >
                  <template #icon><PhPlay :size="16" weight="fill" /></template>
                  调试
                </n-button>
              </div>
              <div class="request-target">
                <n-form-item path="url" :show-label="false">
                  <div class="request-core-input">
                    <n-select
                      v-model:value="formValue.method"
                      size="small"
                      :options="methodOptions"
                      class="request-method-select"
                    />
                    <n-input
                      v-model:value="formValue.url"
                      size="small"
                      placeholder="例如 /api/v2/login"
                    />
                  </div>
                </n-form-item>
              </div>
              <div class="request-tabs">
                <button
                  v-for="tab in requestTabs"
                  :key="tab.value"
                  type="button"
                  :class="{ active: requestTab === tab.value }"
                  @click="selectRequestTab(tab.value)"
                >
                  <component :is="tab.icon" :size="18" /><span>{{ tab.label }}</span
                  ><b v-if="typeof tab.count === 'number'">{{ tab.count }}</b>
                </button>
              </div>

              <template v-if="requestTab !== 'files'">
                <div class="editor-toolbar">
                  <div v-if="requestTab === 'body'" class="body-kind-tabs">
                    <button
                      type="button"
                      :class="{ active: bodyType === 'json' }"
                      @click="bodyType = 'json'"
                      >JSON</button
                    >
                    <button
                      type="button"
                      :class="{ active: bodyType === 'data' }"
                      @click="bodyType = 'data'"
                      >Data</button
                    >
                    <button
                      type="button"
                      :class="{ active: bodyType === 'files' }"
                      @click="
                        bodyType = 'files';
                        requestTab = 'files';
                      "
                      >Form-data</button
                    >
                  </div>
                  <strong v-else>{{ requestTab === 'headers' ? 'Headers' : 'Params' }}</strong>
                  <div class="editor-actions"
                    ><n-button text size="small" @click="formatActiveJson">✨ 格式化</n-button></div
                  >
                </div>
                <div class="json-editor">
                  <pre class="editor-gutter">{{ activeEditorLineNumbers }}</pre>
                  <n-input
                    :value="activeEditorText"
                    type="textarea"
                    :autosize="{ minRows: 7, maxRows: 14 }"
                    :placeholder="activeEditorPlaceholder"
                    @update:value="updateActiveEditor"
                  />
                </div>
                <div class="editor-note"
                  ><span>i</span>支持静态值、项目变量和环境变量；优先使用
                  <code>${变量名}</code></div
                >
              </template>

              <section v-else class="files-panel">
                <div class="files-panel-head"
                  ><div
                    ><strong>Form-data 文件</strong
                    ><p>文本字段与文件会以 multipart/form-data 发送</p></div
                  ><n-upload :show-file-list="false" :custom-request="uploadEndpointFile"
                    ><n-button type="primary" secondary>选择并上传文件</n-button></n-upload
                  ></div
                >
                <n-empty
                  v-if="!fileEntries.length"
                  size="small"
                  description="暂无文件，可上传一个或多个文件"
                  class="file-empty"
                />
                <div
                  v-for="(entry, index) in fileEntries"
                  :key="`${entry.path}-${index}`"
                  class="file-entry"
                >
                  <n-input
                    v-model:value="entry.field"
                    size="small"
                    placeholder="文件字段名，如 file"
                  /><span class="file-name" :title="entry.name">{{ entry.name }}</span
                  ><span class="file-size">{{ formatFileSize(entry.size) }}</span
                  ><n-button text type="error" size="small" @click="fileEntries.splice(index, 1)"
                    >删除</n-button
                  >
                </div>
              </section>
            </section>

            <section class="data-drive-card">
              <div class="data-drive-title"
                ><div><h2>数据驱动</h2><p>每行数据独立执行并生成单独结果</p></div
                ><n-switch v-model:value="dataDrivenEnabled"
              /></div>
              <div v-if="dataDrivenEnabled" class="data-drive-content">
                <label class="data-drive-field-label"
                  ><span>字段名（英文逗号分隔）</span
                  ><n-input
                    v-model:value="dataDriveFieldsText"
                    size="small"
                    placeholder="email, password, expectedCode"
                    @blur="syncDataDriveFields"
                /></label>
                <div v-if="dataDriveFields.length" class="data-drive-table-wrap">
                  <div class="data-drive-table">
                    <div class="data-drive-row data-drive-header" :style="dataDriveGridStyle"
                      ><span>#</span
                      ><span v-for="field in dataDriveFields" :key="field">{{ field }}</span
                      ><span>操作</span></div
                    >
                    <div
                      v-for="(row, rowIndex) in dataDriveRows"
                      :key="rowIndex"
                      class="data-drive-row"
                      :style="dataDriveGridStyle"
                      ><span class="data-drive-index">{{ rowIndex + 1 }}</span
                      ><n-input
                        v-for="(_, columnIndex) in dataDriveFields"
                        :key="columnIndex"
                        v-model:value="row[columnIndex]"
                        size="small"
                        :placeholder="dataDriveFields[columnIndex]"
                      /><div class="data-drive-actions"
                        ><n-button
                          text
                          type="primary"
                          size="small"
                          @click="copyDataDriveRow(rowIndex)"
                          >复制</n-button
                        ><n-button
                          text
                          type="error"
                          size="small"
                          @click="dataDriveRows.splice(rowIndex, 1)"
                          >删除</n-button
                        ></div
                      ></div
                    >
                  </div>
                  <n-button dashed block class="add-data-row" @click="addDataDriveRow"
                    >＋ 添加一行数据</n-button
                  >
                </div>
                <n-alert v-else type="warning" :show-icon="false" class="data-drive-warning"
                  >请先输入字段名，多个字段使用英文逗号分隔。</n-alert
                >
              </div>
            </section>
          </main>

          <aside class="workspace-sidebar">
            <section class="side-card"
              ><h2>请求概览</h2
              ><div class="overview-list"
                ><div
                  ><span><PhStack /> Headers</span><b>{{ requestCount('headers') }}</b></div
                ><div
                  ><span><PhQuestion /> Params</span><b>{{ requestCount('params') }}</b></div
                ><div
                  ><span><PhBracketsCurly /> JSON</span><b>{{ requestCount('json') }}</b></div
                ><div
                  ><span><PhPaperclip /> Files</span><b>{{ fileEntries.length }}</b></div
                ></div
              ></section
            >
            <section class="side-card variables-card"
              ><h2>可用变量</h2
              ><div class="variable-list"
                ><div><code>${token}</code><span>环境 Token</span></div
                ><div v-for="variable in projectVariables" :key="variable.id || variable.name"
                  ><code>{{ variableReference(variable.name) }}</code
                  ><span>项目参数</span></div
                ></div
              ><p>在请求中使用 <code>${变量名}</code> 引用变量值，运行时自动替换。</p></section
            >
          </aside>
        </div>
      </n-form>

      <n-modal
        v-model:show="debugDialogVisible"
        preset="card"
        title="接口调试结果"
        class="endpoint-debug-modal"
        style="width: 720px; max-width: calc(100vw - 48px); margin: 0 auto"
        :mask-closable="!debugRunning"
      >
        <div class="debug-toolbar">
          <div>
            <span>执行环境</span>
            <n-select
              v-model:value="debugEnvironmentId"
              :options="debugEnvironmentOptions"
              :disabled="debugRunning"
              placeholder="请选择执行环境"
            />
          </div>
          <n-button
            type="primary"
            :loading="debugRunning"
            :disabled="!debugEnvironmentId"
            @click="executeDebug"
            >重新执行</n-button
          >
        </div>

        <n-spin :show="debugRunning">
          <div v-if="debugResult" class="debug-result">
            <div class="debug-summary">
              <n-tag :type="debugResult.passed ? 'success' : 'error'" :bordered="false">
                {{ debugResult.passed ? '执行成功' : '执行失败' }}
              </n-tag>
              <span>环境：{{ debugResult.environment || debugEnvironmentName }}</span>
              <span>状态码：{{ debugResult.status_code ?? '—' }}</span>
              <span>耗时：{{ debugResult.duration_ms ?? 0 }} ms</span>
              <span v-if="debugResult.attempts">请求次数：{{ debugResult.attempts }}</span>
            </div>
            <n-alert
              v-if="debugResult.errors?.length"
              type="error"
              :show-icon="true"
              class="debug-errors"
            >
              <div v-for="(error, index) in debugResult.errors" :key="index">{{ error }}</div>
            </n-alert>
            <section class="debug-response">
              <h3>响应正文</h3>
              <pre>{{ debugResult.response_body || '（无响应正文）' }}</pre>
            </section>
          </div>
          <n-empty v-else-if="!debugRunning" description="暂无执行结果" />
        </n-spin>
      </n-modal>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref, reactive, onMounted } from 'vue';
  import { FormRules, useMessage } from 'naive-ui';
  import { useRoute, useRouter } from 'vue-router';
  import { PhBracketsCurly, PhPaperclip, PhPlay, PhQuestion, PhStack } from '@phosphor-icons/vue';
  import { useSubmitRedirect } from '@/hooks/web/useSubmitRedirect';
  import { EnvironmentAPI, ProjectAPI, ProjectVariableAPI } from '@/api/project/http';
  import { Environment, ProjectVariable } from '@/api/project/models';
  import { EndpointAPI, EndpointModuleAPI } from '@/api/case_api/http';
  import { Endpoint, EndpointRunResult, UploadedEndpointFile } from '@/api/case_api/models';

  const route = useRoute();
  const router = useRouter();
  const { redirectAfterSubmit } = useSubmitRedirect();

  // 路由未携带 id 或携带非法值时按新增接口处理，避免请求 /endpoint/NaN/。
  const routeId = Number(route.params.id);
  const dataID = Number.isInteger(routeId) && routeId > 0 ? routeId : 0;
  const endpointId = ref(dataID);

  const api = new EndpointAPI();
  const moduleApi = new EndpointModuleAPI();
  const project_api = new ProjectAPI();
  const projectVariableApi = new ProjectVariableAPI();
  const environmentApi = new EnvironmentAPI();

  const formRef: any = ref(null);
  const message = useMessage();
  type RequestTab = 'headers' | 'params' | 'body' | 'files';
  type JsonField = 'headers' | 'params' | 'data' | 'json';
  const requestTab = ref<RequestTab>('body');
  const bodyType = ref<'json' | 'data' | 'files'>('json');
  const submitMode = ref<'save' | 'debug' | null>(null);
  const debugDialogVisible = ref(false);
  const debugRunning = ref(false);
  const debugEnvironmentId = ref<number | null>(null);
  const debugEnvironmentOptions = ref<Array<{ label: string; value: number }>>([]);
  const debugEnvironments = ref<Environment[]>([]);
  const debugResult = ref<EndpointRunResult | null>(null);
  const debugEnvironmentName = computed(
    () => debugEnvironments.value.find((item) => item.id === debugEnvironmentId.value)?.name || '—'
  );
  const methodOptions = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((value) => ({
    label: value,
    value,
  }));

  const rules: FormRules = {
    project: {
      required: true,
      type: 'number',
      message: '请选择项目',
      trigger: 'blur',
    },
    module: {
      required: true,
      type: 'number',
      message: '请选择所属模块',
      trigger: 'blur',
    },
    name: {
      required: true,
      message: '请选择输入接口名称',
      trigger: 'blur',
    },
    method: {
      required: true,
      message: '请选择输入请求方法',
      trigger: 'blur',
    },
    url: {
      required: true,
      message: '请选择输入接口地址',
      trigger: 'blur',
    },
    test_headers: {
      trigger: 'input',
      validator(rule: unknown, value: string) {
        if (value.length >= 5) return new Error('最多输入四个字符');
        return true;
      },
    },
  };

  function createDefaultValue() {
    return {
      id: -1,
      project: null,
      module: null,
      name: '',
      method: 'GET',
      url: '',
      headers: {},
      params: {},
      data: {},
      json: {},
      files: {},
      parametrize: [],
    };
  }

  const project_list = ref<any[]>([]);
  const module_list = ref<any[]>([]);
  const projectVariables = ref<ProjectVariable[]>([]);
  const formValue = reactive(createDefaultValue());
  const fileEntries = ref<Array<UploadedEndpointFile & { field: string }>>([]);
  const dataDrivenEnabled = ref(false);
  const dataDriveFieldsText = ref('');
  const dataDriveFields = ref<string[]>([]);
  const dataDriveRows = ref<string[][]>([]);
  const dataDriveGridStyle = computed(() => ({
    gridTemplateColumns: `42px repeat(${Math.max(
      dataDriveFields.value.length,
      1
    )}, minmax(130px, 1fr)) 104px`,
  }));
  const jsonText = reactive({
    headers: '{}',
    params: '{}',
    data: '{}',
    json: '{}',
  });
  const requestCount = (field: JsonField) => Object.keys(formValue[field] || {}).length;
  const requestTabs = computed(() => [
    { value: 'headers' as const, label: 'Headers', icon: PhStack, count: requestCount('headers') },
    { value: 'params' as const, label: 'Params', icon: PhQuestion, count: requestCount('params') },
    { value: 'body' as const, label: 'Body', icon: PhBracketsCurly },
    { value: 'files' as const, label: 'Files', icon: PhPaperclip, count: fileEntries.value.length },
  ]);
  const activeEditorField = computed<JsonField>(() =>
    requestTab.value === 'headers'
      ? 'headers'
      : requestTab.value === 'params'
      ? 'params'
      : bodyType.value === 'data'
      ? 'data'
      : 'json'
  );
  const activeEditorText = computed(() => jsonText[activeEditorField.value]);
  const activeEditorLineNumbers = computed(() =>
    Array.from(
      { length: Math.max(activeEditorText.value.split('\n').length, 1) },
      (_, index) => index + 1
    ).join('\n')
  );
  const activeEditorPlaceholder = computed(() =>
    activeEditorField.value === 'headers'
      ? '{\n  "Authorization": "Bearer ${token}"\n}'
      : activeEditorField.value === 'params'
      ? '{\n  "page": 1,\n  "pageSize": 20\n}'
      : activeEditorField.value === 'data'
      ? '{\n  "name": "demo"\n}'
      : '{\n  "email": "admin@example.com"\n}'
  );

  function normalizeEndpoint(data?: Partial<Endpoint>) {
    const defaults = createDefaultValue();
    return {
      ...defaults,
      ...data,
      headers: data?.headers || defaults.headers,
      params: data?.params || defaults.params,
      data: data?.data || defaults.data,
      json: data?.json || defaults.json,
      files: data?.files || defaults.files,
      parametrize: data?.parametrize || defaults.parametrize,
    };
  }

  async function formSubmit(runAfterSave = false) {
    if (submitMode.value) return;
    submitMode.value = runAfterSave ? 'debug' : 'save';
    try {
      await formRef.value.validate();
      let data: Endpoint;
      try {
        // 请求体以当前选择的类型为准，避免 data 与 json 同时发送造成语义不明确。
        data = {
          ...formValue,
          data:
            bodyType.value === 'data' || bodyType.value === 'files'
              ? parseJson(jsonText.data, '表单参数')
              : {},
          json: bodyType.value === 'json' ? parseJson(jsonText.json, 'JSON 请求体') : {},
          headers: parseJson(jsonText.headers, '请求头'),
          params: parseJson(jsonText.params, '查询参数'),
          cookies: {},
          files: serializeFiles(),
          parametrize: serializeDataDrive(),
        } as Endpoint;
      } catch (error: any) {
        message.error(error.message);
        return;
      }

      const isCreate = endpointId.value === 0;
      const saved = isCreate
        ? await api.createData(data as Endpoint)
        : await api.update(endpointId.value, data as Endpoint);
      const savedId = Number((saved as Endpoint)?.id || endpointId.value);
      if (!savedId) throw new Error('接口保存成功，但未获取到接口 ID。');
      endpointId.value = savedId;
      Object.assign(formValue, normalizeEndpoint(saved || { ...data, id: savedId }));

      if (isCreate) {
        await router.replace({
          name: 'case_api_endpoint_edit',
          params: { id: savedId },
        });
      }

      if (runAfterSave) {
        message.success('保存成功，正在执行接口');
        await prepareDebugRun(savedId, Number(formValue.project));
      } else {
        message.success('保存成功');
        redirectAfterSubmit({ name: 'case_api_endpoint' });
      }
    } catch (error: any) {
      if (Array.isArray(error)) message.error('验证失败，请填写完整信息');
      else message.error(error?.message || '保存接口失败');
    } finally {
      submitMode.value = null;
    }
  }

  async function prepareDebugRun(savedId: number, projectId: number) {
    if (!projectId) throw new Error('接口未关联有效项目，无法执行。');
    const response: any = await environmentApi.getDataList({ project: projectId, pageSize: 999 });
    const environments: Environment[] = (
      Array.isArray(response) ? response : response?.list || response?.results || []
    ).filter((item: Environment) => Number(item.project) === projectId && Number(item.id) > 0);
    debugEnvironments.value = environments;
    debugEnvironmentOptions.value = environments.map((item) => ({
      label: `${item.name} · ${item.base_url}`,
      value: Number(item.id),
    }));
    if (!environments.length) throw new Error('当前项目尚未配置执行环境。');

    const selectedExists = environments.some((item) => item.id === debugEnvironmentId.value);
    if (!selectedExists) {
      const preferred = environments.find((item) => item.name === 'Dev') || environments[0];
      debugEnvironmentId.value = Number(preferred.id);
    }
    debugDialogVisible.value = true;
    await executeDebug(savedId);
  }

  async function executeDebug(savedId = endpointId.value) {
    if (!savedId || !debugEnvironmentId.value || debugRunning.value) return;
    debugRunning.value = true;
    debugResult.value = null;
    try {
      debugResult.value = await api.runById(savedId, debugEnvironmentId.value);
      if (debugResult.value.passed) message.success('接口执行成功');
      else message.error('接口执行失败');
    } catch (error: any) {
      debugResult.value = {
        environment: debugEnvironmentName.value,
        passed: false,
        errors: [error?.message || '接口执行失败'],
        response_body: '',
      };
    } finally {
      debugRunning.value = false;
    }
  }

  function back() {
    router.push({ name: 'case_api_endpoint' });
  }

  async function get_data_by_api() {
    // 加载项目列表
    const project_by_api = await project_api.getDataList({});
    project_list.value = project_by_api.map((project) => {
      return { label: project.name, value: project.id };
    });

    if (dataID == 0) {
      Object.assign(formValue, normalizeEndpoint());
      const projectId = Number(route.query.project);
      const moduleId = Number(route.query.module);
      if (Number.isInteger(projectId) && projectId > 0) {
        formValue.project = projectId;
        await loadModuleOptions(projectId);
        if (module_list.value.some((module) => module.value === moduleId))
          formValue.module = moduleId;
      }
    } else {
      const data_by_api = await api.getDataByID(dataID); // 修改默认值
      Object.assign(formValue, normalizeEndpoint(data_by_api));
      if (formValue.project) await loadModuleOptions(formValue.project);
    }
    syncJsonText();
    if (formValue.project) await loadProjectVariables(Number(formValue.project));
  }

  async function loadModuleOptions(projectId: number) {
    const data = await moduleApi.getDataList({ project: projectId, pageSize: 999 });
    const modules = Array.isArray(data) ? data : data?.list || data?.results || [];
    module_list.value = modules.map((module: any) => ({ label: module.name, value: module.id }));
  }

  async function handleProjectChange(projectId: number) {
    formValue.module = null;
    module_list.value = [];
    projectVariables.value = [];
    if (projectId)
      await Promise.all([loadModuleOptions(projectId), loadProjectVariables(projectId)]);
  }

  async function loadProjectVariables(projectId: number) {
    const data: any = await projectVariableApi.getDataList({ project: projectId, pageSize: 999 });
    projectVariables.value = Array.isArray(data) ? data : data?.list || data?.results || [];
  }

  function formatJson(value: unknown) {
    return JSON.stringify(value || {}, null, 2);
  }

  function syncJsonText() {
    jsonText.headers = formatJson(formValue.headers);
    jsonText.params = formatJson(formValue.params);
    jsonText.data = formatJson(formValue.data);
    jsonText.json = formatJson(formValue.json);
    fileEntries.value = Object.entries(formValue.files || {}).flatMap(([field, entries]) =>
      (Array.isArray(entries) ? entries : []).map((entry) => ({ ...entry, field }))
    );
    const parametrize = Array.isArray(formValue.parametrize) ? formValue.parametrize : [];
    dataDrivenEnabled.value = parametrize.length >= 2;
    dataDriveFields.value =
      dataDrivenEnabled.value && Array.isArray(parametrize[0])
        ? parametrize[0].map((field) => String(field).trim()).filter(Boolean)
        : [];
    dataDriveFieldsText.value = dataDriveFields.value.join(', ');
    dataDriveRows.value = dataDrivenEnabled.value
      ? parametrize
          .slice(1)
          .filter((row) => Array.isArray(row))
          .map((row) => row.map((value) => (value == null ? '' : String(value))))
      : [];
    bodyType.value =
      fileEntries.value.length > 0
        ? 'files'
        : Object.keys(formValue.data || {}).length > 0 &&
          Object.keys(formValue.json || {}).length === 0
        ? 'data'
        : 'json';
    requestTab.value =
      fileEntries.value.length > 0
        ? 'files'
        : Object.keys(formValue.params || {}).length > 0 &&
          Object.keys(formValue.json || {}).length === 0 &&
          Object.keys(formValue.data || {}).length === 0
        ? 'params'
        : 'body';
  }

  function selectRequestTab(tab: RequestTab) {
    requestTab.value = tab;
    if (tab === 'files') bodyType.value = 'files';
    else if (tab === 'body' && bodyType.value === 'files') bodyType.value = 'json';
  }

  function updateActiveEditor(value: string) {
    const field = activeEditorField.value;
    jsonText[field] = value;
    updateJsonField(field, value);
  }

  function formatActiveJson() {
    const field = activeEditorField.value;
    try {
      jsonText[field] = JSON.stringify(parseJson(jsonText[field], '当前参数'), null, 2);
      updateJsonField(field, jsonText[field]);
    } catch (error: any) {
      message.error(error.message);
    }
  }

  function variableReference(name: string) {
    return `\${${name}}`;
  }

  function updateJsonField(field: 'headers' | 'params' | 'data' | 'json', value: string) {
    try {
      formValue[field] = value.trim() ? JSON.parse(value) : {};
    } catch {
      // 输入尚未形成完整 JSON 时保留原值，避免编辑过程破坏表单。
    }
  }

  function parseJson(value: string, fieldName: string) {
    try {
      const result = value.trim() ? JSON.parse(value) : {};
      if (!result || Array.isArray(result) || typeof result !== 'object') {
        throw new Error();
      }
      return result;
    } catch {
      throw new Error(`${fieldName}必须填写合法的 JSON 对象。`);
    }
  }

  function serializeFiles(): Record<string, UploadedEndpointFile[]> {
    return fileEntries.value.reduce((result: Record<string, UploadedEndpointFile[]>, entry) => {
      const field = entry.field.trim();
      if (!field) return result;
      (result[field] ||= []).push({ name: entry.name, path: entry.path, size: entry.size });
      return result;
    }, {});
  }

  function syncDataDriveFields() {
    const nextFields = dataDriveFieldsText.value
      .split(/[,，、]/)
      .map((field) => field.trim())
      .filter(Boolean);
    if (new Set(nextFields).size !== nextFields.length) {
      message.warning('数据驱动字段名不能重复。');
      return;
    }
    const previousFields = dataDriveFields.value;
    dataDriveRows.value = dataDriveRows.value.map((row) =>
      nextFields.map((field) => {
        const oldIndex = previousFields.indexOf(field);
        return oldIndex >= 0 ? row[oldIndex] || '' : '';
      })
    );
    dataDriveFields.value = nextFields;
    dataDriveFieldsText.value = nextFields.join(', ');
  }

  function addDataDriveRow() {
    if (!dataDriveFields.value.length) {
      message.warning('请先输入数据驱动字段名。');
      return;
    }
    dataDriveRows.value.push(dataDriveFields.value.map(() => ''));
  }

  function copyDataDriveRow(rowIndex: number) {
    const sourceRow = dataDriveRows.value[rowIndex];
    if (!sourceRow) return;
    dataDriveRows.value.splice(rowIndex + 1, 0, [...sourceRow]);
    message.success(`第 ${rowIndex + 1} 行已复制`);
  }

  function serializeDataDrive() {
    if (!dataDrivenEnabled.value) return [];
    syncDataDriveFields();
    if (!dataDriveFields.value.length) throw new Error('启用数据驱动后请填写字段名。');
    if (!dataDriveRows.value.length) throw new Error('启用数据驱动后请至少添加一行数据。');
    const rows = dataDriveRows.value.map((row) =>
      dataDriveFields.value.map((_, index) => row[index] ?? '')
    );
    return [dataDriveFields.value, ...rows];
  }

  async function uploadEndpointFile({ file, onFinish, onError }: any) {
    try {
      const nativeFile = file.file as File | null;
      if (!nativeFile) throw new Error('未读取到待上传文件。');
      const uploaded = await api.uploadFile(nativeFile);
      fileEntries.value.push({ ...uploaded, field: 'file' });
      message.success(`文件「${uploaded.name}」上传成功`);
      onFinish();
    } catch (error: any) {
      message.error(error.message || '文件上传失败');
      onError();
    }
  }

  function formatFileSize(size?: number) {
    if (!size) return '—';
    return size < 1024 * 1024
      ? `${Math.ceil(size / 1024)} KB`
      : `${(size / 1024 / 1024).toFixed(2)} MB`;
  }

  onMounted(async () => {
    await get_data_by_api();
  });
</script>

<style lang="less" scoped>
  .endpoint-page {
    min-height: 100%;
    padding: 12px 30px 38px;
    background: #f7f9fc;
    color: #172033;
  }
  .endpoint-page-inner {
    width: 100%;
  }
  .page-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 12px;
  }
  .breadcrumb-row {
    display: flex;
    align-items: center;
    gap: 10px;
    color: #8a96a8;
    font-size: 13px;
  }
  .breadcrumb-row i {
    color: #c1c9d6;
    font-style: normal;
  }
  .breadcrumb-row b {
    color: #536176;
    font-weight: 600;
  }
  .page-actions {
    display: flex;
    flex: none;
    gap: 8px;
  }
  .page-actions :deep(.n-button) {
    min-width: 72px;
    height: 34px;
    border-radius: 6px;
    font-size: 13px;
  }
  .save-button {
    color: #5267f5;
    background: #eef1ff;
    border-color: #eef1ff;
  }
  .endpoint-form {
    width: 100%;
  }
  .basic-card,
  .request-card,
  .data-drive-card,
  .side-card {
    border: 1px solid #dce3ee;
    border-radius: 10px;
    background: #fff;
  }
  .basic-card {
    margin-bottom: 16px;
    padding: 10px 18px;
  }
  .basic-card h2,
  .request-card-head h2,
  .side-card h2,
  .data-drive-title h2 {
    margin: 0;
    color: #1b2638;
    font-size: 15px;
    font-weight: 700;
  }
  .basic-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 22px;
    margin-top: 7px;
  }
  .basic-grid :deep(.n-form-item.n-form-item--left-labelled) {
    display: grid;
    grid-template-areas: 'label blank';
    grid-template-columns: max-content minmax(0, 1fr);
    grid-template-rows: 34px;
    align-items: center;
    gap: 12px;
    height: 34px;
    margin: 0;
    min-width: 0;
  }
  .basic-grid :deep(.n-form-item.n-form-item--left-labelled > .n-form-item-label) {
    display: flex !important;
    grid-area: label;
    width: auto !important;
    height: 34px !important;
    min-height: 34px !important;
    align-items: center;
    justify-content: flex-start;
    padding: 0;
    color: #59677b;
    font-size: 13px;
    font-weight: 500;
    line-height: 34px;
    white-space: nowrap;
  }
  .basic-grid :deep(.n-form-item.n-form-item--left-labelled > .n-form-item-blank) {
    display: flex;
    grid-area: blank;
    width: 100%;
    height: 34px;
    min-width: 0;
    min-height: 34px;
    align-items: center;
  }
  .basic-grid :deep(.n-form-item-feedback-wrapper) {
    display: none;
  }
  .basic-grid :deep(.n-base-selection-label),
  .basic-grid :deep(.n-input-wrapper) {
    height: 34px;
    min-height: 34px;
  }
  .basic-grid :deep(.n-input),
  .basic-grid :deep(.n-select),
  .basic-grid :deep(.n-base-selection) {
    width: 100%;
    min-width: 0;
    height: 34px;
  }
  .request-core-input {
    display: grid;
    grid-template-columns: 92px minmax(0, 1fr);
    width: 100%;
    height: 34px;
    overflow: hidden;
    box-sizing: border-box;
    border: 1px solid #dce3ee;
    border-radius: 6px;
    background: #fff;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .request-core-input:focus-within {
    border-color: #5267f5;
    box-shadow: 0 0 0 2px rgb(82 103 245 / 10%);
  }
  .request-core-input :deep(.n-base-selection) {
    border-right: 1px solid #e4e9f1;
  }
  .request-core-input :deep(.n-base-selection-label),
  .request-core-input :deep(.n-input-wrapper) {
    height: 32px;
    min-height: 32px;
    border: 0;
    border-radius: 0;
    box-shadow: none !important;
  }
  .request-core-input :deep(.n-input) {
    min-width: 0;
  }
  .request-method-select :deep(.n-base-selection-label) {
    color: #1d9b50;
    background: #f0faf4;
    font-weight: 700;
  }
  .endpoint-workspace {
    display: grid;
    grid-template-columns: minmax(0, 72fr) minmax(360px, 28fr);
    gap: 16px;
    align-items: start;
  }
  .workspace-main {
    display: grid;
    gap: 16px;
    min-width: 0;
  }
  .request-card {
    overflow: hidden;
  }
  .request-card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 58px;
    padding: 10px 18px;
  }
  .request-debug-button {
    min-width: 88px;
    height: 36px;
    border-radius: 6px;
    background: #5267f5;
  }
  .request-target {
    padding: 0 18px 16px;
    border-bottom: 1px solid #e8edf4;
  }
  .request-target :deep(.n-form-item.n-form-item--left-labelled) {
    display: grid;
    grid-template-areas: 'label blank';
    grid-template-columns: max-content minmax(0, 1fr);
    align-items: center;
    gap: 14px;
    margin: 0;
  }
  .request-target :deep(.n-form-item.n-form-item--left-labelled > .n-form-item-label) {
    grid-area: label;
    width: auto !important;
    min-height: 38px;
    align-items: center;
    padding: 0;
    color: #59677b;
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
  }
  .request-target :deep(.n-form-item.n-form-item--left-labelled > .n-form-item-blank) {
    grid-area: blank;
    min-width: 0;
    min-height: 38px;
  }
  .request-target :deep(.n-form-item-feedback-wrapper) {
    display: none;
  }
  .request-target .request-core-input {
    height: 38px;
  }
  .request-target .request-core-input :deep(.n-base-selection-label),
  .request-target .request-core-input :deep(.n-input-wrapper) {
    height: 36px;
    min-height: 36px;
  }
  .request-tabs {
    display: flex;
    align-items: center;
    height: 52px;
    padding: 0 18px;
    border-bottom: 1px solid #e8edf4;
  }
  .request-tabs button {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    align-self: stretch;
    min-width: 122px;
    padding: 0 16px;
    border: 0;
    color: #536176;
    background: transparent;
    cursor: pointer;
    font: inherit;
  }
  .request-tabs button::after {
    position: absolute;
    right: 14px;
    bottom: -1px;
    left: 14px;
    height: 3px;
    border-radius: 3px 3px 0 0;
    background: transparent;
    content: '';
  }
  .request-tabs button.active {
    color: #5267f5;
    font-weight: 600;
  }
  .request-tabs button.active::after {
    background: #5267f5;
  }
  .request-tabs button b {
    display: inline-flex;
    min-width: 20px;
    height: 20px;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
    color: #718096;
    background: #f1f4f8;
    font-size: 11px;
    font-weight: 600;
  }
  .editor-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 48px;
    padding: 0 18px;
  }
  .editor-toolbar > strong {
    color: #344157;
    font-size: 13px;
  }
  .body-kind-tabs {
    display: flex;
    gap: 8px;
  }
  .body-kind-tabs button {
    min-width: 88px;
    height: 30px;
    padding: 0 14px;
    border: 0;
    border-radius: 5px;
    color: #56647a;
    background: transparent;
    cursor: pointer;
  }
  .body-kind-tabs button.active {
    color: #3f5eea;
    background: #eef2ff;
    font-weight: 600;
  }
  .editor-actions {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .editor-actions :deep(.n-button) {
    color: #5f6e82;
  }
  .json-editor {
    display: grid;
    grid-template-columns: 48px minmax(0, 1fr);
    min-height: 226px;
    margin: 0 18px;
    overflow: hidden;
    border: 1px solid #202938;
    border-radius: 7px;
    background: #202733;
  }
  .editor-gutter {
    min-height: 100%;
    margin: 0;
    padding: 14px 0;
    border-right: 1px solid #3a4352;
    color: #929daf;
    background: #1b222d;
    font: 13px/1.75 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    text-align: center;
    user-select: none;
  }
  .json-editor :deep(.n-input),
  .json-editor :deep(.n-input-wrapper),
  .json-editor :deep(.n-input__textarea-el) {
    min-height: 224px !important;
    color: #dce6f5;
    background: transparent !important;
    box-shadow: none !important;
  }
  .json-editor :deep(.n-input-wrapper) {
    padding: 0;
  }
  .json-editor :deep(textarea) {
    padding: 14px 18px;
    caret-color: #fff;
    font: 13px/1.75 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }
  .json-editor :deep(textarea::placeholder) {
    color: #788498;
  }
  .editor-note {
    display: flex;
    align-items: center;
    gap: 9px;
    min-height: 42px;
    margin: 12px 18px 18px;
    padding: 0 14px;
    border: 1px solid #dbe5f3;
    border-radius: 5px;
    color: #69788d;
    background: #f5f8fc;
    font-size: 12px;
  }
  .editor-note > span {
    display: inline-flex;
    width: 18px;
    height: 18px;
    align-items: center;
    justify-content: center;
    border: 1.5px solid #5267f5;
    border-radius: 50%;
    color: #5267f5;
    font-size: 11px;
    font-weight: 700;
  }
  .editor-note code,
  .variables-card code {
    color: #355be7;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .files-panel {
    min-height: 300px;
    padding: 20px 18px;
  }
  .files-panel-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding-bottom: 16px;
    border-bottom: 1px solid #edf1f6;
  }
  .files-panel-head strong {
    color: #263348;
    font-size: 14px;
  }
  .files-panel-head p {
    margin: 5px 0 0;
    color: #7d8999;
    font-size: 12px;
  }
  .file-entry {
    display: grid;
    grid-template-columns: 180px minmax(160px, 1fr) 76px 48px;
    gap: 12px;
    align-items: center;
    min-height: 50px;
    padding: 8px 0;
    border-bottom: 1px solid #edf1f6;
  }
  .file-name {
    overflow: hidden;
    color: #5b6676;
    font-size: 13px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .file-size {
    color: #97a0ad;
    font-size: 12px;
    text-align: right;
  }
  .file-empty {
    padding: 60px 0;
  }
  .workspace-sidebar {
    display: grid;
    gap: 12px;
  }
  .side-card {
    overflow: hidden;
  }
  .side-card h2 {
    padding: 16px 18px;
    border-bottom: 1px solid #e8edf4;
  }
  .overview-list {
    padding: 8px 18px 14px;
  }
  .overview-list > div {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 37px;
    color: #536176;
    font-size: 13px;
  }
  .overview-list span {
    display: inline-flex;
    align-items: center;
    gap: 10px;
  }
  .overview-list b {
    color: #263348;
    font-size: 13px;
  }
  .variables-card {
    padding-bottom: 16px;
  }
  .variable-list {
    display: grid;
    gap: 8px;
    padding: 14px 18px 8px;
  }
  .variable-list > div {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 12px;
  }
  .variable-list code {
    width: max-content;
    max-width: 100%;
    overflow: hidden;
    padding: 5px 9px;
    border-radius: 4px;
    background: #eef2ff;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .variable-list span {
    color: #66758a;
    font-size: 12px;
  }
  .variables-card > p {
    margin: 8px 18px 0;
    color: #7b8798;
    font-size: 12px;
    line-height: 1.7;
  }
  .data-drive-card {
    overflow: hidden;
  }
  .data-drive-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    min-height: 42px;
    padding: 0 16px;
    border-bottom: 1px solid #e8edf4;
  }
  .data-drive-title > div {
    display: flex;
    align-items: baseline;
    gap: 14px;
  }
  .data-drive-title p {
    margin: 0;
    color: #8290a3;
    font-size: 12px;
  }
  .data-drive-content {
    padding: 10px 16px 14px;
  }
  .data-drive-field-label {
    display: grid;
    grid-template-columns: 176px minmax(0, 1fr);
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
    color: #536176;
    font-size: 12px;
  }
  .data-drive-table-wrap {
    overflow-x: auto;
    border: 1px solid #dce3ee;
    border-radius: 4px;
  }
  .data-drive-table {
    min-width: 620px;
  }
  .data-drive-row {
    display: grid;
    align-items: center;
    gap: 0;
    min-height: 32px;
    padding: 0;
    border-top: 1px solid #e8edf4;
  }
  .data-drive-row > * {
    display: flex;
    height: 100%;
    min-width: 0;
    align-items: center;
    padding: 0 10px;
    border-right: 1px solid #e8edf4;
  }
  .data-drive-row > *:last-child {
    justify-content: center;
    border-right: 0;
  }
  .data-drive-row:first-child {
    border-top: 0;
  }
  .data-drive-header {
    min-height: 28px;
    color: #56647a;
    background: #f7f9fc;
    font-size: 12px;
    font-weight: 600;
  }
  .data-drive-index {
    justify-content: center;
    color: #7c899b;
    font-size: 12px;
    text-align: center;
  }
  .data-drive-actions {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    white-space: nowrap;
  }
  .data-drive-actions :deep(.n-button) {
    padding: 0;
  }
  .data-drive-row :deep(.n-input-wrapper) {
    min-height: 31px;
    padding: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
  }
  .data-drive-row :deep(.n-input) {
    height: 31px;
    background: transparent;
  }
  .data-drive-row :deep(.n-input:focus-within) {
    box-shadow: inset 0 0 0 1px #5267f5;
  }
  .add-data-row {
    height: 36px;
    border-width: 0;
    border-top: 1px dashed #aebcff;
    border-radius: 0;
    color: #5267f5;
  }
  .data-drive-warning {
    margin-top: 10px;
  }
  .endpoint-debug-modal {
    max-height: calc(100vh - 64px);
    overflow: hidden;
  }
  .endpoint-debug-modal :deep(.n-card__content) {
    overflow-y: auto;
  }
  .debug-toolbar {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 18px;
  }
  .debug-toolbar > div {
    display: grid;
    grid-template-columns: 72px minmax(260px, 1fr);
    align-items: center;
    gap: 12px;
    flex: 1;
  }
  .debug-toolbar span {
    color: #59677b;
    font-size: 13px;
    font-weight: 600;
  }
  .debug-result {
    display: grid;
    gap: 14px;
  }
  .debug-summary {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px 18px;
    color: #66758a;
    font-size: 13px;
  }
  .debug-errors {
    font-size: 13px;
  }
  .debug-response {
    overflow: hidden;
    border: 1px solid #dce3ee;
    border-radius: 8px;
  }
  .debug-response h3 {
    margin: 0;
    padding: 12px 14px;
    border-bottom: 1px solid #e8edf4;
    color: #1b2638;
    font-size: 14px;
  }
  .debug-response pre {
    overflow: auto;
    max-height: 420px;
    margin: 0;
    padding: 14px;
    color: #dfe7f3;
    background: #202733;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
    font-size: 12px;
    line-height: 1.7;
    white-space: pre-wrap;
    word-break: break-all;
  }
  @media (max-width: 1400px) {
    .endpoint-page {
      padding-right: 20px;
      padding-left: 20px;
    }
    .endpoint-workspace {
      grid-template-columns: minmax(0, 72fr) minmax(300px, 28fr);
    }
  }
  @media (max-width: 980px) {
    .endpoint-workspace {
      grid-template-columns: 1fr;
    }
    .workspace-sidebar {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .request-tabs {
      overflow-x: auto;
    }
  }
  @media (max-width: 680px) {
    .endpoint-page {
      padding: 16px 12px 28px;
    }
    .page-toolbar {
      align-items: flex-start;
      flex-wrap: wrap;
    }
    .basic-grid,
    .workspace-sidebar {
      grid-template-columns: 1fr;
    }
    .basic-grid :deep(.n-form-item.n-form-item--left-labelled) {
      grid-template-areas:
        'label'
        'blank';
      grid-template-columns: 1fr;
      grid-template-rows: 34px 34px;
      align-items: stretch;
      height: auto;
      gap: 6px;
    }
    .request-tabs button {
      min-width: 108px;
    }
    .data-drive-title,
    .data-drive-title > div {
      align-items: flex-start;
      flex-direction: column;
    }
    .data-drive-title {
      padding: 12px 16px;
    }
    .data-drive-field-label {
      grid-template-columns: 1fr;
    }
    .debug-toolbar {
      align-items: stretch;
      flex-direction: column;
    }
    .debug-toolbar > div {
      grid-template-columns: 1fr;
    }
  }
</style>
