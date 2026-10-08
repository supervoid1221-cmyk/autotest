<template>
  <div class="function-page">
    <header class="page-header">
      <div>
        <h2>动态函数详情</h2>
        <p>集中维护测试数据生成函数，并在保存前即时验证结果</p>
        <div v-if="id" class="version-meta">
          <n-tag size="small" :bordered="false">v{{ form.version || 1 }}</n-tag>
          <n-tag size="small" :bordered="false" :type="approvalState.type">{{ approvalState.label }}</n-tag>
          <code v-if="form.code_hash">{{ form.code_hash.slice(0, 12) }}</code>
        </div>
      </div>
      <n-space
        ><n-button @click="router.back()">返回</n-button
        ><n-button type="primary" @click="submit">保存</n-button></n-space
      >
    </header>

    <n-alert class="isolation-alert" type="info" :show-icon="true">
      Python 在无网络隔离执行器中运行。保存新代码，或调整所属项目、超时和内存上限后，会立即停止用于正式执行，并进入“待审批”。
    </n-alert>

    <div class="editor-layout">
      <!-- 左栏：函数代码 -->
      <section class="detail-card code-card">
        <div class="card-title">
          <h3><PhCode class="title-icon" />函数代码</h3>
          <n-switch v-model:value="form.enabled">
            <template #checked>已启用</template>
            <template #unchecked>已禁用</template>
          </n-switch>
        </div>
        <div class="card-body">
          <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
            <n-form-item label="所属项目" path="projects">
              <n-select
                v-model:value="form.projects"
                multiple
                filterable
                max-tag-count="responsive"
                :options="projectOptions"
                :loading="projectLoading"
                placeholder="请选择一个或多个项目"
              />
            </n-form-item>
            <div class="resource-fields">
              <n-form-item label="执行超时（秒）">
                <n-input-number v-model:value="form.timeout_seconds" :min="1" :max="10" />
              </n-form-item>
              <n-form-item label="内存上限（MB）">
                <n-input-number v-model:value="form.memory_mb" :min="64" :max="512" :step="64" />
              </n-form-item>
            </div>
            <n-form-item path="code" :show-label="false">
              <div class="editor">
                <div class="editor-bar">
                  <span class="lang"><span class="py-dot"></span>python</span>
                  <span>{{ functionOptions.length }} 个函数已识别</span>
                </div>
                <div class="editor-body">
                  <div class="gutter" ref="gutterRef">{{ lineNumbers }}</div>
                  <div class="code-wrap">
                    <pre class="code-hl" ref="hlRef" v-html="highlightedCode"></pre>
                    <textarea
                      class="code-input"
                      ref="codeInputRef"
                      v-model="form.code"
                      spellcheck="false"
                      placeholder="请输入一个或多个 def 函数"
                      @scroll="syncScroll"
                    ></textarea>
                  </div>
                </div>
              </div>
            </n-form-item>
          </n-form>

          <div v-if="functionOptions.length" class="fn-chips">
            <button
              v-for="fn in functionOptions"
              :key="fn.value"
              type="button"
              class="fn-chip"
              :class="{ active: fn.value === selectedFunction }"
              @click="selectFunction(fn.value)"
            >
              <PhFunction class="chip-icon" />{{ fn.value }}
            </button>
          </div>
          <p class="fn-tip"
            >调用格式：<code>${build_order_no}</code>，带参数：<code
              >${amount_boundary("0.01", "9999.99")}</code
            >；关闭启用后场景与套件不再引用这组函数</p
          >
        </div>
      </section>

      <!-- 右栏 -->
      <aside class="right">
        <!-- 函数调试 -->
        <section class="detail-card">
          <div class="card-title"
            ><h3><PhBug class="title-icon" />函数调试</h3></div
          >
          <div class="card-body">
            <div class="field">
              <label class="field-label">选择函数</label>
              <n-select
                v-model:value="selectedFunction"
                :options="functionOptions"
                placeholder="请先在函数代码中定义 def 函数"
                @update:value="syncCallExample"
              />
            </div>
            <div class="field">
              <label class="field-label">调用示例</label>
              <div class="input-group">
                <n-input
                  v-model:value="callExample"
                  class="mono-input"
                  placeholder='例如：${date("%Y年%m月%d日")}'
                />
                <n-button :disabled="!callExample" @click="copyCallExample"
                  ><template #icon><PhCheck v-if="copied" /><PhCopy v-else /></template
                ></n-button>
              </div>
            </div>
            <div class="field">
              <n-button type="primary" block :loading="testing" @click="testFunction"
                ><template #icon><PhPlay /></template>运行测试</n-button
              >
            </div>
            <div class="field">
              <label class="field-label">运行结果</label>
              <div class="result-box" :class="resultClass">
                <pre>{{ resultText }}</pre>
              </div>
            </div>
            <p class="debug-note">调试结果仅用于预览，不会写入场景变量或保存到数据库</p>
          </div>
        </section>

        <!-- 白名单 -->
        <section class="detail-card">
          <div class="card-title"
            ><h3><PhShieldCheck class="title-icon" />允许使用的白名单</h3></div
          >
          <div class="card-body">
            <div class="wl-group">
              <div class="wl-label"><PhPackage />允许导入模块</div>
              <div class="wl-chips"
                ><span v-for="m in whitelist.modules" :key="m" class="wl-chip">{{ m }}</span></div
              >
            </div>
            <div class="wl-group">
              <div class="wl-label"><PhTerminalWindow />允许内置函数</div>
              <div class="wl-chips"
                ><span v-for="m in whitelist.builtins" :key="m" class="wl-chip">{{ m }}</span></div
              >
            </div>
            <div class="wl-group">
              <div class="wl-label"><PhWrench />平台辅助函数</div>
              <div class="wl-chips"
                ><span v-for="m in whitelist.helpers" :key="m" class="wl-chip">{{ m }}</span></div
              >
            </div>
            <div class="wl-group">
              <div class="wl-label"><PhBracketsCurly />context 可用字段</div>
              <div class="wl-chips"
                ><span v-for="m in whitelist.context" :key="m" class="wl-chip">{{ m }}</span></div
              >
            </div>
            <div class="wl-forbid"
              >不允许使用：文件读写、系统命令、网络 Socket、任意导入、exec、eval 等操作</div
            >
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, onMounted, reactive, ref, watch } from 'vue';
  import { useDialog, useMessage } from 'naive-ui';
  import { useRoute, useRouter } from 'vue-router';
  import {
    PhBracketsCurly,
    PhBug,
    PhCheck,
    PhCode,
    PhCopy,
    PhFunction,
    PhPackage,
    PhPlay,
    PhShieldCheck,
    PhTerminalWindow,
    PhWrench,
  } from '@phosphor-icons/vue';
  import { useSubmitRedirect } from '@/hooks/web/useSubmitRedirect';
  import { DynamicFunctionAPI, ProjectAPI } from '@/api/project/http';

  defineOptions({ name: 'project_dynamic_function_edit' });
  const route = useRoute();
  const router = useRouter();
  const message = useMessage();
  const dialog = useDialog();
  const api = new DynamicFunctionAPI();
  const projectApi = new ProjectAPI();
  const formRef = ref();
  const id = Number(route.params.id) || 0;
  const { redirectAfterSubmit } = useSubmitRedirect();
  const form = reactive<any>({
    projects: [],
    enabled: true,
    timeout_seconds: 3,
    memory_mb: 128,
    code: 'def build_order_no(context):\n    return f"TEST_{context[\'timestamp\']}"',
  });
  const rules = {
    projects: { type: 'array', required: true, min: 1, message: '请至少选择一个项目' },
    code: { required: true, message: '请输入函数代码' },
  };
  const projectOptions = ref<Array<{ label: string; value: number }>>([]);
  const projectLoading = ref(false);
  const selectedFunction = ref('');
  const callExample = ref('');
  const testing = ref(false);
  const testResult = ref('');
  const testError = ref('');
  const copied = ref(false);
  const requiredBuiltinWhitelist = ['isinstance', 'hexdigest'];
  const whitelist = reactive({
    modules: [] as string[],
    builtins: [] as string[],
    helpers: [] as string[],
    context: [] as string[],
  });
  const functionOptions = computed(() =>
    Array.from(form.code.matchAll(/^\s*def\s+([A-Za-z_]\w*)\s*\(/gm)).map((match) => ({
      label: match[1],
      value: match[1],
    }))
  );
  const approvalState = computed(() => ({
    draft: { label: '待审批', type: 'warning' as const },
    approved: { label: '已审批', type: 'success' as const },
    rejected: { label: '已驳回', type: 'error' as const },
  }[form.approval_status] || { label: '待审批', type: 'warning' as const }));
  watch(
    functionOptions,
    (options) => {
      if (!options.some((item) => item.value === selectedFunction.value)) {
        selectedFunction.value = options[0]?.value || '';
        syncCallExample(selectedFunction.value);
      }
    },
    { immediate: true }
  );
  onMounted(async () => {
    projectLoading.value = true;
    try {
      const projectPayload: any = await projectApi.getDataList({ pageSize: 1000 });
      const projects = Array.isArray(projectPayload)
        ? projectPayload
        : projectPayload?.list ||
          projectPayload?.results ||
          projectPayload?.data?.list ||
          projectPayload?.data ||
          [];
      projectOptions.value = projects.map((item: any) => ({ label: item.name, value: item.id }));
      if (!projectOptions.value.length) message.warning('当前账号暂无可选择的项目');
    } catch (error: any) {
      projectOptions.value = [];
      message.error(error?.message || '项目列表加载失败');
    } finally {
      projectLoading.value = false;
    }
    if (id) {
      const detail: any = await api.getDataByID(id);
      Object.assign(form, detail, { projects: (detail.projects || []).map(Number) });
    }
    try {
      const payload = await api.getWhitelist();
      Object.assign(whitelist, payload);
      whitelist.builtins = Array.from(
        new Set([...(payload?.builtins || []), ...requiredBuiltinWhitelist])
      );
    } catch {
      whitelist.builtins = [...requiredBuiltinWhitelist];
      /* 白名单使用后端默认校验，加载失败不阻断编辑。 */
    }
  });
  function syncCallExample(name: string) {
    callExample.value = name ? `\${${name}}` : '';
  }
  function selectFunction(name: string) {
    selectedFunction.value = name;
    syncCallExample(name);
  }

  /* 代码编辑器：行号 + 语法着色 */
  const codeInputRef = ref<HTMLTextAreaElement>();
  const gutterRef = ref<HTMLDivElement>();
  const hlRef = ref<HTMLPreElement>();
  const lineCount = computed(() => form.code.split('\n').length);
  const lineNumbers = computed(() =>
    Array.from({ length: lineCount.value }, (_, i) => i + 1).join('\n')
  );
  const highlightedCode = computed(() => highlightPython(form.code));
  function syncScroll() {
    const ta = codeInputRef.value;
    if (!ta) return;
    if (gutterRef.value) gutterRef.value.scrollTop = ta.scrollTop;
    if (hlRef.value) {
      hlRef.value.scrollTop = ta.scrollTop;
      hlRef.value.scrollLeft = ta.scrollLeft;
    }
  }
  const PY_KEYWORDS =
    'def|return|import|from|as|if|elif|else|for|while|in|not|and|or|None|True|False|lambda|class|try|except|finally|with|pass|break|continue|yield|global|del|raise|is';
  function escapeHtml(s: string) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function highlightPython(code: string): string {
    const re = new RegExp(
      '(#.*$)|("""[\\s\\S]*?"""|\'\'\'[\\s\\S]*?\'\'\'|"(?:[^"\\\\\\n]|\\\\.)*"|\'(?:[^\'\\\\\\n]|\\\\.)*\')|(\\b(?:' +
        PY_KEYWORDS +
        ')\\b)|(\\b[A-Za-z_]\\w*(?=\\s*\\())|(\\b\\d+(?:\\.\\d+)?\\b)',
      'gm'
    );
    let out = '';
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(code)) !== null) {
      out += escapeHtml(code.slice(last, m.index));
      if (m[1] !== undefined) out += '<span class="tk-cm">' + escapeHtml(m[1]) + '</span>';
      else if (m[2] !== undefined) out += '<span class="tk-str">' + escapeHtml(m[2]) + '</span>';
      else if (m[3] !== undefined) out += '<span class="tk-kw">' + escapeHtml(m[3]) + '</span>';
      else if (m[4] !== undefined) out += '<span class="tk-fn">' + escapeHtml(m[4]) + '</span>';
      else if (m[5] !== undefined) out += '<span class="tk-num">' + escapeHtml(m[5]) + '</span>';
      else out += escapeHtml(m[0]);
      last = m.index + m[0].length;
    }
    out += escapeHtml(code.slice(last));
    return out;
  }

  async function copyCallExample() {
    if (!callExample.value) return;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(callExample.value);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = callExample.value;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(textarea);
        if (!ok) throw new Error('浏览器未授予复制权限');
      }
      copied.value = true;
      setTimeout(() => (copied.value = false), 1200);
      message.success('调用示例已复制');
    } catch {
      message.error('复制失败，请手动复制调用示例');
    }
  }
  function getFunctionCall() {
    const match = callExample.value
      .trim()
      .match(
        /^(?:\$\{\s*([A-Za-z_]\w*)(?:\(([\s\S]*)\))?\s*\}|\{\{\s*([A-Za-z_]\w*)(?:\(([\s\S]*)\))?\s*\}\})$/
      );
    return { name: match?.[1] || match?.[3] || '', arguments: match?.[2] ?? match?.[4] ?? '' };
  }
  async function testFunction() {
    const functionCall = getFunctionCall();
    if (!functionCall.name) {
      testError.value = '调用示例格式应为 ${函数名} 或 ${函数名("参数")}';
      return;
    }
    testing.value = true;
    testError.value = '';
    testResult.value = '';
    try {
      const response = await api.test(form.code, functionCall.name, functionCall.arguments, form.timeout_seconds, form.memory_mb);
      selectedFunction.value = functionCall.name;
      testResult.value = response.display ?? String(response.result ?? '');
    } catch (error: any) {
      testError.value = error.message || '函数调试失败';
    } finally {
      testing.value = false;
    }
  }
  const resultText = computed(() => {
    if (testing.value) return '执行中…';
    if (testError.value) return testError.value;
    if (testResult.value) return testResult.value;
    return '点击「运行测试」查看本次生成的数据';
  });
  const resultClass = computed(() => {
    if (testing.value || (!testResult.value && !testError.value)) return 'empty';
    return testError.value ? 'err' : 'ok';
  });
  async function submit() {
    await formRef.value.validate();
    const { conflicts } = await api.checkConflicts(form.projects, form.code, id || undefined);
    if (conflicts.length) {
      const conflictText = conflicts
        .map((item) => `${item.project_name}（${item.functions.join('、')}）`)
        .join('；');
      dialog.warning({
        title: '存在重复动态函数',
        content: `以下项目已有同名动态函数：${conflictText}。请调整所属项目或修改函数名后再保存。`,
        positiveText: '知道了',
      });
      return;
    }
    const saved: any = id ? await api.update(id, form) : await api.createData(form);
    message.success(saved?.approval_status === 'approved' ? '保存成功' : '已保存，待管理员审批');
    redirectAfterSubmit({ name: 'project_dynamic_function' });
  }
</script>

<style lang="less" scoped>
  .function-page {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px 28px 32px;
  }
  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 18px;
  }
  .page-header h2 {
    margin: 0;
    color: #111827;
    font-size: 20px;
    font-weight: 600;
  }
  .page-header p {
    margin: 4px 0 0;
    color: #6b7280;
    font-size: 13px;
  }
  .version-meta { display: flex; align-items: center; gap: 8px; margin-top: 9px; }
  .version-meta code { color: #6b7280; font: 12px/1.4 'JetBrains Mono', ui-monospace, monospace; }
  .isolation-alert { margin-bottom: 16px; }
  .resource-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .resource-fields :deep(.n-input-number) { width: 100%; }

  .editor-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 360px;
    gap: 16px;
    align-items: start;
  }
  .right {
    position: sticky;
    top: 20px;
    display: grid;
    gap: 16px;
  }

  .detail-card {
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    background: #fff;
    overflow: hidden;
  }
  .card-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 13px 22px;
    border-bottom: 1px solid #f3f4f6;
    background: #fafafb;
  }
  .card-title h3 {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0;
    color: #111827;
    font-size: 14px;
    font-weight: 600;
  }
  .title-icon {
    color: #5b6af0;
    font-size: 15px;
  }
  .card-body {
    padding: 16px 22px 20px;
  }

  /* 代码编辑器 */
  .code-card :deep(.n-form),
  .code-card :deep(.n-form-item),
  .code-card :deep(.n-form-item-blank) {
    width: 100%;
    min-width: 0;
  }
  .editor {
    width: 100%;
    min-width: 0;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    overflow: hidden;
  }
  .editor-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 14px;
    background: #fafafb;
    border-bottom: 1px solid #f3f4f6;
    font-size: 11.5px;
    color: #9ca3af;
  }
  .lang {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
  }
  .py-dot {
    width: 8px;
    height: 8px;
    border-radius: 2px;
    background: linear-gradient(135deg, #3b82f6, #f59e0b);
  }
  .editor-body {
    display: flex;
    height: 460px;
    background: #fcfcfd;
    overflow: hidden;
  }
  .gutter {
    height: 100%;
    box-sizing: border-box;
    padding: 12px 10px 12px 14px;
    text-align: right;
    white-space: pre;
    overflow: hidden;
    user-select: none;
    border-right: 1px solid #f3f4f6;
    color: #c3c7ce;
    font: 12px/22px 'JetBrains Mono', ui-monospace, monospace;
  }
  .code-wrap {
    position: relative;
    flex: 1;
    min-width: 0;
    height: 100%;
  }
  .code-hl,
  .code-input {
    position: absolute;
    inset: 0;
    margin: 0;
    padding: 12px 16px;
    white-space: pre;
    tab-size: 4;
    font: 12.5px/22px 'JetBrains Mono', ui-monospace, monospace;
  }
  .code-hl {
    overflow: hidden;
    color: #374151;
    pointer-events: none;
  }
  .code-hl :deep(.tk-kw) {
    color: #9333ea;
  }
  .code-hl :deep(.tk-fn) {
    color: #2563eb;
  }
  .code-hl :deep(.tk-str) {
    color: #059669;
  }
  .code-hl :deep(.tk-cm) {
    color: #9ca3af;
    font-style: italic;
  }
  .code-hl :deep(.tk-num) {
    color: #d97706;
  }
  .code-input {
    width: 100%;
    height: 100%;
    border: none;
    outline: none;
    resize: none;
    overflow: auto;
    background: transparent;
    color: transparent;
    caret-color: #111827;
    -webkit-text-fill-color: transparent;
  }
  .code-input::placeholder {
    color: #9ca3af;
    -webkit-text-fill-color: #9ca3af;
  }

  /* 函数 chips */
  .fn-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 16px;
  }
  .fn-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    background: #fff;
    color: #374151;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .fn-chip:hover {
    border-color: #5b6af0;
    color: #5b6af0;
    background: #eef0ff;
  }
  .fn-chip.active {
    border-color: #5b6af0;
    color: #5b6af0;
    background: #eef0ff;
    font-weight: 600;
  }
  .chip-icon {
    font-size: 13px;
  }
  .fn-tip {
    margin: 12px 0 0;
    font-size: 12px;
    color: #9ca3af;
    line-height: 1.6;
  }
  .fn-tip code {
    margin: 0 2px;
    padding: 1px 5px;
    border-radius: 3px;
    color: #5b6af0;
    background: #eef0ff;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
  }

  /* 调试表单 */
  .field {
    margin-bottom: 16px;
  }
  .field:last-of-type {
    margin-bottom: 0;
  }
  .field-label {
    display: block;
    margin-bottom: 7px;
    color: #374151;
    font-size: 13px;
    font-weight: 600;
  }
  .input-group {
    display: flex;
    gap: 8px;
  }
  .input-group .n-input {
    flex: 1;
  }
  .mono-input :deep(input) {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 12.5px;
  }

  /* 运行结果 */
  .result-box {
    min-height: 96px;
    border: 1px solid #e5e7eb;
    border-left-width: 3px;
    border-radius: 6px;
    background: #fcfcfd;
  }
  .result-box pre {
    margin: 0;
    padding: 12px 14px;
    color: #374151;
    font: 12.5px/1.7 'JetBrains Mono', ui-monospace, monospace;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .result-box.empty pre {
    color: #9ca3af;
  }
  .result-box.ok {
    border-left-color: #059669;
  }
  .result-box.ok pre {
    color: #059669;
  }
  .result-box.err {
    border-left-color: #e11d48;
  }
  .result-box.err pre {
    color: #e11d48;
  }
  .debug-note {
    margin: 12px 0 0;
    font-size: 12px;
    color: #9ca3af;
    line-height: 1.6;
  }

  /* 白名单 */
  .wl-group {
    margin-bottom: 16px;
  }
  .wl-group:last-of-type {
    margin-bottom: 0;
  }
  .wl-label {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
    color: #6b7280;
    font-size: 12px;
    font-weight: 600;
  }
  .wl-label svg {
    color: #5b6af0;
    font-size: 13px;
  }
  .wl-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .wl-chip {
    padding: 3px 9px;
    border-radius: 4px;
    background: #f3f4f6;
    color: #374151;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 11.5px;
  }
  .wl-forbid {
    margin-top: 16px;
    padding: 10px 12px;
    border-radius: 6px;
    background: #fff1f2;
    color: #e11d48;
    font-size: 12px;
    line-height: 1.6;
  }

  @media (max-width: 900px) {
    .editor-layout {
      grid-template-columns: 1fr;
    }
    .right {
      position: static;
    }
    .editor-body {
      height: 420px;
    }
  }
  @media (max-width: 560px) {
    .function-page {
      padding: 12px 16px 24px;
    }
    .page-header {
      gap: 14px;
      flex-direction: column;
    }
  }
</style>
