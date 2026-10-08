<template>
  <div class="yaml-page" :class="{ 'editor-expanded': editorExpanded }">
    <header class="page-header">
      <div class="page-title">
        <h1>YAML 用例</h1>
        <p>通过 YAML 文件编写、管理和执行 UI 自动化测试用例</p>
      </div>
      <div class="header-actions">
        <n-button :loading="previewing" :disabled="!projectId" @click="preview"><template #icon><n-icon><FileSearchOutlined /></n-icon></template>解析预览</n-button>
        <n-button :loading="converting" :disabled="!projectId || saving || running" @click="convertToSmartCases"><template #icon><n-icon><SwapOutlined /></n-icon></template>转为智能用例</n-button>
        <n-button :loading="saving" :disabled="!projectId" @click="save()"><template #icon><n-icon><SaveOutlined /></n-icon></template>保存文件</n-button>
        <n-button type="primary" color="#49cfa7" :loading="running" :disabled="!projectId" @click="saveAndRun"><template #icon><n-icon><PlayCircleOutlined /></n-icon></template>保存并执行</n-button>
      </div>
    </header>

    <section class="settings-strip" aria-label="YAML 用例运行配置">
      <label><span>项目</span><n-select :value="projectId" :options="projectOptions" filterable placeholder="选择项目" @update:value="changeProject" /></label>
      <label><span>执行环境</span><n-select v-model:value="environmentName" :options="environmentOptions" clearable placeholder="执行前选择环境" :disabled="!projectId" /></label>
      <label><span>浏览器</span><n-select v-model:value="browser" :options="browserOptions" :disabled="!projectId" /></label>
      <label><span>运行模式</span><n-select v-model:value="runMode" :options="runModeOptions" :disabled="!projectId" /></label>
    </section>

    <div v-if="projectId" class="workspace">
      <aside class="file-list">
        <div class="file-list-header"><strong>文件列表</strong><span>{{ files.length }}</span></div>
        <n-input v-model:value="fileKeyword" clearable placeholder="搜索文件名..." class="file-search">
          <template #prefix><n-icon><SearchOutlined /></n-icon></template>
        </n-input>
        <n-button class="new-file-button" secondary color="#49cfa7" @click="newFile"><template #icon><n-icon><PlusOutlined /></n-icon></template>新建文件</n-button>
        <div class="file-scroll">
          <n-spin :show="loadingFiles">
            <button
              v-for="file in filteredFiles"
              :key="file.id"
              type="button"
              class="file-item"
              :class="{ active: fileId === file.id }"
              :title="file.filename"
              @click="selectFile(file)"
            >
              <n-icon><FileTextOutlined /></n-icon>
              <span class="file-name">{{ file.filename }}</span>
            </button>
            <p v-if="!filteredFiles.length" class="empty-files">{{ files.length ? '没有匹配的文件' : '还没有 YAML 文件，点击上方新建。' }}</p>
          </n-spin>
        </div>
        <div class="upload-library">
          <div class="upload-library-heading"><strong>测试文件</strong><span>{{ uploadedFiles.length }}</span></div>
          <input ref="uploadInputRef" type="file" multiple aria-label="上传测试文件" @change="uploadTestFiles" />
          <n-button size="small" secondary :loading="uploadingFiles" @click="uploadInputRef?.click()">上传测试文件</n-button>
          <div class="uploaded-file-list">
            <div v-for="file in uploadedFiles" :key="file.id" class="uploaded-file-item" :title="file.original_name">
              <span>{{ file.original_name }}</span><code>#{{ file.id }}</code>
            </div>
            <p v-if="!uploadedFiles.length">上传后在 YAML 中填写文件 ID</p>
          </div>
        </div>
      </aside>

      <main class="editor-panel">
        <div class="editor-heading">
          <div class="file-heading-main">
            <n-input v-model:value="filename" class="filename-input" placeholder="请输入文件名.yaml" aria-label="文件名" />
            <span v-if="dirty || !fileId" class="unsaved"><i></i>未保存</span>
            <span v-else class="saved-state"><i></i>已保存</span>
          </div>
          <div class="editor-tools">
            <span class="indent-hint">Tab 缩进 · Shift+Tab 取消缩进</span>
            <n-popover trigger="hover" placement="bottom-end" :delay="200" :style="{ padding: '0', width: '390px', maxWidth: 'calc(100vw - 24px)' }">
              <template #trigger>
                <n-button text class="steps-help-trigger" aria-label="查看支持的操作步骤"><n-icon><QuestionCircleOutlined /></n-icon></n-button>
              </template>
              <div class="steps-help-content">
                <strong>支持的操作步骤</strong>
                <p>在「步骤:」下逐行填写，每行以「- 」开头。</p>
                <div class="steps-help-list">
                  <div v-for="item in supportedStepExamples" :key="item.label">
                    <span>{{ item.label }}</span><code>{{ item.example }}</code>
                    <n-button text class="copy-step-button" :title="`复制${item.label}示例（含前导两个空格）`" :aria-label="`复制${item.label}示例`" @click="copyStepExample(item.example)"><n-icon><CopyOutlined /></n-icon></n-button>
                  </div>
                </div>
                <p class="steps-help-note">连续点击用 -- 分隔元素；上传文件先在左侧上传，再填写文件 ID。提取的文本可用 ${变量名} 引用。截图配置紧跟要截图的步骤或断言。</p>
              </div>
            </n-popover>
            <n-button text :disabled="!fileId" title="下载 YAML 文件" aria-label="下载 YAML 文件" @click="downloadFile"><n-icon><DownloadOutlined /></n-icon></n-button>
            <n-popconfirm v-if="fileId" @positive-click="deleteFile">
              <template #trigger><n-button text type="error" title="删除文件" aria-label="删除文件"><n-icon><DeleteOutlined /></n-icon></n-button></template>
              确定删除 {{ filename }}？此操作无法撤销。
            </n-popconfirm>
            <n-button text :title="editorExpanded ? '退出专注模式' : '专注编辑'" :aria-label="editorExpanded ? '退出专注模式' : '专注编辑'" @click="editorExpanded = !editorExpanded"><n-icon><CompressOutlined v-if="editorExpanded" /><ExpandOutlined v-else /></n-icon></n-button>
          </div>
        </div>
        <div ref="editorHostRef" class="yaml-code-editor" aria-label="YAML 文件内容"></div>
        <div class="editor-footnote">同一文件的场景按顺序共用浏览器会话；前一场景失败后停止执行。上传文件格式：上传文件 附件：文件ID；*** 运行前请替换为真实值或项目变量。</div>
      </main>

      <aside class="preview-panel">
        <div class="preview-heading"><strong>解析预览</strong><n-button text :loading="previewing" title="重新解析" aria-label="重新解析" @click="preview"><n-icon><ReloadOutlined /></n-icon></n-button></div>
        <div class="preview-tabs" role="tablist" aria-label="预览模式">
          <button type="button" role="tab" :aria-selected="previewMode === 'scenarios'" :class="{ active: previewMode === 'scenarios' }" @click="previewMode = 'scenarios'">场景视图（{{ scenarios.length }}）</button>
          <button type="button" role="tab" :aria-selected="previewMode === 'raw'" :class="{ active: previewMode === 'raw' }" @click="previewMode = 'raw'">原始结构</button>
        </div>
        <div class="preview-scroll">
          <n-spin :show="previewing">
            <n-empty v-if="!scenarios.length" size="small" class="preview-empty" description="点击“解析预览”查看场景和步骤" />
            <div v-else-if="previewMode === 'scenarios'" class="scenario-list">
              <article v-for="(scenario, sceneIndex) in scenarios" :key="`${scenario.scenario_id || scenario.name}-${sceneIndex}`" class="scenario-item">
                <div class="scenario-heading"><span class="scenario-index">{{ sceneIndex + 1 }}</span><strong>{{ scenario.name }}</strong><span class="valid-badge" :class="{ stale: previewStale }">{{ previewStale ? '待更新' : '有效' }}</span></div>
                <dl><div v-if="scenario.scenario_id"><dt>场景 ID</dt><dd>{{ scenario.scenario_id }}</dd></div><div v-if="scenario.description"><dt>描述</dt><dd>{{ scenario.description }}</dd></div></dl>
                <div class="steps-heading">执行步骤（{{ executionSteps(scenario).length }}）</div>
                <ol class="preview-steps"><li v-for="(step, stepIndex) in executionSteps(scenario)" :key="stepIndex"><span>{{ stepIndex + 1 }}</span><p>{{ formatPreviewStep(step) }}<em v-if="step.options?.screenshot">执行后截图</em></p></li></ol>
                <div v-if="assertionSteps(scenario).length" class="assertion-heading">预期结果</div>
                <ul v-if="assertionSteps(scenario).length" class="preview-assertions"><li v-for="(step, stepIndex) in assertionSteps(scenario)" :key="stepIndex"><span>✓</span>{{ step.target || step.value }}<em v-if="step.options?.screenshot">执行后截图</em></li></ul>
              </article>
            </div>
            <pre v-else class="raw-preview">{{ sanitizedPreviewJson }}</pre>
          </n-spin>
        </div>
        <div class="preview-footer" v-if="scenarios.length">
          <span v-if="previewStale" class="stale-note">文件内容已修改，请重新解析</span>
          <span v-else>当前文件共 {{ scenarios.length }} 个场景 · {{ previewStepCount }} 个步骤</span>
        </div>
        <n-alert v-if="runResult" :type="runResult.passed ? 'success' : 'error'" :bordered="false" class="result-panel">
          {{ runResult.passed ? '执行通过' : '执行失败' }}：
          <span v-for="(result, index) in runResult.scenarios" :key="index">
            {{ result.name }}{{ result.passed ? '通过' : `失败：${result.error || '请查看详情'}` }}<span v-if="index < runResult.scenarios.length - 1">；</span>
          </span>
        </n-alert>
        <div v-if="runScreenshots.length" class="run-screenshots">
          <strong>执行截图（{{ runScreenshots.length }}）</strong>
          <a v-for="item in runScreenshots" :key="item.key" :href="item.url" :download="item.filename">
            <img :src="item.url" :alt="item.label" />
            <span>{{ item.label }} · 点击下载</span>
          </a>
        </div>
      </aside>
    </div>
    <n-empty v-else description="请先选择项目" class="project-empty" />
  </div>
</template>

<script lang="ts" setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { indentWithTab, defaultKeymap, history, historyKeymap } from '@codemirror/commands';
import { yaml } from '@codemirror/lang-yaml';
import { indentUnit } from '@codemirror/language';
import { EditorState } from '@codemirror/state';
import { Decoration, EditorView, keymap, lineNumbers as codeLineNumbers, MatchDecorator, ViewPlugin } from '@codemirror/view';
import { useRouter } from 'vue-router';
import { NPopover, NPopconfirm, useMessage } from 'naive-ui';
import {
  CompressOutlined, CopyOutlined, DeleteOutlined, DownloadOutlined, ExpandOutlined, FileSearchOutlined,
  FileTextOutlined, PlayCircleOutlined, PlusOutlined, QuestionCircleOutlined, ReloadOutlined, SaveOutlined, SearchOutlined, SwapOutlined,
} from '@vicons/antd';
import { PlaywrightScenarioFileAPI, UiUploadedFileAPI } from '@/api/case_ui/http';
import { EnvironmentAPI, ProjectAPI } from '@/api/project/http';
import { asList } from '@/utils/list';

defineOptions({ name: 'case_ui_yaml_case' });

const message = useMessage();
const router = useRouter();
const fileApi = new PlaywrightScenarioFileAPI();
const uploadedFileApi = new UiUploadedFileAPI();
const projectApi = new ProjectAPI();
const environmentApi = new EnvironmentAPI();
const projects = ref<any[]>([]);
const environments = ref<any[]>([]);
const files = ref<any[]>([]);
const uploadedFiles = ref<any[]>([]);
const fileKeyword = ref('');
const projectId = ref<number | null>(null);
const fileId = ref<number | null>(null);
const filename = ref('');
const content = ref('');
const environmentName = ref<string | null>(null);
const browser = ref('chromium');
const runMode = ref('headless');
const savedSignature = ref('');
const scenarios = ref<any[]>([]);
const previewedContent = ref('');
const previewMode = ref<'scenarios' | 'raw'>('scenarios');
const editorExpanded = ref(false);
const runResult = ref<any>(null);
const loadingFiles = ref(false);
const previewing = ref(false);
const saving = ref(false);
const running = ref(false);
const converting = ref(false);
const uploadingFiles = ref(false);
const uploadInputRef = ref<HTMLInputElement | null>(null);
const editorHostRef = ref<HTMLElement | null>(null);
let editorView: EditorView | null = null;
const filteredFiles = computed(() => files.value.filter((file) =>
  String(file.filename || '').toLowerCase().includes(fileKeyword.value.trim().toLowerCase())
));
const previewStale = computed(() => !!scenarios.value.length && previewedContent.value !== content.value);
const executionSteps = (scene: any) => (scene.steps || []).filter((step: any) => step.action !== 'assert_text');
const assertionSteps = (scene: any) => (scene.steps || []).filter((step: any) => step.action === 'assert_text');
const previewStepCount = computed(() => scenarios.value.reduce((count, scene) => count + executionSteps(scene).length, 0));
const runScreenshots = computed(() => (runResult.value?.scenarios || []).flatMap((scene: any, sceneIndex: number) =>
  (scene.report?.steps || []).flatMap((step: any, stepIndex: number) => {
    const screenshot = step.detail?.screenshot;
    const url = String(screenshot?.path || '');
    if (!url.startsWith('data:image/png;base64,')) return [];
    return [{
      key: `${sceneIndex}-${stepIndex}`,
      url,
      label: `${scene.name} · ${step.name || `第 ${stepIndex + 1} 步`}`,
      filename: `yaml-${scene.scenario_id || sceneIndex + 1}-step-${stepIndex + 1}.png`,
    }];
  })
));
const sensitiveTarget = (target: string) => /密码|password|passwd|token|secret|密钥/i.test(target);
function formatPreviewStep(step: any) {
  const target = String(step.target || '');
  const value = sensitiveTarget(target) ? '***' : String(step.value || '');
  if (step.action === 'sleep') return `固定等待：${value} 秒`;
  if (step.action === 'goto') return `打开页面：${target}`;
  if (step.action === 'input') return `输入${target}：${value}`;
  if (step.action === 'upload_file') return `上传文件${target}：${(step.options?.file_ids || []).map((id: number) => `#${id}`).join('、')}`;
  if (step.action === 'clear') return `清空输入：${target}`;
  if (step.action === 'check') return `勾选：${target}`;
  if (step.action === 'save_text') return `提取文本${target}：${value}`;
  if (step.action === 'select') return `下拉选择${target}：${value}`;
  if (step.action === 'click') return `点击：${target}`;
  if (step.action === 'assert_text') return `断言：${target}`;
  return `${step.action || '步骤'}：${target}`;
}
const sanitizedPreviewJson = computed(() => JSON.stringify(scenarios.value.map((scene) => ({
  ...scene,
  steps: (scene.steps || []).map((step: any) => sensitiveTarget(String(step.target || ''))
    ? { ...step, value: '***' } : step),
})), null, 2));

// Decorations live in the editable DOM: the caret, selected text, and colors
// can no longer drift apart as they could with a transparent textarea overlay.
const yamlTokens = new MatchDecorator({
  regexp: /#[^\n]*|(?:测试场景|场景名称|场景ID|描述|步骤|断言|截图|点击|打开页面|固定等待|清空输入|勾选|输入[^：:\n]*|上传文件[^：:\n]*|提取文本[^：:\n]*|选择[^：:\n]*|下拉选择[^：:\n]*)\s*[:：]/g,
  decoration: (match) => Decoration.mark({ class: match[0].startsWith('#') ? 'yaml-token-comment' : 'yaml-token-key' }),
});
const yamlTokenPlugin = ViewPlugin.fromClass(class {
  decorations;
  constructor(view: EditorView) { this.decorations = yamlTokens.createDeco(view); }
  update(update: any) { this.decorations = yamlTokens.updateDeco(update, this.decorations); }
}, { decorations: (plugin) => plugin.decorations });

function createEditor(host: HTMLElement) {
  editorView?.destroy();
  editorView = new EditorView({
    parent: host,
    state: EditorState.create({
      doc: content.value,
      extensions: [
        codeLineNumbers(), history(), yaml(), yamlTokenPlugin,
        indentUnit.of('  '), EditorState.tabSize.of(2),
        keymap.of([indentWithTab, ...defaultKeymap, ...historyKeymap]),
        EditorView.contentAttributes.of({ 'aria-label': 'YAML 文件内容', spellcheck: 'false' }),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) content.value = update.state.doc.toString();
        }),
      ],
    }),
  });
}

function resetEditorScroll() {
  void nextTick(() => {
    if (editorView) {
      editorView.scrollDOM.scrollTop = 0;
      editorView.scrollDOM.scrollLeft = 0;
    }
  });
}

const projectOptions = computed(() => projects.value.map((item) => ({ label: item.name, value: item.id })));
const environmentOptions = computed(() => environments.value.map((item) => ({ label: item.name, value: item.name })));
const browserOptions = [
  { label: 'Chromium', value: 'chromium' }, { label: 'Firefox', value: 'firefox' }, { label: 'WebKit', value: 'webkit' },
];
const runModeOptions = [
  { label: '无头模式', value: 'headless' }, { label: '有界面模式', value: 'headed' },
];
const supportedStepExamples = [
  { label: '打开页面', example: '- 打开页面：http://localhost:8089/login' },
  { label: '输入文本', example: '- 输入账号：demo_user' },
  { label: '点击元素', example: '- 点击：登录' },
  { label: '选择下拉项', example: '- 下拉选择状态：启用' },
  { label: '固定等待', example: '- 固定等待：2' },
  { label: '勾选', example: '- 勾选：同意协议' },
  { label: '上传文件', example: '- 上传文件 附件：12' },
  { label: '清空输入', example: '- 清空输入：搜索框' },
  { label: '提取文本', example: '- 提取文本 订单号：order_id' },
  { label: '断言文本', example: '断言: 登录成功' },
  { label: '执行后截图', example: '截图：true' },
];
async function copyStepExample(example: string) {
  const text = `  ${example}`;
  try {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard API unavailable');
      await navigator.clipboard.writeText(text);
    } catch {
      const fallback = document.createElement('textarea');
      fallback.value = text;
      fallback.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0';
      document.body.appendChild(fallback);
      try {
        fallback.select();
        if (!document.execCommand('copy')) throw new Error('Copy failed');
      } finally {
        fallback.remove();
      }
    }
    message.success('复制成功');
  } catch {
    message.error('复制失败，请手动选择示例文本');
  }
}
const template = '测试场景:\n\n# ============================================\n# 场景1: 新场景\n# ============================================\n\n- 场景名称: 新场景\n  场景ID: NEW_SCENARIO\n  描述: 请填写描述\n  步骤:\n  - 打开页面：http://localhost:8089/login\n  - 点击：登录\n  断言: 登录成功\n  截图：true\n';

function signature() {
  return JSON.stringify({ filename: filename.value, content: content.value,
    environment_name: environmentName.value, browser: browser.value, run_mode: runMode.value });
}
const dirty = computed(() => signature() !== savedSignature.value);
function mayDiscard() {
  return !dirty.value || window.confirm('当前文件有未保存的修改，确定放弃吗？');
}
function changeProject(next: number | null) {
  if (next === projectId.value || !mayDiscard()) return;
  projectId.value = next;
}
function newFile() {
  if (!mayDiscard()) return;
  fileId.value = null;
  filename.value = '';
  content.value = template;
  environmentName.value = null;
  browser.value = 'chromium';
  runMode.value = 'headless';
  scenarios.value = [];
  previewedContent.value = '';
  runResult.value = null;
  savedSignature.value = signature();
  resetEditorScroll();
}
function selectFile(file: any) {
  if (fileId.value === file.id || !mayDiscard()) return;
  fileId.value = file.id;
  filename.value = file.filename;
  content.value = String(file.content || '').replace(/\r\n?/g, '\n');
  environmentName.value = file.environment_name || null;
  browser.value = file.browser || 'chromium';
  runMode.value = file.run_mode || 'headless';
  scenarios.value = [];
  previewedContent.value = '';
  runResult.value = null;
  savedSignature.value = signature();
  resetEditorScroll();
}
async function loadFiles() {
  if (!projectId.value) { files.value = []; return; }
  loadingFiles.value = true;
  try {
    files.value = asList(await fileApi.getDataList({ project: projectId.value, pageSize: 1000 }));
  } catch (error: any) {
    message.error(error?.message || '加载 YAML 文件失败');
  } finally {
    loadingFiles.value = false;
  }
}
async function loadEnvironments() {
  if (!projectId.value) { environments.value = []; return; }
  try {
    environments.value = asList(await environmentApi.getDataList({ project: projectId.value, pageSize: 1000 }))
      .filter((item: any) => Number(item.project) === Number(projectId.value));
  } catch (error: any) {
    environments.value = [];
    message.error(error?.message || '加载执行环境失败');
  }
}
async function loadUploadedFiles() {
  if (!projectId.value) { uploadedFiles.value = []; return; }
  try {
    uploadedFiles.value = asList(await uploadedFileApi.list(projectId.value));
  } catch (error: any) {
    uploadedFiles.value = [];
    message.error(error?.message || '加载测试文件失败');
  }
}
async function uploadTestFiles(event: Event) {
  const input = event.target as HTMLInputElement;
  const selected = Array.from(input.files || []);
  const uploadProjectId = projectId.value;
  if (!uploadProjectId || !selected.length) return;
  uploadingFiles.value = true;
  try {
    for (const file of selected) await uploadedFileApi.upload(uploadProjectId, file);
    await loadUploadedFiles();
    message.success(`已上传 ${selected.length} 个测试文件，请在 YAML 中填写对应文件 ID`);
  } catch (error: any) {
    await loadUploadedFiles();
    message.error(error?.message || '上传测试文件失败');
  } finally {
    input.value = '';
    uploadingFiles.value = false;
  }
}
async function preview() {
  try {
    previewing.value = true;
    const result = await fileApi.preview(content.value);
    scenarios.value = result.scenarios || [];
    previewedContent.value = content.value;
    message.success(`已解析 ${scenarios.value.length} 个场景`);
  } catch (error: any) {
    scenarios.value = [];
    previewedContent.value = '';
    message.error(error?.message || '场景解析失败');
  } finally {
    previewing.value = false;
  }
}
async function save(showSuccess = true): Promise<number | null> {
  if (!projectId.value) { message.error('请选择项目'); return null; }
  if (!filename.value.trim()) { message.error('请填写文件名'); return null; }
  try {
    saving.value = true;
    const payload = { project: projectId.value, filename: filename.value.trim(), content: content.value,
      environment_name: environmentName.value || '', browser: browser.value, run_mode: runMode.value };
    const saved: any = fileId.value ? await fileApi.update(fileId.value, payload) : await fileApi.createFile(payload);
    fileId.value = saved.id;
    filename.value = saved.filename;
    savedSignature.value = signature();
    await loadFiles();
    if (showSuccess) message.success('YAML 文件已保存');
    return saved.id;
  } catch (error: any) {
    message.error(error?.message || '保存文件失败');
    return null;
  } finally {
    saving.value = false;
  }
}
async function convertToSmartCases() {
  if (converting.value) return;
  converting.value = true;
  try {
    const id = await save(false);
    if (!id) return;
    const result = await fileApi.convertToSmartCases(id);
    message.success(`已同步 ${result.count} 个智能用例（新建 ${result.created_count ?? 0}，更新 ${result.updated_count ?? 0}）`);
    if (result.count === 1) {
      await router.push({ name: 'case_ui_playwright_case_edit', params: { id: result.cases[0].id } });
    } else {
      await router.push({ name: 'case_ui_playwright_case' });
    }
  } catch (error: any) {
    message.error(error?.message || '转换智能用例失败');
  } finally {
    converting.value = false;
  }
}
async function saveAndRun() {
  if (!environmentName.value) { message.error('执行前请选择执行环境'); return; }
  const id = await save();
  if (!id) return;
  try {
    running.value = true;
    runResult.value = await fileApi.run(id);
    if (runResult.value?.passed) message.success('所有场景执行通过');
    else message.error('部分场景执行失败');
  } catch (error: any) {
    runResult.value = null;
    message.error(error?.message || '执行失败');
  } finally {
    running.value = false;
  }
}
async function deleteFile() {
  if (!fileId.value) return;
  try {
    await fileApi.DeleteDataByID(fileId.value);
    fileId.value = null;
    filename.value = '';
    content.value = '';
    savedSignature.value = signature();
    scenarios.value = [];
    previewedContent.value = '';
    runResult.value = null;
    await loadFiles();
    message.success('YAML 文件已删除');
  } catch (error: any) {
    message.error(error?.message || '删除文件失败');
  }
}
function downloadFile() {
  if (!fileId.value) return;
  const url = URL.createObjectURL(new Blob([content.value], { type: 'text/yaml;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename.value;
  link.click();
  URL.revokeObjectURL(url);
}

watch(editorHostRef, (host) => {
  if (host) createEditor(host);
  else { editorView?.destroy(); editorView = null; }
}, { flush: 'post' });
watch(content, (value) => {
  if (!editorView || editorView.state.doc.toString() === value) return;
  editorView.dispatch({ changes: { from: 0, to: editorView.state.doc.length, insert: value } });
}, { flush: 'post' });
onBeforeUnmount(() => { editorView?.destroy(); editorView = null; });

watch(projectId, async () => {
  fileKeyword.value = '';
  files.value = [];
  fileId.value = null;
  filename.value = '';
  content.value = '';
  environmentName.value = null;
  scenarios.value = [];
  previewedContent.value = '';
  runResult.value = null;
  savedSignature.value = signature();
  await Promise.all([loadFiles(), loadEnvironments(), loadUploadedFiles()]);
  if (files.value.length) selectFile(files.value[0]);
  else if (projectId.value) newFile();
});
onMounted(async () => {
  try {
    projects.value = asList(await projectApi.getDataList({ pageSize: 1000 }));
    if (projects.value.length) projectId.value = projects.value[0].id;
  } catch (error: any) {
    message.error(error?.message || '加载项目失败');
  }
});
</script>

<style scoped>
.yaml-page {
  --yaml-bg: #f5f7f8;
  --yaml-surface: #ffffff;
  --yaml-surface-soft: #f8fafb;
  --yaml-border: #dce3e6;
  --yaml-text: #1b2730;
  --yaml-muted: #6d7c88;
  --yaml-accent: #0b9270;
  --yaml-accent-soft: #e4f5ed;
  --yaml-code: #151a1d;
  min-height: 100%;
  padding: 24px 28px;
  background: var(--yaml-bg);
  color: var(--yaml-text);
}
:global(html[data-theme='dark'] .yaml-page) {
  --yaml-bg: #191c1f;
  --yaml-surface: #1e2225;
  --yaml-surface-soft: #22282b;
  --yaml-border: #363e42;
  --yaml-text: #e3e9ea;
  --yaml-muted: #94a3ac;
  --yaml-accent: #58d2a9;
  --yaml-accent-soft: #18382f;
  --yaml-code: #161a1d;
}
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 22px; margin-bottom: 20px; }
.page-title { display: flex; align-items: baseline; gap: 22px; min-width: 0; }
.page-title h1 { flex: none; margin: 0; color: var(--yaml-text); font-size: 28px; font-weight: 750; letter-spacing: -.035em; }
.page-title p { margin: 0; color: var(--yaml-muted); font-size: 13px; }
.header-actions { display: flex; flex: none; gap: 10px; align-items: center; }
.header-actions :deep(.n-button) { min-height: 40px; padding: 0 16px; }
.header-actions :deep(.n-button--primary-type) { color: #09251b; font-weight: 700; }
.settings-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 24px; margin-bottom: 14px; padding: 14px 20px; border: 1px solid var(--yaml-border); border-radius: 7px; background: var(--yaml-surface); }
.settings-strip label { display: grid; gap: 7px; min-width: 0; color: var(--yaml-muted); font-size: 12px; font-weight: 600; }
.settings-strip :deep(.n-base-selection) { width: 100%; }
.workspace { display: grid; grid-template-columns: 248px minmax(0, 1fr) 340px; gap: 12px; height: calc(100dvh - 285px); min-height: 610px; }
.file-list, .editor-panel, .preview-panel { min-width: 0; min-height: 0; overflow: hidden; border: 1px solid var(--yaml-border) !important; border-radius: 7px; background: var(--yaml-surface) !important; }
.file-list { display: flex; flex-direction: column; padding: 16px 12px; }
.file-list-header { display: flex; align-items: center; justify-content: space-between; margin: 0 4px 17px; }
.file-list-header strong, .preview-heading strong { color: var(--yaml-text); font-size: 16px; font-weight: 700; }
.file-list-header span { color: var(--yaml-muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.file-search { margin-bottom: 10px; }
.new-file-button { width: 100%; min-height: 39px; margin-bottom: 14px; font-weight: 650; }
.file-scroll { flex: 1; min-height: 0; overflow: auto; }
.file-item { display: flex; align-items: center; gap: 11px; width: 100%; min-height: 44px; padding: 0 10px; border: 0; border-left: 3px solid transparent; border-radius: 4px; background: transparent; color: var(--yaml-text); text-align: left; cursor: pointer; transition: background-color .18s, color .18s; }
.file-item .n-icon { flex: none; color: var(--yaml-muted); font-size: 17px; }
.file-item:hover { background: var(--yaml-surface-soft); }
.file-item.active { border-left-color: var(--yaml-accent); background: var(--yaml-accent-soft); }
.file-item.active .n-icon { color: var(--yaml-accent); }
.file-item:focus-visible, .preview-tabs button:focus-visible { outline: 2px solid var(--yaml-accent); outline-offset: -2px; }
.file-name { overflow: hidden; min-width: 0; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 550; }
.empty-files { padding: 18px 8px; color: var(--yaml-muted); font-size: 12px; line-height: 1.6; }
.upload-library { display: grid; gap: 9px; margin-top: 12px; padding: 13px 4px 0; border-top: 1px solid var(--yaml-border); }
.upload-library-heading { display: flex; justify-content: space-between; color: var(--yaml-text); font-size: 12px; }
.upload-library-heading span { color: var(--yaml-muted); font-variant-numeric: tabular-nums; }
.upload-library input[type='file'] { display: none; }
.uploaded-file-list { display: grid; gap: 5px; max-height: 110px; overflow: auto; }
.uploaded-file-item { display: flex; justify-content: space-between; gap: 8px; color: var(--yaml-muted); font-size: 11px; }
.uploaded-file-item span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.uploaded-file-item code { flex: none; color: var(--yaml-accent); }
.uploaded-file-list p { margin: 0; color: var(--yaml-muted); font-size: 11px; line-height: 1.5; }
.editor-panel { display: flex; flex-direction: column; }
.editor-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 54px; padding: 0 16px; border-bottom: 1px solid var(--yaml-border); }
.file-heading-main { display: flex; align-items: center; gap: 10px; min-width: 0; flex: 1; }
.filename-input { width: min(300px, 100%); font-size: 15px; font-weight: 700; }
.filename-input :deep(.n-input-wrapper) { padding-left: 0; box-shadow: none !important; }
.filename-input :deep(.n-input__input-el) { font-weight: 700; }
.filename-input:hover :deep(.n-input-wrapper), .filename-input:focus-within :deep(.n-input-wrapper) { box-shadow: 0 0 0 1px var(--yaml-accent) inset !important; }
.unsaved, .saved-state { display: inline-flex; flex: none; align-items: center; gap: 6px; font-size: 12px; }
.unsaved { color: #e2a655; }.saved-state { color: var(--yaml-muted); }
.unsaved i, .saved-state i { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.editor-tools { display: flex; align-items: center; gap: 5px; }
.editor-tools .n-button { width: 27px; height: 27px; font-size: 16px; }
.steps-help-trigger { color: var(--yaml-muted); }
.steps-help-trigger:hover, .steps-help-trigger:focus-visible { color: var(--yaml-accent); }
.steps-help-content { --yaml-surface: #ffffff; --yaml-text: #1b2730; --yaml-muted: #6d7c88; --yaml-border: #dce3e6; --yaml-accent: #0b9270; box-sizing: border-box; max-height: min(560px, 70vh); overflow: auto; padding: 16px; background: var(--yaml-surface); color: var(--yaml-text); }
:global(html[data-theme='dark'] .steps-help-content) { --yaml-surface: #1e2225; --yaml-text: #e3e9ea; --yaml-muted: #94a3ac; --yaml-border: #363e42; --yaml-accent: #58d2a9; }
.steps-help-content > strong { display: block; margin-bottom: 4px; font-size: 14px; }
.steps-help-content > p { margin: 0 0 12px; color: var(--yaml-muted); font-size: 12px; line-height: 1.5; }
.steps-help-list { display: grid; gap: 0; }
.steps-help-list > div { display: grid; grid-template-columns: 72px minmax(0, 1fr) 24px; gap: 8px; align-items: center; padding: 6px 0; border-top: 1px solid var(--yaml-border); }
.steps-help-list span { color: var(--yaml-accent); font-size: 11px; }
.steps-help-list code { overflow-wrap: anywhere; color: var(--yaml-text); font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 11px; }
.steps-help-list .copy-step-button { width: 24px; height: 24px; color: var(--yaml-muted); font-size: 14px; }
.steps-help-list .copy-step-button:hover, .steps-help-list .copy-step-button:focus-visible { color: var(--yaml-accent); }
.steps-help-content .steps-help-note { margin: 12px 0 0; }
.indent-hint { margin-right: 6px; color: var(--yaml-muted); font-size: 11px; white-space: nowrap; }
.yaml-code-editor { flex: 1; min-height: 0; overflow: hidden; background: var(--yaml-code); color: #d9e4ef; }
.yaml-code-editor:focus-within { box-shadow: 0 0 0 1px var(--yaml-accent) inset; }
.yaml-code-editor :deep(.cm-editor) { height: 100%; background: transparent; color: #d9e4ef; font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 13px; font-weight: 500; }
.yaml-code-editor :deep(.cm-editor.cm-focused) { outline: none; }
.yaml-code-editor :deep(.cm-scroller) { overflow: auto; font-family: inherit; line-height: 24px; }
.yaml-code-editor :deep(.cm-content) { padding: 18px 0; caret-color: #e6edf3; }
.yaml-code-editor :deep(.cm-line) { padding: 0 18px; }
.yaml-code-editor :deep(.cm-gutters) { min-width: 56px; padding: 18px 0; border-right: 1px solid #2b3439; background: var(--yaml-code); color: #7e8b96; }
.yaml-code-editor :deep(.cm-lineNumbers .cm-gutterElement) { min-width: 44px; padding: 0 11px 0 0; line-height: 24px; }
.yaml-code-editor :deep(.cm-selectionBackground), .yaml-code-editor :deep(.cm-editor.cm-focused .cm-selectionBackground) { background: rgba(91, 160, 244, .36); }
.yaml-code-editor :deep(.yaml-token-comment) { color: #82919b; }
.yaml-code-editor :deep(.yaml-token-key) { color: #73e5a3; font-weight: 650; }
.editor-footnote { padding: 9px 16px; border-top: 1px solid var(--yaml-border); color: var(--yaml-muted); font-size: 11px; line-height: 1.5; }
.preview-panel { display: flex; flex-direction: column; padding: 15px 13px 12px; }
.preview-heading { display: flex; align-items: center; justify-content: space-between; min-height: 28px; margin: 0 2px 13px; }
.preview-heading .n-button { font-size: 16px; }
.preview-tabs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); margin-bottom: 14px; border: 1px solid var(--yaml-border); border-radius: 5px; overflow: hidden; }
.preview-tabs button { min-height: 36px; border: 0; background: transparent; color: var(--yaml-muted); font-size: 12px; cursor: pointer; }
.preview-tabs button + button { border-left: 1px solid var(--yaml-border); }
.preview-tabs button.active { background: var(--yaml-accent-soft); color: var(--yaml-accent); font-weight: 700; box-shadow: inset 0 0 0 1px var(--yaml-accent); }
.preview-scroll { flex: 1; min-height: 0; overflow: auto; }
.preview-empty { margin-top: 95px; }
.scenario-list { display: grid; gap: 10px; }
.scenario-item { padding: 12px 13px; border: 1px solid var(--yaml-border); border-radius: 6px; background: var(--yaml-surface-soft); }
.scenario-heading { display: flex; align-items: center; gap: 9px; }
.scenario-heading strong { overflow: hidden; min-width: 0; color: var(--yaml-text); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.scenario-index { display: grid; flex: none; width: 26px; height: 26px; place-items: center; border-radius: 50%; background: var(--yaml-accent-soft); color: var(--yaml-accent); font-size: 12px; font-weight: 700; }
.valid-badge { flex: none; margin-left: auto; padding: 2px 7px; border: 1px solid var(--yaml-accent); border-radius: 20px; color: var(--yaml-accent); font-size: 11px; }
.valid-badge.stale { border-color: #d39954; color: #d39954; }
.scenario-item dl { display: grid; gap: 5px; margin: 12px 0; }
.scenario-item dl > div { display: grid; grid-template-columns: 62px minmax(0, 1fr); gap: 4px; font-size: 11px; }
.scenario-item dt { color: var(--yaml-muted); }.scenario-item dd { overflow: hidden; margin: 0; color: var(--yaml-text); text-overflow: ellipsis; white-space: nowrap; }
.steps-heading { padding-top: 10px; border-top: 1px solid var(--yaml-border); color: var(--yaml-muted); font-size: 11px; }
.preview-steps { display: grid; gap: 8px; margin: 10px 0 0; padding: 0; list-style: none; }
.preview-steps li { display: flex; align-items: flex-start; gap: 8px; min-width: 0; }
.preview-steps li > span { display: grid; flex: none; width: 20px; height: 20px; place-items: center; border-radius: 50%; background: var(--yaml-border); color: var(--yaml-text); font-size: 10px; font-variant-numeric: tabular-nums; }
.preview-steps p { overflow-wrap: anywhere; margin: 2px 0 0; color: var(--yaml-text); font-size: 11px; line-height: 1.5; }
.preview-steps em, .preview-assertions em { display: inline-block; margin-left: 6px; color: var(--yaml-accent); font-size: 10px; font-style: normal; white-space: nowrap; }
.assertion-heading { margin-top: 13px; padding-top: 10px; border-top: 1px solid var(--yaml-border); color: var(--yaml-muted); font-size: 11px; }
.preview-assertions { display: grid; gap: 7px; margin: 9px 0 0; padding: 0; list-style: none; }
.preview-assertions li { display: flex; align-items: flex-start; gap: 8px; overflow-wrap: anywhere; color: var(--yaml-text); font-size: 11px; line-height: 1.5; }
.preview-assertions span { display: grid; flex: none; width: 18px; height: 18px; place-items: center; border-radius: 50%; background: var(--yaml-accent); color: #09251b; font-size: 11px; font-weight: 750; }
.raw-preview { overflow: auto; margin: 0; padding: 12px; border: 1px solid var(--yaml-border); border-radius: 5px; background: var(--yaml-surface-soft); color: var(--yaml-text); font-size: 11px; line-height: 1.55; }
.preview-footer { padding: 13px 3px 0; border-top: 1px solid var(--yaml-border); color: var(--yaml-muted); font-size: 11px; text-align: center; }
.stale-note { color: #d39954; }
.result-panel { max-height: 135px; margin-top: 12px; overflow: auto; font-size: 12px; }
.run-screenshots { display: grid; gap: 8px; max-height: 230px; margin-top: 10px; overflow: auto; padding: 10px; border: 1px solid var(--yaml-border); border-radius: 5px; }
.run-screenshots > strong { color: var(--yaml-text); font-size: 12px; }
.run-screenshots a { display: grid; gap: 4px; color: var(--yaml-accent); font-size: 11px; text-decoration: none; }
.run-screenshots img { display: block; width: 100%; max-height: 155px; object-fit: contain; object-position: left top; border: 1px solid var(--yaml-border); border-radius: 4px; background: var(--yaml-code); }
.project-empty { margin-top: 120px; }
.editor-expanded .workspace { grid-template-columns: minmax(0, 1fr); }
.editor-expanded .file-list, .editor-expanded .preview-panel { display: none; }
@media (max-width: 1260px) {
  .workspace { grid-template-columns: 210px minmax(0, 1fr) 290px; }
  .settings-strip { gap: 12px; }
  .indent-hint { display: none; }
}
@media (max-width: 980px) {
  .page-header { align-items: flex-start; flex-direction: column; }
  .workspace { grid-template-columns: 210px minmax(0, 1fr); height: auto; min-height: 650px; }
  .file-list, .editor-panel { min-height: 650px; }
  .preview-panel { grid-column: 1 / -1; min-height: 360px; }
  .preview-scroll { max-height: 410px; }
}
@media (max-width: 680px) {
  .yaml-page { padding: 16px 12px; }
  .page-title { display: block; }.page-title p { margin-top: 4px; }
  .header-actions { flex-wrap: wrap; width: 100%; }.header-actions :deep(.n-button) { flex: 1; }
  .settings-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); padding: 12px; }
  .workspace { grid-template-columns: minmax(0, 1fr); }
  .file-list { min-height: 170px; max-height: 260px; }
  .editor-panel { min-height: 550px; }.preview-panel { grid-column: 1; }
  .file-heading-main { max-width: 60%; }.saved-state, .unsaved { font-size: 10px; }
  .editor-footnote { font-size: 10px; }
}
</style>
