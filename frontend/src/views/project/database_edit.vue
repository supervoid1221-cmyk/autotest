<template>
  <div class="database-detail-page">
    <div class="page-breadcrumb">项目管理 <span>/</span> 数据库连接 <span>/</span> 连接详情</div>
    <header class="page-header">
      <div class="page-title">
        <span class="title-icon"
          ><n-icon><ServerOutline /></n-icon
        ></span>
        <div class="title-line"><h1>数据库连接详情</h1><p>配置可复用的查询与受控更新能力</p></div>
      </div>
      <div class="header-actions">
        <span class="connection-badge" :class="connectionBadgeClass"
          ><i></i>{{ connectionBadgeText }}</span
        >
        <n-button size="large" @click="goBack"
          ><template #icon
            ><n-icon><ArrowBackOutline /></n-icon></template
          >返回</n-button
        >
        <n-button size="large" type="primary" ghost :loading="testing" @click="testConnection"
          ><template #icon
            ><n-icon><GitNetworkOutline /></n-icon></template
          >测试连接</n-button
        >
        <n-button size="large" type="primary" :loading="saving" @click="submit"
          ><template #icon
            ><n-icon><SaveOutline /></n-icon></template
          >保存配置</n-button
        >
      </div>
    </header>

    <n-form ref="formRef" :model="formValue" :rules="rules" label-placement="top">
      <div class="connection-layout">
        <section class="panel connection-panel">
          <div class="panel-heading">
            <div class="panel-title"
              ><n-icon><ServerOutline /></n-icon><h2>A. 连接配置</h2></div
            >
            <div class="enabled-control"
              ><span>{{ formValue.enabled ? '启用' : '停用' }}</span
              ><n-switch v-model:value="formValue.enabled"
            /></div>
          </div>
          <div class="panel-body connection-form">
            <div class="form-row form-row-primary">
              <n-form-item label="所属项目" path="projects"
                ><n-select
                  v-model:value="formValue.projects"
                  multiple
                  filterable
                  :options="projectOptions"
                  placeholder="请选择一个或多个项目"
              /></n-form-item>
              <n-form-item label="执行环境" path="environment_name"
                ><n-select v-model:value="formValue.environment_name" :options="environmentOptions"
              /></n-form-item>
              <n-form-item label="数据库类型" path="database_type"
                ><n-select
                  v-model:value="formValue.database_type"
                  :options="databaseTypeOptions"
                  @update:value="setDefaultFunction"
              /></n-form-item>
              <n-form-item label="调用函数" path="function_name"
                ><n-input v-model:value="formValue.function_name" placeholder="execute_sql_mysql"
              /></n-form-item>
            </div>
            <div class="form-row form-row-address">
              <n-form-item label="Host" path="host"
                ><n-input v-model:value="formValue.host" placeholder="127.0.0.1"
              /></n-form-item>
              <n-form-item label="Port" path="port"
                ><n-input-number
                  v-model:value="formValue.port"
                  :min="1"
                  :max="65535"
                  :show-button="false"
              /></n-form-item>
              <n-form-item label="Database" path="database"
                ><n-input v-model:value="formValue.database" placeholder="order_center"
              /></n-form-item>
            </div>
            <div class="form-row form-row-account">
              <n-form-item label="用户名" path="username"
                ><n-input v-model:value="formValue.username" placeholder="test_runner"
              /></n-form-item>
              <n-form-item label="密码" path="password"
                ><n-input
                  v-model:value="formValue.password"
                  type="password"
                  show-password-on="click"
                  :placeholder="formValue.password_configured ? '留空表示不修改' : '请输入密码'"
              /></n-form-item>
              <n-form-item label="TLS 模式" path="ssl_mode"
                ><n-select v-model:value="formValue.ssl_mode" :options="sslModeOptions"
              /></n-form-item>
              <n-form-item label="连接超时" path="connect_timeout"
                ><n-input-number
                  v-model:value="formValue.connect_timeout"
                  :min="1"
                  :max="120"
                  :show-button="false"
                  ><template #suffix>秒</template></n-input-number
                ></n-form-item
              >
            </div>
            <div class="encryption-tip"
              ><n-icon><InformationCircleOutline /></n-icon
              >连接信息将被加密存储，仅在执行时使用。</div
            >
          </div>
        </section>

        <aside class="side-column">
          <section class="panel status-panel">
            <div class="side-heading"><h2>B. 连接状态</h2></div>
            <div class="status-content">
              <div class="status-mark" :class="connectionMarkClass"
                ><n-icon><CheckmarkCircleOutline /></n-icon
              ></div>
              <div class="status-copy">
                <strong :class="connectionTextClass">{{ connectionTitle }}</strong>
                <div class="address-line"
                  ><span>{{ connectionSummary }}</span
                  ><n-button text title="复制连接地址" @click="copy(connectionAddress)"
                    ><n-icon><CopyOutline /></n-icon></n-button
                ></div>
                <dl>
                  <div
                    ><dt>最后校验时间</dt><dd>{{ lastTestedAt || '—' }}</dd></div
                  >
                  <div
                    ><dt>响应耗时</dt
                    ><dd :class="{ success: connectionState?.connected }">{{
                      elapsedText
                    }}</dd></div
                  >
                  <div
                    ><dt>数据库类型</dt><dd>{{ databaseTypeLabel }}</dd></div
                  >
                  <div
                    ><dt>连接地址</dt
                    ><dd class="copy-value"
                      >{{ connectionAddress
                      }}<n-button text title="复制连接地址" @click="copy(connectionAddress)"
                        ><n-icon><CopyOutline /></n-icon></n-button></dd
                  ></div>
                </dl>
              </div>
            </div>
          </section>
          <section class="panel security-panel">
            <div class="side-heading"><h2>C. 写操作安全</h2></div>
            <div class="security-box">
              <span class="security-icon"
                ><n-icon><ShieldCheckmarkOutline /></n-icon
              ></span>
              <div class="security-copy">
                <div class="security-title"
                  ><strong>允许执行 UPDATE</strong><n-switch v-model:value="formValue.allow_write"
                /></div>
                <p>仅允许包含 WHERE 条件的 UPDATE，不支持 DELETE、INSERT</p>
                <div class="security-tags"
                  ><span>WHERE 必填</span><span>二次确认</span><span>记录审计</span></div
                >
              </div>
            </div>
          </section>
        </aside>
      </div>
    </n-form>

    <section class="panel sql-panel">
      <div class="sql-heading">
        <div>
          <h2>D. SQL 校验</h2>
          <div class="sql-tabs">
            <button
              type="button"
              :class="{ active: sqlMode === 'select' }"
              @click="changeSqlMode('select')"
              >SELECT 查询</button
            >
            <button
              type="button"
              :class="{ active: sqlMode === 'update' }"
              @click="changeSqlMode('update')"
              >UPDATE 更新</button
            >
          </div>
        </div>
        <n-button type="primary" :loading="sqlTesting" @click="testSql"
          ><template #icon
            ><n-icon><PlayOutline /></n-icon></template
          >执行校验</n-button
        >
      </div>
      <div class="sql-workspace">
        <div class="sql-editor-shell">
          <pre class="line-numbers">{{ sqlLineNumbers }}</pre>
          <n-input
            v-model:value="testSqlText"
            type="textarea"
            spellcheck="false"
            placeholder="SELECT id, amount FROM orders LIMIT 10;"
          />
        </div>
        <div class="result-shell">
          <div class="result-meta"
            ><span v-if="sqlResult"
              >返回 <strong>{{ resultRowCount }}</strong> 行 · {{ sqlResult.elapsed_ms }} ms</span
            ><span v-else>等待执行结果</span></div
          >
          <div v-if="sqlResult?.operation === 'update'" class="update-result"
            ><strong>{{ sqlResult.affected_rows || 0 }}</strong
            ><span>行数据已更新</span></div
          >
          <div v-else-if="sqlRows.length" class="result-table-wrap">
            <table>
              <thead
                ><tr
                  ><th v-for="column in sqlColumnKeys" :key="column">{{ column }}</th></tr
                ></thead
              >
              <tbody>
                <tr v-for="(row, index) in sqlRows" :key="index"
                  ><td v-for="column in sqlColumnKeys" :key="column">{{
                    formatCell(row[column])
                  }}</td></tr
                >
              </tbody>
            </table>
          </div>
          <div v-else class="result-empty">输入 SQL 后点击“执行校验”查看结果</div>
          <div class="execution-plan"><span>›</span>执行计划</div>
        </div>
      </div>
    </section>

    <section class="panel usage-panel">
      <h2>E. 调用示例</h2>
      <div class="usage-grid">
        <div class="usage-item">
          <label>接口参数中使用</label>
          <div class="code-line"
            ><code>{{ queryExample }}</code
            ><n-button size="small" @click="copy(queryExample)"
              ><template #icon
                ><n-icon><CopyOutline /></n-icon></template
              >复制</n-button
            ></div
          >
        </div>
        <div class="usage-item">
          <label>后置数据库更新</label>
          <div class="code-line"
            ><code>{{ updateExample }}</code
            ><n-button size="small" @click="copy(updateExample)"
              ><template #icon
                ><n-icon><CopyOutline /></n-icon></template
              >复制</n-button
            ></div
          >
        </div>
      </div>
      <div class="usage-tip"
        ><n-icon><InformationCircleOutline /></n-icon>SELECT 默认返回第一行第一列；UPDATE
        执行结果返回影响行数。</div
      >
    </section>
  </div>
</template>

<script lang="ts" setup>
  import { computed, onMounted, reactive, ref } from 'vue';
  import { useMessage } from 'naive-ui';
  import {
    ArrowBackOutline,
    CheckmarkCircleOutline,
    CopyOutline,
    GitNetworkOutline,
    InformationCircleOutline,
    PlayOutline,
    SaveOutline,
    ServerOutline,
    ShieldCheckmarkOutline,
  } from '@vicons/ionicons5';
  import { useRoute, useRouter } from 'vue-router';
  import { DatabaseConnectionAPI, ProjectAPI } from '@/api/project/http';
  import type { DatabaseConnection } from '@/api/project/models';
  import { useSubmitRedirect } from '@/hooks/web/useSubmitRedirect';

  type SqlMode = 'select' | 'update';
  type ConnectionState = { connected: boolean; text: string; elapsed_ms?: number };
  const route = useRoute();
  const router = useRouter();
  const message = useMessage();
  const { redirectAfterSubmit } = useSubmitRedirect();
  const api = new DatabaseConnectionAPI();
  const projectApi = new ProjectAPI();
  const id = Number(route.params.id || 0);
  const formRef = ref<any>();
  const saving = ref(false);
  const testing = ref(false);
  const sqlTesting = ref(false);
  const projectOptions = ref<any[]>([]);
  const connectionState = ref<ConnectionState | null>(null);
  const lastTestedAt = ref('');
  const sqlMode = ref<SqlMode>('select');
  const testSqlText = ref(
    'SELECT id, amount, status\nFROM orders\nWHERE user_id = 1001\nLIMIT 10;'
  );
  const sqlResult = ref<any>(null);
  const initial = (): DatabaseConnection => ({
    projects: [],
    environment_name: 'Test',
    database_type: 'mysql',
    function_name: 'execute_sql_mysql',
    host: '',
    port: 3306,
    database: '',
    username: '',
    password: '',
    ssl_mode: 'preferred',
    connect_timeout: 10,
    allow_write: false,
    enabled: true,
  });
  const formValue = reactive<DatabaseConnection>(initial());
  const environmentOptions = ['Dev', 'Test', 'Pre', 'Prod'].map((value) => ({
    label: value,
    value,
  }));
  const databaseTypeOptions = [
    { label: 'MySQL', value: 'mysql' },
    { label: 'PostgreSQL', value: 'postgresql' },
  ];
  const sslModeOptions = [
    { label: '优先使用 TLS', value: 'preferred' },
    { label: '强制使用 TLS', value: 'required' },
    { label: '关闭 TLS', value: 'disabled' },
  ];
  const rules = {
    projects: {
      required: true,
      type: 'array',
      min: 1,
      message: '请至少选择一个项目',
      trigger: ['blur', 'change'],
    },
    environment_name: { required: true, message: '请选择执行环境', trigger: 'change' },
    database_type: { required: true, message: '请选择数据库类型', trigger: 'change' },
    function_name: {
      required: true,
      pattern: /^execute_sql_[A-Za-z_]\w*$/,
      message: '函数名必须以 execute_sql_ 开头',
      trigger: 'blur',
    },
    host: { required: true, message: '请输入 Host', trigger: 'blur' },
    port: { required: true, type: 'number', message: '请输入 Port', trigger: 'blur' },
    database: { required: true, message: '请输入 Database', trigger: 'blur' },
    username: { required: true, message: '请输入用户名', trigger: 'blur' },
  };
  const databaseTypeLabel = computed(() =>
    formValue.database_type === 'postgresql' ? 'PostgreSQL' : 'MySQL'
  );
  const connectionAddress = computed(() =>
    formValue.host ? `${formValue.host}:${formValue.port || ''}` : '—'
  );
  const connectionSummary = computed(() =>
    formValue.host
      ? `${formValue.host}:${formValue.port || ''} / ${formValue.database || '—'}`
      : '尚未配置连接地址'
  );
  const connectionTitle = computed(() =>
    connectionState.value?.connected
      ? '连接正常'
      : connectionState.value
      ? '连接失败'
      : '等待连接测试'
  );
  const connectionBadgeText = computed(() =>
    connectionState.value?.connected
      ? `连接正常 · ${connectionState.value.elapsed_ms || 0} ms`
      : connectionState.value
      ? '连接失败'
      : '尚未测试'
  );
  const connectionBadgeClass = computed(() =>
    connectionState.value?.connected ? 'success' : connectionState.value ? 'error' : 'neutral'
  );
  const connectionMarkClass = computed(() =>
    connectionState.value?.connected ? 'success' : connectionState.value ? 'error' : 'neutral'
  );
  const connectionTextClass = computed(() =>
    connectionState.value?.connected ? 'success' : connectionState.value ? 'error' : ''
  );
  const elapsedText = computed(() =>
    connectionState.value?.elapsed_ms === undefined ? '—' : `${connectionState.value.elapsed_ms} ms`
  );
  const sqlRows = computed<Record<string, unknown>[]>(() =>
    !sqlResult.value?.row
      ? []
      : Array.isArray(sqlResult.value.row)
      ? sqlResult.value.row
      : [sqlResult.value.row]
  );
  const sqlColumnKeys = computed<string[]>(() =>
    Array.isArray(sqlResult.value?.columns) && sqlResult.value.columns.length
      ? sqlResult.value.columns
      : sqlRows.value.length
      ? Object.keys(sqlRows.value[0])
      : []
  );
  const resultRowCount = computed(() => sqlResult.value?.row_count ?? sqlRows.value.length);
  const sqlLineNumbers = computed(() =>
    Array.from(
      { length: Math.max(5, testSqlText.value.split('\n').length) },
      (_, index) => index + 1
    ).join('\n')
  );
  const queryExample = computed(
    () =>
      `\${${
        formValue.function_name || 'execute_sql_mysql'
      }("SELECT amount FROM orders WHERE user_id=1001")}`
  );
  const updateExample = computed(
    () =>
      `\${${
        formValue.function_name || 'execute_sql_mysql'
      }("UPDATE orders SET status='PAID' WHERE order_id=\${order_id}")}`
  );

  function normalizeList<T>(value: unknown): T[] {
    if (Array.isArray(value)) return value as T[];
    if (value && typeof value === 'object') {
      const payload = value as Record<string, unknown>;
      if (Array.isArray(payload.results)) return payload.results as T[];
      if (Array.isArray(payload.data)) return payload.data as T[];
    }
    return [];
  }
  function setDefaultFunction(type: string) {
    formValue.function_name = type === 'postgresql' ? 'execute_sql_pg' : 'execute_sql_mysql';
    formValue.port = type === 'postgresql' ? 5432 : 3306;
  }
  function changeSqlMode(mode: SqlMode) {
    sqlMode.value = mode;
    sqlResult.value = null;
    testSqlText.value =
      mode === 'update'
        ? "UPDATE orders SET status = 'PAID' WHERE order_id = 1001;"
        : 'SELECT id, amount, status\nFROM orders\nWHERE user_id = 1001\nLIMIT 10;';
  }
  function formatDateTime(date: Date) {
    const pad = (value: number) => String(value).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
      date.getHours()
    )}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  }
  function formatCell(value: unknown) {
    if (value === null) return 'null';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value ?? '');
  }
  async function load() {
    const projects = normalizeList<any>(await projectApi.getDataList({}));
    projectOptions.value = projects.map((item: any) => ({ label: item.name, value: item.id }));
    if (id) Object.assign(formValue, await api.getDataByID(id), { password: '' });
  }
  async function validate() {
    await formRef.value?.validate();
  }
  async function testConnection() {
    try {
      await validate();
      testing.value = true;
      const result = await api.testConnection({ ...formValue, id });
      connectionState.value = { connected: true, text: '连接正常', elapsed_ms: result.elapsed_ms };
      lastTestedAt.value = formatDateTime(new Date());
      message.success(`连接成功，耗时 ${result.elapsed_ms} ms`);
    } catch (error: any) {
      connectionState.value = { connected: false, text: error?.message || '连接失败' };
      lastTestedAt.value = formatDateTime(new Date());
      message.error(error?.message || '连接失败');
    } finally {
      testing.value = false;
    }
  }
  async function testSql() {
    try {
      await validate();
      if (!testSqlText.value.trim()) return message.warning('请输入 SQL');
      const isUpdate = /^\s*update\b/i.test(testSqlText.value);
      if (isUpdate && !formValue.allow_write)
        return message.warning('请先开启“允许执行 UPDATE”并保存连接配置');
      if (isUpdate && !window.confirm('将对目标数据库执行 UPDATE，确认继续吗？')) return;
      sqlTesting.value = true;
      sqlResult.value = await api.testSql({
        ...formValue,
        id,
        sql: testSqlText.value,
        confirm_write: isUpdate,
      });
      message.success('SQL 校验成功');
    } catch (error: any) {
      sqlResult.value = null;
      message.error(error?.message || 'SQL 校验失败');
    } finally {
      sqlTesting.value = false;
    }
  }
  async function submit() {
    try {
      await validate();
      saving.value = true;
      const data = { ...formValue };
      if (id) await api.update(id, data);
      else await api.createData(data);
      message.success('保存成功');
      redirectAfterSubmit({ name: 'project_database' });
    } catch (error: any) {
      if (error?.message) message.error(error.message);
    } finally {
      saving.value = false;
    }
  }
  function goBack() {
    router.push({ name: 'project_database' });
  }
  async function copy(value: string) {
    if (!value || value === '—') return message.warning('暂无可复制内容');
    try {
      await navigator.clipboard.writeText(value);
      message.success('已复制');
    } catch {
      message.error('复制失败');
    }
  }
  onMounted(load);
</script>

<style lang="less" scoped>
  .database-detail-page {
    box-sizing: border-box;
    width: 100%;
    min-height: 100%;
    padding: 16px 18px 28px;
    color: #1f2937;
    background: #f6f8fc;
  }
  .page-breadcrumb {
    margin: 0 4px 14px;
    color: #526078;
    font-size: 13px;
  }
  .page-breadcrumb span {
    margin: 0 10px;
    color: #a5afbe;
  }
  .page-header {
    display: flex;
    min-height: 72px;
    box-sizing: border-box;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    padding: 12px 18px;
    border: 1px solid #dfe5ee;
    border-radius: 6px;
    background: #fff;
  }
  .page-title,
  .title-line,
  .header-actions,
  .panel-title,
  .enabled-control,
  .address-line,
  .copy-value,
  .security-title,
  .usage-tip {
    display: flex;
    align-items: center;
  }
  .page-title {
    gap: 14px;
  }
  .title-icon {
    display: grid;
    width: 34px;
    height: 34px;
    place-items: center;
    color: #3565f6;
    font-size: 28px;
  }
  .title-line {
    align-items: baseline;
    gap: 18px;
  }
  .title-line h1 {
    margin: 0;
    color: #172033;
    font-size: 23px;
    font-weight: 650;
  }
  .title-line p {
    margin: 0;
    color: #8a95a8;
    font-size: 13px;
  }
  .header-actions {
    gap: 12px;
  }
  .connection-badge {
    display: inline-flex;
    min-height: 34px;
    align-items: center;
    gap: 8px;
    padding: 0 14px;
    border: 1px solid #d7dee8;
    border-radius: 4px;
    color: #748094;
    font-size: 13px;
    background: #f8fafc;
  }
  .connection-badge i {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: currentColor;
  }
  .connection-badge.success {
    border-color: #b9e6cf;
    color: #14935b;
    background: #f0fbf5;
  }
  .connection-badge.error {
    border-color: #f2c7ce;
    color: #d03050;
    background: #fff5f6;
  }
  :deep(.n-button),
  :deep(.n-base-selection),
  :deep(.n-input-wrapper) {
    border-radius: 4px;
  }
  .connection-layout {
    display: grid;
    grid-template-columns: minmax(0, 3fr) minmax(360px, 1.9fr);
    gap: 14px;
    margin-top: 14px;
  }
  .panel {
    min-width: 0;
    border: 1px solid #dfe5ee;
    border-radius: 6px;
    background: #fff;
  }
  .panel-heading,
  .side-heading {
    display: flex;
    min-height: 48px;
    box-sizing: border-box;
    align-items: center;
    justify-content: space-between;
    padding: 10px 18px;
    border-bottom: 1px solid #e8edf3;
  }
  .panel-title {
    gap: 8px;
    color: #2360ed;
  }
  .panel-title h2,
  .side-heading h2,
  .sql-heading h2,
  .usage-panel h2 {
    margin: 0;
    color: #1f2937;
    font-size: 15px;
    font-weight: 650;
  }
  .enabled-control {
    gap: 12px;
    color: #475569;
    font-size: 13px;
  }
  .panel-body {
    padding: 16px 18px 14px;
  }
  .form-row {
    display: grid;
    gap: 18px;
  }
  .form-row + .form-row {
    margin-top: 4px;
  }
  .form-row-primary {
    grid-template-columns: 1.5fr 0.72fr 0.72fr 1.05fr;
  }
  .form-row-address {
    grid-template-columns: 1.05fr 0.78fr 1.12fr;
  }
  .form-row-account {
    grid-template-columns: 1fr 1.1fr 1fr 0.72fr;
  }
  :deep(.n-form-item) {
    min-width: 0;
    margin-bottom: 10px;
  }
  :deep(.n-form-item-label) {
    color: #445168;
    font-size: 13px;
    font-weight: 500;
  }
  :deep(.n-input-number),
  :deep(.n-select) {
    width: 100%;
  }
  .encryption-tip {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 2px;
    color: #778398;
    font-size: 12px;
  }
  .encryption-tip .n-icon {
    color: #2c69f7;
    font-size: 17px;
  }
  .side-column {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .side-heading {
    justify-content: flex-start;
    min-height: 42px;
    padding: 8px 16px;
  }
  .status-content {
    display: grid;
    grid-template-columns: 104px 1fr;
    gap: 14px;
    padding: 14px 18px 16px;
  }
  .status-mark {
    display: grid;
    width: 78px;
    height: 78px;
    margin: 2px auto 0;
    place-items: center;
    border-radius: 50%;
    color: #fff;
    font-size: 68px;
    background: #aeb7c5;
  }
  .status-mark.success {
    background: #16a36a;
  }
  .status-mark.error {
    background: #d03050;
  }
  .status-copy > strong {
    display: block;
    margin: 0 0 4px;
    color: #536075;
    font-size: 18px;
  }
  .status-copy > strong.success,
  .status-copy dd.success {
    color: #15975d;
  }
  .status-copy > strong.error {
    color: #d03050;
  }
  .address-line {
    gap: 6px;
    color: #4b5870;
    font: 12px ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .status-copy dl {
    margin: 10px 0 0;
  }
  .status-copy dl > div {
    display: grid;
    grid-template-columns: 110px minmax(0, 1fr);
    gap: 8px;
    margin-top: 7px;
    font-size: 12px;
  }
  .status-copy dt {
    color: #7d899c;
  }
  .status-copy dd {
    min-width: 0;
    margin: 0;
    overflow: hidden;
    color: #465269;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .copy-value {
    gap: 5px;
  }
  .security-panel {
    flex: 1;
  }
  .security-box {
    display: grid;
    grid-template-columns: 58px 1fr;
    gap: 12px;
    margin: 12px 16px 14px;
    padding: 12px 14px;
    border: 1px solid #f0b95d;
    border-radius: 5px;
    background: #fffaf0;
  }
  .security-icon {
    display: grid;
    place-items: center;
    color: #d8810a;
    font-size: 42px;
  }
  .security-title {
    justify-content: space-between;
    color: #8b4c08;
    font-size: 14px;
  }
  .security-copy p {
    margin: 4px 0 9px;
    color: #8e6b3e;
    font-size: 12px;
  }
  .security-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .security-tags span {
    padding: 2px 8px;
    border: 1px solid #efbc6b;
    border-radius: 3px;
    color: #b56600;
    font-size: 11px;
    background: #fffdf8;
  }
  .sql-panel,
  .usage-panel {
    margin-top: 14px;
  }
  .sql-heading {
    display: flex;
    min-height: 68px;
    box-sizing: border-box;
    align-items: flex-start;
    justify-content: space-between;
    padding: 13px 18px 0;
    border-bottom: 1px solid #e8edf3;
  }
  .sql-tabs {
    display: flex;
    gap: 28px;
    margin-top: 10px;
  }
  .sql-tabs button {
    position: relative;
    padding: 0 4px 11px;
    border: 0;
    color: #5f6b80;
    font: inherit;
    font-size: 12px;
    background: transparent;
    cursor: pointer;
  }
  .sql-tabs button.active {
    color: #2c66f4;
    font-weight: 600;
  }
  .sql-tabs button.active::after {
    position: absolute;
    right: 0;
    bottom: -1px;
    left: 0;
    height: 2px;
    background: #426bf6;
    content: '';
  }
  .sql-workspace {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    padding: 0 10px 10px;
  }
  .sql-editor-shell {
    display: grid;
    grid-template-columns: 44px minmax(0, 1fr);
    min-height: 208px;
    overflow: hidden;
    border-radius: 4px;
    background: #142947;
  }
  .line-numbers {
    margin: 0;
    padding: 14px 12px;
    border-right: 1px solid #2b4160;
    color: #a9b6c9;
    font: 12px/1.9 ui-monospace, SFMono-Regular, Menlo, monospace;
    text-align: right;
  }
  .sql-editor-shell :deep(.n-input),
  .sql-editor-shell :deep(.n-input-wrapper),
  .sql-editor-shell :deep(.n-input__textarea-el) {
    height: 100%;
    color: #f2f6fd;
    font: 13px/1.9 ui-monospace, SFMono-Regular, Menlo, monospace;
    background: transparent;
  }
  .sql-editor-shell :deep(.n-input-wrapper) {
    padding: 9px 13px;
    box-shadow: none !important;
  }
  .result-shell {
    display: flex;
    min-height: 208px;
    overflow: hidden;
    flex-direction: column;
    border: 1px solid #dfe5ed;
    border-radius: 4px;
  }
  .result-meta {
    min-height: 31px;
    box-sizing: border-box;
    padding: 7px 12px;
    border-bottom: 1px solid #e6ebf1;
    color: #667287;
    font-size: 12px;
  }
  .result-meta strong {
    color: #19a36a;
  }
  .result-table-wrap {
    flex: 1;
    overflow: auto;
  }
  .result-table-wrap table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }
  .result-table-wrap th,
  .result-table-wrap td {
    padding: 7px 12px;
    border-right: 1px solid #e2e7ee;
    border-bottom: 1px solid #e2e7ee;
    color: #344054;
    text-align: left;
  }
  .result-table-wrap th {
    color: #526078;
    font-weight: 500;
    background: #f8fafc;
  }
  .result-empty,
  .update-result {
    display: flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    color: #98a2b3;
    font-size: 13px;
  }
  .update-result {
    flex-direction: column;
    gap: 6px;
    color: #667085;
  }
  .update-result strong {
    color: #16a36a;
    font-size: 34px;
  }
  .execution-plan {
    min-height: 30px;
    box-sizing: border-box;
    padding: 7px 12px;
    border-top: 1px solid #e6ebf1;
    color: #58657a;
    font-size: 12px;
  }
  .execution-plan span {
    margin-right: 8px;
  }
  .usage-panel {
    padding: 12px 18px 10px;
  }
  .usage-panel h2 {
    margin-bottom: 10px;
  }
  .usage-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }
  .usage-item {
    min-width: 0;
  }
  .usage-item label {
    display: block;
    margin: 0 0 5px;
    color: #475569;
    font-size: 12px;
  }
  .code-line {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px;
  }
  .code-line code {
    min-width: 0;
    overflow: hidden;
    padding: 8px 10px;
    border: 1px solid #dfe5ee;
    border-radius: 4px;
    color: #315fd8;
    font: 11px/1.35 ui-monospace, SFMono-Regular, Menlo, monospace;
    text-overflow: ellipsis;
    white-space: nowrap;
    background: #fbfcfe;
  }
  .usage-tip {
    gap: 7px;
    margin-top: 12px;
    padding: 8px 10px;
    border: 1px solid #cfe0ff;
    border-radius: 4px;
    color: #3465db;
    font-size: 12px;
    background: #f4f8ff;
  }
  @media (max-width: 1180px) {
    .connection-layout {
      grid-template-columns: 1fr;
    }
    .side-column {
      display: grid;
      grid-template-columns: 1fr 1fr;
    }
  }
  @media (max-width: 900px) {
    .page-header,
    .header-actions {
      align-items: flex-start;
      flex-wrap: wrap;
    }
    .title-line {
      align-items: flex-start;
      flex-direction: column;
      gap: 3px;
    }
    .form-row-primary,
    .form-row-account {
      grid-template-columns: 1fr 1fr;
    }
    .sql-workspace,
    .usage-grid,
    .side-column {
      grid-template-columns: 1fr;
    }
  }
  @media (max-width: 620px) {
    .database-detail-page {
      padding: 12px;
    }
    .form-row,
    .form-row-primary,
    .form-row-address,
    .form-row-account {
      grid-template-columns: 1fr;
    }
    .status-content {
      grid-template-columns: 76px 1fr;
    }
    .status-mark {
      width: 60px;
      height: 60px;
      font-size: 52px;
    }
  }
</style>
