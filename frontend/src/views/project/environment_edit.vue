<template>
  <div class="environment-detail-page">
    <div class="page-breadcrumb">项目管理 <span>/</span> 环境与认证 <span>/</span> 环境详情</div>

    <header class="page-header">
      <div>
        <div class="title-line">
          <h1>{{ formValue.name || '新建' }} 环境</h1>
          <p>配置服务地址、登录认证与 Token 生命周期</p>
        </div>
        <div class="environment-tabs">
          <button
            v-for="name in environmentNames"
            :key="name"
            type="button"
            :class="{ active: formValue.name === name }"
            :disabled="switching"
            @click="switchEnvironment(name)"
            >{{ name }}</button
          >
        </div>
      </div>
      <div class="header-actions">
        <n-button size="large" @click="router.back()">返回</n-button>
        <n-button size="large" type="primary" ghost :loading="saving" @click="saveConfiguration"
          >保存配置</n-button
        >
        <n-button size="large" type="primary" :loading="validating" @click="saveAndValidate">
          <template #icon
            ><n-icon><PlayCircleOutline /></n-icon
          ></template>
          保存并验证
        </n-button>
      </div>
    </header>

    <section class="status-strip">
      <div class="status-item"
        ><span class="status-label">服务状态：</span
        ><span class="status-value" :class="serviceStatusClass"
          ><i></i>{{ serviceStatusText }}</span
        ></div
      >
      <div class="status-divider"></div>
      <div class="status-item"
        ><span class="status-label">自动认证：</span
        ><span class="status-tag" :class="formValue.auth_enabled ? 'success' : 'neutral'">{{
          formValue.auth_enabled ? '已启用' : '未启用'
        }}</span></div
      >
      <div class="status-divider"></div>
      <div class="status-item"
        ><span class="status-label">Token 状态：</span
        ><span class="status-tag" :class="authStatus?.valid ? 'success' : 'neutral'">{{
          tokenStatusText
        }}</span></div
      >
      <div class="status-divider"></div>
      <div class="status-item"
        ><span class="status-label">剩余有效期：</span><span>{{ remainingText }}</span></div
      >
      <div class="last-refresh"
        >最近刷新&nbsp;&nbsp;{{ formatDate(authStatus?.token_refreshed_at) }}</div
      >
    </section>

    <n-form ref="formRef" :model="formValue" :rules="rules" :show-label="false">
      <div class="content-grid">
        <main class="configuration-column">
          <section class="config-panel basic-panel">
            <div class="panel-heading inline-heading">
              <div class="heading-copy"
                ><h2>A. 基础信息</h2><span>定义当前环境的服务入口</span></div
              >
              <div class="heading-switch"
                ><span>启用环境</span><n-switch :value="true" disabled
              /></div>
            </div>
            <div class="basic-grid">
              <n-form-item path="project"
                ><label class="field-label">所属项目</label
                ><n-select
                  v-model:value="formValue.project"
                  :options="projectOptions"
                  placeholder="请选择项目"
                  @update:value="handleProjectChange"
                /></n-form-item
              >
              <n-form-item path="name"
                ><label class="field-label">环境名称</label
                ><n-select
                  v-model:value="formValue.name"
                  :options="environmentNameOptions"
                  placeholder="请选择环境"
                  @update:value="handleEnvironmentNameChange"
                /></n-form-item
              >
              <n-form-item path="base_url"
                ><label class="field-label">服务基础地址</label
                ><n-input
                  v-model:value="formValue.base_url"
                  placeholder="https://api-test.example.com"
              /></n-form-item>
            </div>
          </section>

          <section class="config-panel auth-panel">
            <div class="panel-heading inline-heading auth-heading">
              <div class="heading-copy auth-title-copy"
                ><h2>B. 自动认证</h2
                ><n-switch v-model:value="formValue.auth_enabled" size="small" /><span
                  >运行前自动获取并复用 Token</span
                ></div
              >
            </div>
            <div v-if="formValue.auth_enabled" class="auth-content">
              <n-form-item path="login_url" class="request-target-item">
                <label class="horizontal-label">登录接口</label>
                <div class="request-target"
                  ><n-select
                    v-model:value="formValue.login_method"
                    :options="methodOptions"
                    class="method-select" /><n-input
                    v-model:value="formValue.login_url"
                    placeholder="/api/login，也可填写完整 URL"
                /></div>
              </n-form-item>
              <div class="request-tabs">
                <button
                  v-for="tab in requestTabs"
                  :key="tab.key"
                  type="button"
                  :class="{ active: activeRequestTab === tab.key }"
                  @click="activeRequestTab = tab.key"
                  >{{ tab.label }} <span>{{ parameterCount(tab.key) }}</span></button
                >
              </div>
              <div class="json-editor-shell">
                <div class="editor-actions"
                  ><button type="button" @click="formatActiveParameter">格式化</button
                  ><button type="button" @click="restoreActiveParameter">恢复默认值</button></div
                >
                <div class="editor-body">
                  <pre class="line-numbers">{{ editorLineNumbers }}</pre>
                  <n-input
                    :value="parameterTexts[activeRequestTab]"
                    type="textarea"
                    :autosize="{ minRows: 5, maxRows: 8 }"
                    spellcheck="false"
                    placeholder="{}"
                    @update:value="updateParameterText(activeRequestTab, $event)"
                  />
                </div>
              </div>
            </div>
            <div v-else class="auth-disabled-state"
              >自动认证已关闭，执行时仅使用当前环境的服务基础地址。</div
            >
          </section>

          <section v-if="formValue.auth_enabled" class="config-panel token-panel">
            <div class="panel-heading"
              ><div class="heading-copy"
                ><h2>C. Token 提取与注入</h2
                ><span>从登录响应提取 Token，并自动注入后续请求</span></div
              ></div
            >
            <div class="token-grid first-row">
              <n-form-item path="token_jsonpath"
                ><label class="field-label">Token JSONPath</label
                ><n-input v-model:value="formValue.token_jsonpath" placeholder="$.data.token"
              /></n-form-item>
              <n-form-item
                ><label class="field-label">变量名</label
                ><n-input v-model:value="formValue.token_name" placeholder="token"
              /></n-form-item>
            </div>
            <div class="token-grid second-row">
              <n-form-item path="token_header"
                ><label class="field-label">请求头字段</label
                ><n-input v-model:value="formValue.token_header" placeholder="Authorization"
              /></n-form-item>
              <n-form-item
                ><label class="field-label">请求头前缀</label
                ><n-input v-model:value="formValue.token_prefix" placeholder="Bearer "
              /></n-form-item>
              <n-form-item
                ><label class="field-label">默认有效期（秒）</label
                ><n-input-number v-model:value="formValue.token_ttl" :min="60" :max="86400"
              /></n-form-item>
            </div>
            <div class="ttl-note"
              ><n-icon><InformationCircleOutline /></n-icon>平台优先按 Token TTL 判断缓存；接口返回
              jwt expired 或 HTTP 401 时触发兜底刷新。</div
            >
          </section>
        </main>

        <aside class="side-column">
          <section class="side-panel token-status-panel">
            <h2>D. Token 运行状态</h2>
            <div class="token-state-hero" :class="authStatus?.valid ? 'valid' : 'empty'"
              ><div class="state-check">{{ authStatus?.valid ? '✓' : '—' }}</div
              ><strong>{{ authStatus?.valid ? 'Token 缓存有效' : '暂无有效 Token' }}</strong></div
            >
            <dl class="status-details">
              <div
                ><dt>缓存状态：</dt
                ><dd :class="{ green: authStatus?.valid }">{{ cacheStatusText }}</dd></div
              >
              <div
                ><dt>最近刷新：</dt><dd>{{ formatDate(authStatus?.token_refreshed_at) }}</dd></div
              >
              <div
                ><dt>预计过期：</dt><dd>{{ formatDate(authStatus?.token_expires_at) }}</dd></div
              >
              <div
                ><dt>缓存值：</dt
                ><dd class="token-preview-row"
                  ><span class="token-preview">{{ authStatus?.masked_token || '—' }}</span
                  ><n-button
                    text
                    class="token-copy-button"
                    aria-label="复制缓存值"
                    title="复制缓存值"
                    :disabled="!authStatus?.masked_token"
                    :loading="copyingToken"
                    @click="copyCachedToken"
                    ><n-icon size="16"><CopyOutline /></n-icon></n-button></dd
              ></div>
            </dl>
            <div class="token-actions"
              ><n-button
                type="primary"
                :loading="refreshing"
                :disabled="!formValue.auth_enabled"
                @click="refreshToken"
                >立即刷新 Token</n-button
              ><n-button type="error" ghost :disabled="!authStatus?.cached" @click="clearToken"
                >清除缓存</n-button
              ></div
            >
          </section>

          <section class="side-panel flow-panel">
            <h2>E. 认证流程预览</h2>
            <ol class="auth-flow">
              <li
                ><span class="step-number">1</span
                ><div
                  ><strong>发起登录请求</strong
                  ><small
                    >{{ formValue.login_method }} {{ formValue.login_url || '/api/login' }}</small
                  ></div
                ></li
              >
              <li
                ><span class="step-number">2</span
                ><div
                  ><strong>提取响应字段</strong
                  ><small>{{ formValue.token_jsonpath || '$.data.token' }}</small></div
                ></li
              >
              <li
                ><span class="step-number">3</span
                ><div
                  ><strong>注入后续请求</strong
                  ><small
                    >{{ formValue.token_header || 'Authorization' }}:
                    {{ formValue.token_prefix }}${{ '{' }}{{ formValue.token_name || 'token'
                    }}{{ '}' }}</small
                  ></div
                ></li
              >
              <li
                ><span class="step-number">4</span
                ><div
                  ><strong>过期自动刷新</strong><small>TTL 到期 / jwt expired / 401</small></div
                ></li
              >
            </ol>
          </section>

          <section class="side-panel validation-panel">
            <h2>F. 验证结果</h2>
            <div class="validation-result" :class="validationResultClass">
              <div class="validation-icon">{{
                validationResult?.connected
                  ? '✓'
                  : validationResult?.connected === false
                  ? '!'
                  : '·'
              }}</div>
              <div class="validation-copy"
                ><strong>{{ validationTitle }}</strong
                ><span>{{ validationDetail }}</span></div
              >
              <small v-if="validationResult">耗时 {{ validationResult.elapsed_ms }} ms</small>
            </div>
          </section>
        </aside>
      </div>
    </n-form>
  </div>
</template>

<script lang="ts" setup>
  import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
  import { useMessage } from 'naive-ui';
  import { CopyOutline, InformationCircleOutline, PlayCircleOutline } from '@vicons/ionicons5';
  import { useRoute, useRouter } from 'vue-router';
  import { EnvironmentAPI, ProjectAPI } from '@/api/project/http';
  import {
    Environment,
    EnvironmentAuthStatus,
    EnvironmentValidationResult,
  } from '@/api/project/models';

  type ParameterKey = 'login_headers' | 'login_params' | 'login_data' | 'login_json';
  const route = useRoute();
  const router = useRouter();
  const message = useMessage();
  const formRef = ref<any>();
  const api = new EnvironmentAPI();
  const projectApi = new ProjectAPI();
  const environmentId = ref(Number(route.params.id));
  const activeProjectId = ref<number | null>(null);
  const projectOptions = ref<Array<{ label: string; value: number }>>([]);
  const projectEnvironments = ref<Environment[]>([]);
  const authStatus = ref<EnvironmentAuthStatus | null>(null);
  const validationResult = ref<EnvironmentValidationResult | null>(null);
  const saving = ref(false);
  const validating = ref(false);
  const refreshing = ref(false);
  const copyingToken = ref(false);
  const switching = ref(false);
  const connected = ref<boolean | null>(null);
  const currentTime = ref(Date.now());
  const activeRequestTab = ref<ParameterKey>('login_json');
  const environmentNames = ['Dev', 'Test', 'Pre', 'Prod'];
  const environmentNameOptions = environmentNames.map((value) => ({ label: value, value }));
  const methodOptions = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((value) => ({
    label: value,
    value,
  }));
  const requestTabs: Array<{ key: ParameterKey; label: string }> = [
    { key: 'login_headers', label: 'Headers' },
    { key: 'login_params', label: 'Params' },
    { key: 'login_data', label: 'Data' },
    { key: 'login_json', label: 'JSON' },
  ];
  const initial = (): Environment => ({
    project: null,
    name: 'Test',
    base_url: '',
    auth_enabled: false,
    login_url: '',
    login_method: 'POST',
    login_headers: {},
    login_params: {},
    login_data: {},
    login_json: {},
    token_jsonpath: '$.data.token',
    token_name: 'token',
    token_header: 'Authorization',
    token_prefix: 'Bearer ',
    token_ttl: 1800,
  });
  const formValue = reactive<Environment>(initial());
  const parameterTexts = reactive<Record<ParameterKey, string>>({
    login_headers: '{}',
    login_params: '{}',
    login_data: '{}',
    login_json: '{}',
  });
  const loadedParameterTexts = reactive<Record<ParameterKey, string>>({ ...parameterTexts });
  const rules = {
    project: { required: true, type: 'number', message: '请选择项目', trigger: ['blur', 'change'] },
    name: { required: true, message: '请选择环境名称', trigger: ['blur', 'change'] },
    base_url: { required: true, message: '请输入服务基础地址', trigger: ['blur', 'input'] },
    login_url: { required: true, message: '请输入登录接口', trigger: ['blur', 'input'] },
    token_jsonpath: {
      required: true,
      message: '请输入 Token JSONPath',
      trigger: ['blur', 'input'],
    },
    token_header: { required: true, message: '请输入请求头字段', trigger: ['blur', 'input'] },
  };
  const editorLineNumbers = computed(() =>
    Array.from(
      { length: Math.max(5, parameterTexts[activeRequestTab.value].split('\n').length) },
      (_, index) => index + 1
    ).join('\n')
  );
  const remainingSeconds = computed(() =>
    !authStatus.value?.valid || !authStatus.value.token_expires_at
      ? 0
      : Math.max(
          0,
          Math.floor(
            (new Date(authStatus.value.token_expires_at).getTime() - currentTime.value) / 1000
          )
        )
  );
  const remainingText = computed(() =>
    !remainingSeconds.value
      ? '—'
      : `${Math.floor(remainingSeconds.value / 60)}分${String(remainingSeconds.value % 60).padStart(
          2,
          '0'
        )}秒`
  );
  const tokenStatusText = computed(() =>
    authStatus.value?.valid ? '有效' : authStatus.value?.cached ? '已过期' : '无缓存'
  );
  const cacheStatusText = computed(() =>
    authStatus.value?.valid ? '有效' : authStatus.value?.cached ? '已过期' : '未缓存'
  );
  const serviceStatusText = computed(() =>
    connected.value === true ? '可连接' : connected.value === false ? '连接失败' : '待验证'
  );
  const serviceStatusClass = computed(() =>
    connected.value === true ? 'online' : connected.value === false ? 'offline' : 'pending'
  );
  const currentProjectName = computed(
    () =>
      projectOptions.value.find((item) => Number(item.value) === Number(formValue.project))
        ?.label ||
      formValue.project_name ||
      '—'
  );
  const validationResultClass = computed(() =>
    validationResult.value?.connected === true
      ? 'success'
      : validationResult.value?.connected === false
      ? 'error'
      : 'idle'
  );
  const validationTitle = computed(() =>
    validationResult.value?.connected === true
      ? '验证通过'
      : validationResult.value?.connected === false
      ? '验证失败'
      : '尚未验证'
  );
  const validationDetail = computed(
    () => validationResult.value?.detail || '保存配置后，可验证服务连接和 Token 提取结果'
  );

  function stringify(value: Record<string, unknown>) {
    return JSON.stringify(value || {}, null, 2);
  }
  function normalizeList<T>(value: unknown): T[] {
    if (Array.isArray(value)) return value as T[];
    if (value && typeof value === 'object') {
      const payload = value as Record<string, unknown>;
      if (Array.isArray(payload.results)) return payload.results as T[];
      if (Array.isArray(payload.data)) return payload.data as T[];
    }
    return [];
  }
  function syncParameterTexts() {
    requestTabs.forEach(({ key }) => {
      const text = stringify(formValue[key] as Record<string, unknown>);
      parameterTexts[key] = text;
      loadedParameterTexts[key] = text;
    });
    activeRequestTab.value = Object.keys(formValue.login_json || {}).length
      ? 'login_json'
      : Object.keys(formValue.login_data || {}).length
      ? 'login_data'
      : Object.keys(formValue.login_params || {}).length
      ? 'login_params'
      : 'login_headers';
  }
  function resetEnvironmentRuntime() {
    authStatus.value = null;
    validationResult.value = null;
    connected.value = null;
  }
  function applyEnvironment(data: Environment, id = Number(data.id || 0)) {
    Object.assign(formValue, initial(), data);
    activeProjectId.value = Number(data.project || 0) || null;
    environmentId.value = id;
    resetEnvironmentRuntime();
    syncParameterTexts();
  }
  function updateParameterText(key: ParameterKey, value: string) {
    parameterTexts[key] = value;
    try {
      const parsed = value.trim() ? JSON.parse(value) : {};
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) formValue[key] = parsed;
    } catch {
      /* 保存时统一校验 */
    }
  }
  function parameterCount(key: ParameterKey) {
    return Object.keys((formValue[key] as Record<string, unknown>) || {}).length;
  }
  function formatActiveParameter() {
    const key = activeRequestTab.value;
    try {
      const parsed = parameterTexts[key].trim() ? JSON.parse(parameterTexts[key]) : {};
      parameterTexts[key] = stringify(parsed);
      formValue[key] = parsed;
    } catch {
      message.error(`${requestTabs.find((item) => item.key === key)?.label} 不是有效的 JSON`);
    }
  }
  function restoreActiveParameter() {
    const key = activeRequestTab.value;
    parameterTexts[key] = loadedParameterTexts[key];
    formValue[key] = JSON.parse(loadedParameterTexts[key] || '{}');
  }
  function validateParameterJson() {
    requestTabs.forEach(({ key, label }) => {
      try {
        const parsed = parameterTexts[key].trim() ? JSON.parse(parameterTexts[key]) : {};
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error();
        formValue[key] = parsed;
      } catch {
        throw new Error(`${label} 必须是 JSON 对象`);
      }
    });
  }
  async function persist(showSuccess = true) {
    try {
      await formRef.value?.validate();
      validateParameterJson();
    } catch (error: any) {
      message.error(error?.message || '请检查必填项和请求参数');
      return null;
    }
    saving.value = true;
    try {
      const data = { ...formValue };
      const result = environmentId.value
        ? await api.update(environmentId.value, data)
        : await api.createData(data);
      if (result?.id) {
        applyEnvironment(result, Number(result.id));
        await router.replace({
          name: 'project_environment_edit',
          params: { id: result.id },
          query: {},
        });
        await loadProjectEnvironments();
      }
      if (showSuccess) message.success('环境配置已保存');
      return result;
    } catch (error: any) {
      message.error(error?.message || '保存失败');
      return null;
    } finally {
      saving.value = false;
    }
  }
  async function saveConfiguration() {
    const result = await persist();
    if (result && environmentId.value) await loadAuthStatus();
  }
  async function saveAndValidate() {
    validating.value = true;
    try {
      const result = await persist(false);
      if (!result || !environmentId.value) return;
      validationResult.value = await api.validateAuth(environmentId.value);
      connected.value = validationResult.value.connected;
      authStatus.value = validationResult.value;
      message.success('配置已保存，认证验证通过');
    } catch (error: any) {
      connected.value = false;
      const detail = error?.response?.data?.detail || error?.message || '认证验证失败';
      validationResult.value = {
        connected: false,
        detail,
        elapsed_ms: 0,
      } as EnvironmentValidationResult;
      message.error(detail);
    } finally {
      validating.value = false;
    }
  }
  async function refreshToken() {
    if (!environmentId.value) {
      const saved = await persist(false);
      if (!saved) return;
    }
    refreshing.value = true;
    try {
      authStatus.value = await api.refreshToken(environmentId.value);
      connected.value = true;
      message.success('Token 刷新成功');
    } catch (error: any) {
      message.error(error?.message || 'Token 刷新失败');
    } finally {
      refreshing.value = false;
    }
  }
  async function clearToken() {
    if (!environmentId.value) return;
    try {
      authStatus.value = await api.clearToken(environmentId.value);
      message.success('Token 缓存已清除');
    } catch (error: any) {
      message.error(error?.message || '清除缓存失败');
    }
  }
  async function copyCachedToken() {
    if (!environmentId.value || !authStatus.value?.cached) return;
    copyingToken.value = true;
    try {
      const result = await api.getTokenValue(environmentId.value);
      const value = result?.token || '';
      if (!value) throw new Error('当前环境没有可复制的 Token 缓存');
      try {
        await navigator.clipboard.writeText(value);
      } catch {
        const textarea = document.createElement('textarea');
        textarea.value = value;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        textarea.remove();
      }
      message.success('完整 Token 已复制');
    } catch (error: any) {
      message.error(error?.message || '复制 Token 失败');
    } finally {
      copyingToken.value = false;
    }
  }
  async function loadAuthStatus() {
    if (!environmentId.value) return;
    try {
      authStatus.value = await api.getAuthStatus(environmentId.value);
    } catch {
      authStatus.value = null;
    }
  }
  async function loadProjectEnvironments() {
    const all = normalizeList<Environment>(await api.getDataList({}));
    projectEnvironments.value = all.filter(
      (item) => Number(item.project) === Number(activeProjectId.value)
    );
  }
  async function handleProjectChange(projectId: number | null) {
    activeProjectId.value = Number(projectId || 0) || null;
    resetEnvironmentRuntime();
    await loadProjectEnvironments();
  }
  function handleEnvironmentNameChange(name: string) {
    if (!environmentNames.includes(name)) return;
    resetEnvironmentRuntime();
  }
  async function switchEnvironment(name: string) {
    if (switching.value || !environmentNames.includes(name)) return;
    const target = projectEnvironments.value.find((item) => item.name === name);
    if (target?.id && Number(target.id) === environmentId.value) return;
    switching.value = true;
    try {
      if (target?.id) {
        const data = await api.getDataByID(target.id);
        applyEnvironment(data, Number(target.id));
        await router.replace({
          name: 'project_environment_edit',
          params: { id: target.id },
          query: {},
        });
        await loadAuthStatus();
        return;
      }
      const project = activeProjectId.value || Number(formValue.project || 0) || null;
      applyEnvironment({ ...initial(), project, name });
      await router.replace({
        name: 'project_environment_edit',
        params: {},
        query: { project: String(project || ''), environment: name },
      });
      message.info(`${name} 环境尚未配置，填写后保存即可创建`);
    } catch (error: any) {
      message.error(error?.message || `${name} 环境加载失败`);
    } finally {
      switching.value = false;
    }
  }
  function formatDate(value?: string | null) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    const pad = (number: number) => String(number).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
      date.getHours()
    )}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  }
  async function load() {
    try {
      const projects = normalizeList<any>(await projectApi.getDataList({}));
      projectOptions.value = projects.map((item) => ({ label: item.name, value: item.id }));
      if (environmentId.value) {
        const data = await api.getDataByID(environmentId.value);
        applyEnvironment(data, environmentId.value);
        await Promise.all([loadAuthStatus(), loadProjectEnvironments()]);
      } else {
        const project = Number(route.query.project || 0) || null;
        const requestedName = String(route.query.environment || 'Test');
        const name = environmentNames.includes(requestedName) ? requestedName : 'Test';
        applyEnvironment({ ...initial(), project, name });
        if (project) await loadProjectEnvironments();
      }
    } catch (error: any) {
      message.error(error?.message || '环境配置加载失败');
    }
  }
  watch(
    () => route.params.id,
    async (value) => {
      const nextId = Number(value || 0);
      if (!nextId || nextId === environmentId.value) return;
      switching.value = true;
      try {
        const data = await api.getDataByID(nextId);
        applyEnvironment(data, nextId);
        await Promise.all([loadAuthStatus(), loadProjectEnvironments()]);
      } catch (error: any) {
        message.error(error?.message || '环境配置加载失败');
      } finally {
        switching.value = false;
      }
    }
  );
  const clock = window.setInterval(() => {
    currentTime.value = Date.now();
  }, 1000);
  onBeforeUnmount(() => window.clearInterval(clock));
  onMounted(load);
</script>

<style lang="less" scoped>
  .environment-detail-page {
    box-sizing: border-box;
    width: 100%;
    max-width: 100%;
    min-height: 100%;
    padding: 18px 24px 26px;
    overflow-x: hidden;
    color: #1f2937;
    background: #f6f8fc;
  }
  .page-breadcrumb {
    margin-bottom: 14px;
    color: #334155;
    font-size: 13px;
    font-weight: 500;
  }
  .page-breadcrumb span {
    margin: 0 10px;
    color: #aab4c3;
  }
  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
  }
  .title-line {
    display: flex;
    align-items: baseline;
    gap: 28px;
  }
  .title-line h1 {
    margin: 0;
    color: #18212f;
    font-size: 28px;
    line-height: 38px;
  }
  .title-line p {
    margin: 0;
    color: #6f7c91;
    font-size: 14px;
  }
  .environment-tabs {
    display: flex;
    margin-top: 10px;
  }
  .environment-tabs button {
    min-width: 72px;
    height: 34px;
    padding: 0 18px;
    border: 0;
    color: #30394a;
    background: transparent;
    cursor: pointer;
  }
  .environment-tabs button.active {
    color: #fff;
    background: #5267f5;
  }
  .environment-tabs button:disabled {
    cursor: wait;
    opacity: 0.72;
  }
  .header-actions {
    display: flex;
    flex: 0 0 auto;
    gap: 14px;
    padding-top: 16px;
  }
  .header-actions :deep(.n-button) {
    min-width: 98px;
    height: 46px;
    border-radius: 4px;
  }
  .header-actions :deep(.n-button:last-child) {
    min-width: 148px;
  }
  .status-strip {
    display: flex;
    align-items: center;
    min-height: 60px;
    margin-top: 10px;
    padding: 0 30px;
    border: 1px solid #dce3ed;
    border-radius: 6px;
    background: #fff;
  }
  .status-item {
    display: flex;
    align-items: center;
    min-width: 220px;
    gap: 8px;
    font-size: 14px;
  }
  .status-label {
    color: #374151;
  }
  .status-value {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-weight: 500;
  }
  .status-value i {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #aab3c0;
  }
  .status-value.online {
    color: #159447;
  }
  .status-value.online i {
    background: #159447;
  }
  .status-value.offline {
    color: #d03050;
  }
  .status-value.offline i {
    background: #d03050;
  }
  .status-value.pending {
    color: #8a94a6;
  }
  .status-tag {
    padding: 4px 12px;
    border-radius: 3px;
    font-size: 13px;
  }
  .status-tag.success {
    color: #178b45;
    background: #eaf8ef;
  }
  .status-tag.neutral {
    color: #7b8798;
    background: #f1f3f6;
  }
  .status-divider {
    width: 1px;
    height: 25px;
    margin-right: 48px;
    background: #d9dfe8;
  }
  .last-refresh {
    margin-left: auto;
    color: #718096;
    font-size: 13px;
  }
  .content-grid {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(330px, 1fr);
    gap: 12px;
    margin-top: 10px;
  }
  .configuration-column,
  .side-column {
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-width: 0;
  }
  .config-panel,
  .side-panel {
    border: 1px solid #dfe5ee;
    border-radius: 6px;
    background: #fff;
  }
  .config-panel {
    padding: 18px 26px;
  }
  .panel-heading {
    display: flex;
    min-height: 28px;
    align-items: center;
  }
  .inline-heading {
    justify-content: space-between;
  }
  .heading-copy {
    display: flex;
    align-items: baseline;
    gap: 22px;
  }
  .heading-copy h2,
  .side-panel h2 {
    margin: 0;
    color: #1f2937;
    font-size: 16px;
    line-height: 24px;
  }
  .heading-copy span {
    color: #8591a5;
    font-size: 13px;
  }
  .heading-switch,
  .auth-title-copy {
    display: flex;
    align-items: center;
    gap: 12px;
    color: #2f3a4c;
    font-size: 13px;
  }
  .auth-title-copy {
    gap: 16px;
  }
  .basic-grid {
    display: grid;
    grid-template-columns: 1fr 0.74fr 1.65fr;
    gap: 48px;
    margin-top: 16px;
  }
  :deep(.n-form-item) {
    min-width: 0;
    margin: 0;
  }
  :deep(.n-form-item-blank) {
    display: flex !important;
    align-items: stretch !important;
    flex-direction: column !important;
    min-width: 0;
  }
  .field-label {
    display: block;
    margin-bottom: 8px;
    color: #313b4d;
    font-size: 13px;
    font-weight: 500;
  }
  .readonly-field {
    display: flex;
    width: 100%;
    min-height: 34px;
    box-sizing: border-box;
    align-items: center;
    padding: 0 11px;
    border: 1px solid #e2e7ef;
    border-radius: 3px;
    color: #344054;
    font-size: 14px;
    background: #f7f9fc;
  }
  :deep(.n-input),
  :deep(.n-select),
  :deep(.n-input-number) {
    width: 100%;
  }
  :deep(.n-base-selection),
  :deep(.n-input-wrapper) {
    border-radius: 3px;
  }
  .auth-panel {
    padding-bottom: 14px;
  }
  .auth-content {
    margin-top: 12px;
  }
  .request-target-item :deep(.n-form-item-blank) {
    display: flex;
    align-items: center !important;
    flex-direction: row !important;
    gap: 18px;
  }
  .horizontal-label {
    flex: 0 0 95px;
    color: #313b4d;
    font-size: 13px;
    font-weight: 500;
  }
  .request-target {
    display: flex;
    flex: 1;
    min-width: 0;
    gap: 12px;
  }
  .method-select {
    flex: 0 0 125px;
  }
  .method-select :deep(.n-base-selection-label) {
    color: #159447;
    font-weight: 600;
  }
  .request-tabs {
    display: flex;
    align-items: flex-end;
    height: 43px;
    margin-top: 8px;
    border-bottom: 1px solid #e8edf4;
    gap: 28px;
  }
  .request-tabs button {
    height: 43px;
    padding: 0 4px;
    border: 0;
    border-bottom: 3px solid transparent;
    color: #526174;
    background: transparent;
    cursor: pointer;
  }
  .request-tabs button span {
    margin-left: 6px;
    color: #5267f5;
  }
  .request-tabs button.active {
    color: #5267f5;
    border-bottom-color: #5267f5;
  }
  .json-editor-shell {
    position: relative;
    overflow: hidden;
    border-radius: 3px;
    background: #202733;
  }
  .editor-actions {
    position: absolute;
    z-index: 2;
    top: 10px;
    right: 12px;
    display: flex;
    gap: 8px;
  }
  .editor-actions button {
    height: 30px;
    padding: 0 13px;
    border: 1px solid #657084;
    border-radius: 3px;
    color: #e4e8ef;
    background: rgba(32, 39, 51, 0.88);
    cursor: pointer;
  }
  .editor-actions button:hover {
    border-color: #8ea1bc;
    background: #2a3341;
  }
  .editor-body {
    display: flex;
    min-height: 140px;
  }
  .line-numbers {
    flex: 0 0 42px;
    min-height: 140px;
    margin: 0;
    padding: 13px 9px 13px 0;
    border-right: 1px solid #3c4656;
    color: #929daf;
    font: 13px/23px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    text-align: right;
    user-select: none;
  }
  .editor-body :deep(.n-input) {
    flex: 1;
    --n-color: #202733 !important;
    --n-color-focus: #202733 !important;
    --n-border: 0 !important;
    --n-border-focus: 0 !important;
    --n-box-shadow-focus: none !important;
    background: #202733 !important;
    box-shadow: none !important;
  }
  .editor-body :deep(.n-input-wrapper) {
    min-height: 140px;
    padding: 0;
    background: transparent;
    box-shadow: none !important;
  }
  .editor-body :deep(.n-input__textarea-el) {
    min-height: 140px !important;
    padding: 13px 16px;
    color: #dbe4f0;
    caret-color: #fff;
    background: transparent;
    font: 13px/23px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }
  .auth-disabled-state {
    margin-top: 14px;
    padding: 20px;
    border: 1px dashed #d6dde8;
    color: #7d899b;
    background: #f9fafc;
    text-align: center;
  }
  .token-panel {
    padding-bottom: 16px;
  }
  .token-grid {
    display: grid;
    gap: 44px;
  }
  .token-grid.first-row {
    grid-template-columns: 1.18fr 1fr;
    margin-top: 15px;
  }
  .token-grid.second-row {
    grid-template-columns: 1fr 0.92fr 0.83fr;
    margin-top: 12px;
    gap: 42px;
  }
  .ttl-note {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 36px;
    margin-top: 12px;
    padding: 0 12px;
    border: 1px solid #b9d6ff;
    border-radius: 3px;
    color: #5e6d82;
    background: #f3f8ff;
    font-size: 12px;
  }
  .ttl-note :deep(.n-icon) {
    color: #3979e9;
  }
  .side-panel {
    overflow: hidden;
  }
  .side-panel > h2 {
    padding: 16px 18px;
    border-bottom: 1px solid #e4e9f0;
  }
  .token-state-hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 18px 0 9px;
    gap: 9px;
  }
  .state-check {
    display: grid;
    width: 39px;
    height: 39px;
    place-items: center;
    border-radius: 50%;
    color: #fff;
    background: #9aa5b4;
    font-size: 24px;
    font-weight: 700;
  }
  .token-state-hero strong {
    color: #7b8797;
    font-size: 15px;
  }
  .token-state-hero.valid .state-check {
    background: #16a05d;
  }
  .token-state-hero.valid strong {
    color: #159653;
  }
  .status-details {
    margin: 0;
    padding: 0 48px 12px;
  }
  .status-details div {
    display: grid;
    grid-template-columns: 106px minmax(0, 1fr);
    margin: 8px 0;
    color: #374151;
    font-size: 12px;
  }
  .status-details dt,
  .status-details dd {
    margin: 0;
  }
  .status-details dd.green {
    color: #159653;
  }
  .token-preview {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .token-preview-row {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: 8px;
  }
  .token-copy-button {
    flex: 0 0 22px;
    width: 22px;
    height: 22px;
    color: #7c899c;
  }
  .token-copy-button:not(:disabled):hover {
    color: #5267f5;
    background: #eef2ff;
  }
  .token-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    padding: 0 24px 16px;
  }
  .token-actions :deep(.n-button) {
    border-radius: 3px;
  }
  .auth-flow {
    margin: 0;
    padding: 14px 22px 8px;
    list-style: none;
  }
  .auth-flow li {
    position: relative;
    display: flex;
    min-height: 52px;
    gap: 14px;
  }
  .auth-flow li:not(:last-child)::after {
    position: absolute;
    top: 25px;
    bottom: 0;
    left: 12px;
    width: 1px;
    background: #cdd9f8;
    content: '';
  }
  .step-number {
    z-index: 1;
    display: grid;
    flex: 0 0 25px;
    height: 25px;
    place-items: center;
    border-radius: 50%;
    color: #fff;
    background: #4773ef;
    font-size: 12px;
  }
  .auth-flow strong,
  .auth-flow small {
    display: block;
  }
  .auth-flow strong {
    color: #30394a;
    font-size: 13px;
    font-weight: 600;
  }
  .auth-flow small {
    max-width: 280px;
    margin-top: 4px;
    overflow: hidden;
    color: #77849a;
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .validation-panel {
    padding-bottom: 14px;
  }
  .validation-result {
    display: grid;
    grid-template-columns: 32px minmax(0, 1fr) auto;
    align-items: center;
    min-height: 88px;
    margin: 14px 16px 0;
    padding: 0 16px;
    border: 1px solid #dfe5ed;
    border-radius: 4px;
    color: #6e7b8f;
    background: #f8fafc;
    gap: 10px;
  }
  .validation-icon {
    display: grid;
    width: 26px;
    height: 26px;
    place-items: center;
    border-radius: 50%;
    color: #fff;
    background: #9aa5b4;
    font-size: 16px;
    font-weight: 700;
  }
  .validation-copy strong,
  .validation-copy span {
    display: block;
  }
  .validation-copy strong {
    margin-bottom: 5px;
    font-size: 15px;
  }
  .validation-copy span {
    font-size: 12px;
  }
  .validation-result > small {
    align-self: end;
    padding-bottom: 12px;
    color: #4d596a;
    font-size: 11px;
  }
  .validation-result.success {
    border-color: #a5dbb9;
    color: #198a4c;
    background: #f0fbf4;
  }
  .validation-result.success .validation-icon {
    background: #16a05d;
  }
  .validation-result.error {
    border-color: #efb5c0;
    color: #c92c4b;
    background: #fff5f7;
  }
  .validation-result.error .validation-icon {
    background: #d03050;
  }
  @media (max-width: 1200px) {
    .content-grid {
      grid-template-columns: 1fr;
    }
    .side-column {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      align-items: start;
    }
    .status-item {
      min-width: auto;
      flex: 1;
    }
    .status-divider {
      margin-right: 24px;
    }
    .last-refresh {
      display: none;
    }
  }
  @media (max-width: 820px) {
    .environment-detail-page {
      padding: 14px;
    }
    .page-header,
    .title-line {
      display: block;
    }
    .title-line p {
      margin-top: 4px;
    }
    .header-actions {
      flex-wrap: wrap;
    }
    .status-strip {
      align-items: flex-start;
      flex-direction: column;
      padding: 14px 18px;
      gap: 10px;
    }
    .status-divider {
      display: none;
    }
    .basic-grid,
    .token-grid.first-row,
    .token-grid.second-row,
    .side-column {
      grid-template-columns: 1fr;
      gap: 12px;
    }
    .request-target-item :deep(.n-form-item-blank) {
      align-items: flex-start;
      flex-direction: column !important;
    }
    .horizontal-label {
      flex-basis: auto;
    }
  }
</style>
