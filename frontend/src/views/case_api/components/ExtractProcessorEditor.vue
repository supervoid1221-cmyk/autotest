<template>
  <section class="processor-editor">
    <header>
      <div><strong>数据处理</strong><span>按从上到下的顺序执行</span></div>
      <n-select
        class="processor-adder"
        :value="null"
        :options="extractProcessorOptions"
        filterable
        placeholder="＋ 添加处理步骤"
        size="small"
        @update:value="addProcessor"
      />
    </header>

    <div v-if="modelValue.length" class="processor-list">
      <article v-for="(processor, index) in modelValue" :key="`${index}-${processor.type}`" class="processor-row">
        <span class="processor-index">{{ index + 1 }}</span>
        <n-select
          class="processor-type"
          :value="processor.type"
          :options="extractProcessorOptions"
          filterable
          size="small"
          @update:value="changeType(index, $event)"
        />
        <div class="processor-fields">
          <n-input v-if="['prefix', 'suffix', 'default'].includes(processor.type)" :value="stringValue(processor.value)" :placeholder="processor.type === 'default' ? '请输入默认值' : '请输入内容'" size="small" @update:value="update(index, 'value', $event)" @blur="changed" />
          <template v-else-if="processor.type === 'replace'">
            <n-input :value="stringValue(processor.search)" placeholder="查找内容" size="small" @update:value="update(index, 'search', $event)" @blur="changed" />
            <n-input :value="stringValue(processor.replacement)" placeholder="替换为" size="small" @update:value="update(index, 'replacement', $event)" @blur="changed" />
            <n-input-number :value="numberValue(processor.count, -1)" :show-button="false" placeholder="次数，-1 为全部" size="small" @update:value="update(index, 'count', $event ?? -1)" @blur="changed" />
          </template>
          <template v-else-if="processor.type === 'regex'">
            <n-input :value="stringValue(processor.pattern)" placeholder="正则表达式" size="small" @update:value="update(index, 'pattern', $event)" @blur="changed" />
            <n-input-number :value="numberValue(processor.group, 0)" :min="0" :show-button="false" placeholder="捕获组" size="small" @update:value="update(index, 'group', $event ?? 0)" @blur="changed" />
          </template>
          <template v-else-if="processor.type === 'split'">
            <n-input :value="stringValue(processor.separator)" placeholder="分隔符，空表示空白字符" size="small" @update:value="update(index, 'separator', $event)" @blur="changed" />
            <n-input-number :value="numberValue(processor.index, 0)" :show-button="false" placeholder="索引" size="small" @update:value="update(index, 'index', $event ?? 0)" @blur="changed" />
          </template>
          <n-select v-else-if="processor.type === 'cast'" :value="processor.target" :options="castOptions" size="small" @update:value="updateAndSave(index, 'target', $event)" />
          <template v-else-if="['datetime_to_timestamp', 'timestamp_to_datetime'].includes(processor.type)">
            <n-input :value="stringValue(processor.format)" :placeholder="processor.type === 'datetime_to_timestamp' ? '日期格式，留空使用 ISO' : '输出格式'" size="small" @update:value="update(index, 'format', $event)" @blur="changed" />
            <n-select :value="processor.unit" :options="processor.type === 'datetime_to_timestamp' ? timestampOutputUnitOptions : timestampInputUnitOptions" size="small" @update:value="updateAndSave(index, 'unit', $event)" />
            <n-input :value="stringValue(processor.timezone)" placeholder="时区，如 Asia/Shanghai" size="small" @update:value="update(index, 'timezone', $event)" @blur="changed" />
          </template>
          <template v-else-if="processor.type === 'array_item'">
            <n-select :value="processor.position" :options="arrayPositionOptions" size="small" @update:value="updateAndSave(index, 'position', $event)" />
            <n-input-number v-if="processor.position === 'index'" :value="numberValue(processor.index, 0)" :show-button="false" placeholder="索引" size="small" @update:value="update(index, 'index', $event ?? 0)" @blur="changed" />
          </template>
          <n-input v-else-if="processor.type === 'object_pick'" :value="stringValue(processor.keys)" placeholder="字段名，多个用逗号分隔" size="small" @update:value="update(index, 'keys', $event)" @blur="changed" />
          <n-input v-else-if="processor.type === 'object_rename'" :value="mappingText(processor.mapping)" placeholder="原字段:新字段，多个用逗号分隔" size="small" @update:value="updateMapping(index, $event)" @blur="changed" />
          <span v-else class="processor-description">{{ description(processor.type) }}</span>
        </div>
        <div class="processor-actions">
          <n-button text size="tiny" :disabled="index === 0" title="上移" @click="move(index, -1)">↑</n-button>
          <n-button text size="tiny" :disabled="index === modelValue.length - 1" title="下移" @click="move(index, 1)">↓</n-button>
          <n-button text size="tiny" type="error" @click="remove(index)">删除</n-button>
        </div>
      </article>
    </div>
    <n-empty v-else size="small" description="未配置数据处理，将直接使用提取结果" />
  </section>
</template>

<script setup lang="ts">
import { defaultProcessor, extractProcessorOptions, type ExtractProcessor } from '../extract-processors';

const props = defineProps<{ modelValue: ExtractProcessor[] }>();
const emit = defineEmits<{ (event: 'update:modelValue', value: ExtractProcessor[]): void; (event: 'change'): void }>();

const castOptions = [{ label: '字符串', value: 'string' }, { label: '数字', value: 'number' }, { label: '布尔值', value: 'boolean' }];
const timestampOutputUnitOptions = [{ label: '秒', value: 'seconds' }, { label: '毫秒', value: 'milliseconds' }];
const timestampInputUnitOptions = [{ label: '自动判断', value: 'auto' }, { label: '秒', value: 'seconds' }, { label: '毫秒', value: 'milliseconds' }];
const arrayPositionOptions = [{ label: '第一项', value: 'first' }, { label: '最后一项', value: 'last' }, { label: '指定索引', value: 'index' }];

const clone = () => JSON.parse(JSON.stringify(props.modelValue || [])) as ExtractProcessor[];
const changed = () => emit('change');
const stringValue = (value: unknown) => value == null ? '' : String(value);
const numberValue = (value: unknown, fallback: number) => Number.isFinite(Number(value)) ? Number(value) : fallback;

function addProcessor(type: string) {
  emit('update:modelValue', [...clone(), defaultProcessor(type)]);
  emit('change');
}
function changeType(index: number, type: string) {
  const values = clone(); values[index] = defaultProcessor(type);
  emit('update:modelValue', values); emit('change');
}
function update(index: number, key: string, value: unknown) {
  const values = clone(); values[index][key] = value; emit('update:modelValue', values);
}
function updateAndSave(index: number, key: string, value: unknown) { update(index, key, value); emit('change'); }
function remove(index: number) { const values = clone(); values.splice(index, 1); emit('update:modelValue', values); emit('change'); }
function move(index: number, offset: number) {
  const values = clone(); const target = index + offset;
  if (target < 0 || target >= values.length) return;
  [values[index], values[target]] = [values[target], values[index]];
  emit('update:modelValue', values); emit('change');
}
function mappingText(value: unknown) {
  if (typeof value === 'string') return value;
  if (!value || typeof value !== 'object' || Array.isArray(value)) return '';
  return Object.entries(value as Record<string, unknown>).map(([from, to]) => `${from}:${String(to)}`).join(',');
}
function updateMapping(index: number, text: string) {
  update(index, 'mapping', text);
}
function description(type: string) {
  return ({
    trim: '去除字符串首尾的空格和换行', json_parse: '将 JSON 字符串转换为对象或数组',
    base64_encode: '使用 UTF-8 进行 Base64 编码', base64_decode: '解码 Base64 并转为 UTF-8 文本',
    url_encode: '对整个字符串进行 URL 编码', url_decode: '解码 URL 编码字符串',
  } as Record<string, string>)[type] || '无需额外参数';
}
</script>

<style scoped>
.processor-editor { grid-column: 1 / -1; margin: 2px 14px 12px; padding: 12px; border: 1px solid #e7ebf2; border-radius: 10px; background: #fafbfd; }
.processor-editor > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.processor-editor > header div { display: flex; align-items: baseline; gap: 8px; }.processor-editor > header strong { color: #344054; font-size: 13px; }.processor-editor > header span { color: #98a2b3; font-size: 12px; }
.processor-adder { width: 190px; }.processor-list { display: flex; flex-direction: column; gap: 8px; }
.processor-row { display: grid; grid-template-columns: 28px 176px minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 8px; border: 1px solid #e6eaf0; border-radius: 8px; background: #fff; }
.processor-index { display: grid; width: 24px; height: 24px; place-items: center; border-radius: 50%; background: #eef3ff; color: #4f6bed; font-size: 12px; font-weight: 700; }
.processor-fields { display: grid; grid-template-columns: repeat(3, minmax(100px, 1fr)); align-items: center; gap: 8px; min-width: 0; }.processor-fields > :only-child { grid-column: 1 / -1; }
.processor-description { color: #667085; font-size: 12px; }.processor-actions { display: flex; align-items: center; gap: 6px; white-space: nowrap; }
.processor-editor :deep(.n-empty) { padding: 8px 0 2px; }.processor-editor :deep(.n-empty__icon) { display: none; }
@media (max-width: 800px) { .processor-editor > header { align-items: stretch; flex-direction: column; }.processor-adder { width: 100%; }.processor-row { grid-template-columns: 28px 1fr auto; }.processor-type { grid-column: 2; }.processor-fields { grid-column: 1 / -1; grid-row: 2; grid-template-columns: 1fr; }.processor-actions { grid-column: 3; grid-row: 1; } }
</style>
