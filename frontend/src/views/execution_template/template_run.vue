<template>
  <div class="run-page">
    <n-spin :show="loading">
      <template v-if="template">
        <header class="page-header">
          <div class="page-heading">
            <nav class="breadcrumb" aria-label="面包屑">
              <span>执行</span>
              <span>/</span>
              <button type="button" class="breadcrumb-link" @click="router.back()">模块管理</button>
              <span>/</span>
              <strong>执行详情</strong>
            </nav>
            <h2>{{ template.name }}</h2>
            <p
              >套件：{{ template.suite_name }} <span>·</span> 默认环境：{{
                template.environment_name || '-'
              }}</p
            >
          </div>
          <n-button class="back-button" size="large" @click="router.back()">
            <template #icon><PhArrowLeft :size="18" /></template>
            返回模板管理
          </n-button>
        </header>

        <main class="workspace">
          <n-form label-placement="top" class="run-form">
            <section class="execution-card">
              <div class="card-head">
                <div class="card-icon"><PhSlidersHorizontal :size="28" weight="bold" /></div>
                <div>
                  <h3>执行配置</h3>
                  <p>配置本次运行环境与输入参数</p>
                </div>
              </div>

              <div class="execution-body">
                <div class="environment-section">
                  <label class="section-label">执行环境</label>
                  <div class="environment-control">
                    <n-select
                      v-model:value="environmentId"
                      :options="environmentOptions"
                      placeholder="选择执行环境"
                    />
                    <span v-if="selectedEnvironmentIsDefault" class="default-environment"
                      >默认环境</span
                    >
                  </div>
                </div>

                <div class="section-divider"></div>

                <div class="parameter-head">
                  <h4>运行参数</h4>
                  <span class="count-badge">{{ template.parameters?.length || 0 }}</span>
                </div>

                <div v-if="template.parameters?.length" class="parameter-list">
                  <div v-for="param in template.parameters" :key="param.key" class="parameter-row">
                    <div class="parameter-label">
                      <span>{{ param.label || param.key }}</span>
                      <i v-if="param.required">*</i>
                    </div>
                    <div class="parameter-control">
                      <n-switch v-if="param.type === 'boolean'" v-model:value="params[param.key]" />
                      <n-input-number
                        v-else-if="param.type === 'number'"
                        v-model:value="params[param.key]"
                        style="width: 100%"
                      />
                      <n-select
                        v-else-if="param.type === 'select'"
                        v-model:value="params[param.key]"
                        :options="(param.options || []).map((o: string) => ({ label: o, value: o }))"
                        :placeholder="`请选择${param.label || param.key}`"
                      />
                      <n-input
                        v-else
                        v-model:value="params[param.key]"
                        :placeholder="`请输入${param.label || param.key}`"
                      />
                      <p v-if="param.description">{{ param.description }}</p>
                    </div>
                  </div>
                </div>
                <n-empty v-else description="当前模板未配置运行参数" class="parameter-empty" />
              </div>

              <footer class="run-actions">
                <span class="run-hint"
                  ><PhInfo :size="18" weight="fill" />将使用本次填写的参数运行关联套件</span
                >
                <n-button type="primary" size="large" :loading="running" @click="run">
                  <template #icon><PhPlay :size="18" weight="fill" /></template>
                  执行
                </n-button>
              </footer>
            </section>
          </n-form>

          <aside class="output-card">
            <div class="output-head">
              <div class="output-title"
                ><PhDatabase :size="28" weight="bold" /><h3>输出结果</h3></div
              >
              <n-tag
                :type="resultId ? (outputActive ? 'info' : 'success') : 'default'"
                size="small"
                round
              >
                {{ resultId ? (outputActive ? '执行中' : outputStatus || '执行完成') : '等待执行' }}
              </n-tag>
            </div>

            <div class="output-content">
              <div v-if="resultId" class="result-meta">执行编号 #{{ resultId }}</div>
              <n-spin v-if="outputActive" size="small" class="output-spinner" />
              <div v-if="resultId && outputFields.length" class="output-grid">
                <template v-for="field in outputFields" :key="field.key">
                  <div class="output-label">{{ field.label }}</div>
                  <div class="output-value" :class="{ 'has-error': field.error }">
                    <template v-if="field.error">{{ field.error }}</template>
                    <pre v-else-if="field.display_type === 'json'">{{
                      formatValue(field.value)
                    }}</pre>
                    <span v-else>{{ formatValue(field.value) }}</span>
                  </div>
                </template>
              </div>
              <div v-else class="output-empty">
                <div class="empty-illustration"
                  ><PhFileText :size="72" weight="light" /><span>•••</span></div
                >
                <h4>{{ resultId ? '暂无输出字段' : '暂无执行结果' }}</h4>
                <p>{{
                  resultId ? '当前模板未配置输出字段' : '执行完成后将在这里展示配置的输出字段'
                }}</p>
              </div>

              <div v-if="template.output_fields?.length" class="configured-output">
                <div class="configured-output-title">
                  <span>输出字段</span>
                  <b>{{ template.output_fields.length }}</b>
                </div>
                <div class="field-chips">
                  <span v-for="field in template.output_fields" :key="field.key">{{
                    field.label || field.key
                  }}</span>
                </div>
              </div>
            </div>
          </aside>
        </main>

        <p class="page-note"
          ><PhInfo :size="17" weight="fill" />模板参数仅用于本次执行，不会修改模板配置</p
        >
      </template>
      <n-empty v-else-if="!loading" description="模板不存在或已被删除" class="empty" />
    </n-spin>
  </div>
</template>

<script lang="ts" setup>
  import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
  import { useMessage } from 'naive-ui';
  import { useRoute, useRouter } from 'vue-router';
  import { ExecutionTemplateAPI } from '@/api/execution_template/http';
  import { EnvironmentAPI } from '@/api/project/http';
  import {
    PhArrowLeft,
    PhDatabase,
    PhFileText,
    PhInfo,
    PhPlay,
    PhSlidersHorizontal,
  } from '@phosphor-icons/vue';

  const route = useRoute();
  const router = useRouter();
  const message = useMessage();
  const api = new ExecutionTemplateAPI();
  const environmentApi = new EnvironmentAPI();
  const id = Number(route.params.id);
  const loading = ref(false);
  const running = ref(false);
  const template = ref<any>(null);
  const environmentId = ref<number | null>(null);
  const environmentOptions = ref<any[]>([]);
  const params = reactive<Record<string, any>>({});
  const selectedEnvironmentIsDefault = computed(
    () => Number(environmentId.value) === Number(template.value?.environment_id)
  );
  const resultId = ref<number | null>(null);
  const outputFields = ref<any[]>([]);
  const outputStatus = ref('');
  const outputActive = ref(false);
  let outputPollTimer: ReturnType<typeof setInterval> | null = null;

  const environmentNames = ['Dev', 'Test', 'Pre', 'Prod'];

  async function load() {
    loading.value = true;
    try {
      template.value = await api.getDataByID(id);
      // 初始化参数默认值
      for (const p of template.value.parameters || []) {
        const def = p.default_value ?? '';
        params[p.key] =
          p.type === 'boolean'
            ? def === 'true' || def === true
            : p.type === 'number'
            ? Number(def) || 0
            : def;
      }
      // 环境列表：仅套件环境所在项目
      const environmentResponse: any = await environmentApi.getDataList({ page: 1, pageSize: 999 });
      const environments = Array.isArray(environmentResponse)
        ? environmentResponse
        : environmentResponse?.list || [];
      const projectId = template.value.project;
      environmentOptions.value = environments
        .filter((e) => Number(e.project) === Number(projectId) && environmentNames.includes(e.name))
        .sort((a, b) => environmentNames.indexOf(a.name) - environmentNames.indexOf(b.name))
        .map((e) => ({ label: e.name, value: e.id }));
      environmentId.value =
        template.value.environment_id || environmentOptions.value[0]?.value || null;
    } catch (error: any) {
      message.error(error?.message || '加载失败');
      template.value = null;
    } finally {
      loading.value = false;
    }
  }

  async function run() {
    const missing = (template.value.parameters || []).filter(
      (p: any) => p.required && !String(params[p.key] ?? '').trim()
    );
    if (missing.length) {
      message.warning(`请填写必填参数：${missing.map((p: any) => p.label || p.key).join('、')}`);
      return;
    }
    running.value = true;
    try {
      const resp = await api.runById(id, { ...params }, environmentId.value);
      resultId.value = resp.result_id;
      outputFields.value = [];
      message.success(`任务已提交，结果ID: ${resp.result_id}`);
      await refreshOutput();
      if (outputPollTimer) clearInterval(outputPollTimer);
      outputPollTimer = setInterval(refreshOutput, 1500);
    } catch (error: any) {
      message.error(error?.message || '执行失败');
    } finally {
      running.value = false;
    }
  }

  async function refreshOutput() {
    if (!resultId.value) return;
    try {
      const output = await api.getOutput(id, resultId.value);
      outputFields.value = output.fields || [];
      outputStatus.value = output.status;
      outputActive.value = output.active;
      if (!output.active && outputPollTimer) {
        clearInterval(outputPollTimer);
        outputPollTimer = null;
      }
    } catch (error: any) {
      outputActive.value = false;
      if (outputPollTimer) clearInterval(outputPollTimer);
      outputPollTimer = null;
      message.error(error?.message || '输出结果加载失败');
    }
  }

  function formatValue(value: unknown) {
    if (value === null || value === undefined || value === '') return '-';
    return typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
  }

  onMounted(load);
  onBeforeUnmount(() => {
    if (outputPollTimer) clearInterval(outputPollTimer);
  });
</script>

<style lang="less" scoped>
  .run-page {
    min-height: 100%;
    padding: 28px 34px 34px;
    background: #f7f9fc;
  }

  .page-header,
  .workspace,
  .page-note {
    max-width: 1280px;
    margin-right: auto;
    margin-left: auto;
  }

  .page-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 32px;
    margin-bottom: 24px;
  }

  .page-heading {
    min-width: 0;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 24px;
    color: #9aa8bc;
    font-size: 13px;
  }

  .breadcrumb strong {
    color: #4a5b72;
    font-weight: 600;
  }

  .breadcrumb-link {
    padding: 0;
    border: 0;
    color: #7a899d;
    background: transparent;
    cursor: pointer;
    font: inherit;
  }

  .breadcrumb-link:hover {
    color: #3d63f3;
  }

  .page-header h2 {
    margin: 0;
    color: #182338;
    font-size: 30px;
    font-weight: 700;
    letter-spacing: -0.025em;
  }

  .page-header p {
    margin: 9px 0 0;
    color: #7e8da3;
    font-size: 14px;
  }

  .page-header p span {
    margin: 0 8px;
    color: #c2cad6;
  }

  .back-button {
    min-width: 146px;
    --n-border: 1px solid #3d63f3 !important;
    --n-border-hover: 1px solid #2f55e9 !important;
    --n-border-pressed: 1px solid #2f55e9 !important;
    --n-color: #fff !important;
    --n-color-hover: #f6f8ff !important;
    --n-text-color: #3d63f3 !important;
    --n-text-color-hover: #2f55e9 !important;
    --n-border-radius: 8px !important;
  }

  .workspace {
    display: grid;
    grid-template-columns: minmax(0, 1.62fr) minmax(390px, 1fr);
    gap: 24px;
    align-items: stretch;
  }

  .run-form {
    min-width: 0;
  }

  .execution-card,
  .output-card {
    overflow: hidden;
    border: 1px solid #dfe6ef;
    border-radius: 12px;
    background: #fff;
    box-shadow: 0 4px 14px rgba(31, 51, 82, 0.025);
  }

  .execution-card {
    display: flex;
    flex-direction: column;
    min-height: 572px;
  }

  .card-head {
    display: flex;
    align-items: center;
    gap: 15px;
    padding: 28px 28px 24px;
  }

  .card-icon {
    display: grid;
    flex: 0 0 38px;
    width: 38px;
    height: 38px;
    place-items: center;
    color: #2f67f4;
  }

  .card-head h3,
  .output-head h3 {
    margin: 0;
    color: #182438;
    font-size: 20px;
    font-weight: 700;
  }

  .card-head p {
    margin: 4px 0 0;
    color: #8a98ab;
    font-size: 13px;
  }

  .execution-body {
    flex: 1;
    padding: 0 28px 24px;
  }

  .environment-section {
    padding-top: 3px;
  }

  .section-label {
    display: block;
    margin-bottom: 12px;
    color: #293a50;
    font-size: 14px;
    font-weight: 650;
  }

  .environment-control {
    position: relative;
  }

  .environment-control :deep(.n-base-selection) {
    min-height: 46px;
    border-radius: 7px;
  }

  .environment-control :deep(.n-base-selection-label) {
    padding-right: 108px;
  }

  .default-environment {
    position: absolute;
    top: 50%;
    right: 42px;
    z-index: 2;
    padding: 4px 10px;
    transform: translateY(-50%);
    border-radius: 5px;
    color: #2b9a5b;
    background: #ecf8f0;
    font-size: 12px;
    pointer-events: none;
  }

  .section-divider {
    height: 1px;
    margin: 26px 0 24px;
    background: #e7ecf3;
  }

  .parameter-head {
    display: flex;
    align-items: center;
    gap: 9px;
    margin-bottom: 14px;
  }

  .parameter-head h4 {
    margin: 0;
    color: #293a50;
    font-size: 15px;
    font-weight: 700;
  }

  .count-badge,
  .configured-output-title b {
    display: inline-grid;
    min-width: 30px;
    height: 24px;
    padding: 0 8px;
    place-items: center;
    border-radius: 12px;
    color: #2f67f4;
    background: #edf3ff;
    font-size: 12px;
    font-style: normal;
    font-weight: 700;
  }

  .parameter-list {
    overflow: hidden;
    border: 1px solid #e0e6ee;
    border-radius: 8px;
  }

  .parameter-row {
    display: grid;
    grid-template-columns: minmax(150px, 36%) minmax(0, 1fr);
    align-items: center;
    min-height: 74px;
    padding: 12px 16px;
    border-bottom: 1px solid #e8edf3;
  }

  .parameter-row:last-child {
    border-bottom: 0;
  }

  .parameter-label {
    color: #2b3b50;
    font-size: 14px;
    font-weight: 600;
  }

  .parameter-label i {
    margin-left: 4px;
    color: #e34352;
    font-style: normal;
  }

  .parameter-control {
    min-width: 0;
  }

  .parameter-control :deep(.n-input),
  .parameter-control :deep(.n-base-selection) {
    min-height: 42px;
    border-radius: 6px;
  }

  .parameter-control p {
    margin: 6px 0 -2px;
    color: #8796aa;
    font-size: 12px;
  }

  .parameter-empty {
    padding: 38px 0 28px;
  }

  .run-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    padding: 18px 28px;
    border-top: 1px solid #e7ecf3;
    background: #fbfcfe;
  }

  .run-hint {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: #75869c;
    font-size: 13px;
  }

  .run-hint svg {
    flex: 0 0 auto;
    color: #7087aa;
  }

  .run-actions :deep(.n-button) {
    min-width: 132px;
    height: 46px;
    border-radius: 7px;
  }

  .output-card {
    display: flex;
    flex-direction: column;
    min-height: 572px;
  }

  .output-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 88px;
    padding: 0 26px;
    border-bottom: 1px solid #e7ecf3;
  }

  .output-title {
    display: flex;
    align-items: center;
    gap: 14px;
    color: #2f67f4;
  }

  .output-content {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-height: 0;
    padding: 24px;
  }

  .result-meta {
    margin-bottom: 16px;
    color: #8391a5;
    font-size: 12px;
  }

  .output-grid {
    display: grid;
    grid-template-columns: 40% minmax(0, 1fr);
    overflow: hidden;
    margin-bottom: 20px;
    border: 1px solid #e3e8f0;
    border-radius: 8px;
  }

  .output-label,
  .output-value {
    min-height: 58px;
    padding: 17px 18px;
    border-bottom: 1px solid #e8edf4;
    font-size: 13px;
    line-height: 1.5;
  }

  .output-label:nth-last-child(2),
  .output-value:last-child {
    border-bottom: 0;
  }

  .output-label {
    color: #64748b;
    background: #fafbfd;
    font-weight: 600;
  }

  .output-value {
    overflow-wrap: anywhere;
    color: #26384f;
    font-weight: 600;
  }

  .output-value.has-error {
    color: #c53c3c;
  }

  .output-value pre {
    margin: 0;
    white-space: pre-wrap;
    font: 12px/1.6 ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  .output-empty {
    display: flex;
    flex: 1;
    align-items: center;
    flex-direction: column;
    justify-content: center;
    min-height: 270px;
    padding: 36px 16px 28px;
    text-align: center;
  }

  .empty-illustration {
    position: relative;
    display: grid;
    width: 126px;
    height: 126px;
    margin-bottom: 22px;
    place-items: center;
    border-radius: 50%;
    color: #2f67f4;
    background: #f2f6ff;
  }

  .empty-illustration span {
    position: absolute;
    right: 12px;
    bottom: 14px;
    display: grid;
    width: 38px;
    height: 38px;
    place-items: center;
    border: 2px solid #2f67f4;
    border-radius: 50%;
    color: #2f67f4;
    background: #fff;
    font-size: 13px;
    letter-spacing: 1px;
  }

  .output-empty h4 {
    margin: 0 0 10px;
    color: #1d2b40;
    font-size: 17px;
    font-weight: 700;
  }

  .output-empty p {
    margin: 0;
    color: #8392a7;
    font-size: 13px;
  }

  .output-spinner {
    display: block;
    margin: 6px auto 0;
  }

  .configured-output {
    margin-top: auto;
    padding: 18px;
    border: 1px solid #dce5f3;
    border-radius: 8px;
    background: #fbfdff;
  }

  .configured-output-title {
    display: flex;
    align-items: center;
    gap: 9px;
    margin-bottom: 14px;
    color: #2c3b50;
    font-size: 14px;
    font-weight: 700;
  }

  .field-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 9px;
  }

  .field-chips span {
    padding: 6px 12px;
    border: 1px solid #d9e1ec;
    border-radius: 6px;
    color: #53657b;
    background: #fff;
    font-size: 12px;
  }

  .page-note {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 22px;
    color: #8493a7;
    font-size: 13px;
  }

  .page-note svg {
    color: #7890b3;
  }

  .empty {
    padding: 80px 0;
  }

  @media (max-width: 1000px) {
    .workspace {
      grid-template-columns: 1fr;
    }

    .output-card {
      min-height: 500px;
    }
  }

  @media (max-width: 640px) {
    .run-page {
      padding: 20px 16px 28px;
    }

    .page-header {
      align-items: flex-start;
      flex-direction: column;
      gap: 18px;
    }

    .breadcrumb {
      margin-bottom: 16px;
    }

    .page-header h2 {
      font-size: 25px;
    }

    .back-button {
      width: 100%;
    }

    .card-head,
    .execution-body,
    .output-content {
      padding-right: 20px;
      padding-left: 20px;
    }

    .parameter-row {
      grid-template-columns: 1fr;
      gap: 10px;
      padding: 16px;
    }

    .run-actions {
      align-items: stretch;
      flex-direction: column;
      padding: 18px 20px;
    }

    .run-actions :deep(.n-button) {
      width: 100%;
    }

    .output-grid {
      grid-template-columns: 1fr;
    }

    .output-label {
      padding-bottom: 4px;
      border-bottom: 0;
    }

    .output-value {
      padding-top: 4px;
    }
  }
</style>
