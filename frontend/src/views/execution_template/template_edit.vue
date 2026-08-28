<template>
  <div class="template-edit-page">
    <header class="page-header">
      <div><h2>模板详情</h2><p>定义参数变量并绑定套件，前台将据此生成执行入口</p></div>
      <n-space><n-button @click="router.back()">返回</n-button><n-button v-if="isAdmin" type="primary" :loading="saving" @click="save">保存</n-button></n-space>
    </header>

    <n-form ref="formRef" :model="formValue" :rules="rules" label-placement="top" class="edit-form">
      <section class="detail-card">
        <h3>基本信息</h3>
        <div class="basic-grid">
          <n-form-item label="模板名称" path="name"><n-input v-model:value="formValue.name" :disabled="!isAdmin" placeholder="请输入模板名称" /></n-form-item>
          <n-form-item label="关联套件" path="suite"><n-select v-model:value="formValue.suite" :disabled="!isAdmin" :options="suiteOptions" filterable placeholder="选择要执行的套件" @update:value="loadSourceSteps" /></n-form-item>
          <n-form-item label="模板描述"><n-input v-model:value="formValue.description" :disabled="!isAdmin" placeholder="选填" /></n-form-item>
          <n-form-item label="状态"><n-switch v-model:value="formValue.enabled" :disabled="!isAdmin"><template #checked>启用</template><template #unchecked>停用</template></n-switch></n-form-item>
        </div>
      </section>

      <section class="detail-card">
        <div class="param-head">
          <h3>参数定义</h3>
          <n-button v-if="isAdmin" size="small" @click="addParam">+ 添加参数</n-button>
        </div>
        <div v-if="!parameters.length" class="param-empty">暂无参数，点击「添加参数」创建变量，前台执行时用户按此填写</div>
        <div v-else class="param-list">
          <div v-for="(param, index) in parameters" :key="index" class="param-row">
            <n-input v-model:value="param.label" :disabled="!isAdmin" size="small" placeholder="显示名，如 订单号" class="cell-label" />
            <n-input v-model:value="param.key" :disabled="!isAdmin" size="small" placeholder="变量名，如 order_id" class="cell-key" />
            <n-select v-model:value="param.type" :disabled="!isAdmin" size="small" :options="typeOptions" class="cell-type" />
            <n-select v-if="param.type === 'select'" v-model:value="param.optionsText" :disabled="!isAdmin" size="small" multiple tag filterable placeholder="输入选项后回车" class="cell-options" />
            <n-input v-else v-model:value="param.default_value" :disabled="!isAdmin" size="small" placeholder="默认值" class="cell-default" />
            <label class="cell-required"><n-switch v-model:value="param.required" :disabled="!isAdmin" size="small" /> 必填</label>
            <n-button v-if="isAdmin" size="small" tertiary type="error" @click="removeParam(index)">删除</n-button>
          </div>
        </div>
        <p class="param-tip">变量名对应请求中的 <code>${变量名}</code> 占位符（推荐），同时兼容 <code v-pre>{{变量名}}</code>；执行时用户填写的值会覆盖同名变量。</p>
      </section>

      <section class="detail-card">
        <div class="param-head">
          <div><h3>输出字段</h3><p class="section-tip">执行完成后，从指定接口响应中按 JSONPath 提取并展示结果。</p></div>
          <n-button v-if="isAdmin" size="small" @click="addOutputField">+ 添加字段</n-button>
        </div>
        <div v-if="!outputFields.length" class="param-empty">暂无输出字段，可按“来源接口 + $.data.id”配置执行结果展示。</div>
        <div v-else class="output-list">
          <div v-for="(field, index) in outputFields" :key="index" class="output-row">
            <n-input v-model:value="field.label" :disabled="!isAdmin" size="small" placeholder="展示名称，如 用户 ID" />
            <n-input v-model:value="field.key" :disabled="!isAdmin" size="small" placeholder="字段标识，如 user_id" />
            <n-select v-model:value="field.source_step_id" :disabled="!isAdmin" :options="sourceStepOptions" size="small" placeholder="选择来源接口" filterable />
            <n-input v-model:value="field.json_path" :disabled="!isAdmin" size="small" placeholder="$.data.id" />
            <n-select v-model:value="field.display_type" :disabled="!isAdmin" :options="outputTypeOptions" size="small" />
            <n-button v-if="isAdmin" size="small" tertiary type="error" @click="removeOutputField(index)">删除</n-button>
          </div>
        </div>
      </section>
    </n-form>
  </div>
</template>

<script lang="ts" setup>
  import { computed, onMounted, reactive, ref } from 'vue';
  import { useMessage } from 'naive-ui';
  import { useRoute, useRouter } from 'vue-router';
  import { ExecutionTemplateAPI } from '@/api/execution_template/http';
  import { SuiteAPI } from '@/api/suite/http';
  import { ScenarioStepAPI } from '@/api/case_api/http';
  import { useSubmitRedirect } from '@/hooks/web/useSubmitRedirect';
  import { useUserStore } from '@/store/modules/user';

  const route = useRoute();
  const router = useRouter();
  const message = useMessage();
  const { redirectAfterSubmit } = useSubmitRedirect();
  const userStore = useUserStore();
  const api = new ExecutionTemplateAPI();
  const suiteApi = new SuiteAPI();
  const scenarioStepApi = new ScenarioStepAPI();
  const formRef = ref<any>();
  const id = Number(route.params.id) || 0;
  const saving = ref(false);
  const suiteOptions = ref<any[]>([]);
  const formValue = reactive<any>({ name: '', description: '', suite: null, enabled: true });
  const parameters = ref<any[]>([]);
  const outputFields = ref<any[]>([]);
  const sourceStepOptions = ref<any[]>([]);
  const isAdmin = computed(() => Boolean((userStore.info as any)?.is_admin));
  const typeOptions = [
    { label: '文本', value: 'text' }, { label: '数字', value: 'number' },
    { label: '开关', value: 'boolean' }, { label: '下拉', value: 'select' },
  ];
  const outputTypeOptions = [{ label: '文本', value: 'text' }, { label: 'JSON', value: 'json' }];
  const rules = {
    name: { required: true, message: '请输入模板名称', trigger: 'blur' },
    suite: { required: true, type: 'number', message: '请选择套件', trigger: 'change' },
  };

  function newParam() { return { key: '', label: '', type: 'text', required: false, default_value: '', optionsText: [] }; }
  function addParam() { parameters.value.push(newParam()); }
  function removeParam(index: number) { parameters.value.splice(index, 1); }
  function newOutputField() { return { key: '', label: '', source_step_id: null, json_path: '$.data.id', display_type: 'text', sort: outputFields.value.length + 1 }; }
  function addOutputField() { outputFields.value.push(newOutputField()); }
  function removeOutputField(index: number) { outputFields.value.splice(index, 1); }

  async function loadSourceSteps(suiteId = formValue.suite) {
    sourceStepOptions.value = [];
    if (!suiteId) return;
    const suite: any = await suiteApi.getDataByID(suiteId);
    const scenarioIds = suite.scenarios || [];
    const response: any = await scenarioStepApi.getDataList({ page: 1, pageSize: 999 });
    const steps = (Array.isArray(response) ? response : response?.list || []).filter((step: any) => scenarioIds.includes(step.scenario));
    sourceStepOptions.value = steps.map((step: any) => ({ label: step.name || step.endpoint_name || `接口步骤 #${step.id}`, value: step.id }));
  }

  function normalizeParams() {
    return parameters.value
      .filter((p) => p.key.trim() && p.label.trim())
      .map((p) => ({
        key: p.key.trim(), label: p.label.trim(), type: p.type, required: !!p.required,
        default_value: String(p.default_value ?? ''),
        options: p.type === 'select' ? (p.optionsText || []).map((s: string) => String(s).trim()).filter(Boolean) : [],
      }));
  }

  async function load() {
    const suiteResponse: any = await suiteApi.getDataList({ page: 1, pageSize: 999 });
    const suites = Array.isArray(suiteResponse) ? suiteResponse : suiteResponse?.list || [];
    suiteOptions.value = suites.map((s) => ({ label: s.name, value: s.id }));
    if (id) {
      const data: any = await api.getDataByID(id);
      Object.assign(formValue, { name: data.name, description: data.description, suite: data.suite, enabled: data.enabled });
      parameters.value = (data.parameters || []).map((p: any) => ({
        key: p.key, label: p.label, type: p.type, required: p.required,
        default_value: p.default_value ?? '', optionsText: p.options || [],
      }));
      outputFields.value = (data.output_fields || []).map((field: any, index: number) => ({ ...field, sort: field.sort ?? index + 1 }));
      await loadSourceSteps(data.suite);
    }
  }

  async function save() {
    await formRef.value.validate();
    const params = normalizeParams();
    if (!params.length) { message.warning('请至少添加一个有效参数'); return; }
    const duplicate = params.find((p, i) => params.findIndex((x) => x.key === p.key) !== i);
    if (duplicate) { message.error(`变量名「${duplicate.key}」重复`); return; }
    saving.value = true;
    try {
      const outputs = outputFields.value.map((field: any, index: number) => ({ ...field, key: field.key.trim(), label: field.label.trim(), json_path: field.json_path.trim(), sort: index + 1 }));
      const payload = { name: formValue.name, description: formValue.description, suite: formValue.suite, enabled: formValue.enabled, parameters: params, output_fields: outputs };
      if (id) await api.update(id, payload); else await api.createData(payload);
      message.success('保存成功');
      redirectAfterSubmit({ name: 'template_list' });
    } catch (error: any) {
      message.error(error?.message || '保存失败');
    } finally {
      saving.value = false;
    }
  }

  onMounted(load);
</script>

<style lang="less" scoped>
  .template-edit-page { min-height: 100%; padding: 16px 28px 28px; }
  .page-header { display: flex; align-items: flex-start; justify-content: space-between; max-width: 1440px; margin: 0 auto 14px; }
  .page-header h2 { margin: 0; color: #1d2b3d; font-size: 20px; font-weight: 700; }
  .page-header p { margin: 3px 0 0; color: #8793a5; font-size: 12px; }
  .edit-form { max-width: 1440px; margin: 0 auto; }
  .detail-card { margin-bottom: 14px; overflow: hidden; border: 1px solid #edf1f6; border-radius: 10px; background: #fff; }
  .detail-card > h3, .param-head h3 { margin: 0; padding: 13px 20px; border-bottom: 1px solid #edf1f6; color: #263549; font-size: 15px; font-weight: 650; }
  .basic-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 20px; padding: 12px 20px 14px; }
  .basic-grid :deep(.n-form-item) { margin: 0; }
  .param-head { display: flex; align-items: center; justify-content: space-between; padding-right: 20px; }
  .param-head h3 { border-bottom: 0; }
  .section-tip { margin: -5px 0 12px; padding-left: 20px; color: #8793a5; font-size: 12px; }
  .param-empty { padding: 24px 20px; color: #8793a5; font-size: 13px; }
  .param-list { display: grid; gap: 8px; padding: 14px 20px 16px; }
  .param-row { display: grid; grid-template-columns: 130px 130px 90px minmax(140px, 1fr) 72px 48px; gap: 8px; align-items: center; }
  .output-list { display: grid; gap: 8px; padding: 14px 20px 16px; }
  .output-row { display: grid; grid-template-columns: 130px 130px minmax(160px, 1fr) 150px 90px 48px; gap: 8px; align-items: center; }
  .cell-required { display: flex; align-items: center; gap: 4px; font-size: 12px; color: #445268; white-space: nowrap; }
  .param-tip { margin: 0; padding: 0 20px 16px; color: #8793a5; font-size: 12px; }
  .param-tip code { padding: 1px 4px; border-radius: 3px; color: #2563eb; background: #eef5ff; }
  @media (max-width: 900px) {
    .basic-grid { grid-template-columns: 1fr; }
    .param-row { grid-template-columns: 1fr 1fr; }
    .output-row { grid-template-columns: 1fr 1fr; }
  }
</style>
