<template>
  <div class="tools-page">
    <div class="tools-shell">
      <header class="page-heading">
        <div>
          <h2>工具</h2>
          <p>集中使用测试数据处理与转换工具，数据仅在当前浏览器中处理。</p>
        </div>
      </header>

      <div class="tools-layout">
        <aside class="tool-navigation" aria-label="工具列表">
          <button
            v-for="item in tools"
            :key="item.key"
            type="button"
            class="tool-entry"
            :class="{ active: activeTool === item.key }"
            @click="activeTool = item.key"
          >
            <span class="tool-icon"><component :is="item.icon" :size="22" /></span>
            <span><strong>{{ item.name }}</strong><small>{{ item.description }}</small></span>
            <PhCaretRight :size="16" />
          </button>
        </aside>

        <main class="tool-workspace">
          <section v-if="activeTool === 'json'" class="tool-panel">
            <div class="panel-heading"><div><h3>JSON 格式化</h3><p>格式化、校验或压缩 JSON 数据</p></div></div>
            <div class="editor-grid">
              <div class="editor-block"><label>原始数据</label><n-input v-model:value="jsonInput" type="textarea" :autosize="editorSize" placeholder="请输入 JSON" /></div>
              <div class="editor-block"><label>处理结果</label><n-input :value="jsonOutput" type="textarea" :autosize="editorSize" readonly placeholder="处理结果将显示在这里" /></div>
            </div>
            <div class="panel-actions"><n-button type="primary" @click="formatJson(false)">格式化</n-button><n-button @click="formatJson(true)">压缩</n-button><n-button @click="copyText(jsonOutput)">复制结果</n-button><n-button quaternary @click="clearJson">清空</n-button></div>
          </section>

          <section v-else-if="activeTool === 'jsonDiff'" class="tool-panel">
            <div class="panel-heading"><div><h3>JSON 对比</h3><p>按字段路径对比两份 JSON，对象字段顺序不影响结果</p></div></div>
            <div class="editor-grid">
              <div class="editor-block"><label>左侧 JSON</label><n-input v-model:value="leftJsonInput" type="textarea" :autosize="editorSize" placeholder="请输入第一份 JSON" /><p v-if="leftJsonError" class="json-input-error">{{ leftJsonError }}</p></div>
              <div class="editor-block"><label>右侧 JSON</label><n-input v-model:value="rightJsonInput" type="textarea" :autosize="editorSize" placeholder="请输入第二份 JSON" /><p v-if="rightJsonError" class="json-input-error">{{ rightJsonError }}</p></div>
            </div>
            <div class="panel-actions"><n-button type="primary" @click="compareJson">开始对比</n-button><n-button quaternary @click="clearJsonDiff">清空</n-button></div>
            <div v-if="jsonDiffCompared" class="diff-result">
              <div class="diff-summary" :class="{ identical: !jsonDifferences.length }">
                <PhCheckCircle v-if="!jsonDifferences.length" :size="21" weight="fill" />
                <PhWarningCircle v-else :size="21" weight="fill" />
                <strong>{{ jsonDifferences.length ? `发现 ${jsonDifferences.length} 处差异` : '两份 JSON 内容一致' }}</strong>
              </div>
              <div v-if="jsonDifferences.length" class="diff-table">
                <div class="diff-table-header"><span>差异类型</span><span>字段路径</span><span>左侧值</span><span>右侧值</span></div>
                <div v-for="(item, index) in jsonDifferences" :key="`${item.path}-${index}`" class="diff-row">
                  <span><n-tag size="small" :type="diffTagType(item.kind)">{{ diffKindLabel(item.kind) }}</n-tag></span>
                  <code>{{ item.path }}</code>
                  <pre>{{ formatDiffValue(item.left) }}</pre>
                  <pre>{{ formatDiffValue(item.right) }}</pre>
                </div>
              </div>
            </div>
          </section>

          <section v-else-if="activeTool === 'uuid'" class="tool-panel">
            <div class="panel-heading"><div><h3>UUID 生成</h3><p>批量生成标准 UUID v4 测试数据</p></div></div>
            <div class="compact-form"><label>生成数量</label><n-input-number v-model:value="uuidCount" :min="1" :max="100" /><n-button type="primary" @click="generateUuids">生成 UUID</n-button></div>
            <n-input :value="uuidOutput" type="textarea" :autosize="editorSize" readonly placeholder="点击生成 UUID" />
            <div class="panel-actions"><n-button @click="copyText(uuidOutput)">复制全部</n-button><n-button quaternary @click="uuidOutput = ''">清空</n-button></div>
          </section>

          <section v-else-if="activeTool === 'timestamp'" class="tool-panel">
            <div class="panel-heading"><div><h3>时间戳转换</h3><p>在 Unix 时间戳和本地日期时间之间转换</p></div></div>
            <div class="timestamp-grid">
              <div class="form-card">
                <label>时间戳转日期时间</label>
                <n-input v-model:value="timestampInput" placeholder="10 位秒或 13 位毫秒时间戳" />
                <div class="result-line"><span>日期时间</span><strong>{{ timestampResult || '-' }}</strong></div>
                <div class="card-actions"><n-button type="primary" @click="convertTimestamp">转换</n-button><n-button @click="setCurrentTimestamp">使用当前时间</n-button></div>
              </div>
              <div class="form-card">
                <label>日期时间转时间戳</label>
                <n-date-picker v-model:value="dateTimeInput" type="datetime" clearable style="width: 100%" />
                <div class="timestamp-results">
                  <div class="result-line"><span>秒级（10 位）</span><strong>{{ secondTimestamp || '-' }}</strong><button type="button" @click="copyText(secondTimestamp)">复制</button></div>
                  <div class="result-line"><span>毫秒级（13 位）</span><strong>{{ millisecondTimestamp || '-' }}</strong><button type="button" @click="copyText(millisecondTimestamp)">复制</button></div>
                </div>
                <div class="card-actions"><n-button type="primary" @click="convertDateTime">转换</n-button><n-button @click="useCurrentDateTime">当前日期时间</n-button></div>
              </div>
            </div>
          </section>

          <section v-else class="tool-panel">
            <div class="panel-heading"><div><h3>Base64 编解码</h3><p>支持中英文及特殊字符的 Base64 编码与解码</p></div></div>
            <div class="editor-grid">
              <div class="editor-block"><label>原始内容</label><n-input v-model:value="base64Input" type="textarea" :autosize="editorSize" placeholder="请输入待处理内容" /></div>
              <div class="editor-block"><label>处理结果</label><n-input :value="base64Output" type="textarea" :autosize="editorSize" readonly placeholder="处理结果将显示在这里" /></div>
            </div>
            <div class="panel-actions"><n-button type="primary" @click="encodeBase64">编码</n-button><n-button @click="decodeBase64">解码</n-button><n-button @click="copyText(base64Output)">复制结果</n-button><n-button quaternary @click="clearBase64">清空</n-button></div>
          </section>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { markRaw, ref } from 'vue';
  import { useMessage } from 'naive-ui';
  import { PhArrowsLeftRight, PhBracketsCurly, PhCaretRight, PhCheckCircle, PhClock, PhFingerprint, PhTextAa, PhWarningCircle } from '@phosphor-icons/vue';

  type ToolKey = 'json' | 'jsonDiff' | 'uuid' | 'timestamp' | 'base64';
  type DiffKind = 'added' | 'removed' | 'changed' | 'type';
  interface JsonDifference { path: string; kind: DiffKind; left?: unknown; right?: unknown }

  const message = useMessage();
  const activeTool = ref<ToolKey>('json');
  const editorSize = { minRows: 12, maxRows: 20 };
  const tools = [
    { key: 'json' as const, name: 'JSON 格式化', description: '格式化、压缩与校验', icon: markRaw(PhBracketsCurly) },
    { key: 'jsonDiff' as const, name: 'JSON 对比', description: '对比两份 JSON 差异', icon: markRaw(PhArrowsLeftRight) },
    { key: 'uuid' as const, name: 'UUID 生成', description: '批量生成唯一标识', icon: markRaw(PhFingerprint) },
    { key: 'timestamp' as const, name: '时间戳转换', description: '时间戳与日期互转', icon: markRaw(PhClock) },
    { key: 'base64' as const, name: 'Base64 编解码', description: '文本编码与解码', icon: markRaw(PhTextAa) },
  ];

  const jsonInput = ref('');
  const jsonOutput = ref('');
  const leftJsonInput = ref('');
  const rightJsonInput = ref('');
  const jsonDifferences = ref<JsonDifference[]>([]);
  const jsonDiffCompared = ref(false);
  const leftJsonError = ref('');
  const rightJsonError = ref('');
  const uuidCount = ref(5);
  const uuidOutput = ref('');
  const timestampInput = ref('');
  const timestampResult = ref('');
  const dateTimeInput = ref<number | null>(null);
  const secondTimestamp = ref('');
  const millisecondTimestamp = ref('');
  const base64Input = ref('');
  const base64Output = ref('');

  function formatJson(compressed: boolean) {
    try {
      jsonOutput.value = JSON.stringify(JSON.parse(jsonInput.value), null, compressed ? 0 : 2);
    } catch {
      message.error('请输入有效的 JSON 数据');
    }
  }

  function clearJson() {
    jsonInput.value = '';
    jsonOutput.value = '';
  }

  function valueType(value: unknown) {
    if (value === null) return 'null';
    if (Array.isArray(value)) return 'array';
    return typeof value;
  }

  function collectJsonDifferences(left: unknown, right: unknown, path = '$', result: JsonDifference[] = []) {
    const leftType = valueType(left);
    const rightType = valueType(right);
    if (leftType !== rightType) {
      result.push({ path, kind: 'type', left, right });
      return result;
    }
    if (leftType === 'array') {
      const leftArray = left as unknown[];
      const rightArray = right as unknown[];
      const length = Math.max(leftArray.length, rightArray.length);
      for (let index = 0; index < length; index += 1) {
        const itemPath = `${path}[${index}]`;
        if (index >= leftArray.length) result.push({ path: itemPath, kind: 'added', right: rightArray[index] });
        else if (index >= rightArray.length) result.push({ path: itemPath, kind: 'removed', left: leftArray[index] });
        else collectJsonDifferences(leftArray[index], rightArray[index], itemPath, result);
      }
      return result;
    }
    if (leftType === 'object') {
      const leftObject = left as Record<string, unknown>;
      const rightObject = right as Record<string, unknown>;
      const keys = new Set([...Object.keys(leftObject), ...Object.keys(rightObject)]);
      keys.forEach((key) => {
        const itemPath = /^[A-Za-z_$][\w$]*$/.test(key) ? `${path}.${key}` : `${path}[${JSON.stringify(key)}]`;
        if (!Object.prototype.hasOwnProperty.call(leftObject, key)) result.push({ path: itemPath, kind: 'added', right: rightObject[key] });
        else if (!Object.prototype.hasOwnProperty.call(rightObject, key)) result.push({ path: itemPath, kind: 'removed', left: leftObject[key] });
        else collectJsonDifferences(leftObject[key], rightObject[key], itemPath, result);
      });
      return result;
    }
    if (!Object.is(left, right)) result.push({ path, kind: 'changed', left, right });
    return result;
  }

  function jsonLinePosition(source: string, index: number) {
    const before = source.slice(0, Math.max(0, index));
    const lines = before.split('\n');
    return `第 ${lines.length} 行、第 ${lines[lines.length - 1].length + 1} 列`;
  }

  function parseJsonInput(source: string, side: '左侧' | '右侧') {
    if (!source.trim()) throw new Error(`${side} JSON 不能为空`);
    try {
      return JSON.parse(source);
    } catch (error: any) {
      const bareValue = /:\s*([A-Za-z_$][\w$.-]*)\s*(?=[,}\]])/g;
      let match: RegExpExecArray | null;
      while ((match = bareValue.exec(source))) {
        if (['true', 'false', 'null'].includes(match[1])) continue;
        const valueIndex = match.index + match[0].indexOf(match[1]);
        throw new Error(`${side} JSON ${jsonLinePosition(source, valueIndex)}：字符串 ${match[1]} 必须使用双引号，请改为 "${match[1]}"`);
      }
      const positionMatch = String(error?.message || '').match(/position\s+(\d+)/i);
      const location = positionMatch ? ` ${jsonLinePosition(source, Number(positionMatch[1]))}` : '';
      throw new Error(`${side} JSON${location}格式不正确，请检查双引号、逗号和括号是否完整`);
    }
  }

  function compareJson() {
    leftJsonError.value = '';
    rightJsonError.value = '';
    let left: unknown;
    let right: unknown;
    try {
      left = parseJsonInput(leftJsonInput.value, '左侧');
    } catch (error: any) {
      leftJsonError.value = error?.message || '左侧 JSON 格式不正确';
    }
    try {
      right = parseJsonInput(rightJsonInput.value, '右侧');
    } catch (error: any) {
      rightJsonError.value = error?.message || '右侧 JSON 格式不正确';
    }
    if (leftJsonError.value || rightJsonError.value) {
      jsonDiffCompared.value = false;
      jsonDifferences.value = [];
      message.error(leftJsonError.value || rightJsonError.value);
      return;
    }
    try {
      jsonDifferences.value = collectJsonDifferences(left, right);
      jsonDiffCompared.value = true;
    } catch (error: any) {
      jsonDiffCompared.value = false;
      jsonDifferences.value = [];
      message.error(`JSON 解析失败：${error?.message || '请检查输入内容'}`);
    }
  }

  function clearJsonDiff() {
    leftJsonInput.value = '';
    rightJsonInput.value = '';
    jsonDifferences.value = [];
    jsonDiffCompared.value = false;
    leftJsonError.value = '';
    rightJsonError.value = '';
  }

  const diffKindLabel = (kind: DiffKind) => ({ added: '新增', removed: '删除', changed: '变更', type: '类型变更' }[kind]);
  const diffTagType = (kind: DiffKind) => kind === 'added' ? 'success' : kind === 'removed' ? 'error' : kind === 'type' ? 'warning' : 'info';
  const formatDiffValue = (value: unknown) => value === undefined ? '—' : typeof value === 'string' ? value : JSON.stringify(value, null, 2);

  function createUuid() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
      const random = Math.floor(Math.random() * 16);
      return (char === 'x' ? random : (random & 0x3) | 0x8).toString(16);
    });
  }

  function generateUuids() {
    uuidOutput.value = Array.from({ length: uuidCount.value || 1 }, createUuid).join('\n');
  }

  function convertTimestamp() {
    const raw = timestampInput.value.trim();
    const numeric = Number(raw);
    if (!raw || !Number.isFinite(numeric)) {
      message.error('请输入有效的时间戳');
      return;
    }
    const date = new Date(raw.length <= 10 ? numeric * 1000 : numeric);
    if (Number.isNaN(date.getTime())) {
      message.error('时间戳无法转换');
      return;
    }
    timestampResult.value = date.toLocaleString('zh-CN', { hour12: false });
  }

  function setCurrentTimestamp() {
    timestampInput.value = String(Date.now());
    convertTimestamp();
  }

  function convertDateTime() {
    if (dateTimeInput.value === null) {
      message.error('请选择日期和时间');
      return;
    }
    const milliseconds = Number(dateTimeInput.value);
    millisecondTimestamp.value = String(milliseconds);
    secondTimestamp.value = String(Math.floor(milliseconds / 1000));
  }

  function useCurrentDateTime() {
    dateTimeInput.value = Date.now();
    convertDateTime();
  }

  function encodeBase64() {
    const bytes = new TextEncoder().encode(base64Input.value);
    base64Output.value = btoa(Array.from(bytes, (byte) => String.fromCharCode(byte)).join(''));
  }

  function decodeBase64() {
    try {
      const binary = atob(base64Input.value.trim());
      const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
      base64Output.value = new TextDecoder().decode(bytes);
    } catch {
      message.error('请输入有效的 Base64 内容');
    }
  }

  function clearBase64() {
    base64Input.value = '';
    base64Output.value = '';
  }

  async function copyText(value: string) {
    if (!value) {
      message.warning('暂无可复制的内容');
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      message.success('已复制');
    } catch {
      message.error('复制失败，请手动复制');
    }
  }
</script>

<style scoped lang="less">
  .tools-page { min-height: 100%; padding: 28px 32px 36px; background: #f7f9fc; }
  .tools-shell { width: 100%; max-width: 1440px; margin: 0 auto; }
  .page-heading { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 20px; }
  .page-heading h2 { margin: 0; color: #18243a; font-size: 26px; font-weight: 700; }
  .page-heading p { margin: 8px 0 0; color: #7b899d; font-size: 14px; }
  .tools-layout { display: grid; grid-template-columns: 268px minmax(0, 1fr); min-height: 590px; overflow: hidden; border: 1px solid #dfe5ee; border-radius: 10px; background: #fff; }
  .tool-navigation { padding: 14px; border-right: 1px solid #e5eaf1; background: #fafbfc; }
  .tool-entry { display: grid; width: 100%; grid-template-columns: 40px minmax(0, 1fr) 16px; align-items: center; gap: 11px; margin-bottom: 6px; padding: 12px; border: 0; border-radius: 8px; color: #536176; background: transparent; text-align: left; cursor: pointer; }
  .tool-entry:hover { background: #f0f4fb; }
  .tool-entry.active { color: #315ee8; background: #eaf0ff; }
  .tool-icon { display: grid; width: 40px; height: 40px; place-items: center; border-radius: 8px; color: #4367dd; background: #fff; box-shadow: 0 1px 3px rgba(25, 44, 82, .08); }
  .tool-entry strong, .tool-entry small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tool-entry strong { font-size: 14px; }
  .tool-entry small { margin-top: 3px; color: #8a96a8; font-size: 12px; }
  .tool-workspace { min-width: 0; padding: 28px 30px; }
  .panel-heading { display: flex; align-items: flex-start; justify-content: space-between; padding-bottom: 20px; border-bottom: 1px solid #e7ebf1; }
  .panel-heading h3 { margin: 0; color: #1d293b; font-size: 20px; }
  .panel-heading p { margin: 7px 0 0; color: #7b899d; font-size: 13px; }
  .editor-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 22px; }
  .editor-block label, .compact-form label, .form-card label { display: block; margin-bottom: 9px; color: #3a485d; font-size: 14px; font-weight: 600; }
  :deep(.editor-block textarea) { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; line-height: 1.65; }
  .panel-actions { display: flex; align-items: center; gap: 10px; margin-top: 18px; }
  .json-input-error { margin: 8px 0 0; color: #e5484d; font-size: 12px; line-height: 1.55; }
  .diff-result { margin-top: 22px; }
  .diff-summary { display: flex; align-items: center; gap: 9px; padding: 13px 15px; border: 1px solid #f1d39a; border-radius: 8px; color: #c77908; background: #fff9ee; }
  .diff-summary.identical { border-color: #bde5cf; color: #16975f; background: #f2fbf6; }
  .diff-table { margin-top: 12px; overflow: hidden; border: 1px solid #e1e6ed; border-radius: 8px; }
  .diff-table-header, .diff-row { display: grid; grid-template-columns: 108px minmax(180px, .8fr) minmax(180px, 1fr) minmax(180px, 1fr); align-items: stretch; }
  .diff-table-header { min-height: 42px; align-items: center; color: #647287; background: #f6f8fb; font-size: 13px; font-weight: 600; }
  .diff-table-header span, .diff-row > span, .diff-row > code, .diff-row > pre { padding: 10px 12px; border-right: 1px solid #e7ebf1; }
  .diff-table-header span:last-child, .diff-row > pre:last-child { border-right: 0; }
  .diff-row { min-height: 48px; border-top: 1px solid #e7ebf1; }
  .diff-row > span { display: flex; align-items: flex-start; }
  .diff-row code { overflow-wrap: anywhere; color: #315ee8; font-size: 12px; }
  .diff-row pre { max-height: 150px; margin: 0; overflow: auto; color: #35445a; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; }
  .compact-form { display: flex; align-items: end; gap: 12px; margin: 24px 0 18px; }
  .compact-form label { align-self: center; margin: 0 4px 0 0; }
  .timestamp-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 24px; }
  .form-card { display: flex; min-height: 190px; flex-direction: column; gap: 14px; padding: 22px; border: 1px solid #e3e8ef; border-radius: 9px; background: #fbfcfe; }
  .form-card label { margin: 0; }
  .form-card .n-button { align-self: flex-start; }
  .card-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: auto; }
  .timestamp-results { display: grid; gap: 9px; }
  .result-line { display: grid; min-height: 42px; grid-template-columns: 112px minmax(0, 1fr) auto; align-items: center; gap: 10px; padding: 9px 11px; border: 1px solid #e4e9f0; border-radius: 7px; background: #fff; }
  .result-line span { color: #7b899d; font-size: 12px; }
  .result-line strong { overflow: hidden; color: #24334a; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 14px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
  .result-line button { padding: 0; border: 0; color: #315ee8; background: transparent; cursor: pointer; }
  @media (max-width: 900px) { .tools-page { padding: 20px; } .tools-layout { grid-template-columns: 1fr; } .tool-navigation { display: grid; grid-template-columns: repeat(2, 1fr); border-right: 0; border-bottom: 1px solid #e5eaf1; } .editor-grid, .timestamp-grid { grid-template-columns: 1fr; } .diff-table { overflow-x: auto; } .diff-table-header, .diff-row { min-width: 760px; } }
</style>
