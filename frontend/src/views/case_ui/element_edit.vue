<template>
  <div class="element-editor-page">
    <header class="page-header">
      <div>
        <div class="breadcrumb"
          ><span>UI 测试</span><i>/</i><span>元素管理</span><i>/</i
          ><strong>{{ dataId ? '编辑元素' : '新增元素' }}</strong></div
        >
        <h1>{{ dataId ? '编辑元素' : '新增元素' }}</h1>
        <p>维护元素归属与 Selenium 定位配置</p>
      </div>
      <n-space
        ><n-button @click="goBack">返回</n-button
        ><n-button type="primary" :loading="saving" @click="formSubmit">保存元素</n-button></n-space
      >
    </header>

    <n-form ref="formRef" :model="formValue" :rules="rules" label-placement="top">
      <section class="editor-card basic-card">
        <div class="card-heading"><h2>基本信息</h2><span>定义元素名称和目录归属</span></div>
        <div class="basic-grid">
          <n-form-item label="元素名称" path="name">
            <n-input v-model:value="formValue.name" placeholder="例如：登录按钮" maxlength="32" />
          </n-form-item>
          <n-form-item label="关联项目" path="project">
            <n-select
              v-model:value="formValue.project"
              :options="projectOptions"
              filterable
              placeholder="请选择项目"
              @update:value="handleProjectChange"
            />
          </n-form-item>
          <n-form-item label="所属模块" path="module">
            <n-select
              v-model:value="formValue.module"
              :options="moduleOptions"
              :disabled="!formValue.project"
              filterable
              placeholder="请选择模块"
            />
          </n-form-item>
        </div>
      </section>

      <div class="content-grid">
        <section class="editor-card locator-card">
          <div class="card-heading"><h2>定位配置</h2><span>配置元素的主定位表达式</span></div>
          <div class="locator-body">
            <div class="locator-method-row">
              <n-form-item label="定位方式" path="by" :show-feedback="false">
                <n-select
                  v-model:value="formValue.by"
                  :options="byOptions"
                  placeholder="请选择定位方式"
                />
              </n-form-item>
              <div class="method-summary">
                <span class="method-badge">{{ currentLocator?.label }}</span>
                <span>{{ currentLocator?.description }}</span>
              </div>
            </div>
            <n-form-item label="定位表达式" path="value" class="expression-field">
              <div class="expression-panel">
                <div class="expression-toolbar">
                  <div class="expression-meta">
                    <span class="status-dot"></span>
                    <span>{{ currentLocator?.label }} 表达式</span>
                  </div>
                  <n-space size="small">
                    <n-button size="small" @click="openElementRecognizer">粘贴元素识别</n-button>
                    <n-button size="small" @click="formatExpression">格式化</n-button>
                    <n-button size="small" type="primary" ghost @click="validateExpression">
                      验证表达式
                    </n-button>
                  </n-space>
                </div>
                <div class="code-input">
                  <span class="line-number">1</span>
                  <n-input
                    v-model:value="formValue.value"
                    type="textarea"
                    :autosize="{ minRows: 5, maxRows: 9 }"
                    :placeholder="locatorPlaceholder"
                  />
                </div>
                <div class="expression-help">
                  <span class="help-icon">i</span>
                  <span>{{ locatorTip }}</span>
                </div>
              </div>
            </n-form-item>
          </div>
        </section>

        <aside class="side-column">
          <section class="editor-card strategy-card">
            <div class="card-heading"><h2>支持的定位方式</h2></div>
            <div class="strategy-list">
              <button
                v-for="item in byOptions"
                :key="item.value"
                type="button"
                :class="['strategy-item', { active: formValue.by === item.value }]"
                @click="formValue.by = item.value"
              >
                <span class="strategy-code">{{ item.short }}</span>
                <span
                  ><strong>{{ item.label }}</strong
                  ><small>{{ item.description }}</small></span
                >
                <i v-if="formValue.by === item.value">当前</i>
              </button>
            </div>
          </section>
          <div class="locator-advice"
            >建议优先使用 ID 或稳定的业务属性，避免依赖容易变化的层级 XPath。</div
          >
        </aside>
      </div>
    </n-form>

    <n-modal v-model:show="recognizerVisible" :mask-closable="false">
      <n-card class="recognizer-dialog" title="粘贴元素并识别" :bordered="false" role="dialog">
        <p class="recognizer-intro">
          从浏览器开发者工具复制完整元素 HTML，系统会优先生成稳定的定位表达式。
        </p>
        <n-input
          v-model:value="elementHtml"
          type="textarea"
          :autosize="{ minRows: 8, maxRows: 14 }"
          placeholder='例如：&lt;button data-testid="create-user"&gt;创建用户&lt;/button&gt;'
        />
        <div v-if="recognitionPreview" class="recognition-preview">
          <span>将使用</span>
          <strong>{{ recognitionPreview.by }}</strong>
          <code>{{ recognitionPreview.value }}</code>
        </div>
        <template #footer>
          <n-space justify="end">
            <n-button @click="recognizerVisible = false">取消</n-button>
            <n-button type="primary" @click="recognizeAndApply">识别并应用</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>
  </div>
</template>

<script lang="ts" setup>
import { asList } from '@/utils/list';

  import { computed, onMounted, reactive, ref } from 'vue';
  import { useRoute, useRouter } from 'vue-router';
  import { useMessage } from 'naive-ui';
  import { useSubmitRedirect } from '@/hooks/web/useSubmitRedirect';
  import { ModuleAPI, ProjectAPI } from '@/api/project/http';
  import { ElementAPI } from '@/api/case_ui/http';

  const route = useRoute();
  const router = useRouter();
  const message = useMessage();
  const { redirectAfterSubmit } = useSubmitRedirect();
  const dataId = Number(route.params.id);
  const formRef = ref<any>();
  const saving = ref(false);
  const recognizerVisible = ref(false);
  const elementHtml = ref('');
  const recognitionPreview = ref<{ by: string; value: string } | null>(null);
  const api = new ElementAPI();
  const moduleApi = new ModuleAPI();
  const projectApi = new ProjectAPI();
  const projects = ref<any[]>([]);
  const modules = ref<any[]>([]);
  const formValue = reactive<any>({
    project: null,
    module: null,
    name: '',
    by: 'XPATH',
    value: '',
  });
  const rules = {
    project: { required: true, type: 'number', message: '请选择项目', trigger: 'change' },
    module: { required: true, type: 'number', message: '请选择模块', trigger: 'change' },
    name: { required: true, message: '请输入元素名称', trigger: 'blur' },
    by: { required: true, message: '请选择定位方式', trigger: 'change' },
    value: { required: true, message: '请输入定位表达式', trigger: 'blur' },
  };
  const byOptions = [
    { label: 'ID', value: 'ID', short: 'ID', description: '使用元素唯一 ID' },
    { label: 'Name', value: 'NAME', short: 'N', description: '使用 name 属性' },
    { label: 'Class Name', value: 'CLASS_NAME', short: 'C', description: '使用单个 class 名称' },
    { label: 'Link Text', value: 'LINK_TEXT', short: 'L', description: '使用链接完整文本' },
    { label: 'CSS Selector', value: 'CSS_SELECTOR', short: '#', description: '使用 CSS 选择器' },
    { label: 'XPath', value: 'XPATH', short: '/', description: '使用 XPath 表达式' },
  ];
  const locatorExamples: Record<string, { placeholder: string; tip: string }> = {
    ID: { placeholder: 'login-button', tip: '填写元素的 id 属性值，不需要添加 #。' },
    NAME: { placeholder: 'username', tip: '填写元素的 name 属性值。' },
    CLASS_NAME: { placeholder: 'submit-button', tip: '仅填写一个 class 名称，不支持空格组合。' },
    LINK_TEXT: { placeholder: '立即登录', tip: '填写链接元素的完整可见文本。' },
    CSS_SELECTOR: {
      placeholder: "[data-testid='login-submit']",
      tip: '支持标准 CSS Selector，建议使用稳定的 data-* 属性。',
    },
    XPATH: {
      placeholder: "//button[@type='submit']",
      tip: '支持标准 XPath，避免依赖过深的 DOM 层级。',
    },
  };
  const locatorPlaceholder = computed(
    () => locatorExamples[formValue.by]?.placeholder || '请输入定位表达式'
  );
  const currentLocator = computed(() => byOptions.find((item) => item.value === formValue.by));
  const locatorTip = computed(
    () => locatorExamples[formValue.by]?.tip || '表达式必须与定位方式匹配。'
  );
  const projectOptions = computed(() =>
    projects.value.map((item) => ({ label: item.name, value: item.id }))
  );
  const moduleOptions = computed(() =>
    modules.value
      .filter((item) => item.project === formValue.project)
      .map((item) => ({ label: item.name, value: item.id }))
  );

  
  function handleProjectChange() {
    if (!moduleOptions.value.some((item) => item.value === formValue.module))
      formValue.module = null;
  }
  function formatExpression() {
    formValue.value = String(formValue.value || '').trim();
  }
  function xpathLiteral(value: string) {
    if (!value.includes("'")) return `'${value}'`;
    if (!value.includes('"')) return `"${value}"`;
    return `concat('${value.replace(/'/g, `', "'", '`)}')`;
  }
  function cssAttributeValue(value: string) {
    return value.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  }
  function cssClassName(value: string) {
    return value.replace(/([^a-zA-Z0-9_-])/g, '\\$1');
  }
  function buildLocatorFromHtml(html: string) {
    const documentNode = new DOMParser().parseFromString(html.trim(), 'text/html');
    const element = documentNode.body.firstElementChild as HTMLElement | null;
    if (!element) throw new Error('未识别到有效的 HTML 元素');

    const id = element.getAttribute('id')?.trim();
    if (id) return { by: 'ID', value: id, text: element.textContent?.trim() || '' };

    for (const attribute of ['data-testid', 'data-test-id', 'data-test', 'data-qa', 'data-cy']) {
      const value = element.getAttribute(attribute)?.trim();
      if (value)
        return {
          by: 'CSS_SELECTOR',
          value: `[${attribute}="${cssAttributeValue(value)}"]`,
          text: element.textContent?.trim() || '',
        };
    }

    const name = element.getAttribute('name')?.trim();
    if (name) return { by: 'NAME', value: name, text: element.textContent?.trim() || '' };

    const text = (element.textContent || '').replace(/\s+/g, ' ').trim();
    const tag = element.tagName.toLowerCase();
    if (tag === 'a' && text) return { by: 'LINK_TEXT', value: text, text };
    if (text && ['button', 'label', 'option', 'summary'].includes(tag)) {
      return { by: 'XPATH', value: `//${tag}[normalize-space(.)=${xpathLiteral(text)}]`, text };
    }

    const stableClasses = Array.from(element.classList)
      .filter((item) => !/[\[\]:/]/.test(item) && !/^\d/.test(item))
      .slice(0, 3);
    if (stableClasses.length) {
      return {
        by: 'CSS_SELECTOR',
        value: `${tag}.${stableClasses.map(cssClassName).join('.')}`,
        text,
      };
    }
    return { by: 'CSS_SELECTOR', value: tag, text };
  }
  async function openElementRecognizer() {
    recognitionPreview.value = null;
    recognizerVisible.value = true;
    if (elementHtml.value.trim() || !navigator.clipboard?.readText) return;
    try {
      const clipboardText = await navigator.clipboard.readText();
      if (clipboardText.trim().startsWith('<')) elementHtml.value = clipboardText;
    } catch (_) {
      // 浏览器未授权读取剪贴板时，仍可在弹窗中手动粘贴。
    }
  }
  function recognizeAndApply() {
    try {
      const result = buildLocatorFromHtml(elementHtml.value);
      recognitionPreview.value = { by: result.by, value: result.value };
      formValue.by = result.by;
      formValue.value = result.value;
      if (!formValue.name && result.text) formValue.name = result.text.slice(0, 32);
      recognizerVisible.value = false;
      message.success(`已识别为 ${result.by} 定位`);
    } catch (error: any) {
      message.error(error?.message || '元素识别失败');
    }
  }
  function validateExpression() {
    const value = String(formValue.value || '').trim();
    if (!value) return message.warning('请先填写定位表达式');
    if (formValue.by === 'CLASS_NAME' && /\s/.test(value))
      return message.error('Class Name 只能填写一个类名，不能包含空格');
    if (formValue.by === 'XPATH' && !/^(\/\/|\.|\(|\/)/.test(value))
      return message.error('XPath 表达式格式不正确');
    message.success('表达式格式校验通过');
  }
  function goBack() {
    router.push({ name: 'case_ui_element' });
  }
  async function load() {
    const [projectResponse, moduleResponse] = await Promise.all([
      projectApi.getDataList({ pageSize: 1000 }),
      moduleApi.getDataList({ pageSize: 1000 }),
    ]);
    projects.value = asList(projectResponse);
    modules.value = asList(moduleResponse);
    if (dataId) Object.assign(formValue, await api.getDataByID(dataId));
    else {
      formValue.project = Number(route.query.project) || null;
      formValue.module = Number(route.query.module) || null;
    }
  }
  async function formSubmit() {
    try {
      await formRef.value?.validate();
      saving.value = true;
      const payload = {
        project: formValue.project,
        module: formValue.module,
        name: formValue.name.trim(),
        by: formValue.by,
        value: formValue.value.trim(),
      };
      if (dataId) await api.update(dataId, payload as any);
      else await api.createData(payload as any);
      message.success('元素保存成功');
      redirectAfterSubmit({ name: 'case_ui_element' });
    } catch (error: any) {
      message.error(error?.message || '保存失败，请检查配置');
    } finally {
      saving.value = false;
    }
  }
  onMounted(load);
</script>

<style scoped lang="less">
  .element-editor-page {
    min-height: 100%;
    padding: 20px 28px 36px;
    background: #f6f8fb;
    color: #172033;
  }
  .page-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    max-width: 1440px;
    margin: 0 auto 18px;
  }
  .breadcrumb {
    display: flex;
    gap: 9px;
    align-items: center;
    margin-bottom: 13px;
    color: #7b8798;
    font-size: 13px;
  }
  .breadcrumb i {
    color: #aab3c0;
    font-style: normal;
  }
  .breadcrumb strong {
    color: #344054;
  }
  .page-header h1 {
    margin: 0;
    font-size: 27px;
    font-weight: 700;
    letter-spacing: -0.4px;
  }
  .page-header p {
    margin: 7px 0 0;
    color: #758297;
    font-size: 13px;
  }
  .page-header :deep(.n-button) {
    min-width: 108px;
    height: 40px;
  }
  .editor-card {
    overflow: hidden;
    border: 1px solid #dce3ed;
    border-radius: 9px;
    background: #fff;
  }
  .basic-card {
    max-width: 1440px;
    margin: 0 auto 14px;
  }
  .card-heading {
    display: flex;
    gap: 16px;
    align-items: baseline;
    min-height: 58px;
    padding: 17px 20px;
    box-sizing: border-box;
    border-bottom: 1px solid #edf1f5;
  }
  .card-heading h2 {
    margin: 0;
    color: #202b3d;
    font-size: 17px;
    font-weight: 650;
  }
  .card-heading span {
    color: #8a96a8;
    font-size: 12px;
  }
  .basic-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 20px;
    padding: 18px 20px 12px;
  }
  .content-grid {
    display: grid;
    grid-template-columns: minmax(0, 2.2fr) minmax(310px, 0.8fr);
    gap: 14px;
    max-width: 1440px;
    margin: 0 auto;
  }
  .locator-body {
    padding: 20px 22px 24px;
  }
  .locator-method-row {
    display: grid;
    grid-template-columns: minmax(240px, 360px) minmax(0, 1fr);
    gap: 18px;
    align-items: end;
    padding-bottom: 20px;
    border-bottom: 1px solid #edf1f5;
  }
  .locator-method-row :deep(.n-form-item) {
    margin-bottom: 0;
  }
  .method-summary {
    display: flex;
    gap: 10px;
    align-items: center;
    min-height: 34px;
    color: #7b8798;
    font-size: 12px;
  }
  .method-badge {
    padding: 4px 9px;
    border: 1px solid #ccdafd;
    border-radius: 5px;
    background: #f2f6ff;
    color: #2f64e8;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 650;
  }
  .field-tip {
    margin-top: 7px;
    color: #8793a6;
    font-size: 12px;
    line-height: 1.5;
  }
  .code-input {
    display: grid;
    grid-template-columns: 52px 1fr;
    overflow: hidden;
    width: 100%;
    border-top: 1px solid #2e3746;
    border-radius: 0;
    background: #202733;
  }
  .line-number {
    padding-top: 13px;
    border-right: 1px solid #364052;
    color: #8290a5;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    text-align: center;
  }
  .code-input :deep(.n-input) {
    --n-border: none !important;
    --n-border-hover: none !important;
    --n-border-focus: none !important;
    --n-box-shadow-focus: none !important;
    --n-color: #202733 !important;
    --n-color-hover: #202733 !important;
    --n-color-focus: #202733 !important;
    --n-text-color: #dce7f7 !important;
    --n-caret-color: #7da2ff !important;
    border-radius: 0;
    background-color: #202733 !important;
  }
  .code-input :deep(.n-input:hover),
  .code-input :deep(.n-input.n-input--focus) {
    background-color: #202733 !important;
  }
  .code-input :deep(.n-input-wrapper),
  .code-input :deep(.n-input__textarea-el),
  .code-input :deep(.n-input__textarea-mirror) {
    background: transparent !important;
  }
  .code-input :deep(textarea) {
    padding: 11px 14px;
    background: transparent !important;
    color: #dce7f7 !important;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    line-height: 1.65;
  }
  .expression-field {
    margin-top: 20px;
  }
  .expression-panel {
    overflow: hidden;
    width: 100%;
    border: 1px solid #dce3ed;
    border-radius: 8px;
    background: #fff;
  }
  .expression-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-height: 48px;
    padding: 7px 10px 7px 14px;
    box-sizing: border-box;
    background: #f8fafc;
  }
  .expression-meta {
    display: flex;
    gap: 8px;
    align-items: center;
    color: #53627a;
    font-size: 12px;
    font-weight: 600;
  }
  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #3f72ed;
    box-shadow: 0 0 0 3px #e6edff;
  }
  .expression-help {
    display: flex;
    gap: 8px;
    align-items: center;
    min-height: 40px;
    padding: 8px 13px;
    box-sizing: border-box;
    background: #f8fafc;
    color: #7b8798;
    font-size: 12px;
  }
  .help-icon {
    display: grid;
    flex: 0 0 auto;
    place-items: center;
    width: 17px;
    height: 17px;
    border: 1px solid #9aa8bc;
    border-radius: 50%;
    color: #68778d;
    font-family: Georgia, serif;
    font-size: 11px;
    font-weight: 700;
  }
  .side-column {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .strategy-list {
    padding: 10px;
  }
  .strategy-item {
    display: grid;
    grid-template-columns: 34px 1fr auto;
    gap: 10px;
    align-items: center;
    width: 100%;
    padding: 10px;
    border: 1px solid transparent;
    border-radius: 7px;
    background: transparent;
    color: #344054;
    text-align: left;
    cursor: pointer;
    transition: 0.18s ease;
  }
  .strategy-item:hover {
    background: #f6f8fc;
  }
  .strategy-item.active {
    border-color: #c9d7ff;
    background: #f2f6ff;
  }
  .strategy-code {
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    border-radius: 6px;
    background: #eef2f7;
    color: #53627a;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 700;
  }
  .strategy-item.active .strategy-code {
    background: #e3ebff;
    color: #2f64e8;
  }
  .strategy-item strong,
  .strategy-item small {
    display: block;
  }
  .strategy-item strong {
    font-size: 13px;
    font-weight: 600;
  }
  .strategy-item small {
    margin-top: 2px;
    color: #8a96a8;
    font-size: 11px;
  }
  .strategy-item i {
    color: #2f64e8;
    font-size: 11px;
    font-style: normal;
  }
  .locator-advice {
    padding: 14px 16px;
    border: 1px solid #d7e4ff;
    border-radius: 8px;
    background: #f3f7ff;
    color: #5c6f91;
    font-size: 12px;
    line-height: 1.6;
  }
  .recognizer-dialog {
    width: min(680px, calc(100vw - 32px));
    border-radius: 10px;
  }
  .recognizer-intro {
    margin: 0 0 14px;
    color: #6f7d91;
    font-size: 13px;
    line-height: 1.7;
  }
  .recognition-preview {
    display: grid;
    grid-template-columns: auto auto minmax(0, 1fr);
    gap: 9px;
    align-items: center;
    margin-top: 14px;
    padding: 11px 13px;
    border: 1px solid #d7e4ff;
    border-radius: 7px;
    background: #f3f7ff;
    color: #63728a;
    font-size: 12px;
  }
  .recognition-preview strong {
    color: #2f64e8;
  }
  .recognition-preview code {
    overflow: hidden;
    color: #344054;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  @media (max-width: 960px) {
    .content-grid {
      grid-template-columns: 1fr;
    }
    .basic-grid {
      grid-template-columns: 1fr 1fr;
    }
  }
  @media (max-width: 720px) {
    .element-editor-page {
      padding: 14px;
    }
    .page-header {
      align-items: flex-start;
      flex-direction: column;
      gap: 14px;
    }
    .basic-grid {
      grid-template-columns: 1fr;
    }
    .card-heading {
      align-items: flex-start;
      flex-direction: column;
      gap: 5px;
    }
    .locator-method-row {
      grid-template-columns: 1fr;
      gap: 10px;
      align-items: stretch;
    }
    .expression-toolbar {
      align-items: flex-start;
      flex-direction: column;
      padding: 10px;
    }
  }
</style>
