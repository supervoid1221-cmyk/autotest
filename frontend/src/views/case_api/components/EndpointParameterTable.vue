<template>
  <div class="parameter-table">
    <div class="parameter-row table-heading"><span>#</span><span>参数名</span><span>参数值</span><span>来源</span><span>操作</span></div>
    <div v-for="(row, index) in rows" :key="row.name" class="parameter-row">
      <span class="ordinal">{{ index + 1 }}</span>
      <input :value="row.name" aria-label="参数名" @change="rename(row.name, $event)" />
      <div class="value-field" :class="{ sensitive: sensitive(row.name) }">
        <input :type="sensitive(row.name) && !isRevealed(row.name) ? 'password' : 'text'" :value="display(row.value)" aria-label="参数值" autocomplete="off" @focus="remember(row.name, $event)" @click="remember(row.name, $event)" @keyup="remember(row.name, $event)" @select="remember(row.name, $event)" @change="update(row.name, ($event.target as HTMLInputElement).value)" />
        <button v-if="sensitive(row.name)" type="button" class="reveal-button" :title="isRevealed(row.name) ? '隐藏具体信息' : '查看具体信息'" :aria-label="isRevealed(row.name) ? `隐藏 ${row.name}` : `查看 ${row.name}`" @mousedown.prevent @click="toggleReveal(row.name)"><PhEyeSlash v-if="isRevealed(row.name)" /><PhEye v-else /></button>
      </div>
      <span class="source">接口配置</span>
      <button type="button" class="icon-button" :aria-label="`删除参数 ${row.name}`" @click="remove(row.name)"><PhTrash /></button>
    </div>
    <div class="parameter-row add-row"><PhPlus /><input v-model="newKey" placeholder="添加参数" aria-label="新增参数名" @keydown.enter.prevent="add"/><div class="value-field" :class="{ sensitive: sensitive(newKey) }"><input v-model="newValue" :type="sensitive(newKey) && !newValueRevealed ? 'password' : 'text'" placeholder="参数值" aria-label="新增参数值" @focus="remember(null, $event)" @click="remember(null, $event)" @keyup="remember(null, $event)" @keydown.enter.prevent="add"/><button v-if="sensitive(newKey)" type="button" class="reveal-button" :title="newValueRevealed ? '隐藏具体信息' : '查看具体信息'" :aria-label="newValueRevealed ? '隐藏新增参数值' : '查看新增参数值'" @mousedown.prevent @click="newValueRevealed = !newValueRevealed"><PhEyeSlash v-if="newValueRevealed"/><PhEye v-else/></button></div><span></span><button type="button" class="icon-button" aria-label="添加参数" :disabled="!newKey.trim()" @click="add"><PhPlus /></button></div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useMessage } from 'naive-ui';
import { PhEye, PhEyeSlash, PhPlus, PhTrash } from '@phosphor-icons/vue';
const props = defineProps<{ modelValue: string }>();
const emit = defineEmits<{ (event: 'update:modelValue', value: string): void }>();
const message = useMessage();
const newKey = ref('');
const newValue = ref('');
const newValueRevealed = ref(false);
const revealedKeys = ref(new Set<string>());
const cursor = ref<{ key: string | null; start: number; end: number } | null>(null);
const values = computed<Record<string, any>>(() => {
  try { const value = JSON.parse(props.modelValue || '{}'); return value && typeof value === 'object' && !Array.isArray(value) ? value : {}; }
  catch { return {}; }
});
const rows = computed(() => Object.entries(values.value).map(([name, value]) => ({ name, value })));
const display = (value: any): string => typeof value === 'string' ? value : JSON.stringify(value);
const sensitive = (key: string) => /authorization|token|secret|password|passwd|cookie|credential|private[_-]?key|api[_-]?key/i.test(key);
const isRevealed = (key: string) => revealedKeys.value.has(key);
function toggleReveal(key: string) {
  const next = new Set(revealedKeys.value);
  if (next.has(key)) next.delete(key); else next.add(key);
  revealedKeys.value = next;
}
const publish = (value: Record<string, any>) => emit('update:modelValue', JSON.stringify(value, null, 2));
function update(key: string, text: string) {
  let value: any = text;
  // 未改动的参数保留原类型；已有非字符串值只接受同类型 JSON 转换。
  const previous = values.value[key];
  if (typeof previous !== 'string') {
    try { const parsed = JSON.parse(text); if (typeof parsed === typeof previous && Array.isArray(parsed) === Array.isArray(previous)) value = parsed; } catch { /* 变量表达式和普通输入保留为字符串。 */ }
  }
  publish({ ...values.value, [key]: value });
}
function rename(key: string, event: Event) {
  const input = event.target as HTMLInputElement;
  const name = input.value.trim();
  if (name === key) return;
  if (!name || Object.prototype.hasOwnProperty.call(values.value, name)) {
    message.warning(!name ? '参数名不能为空' : '参数名不能重复'); input.value = key; return;
  }
  publish(Object.fromEntries(Object.entries(values.value).map(([k, v]) => [k === key ? name : k, v])));
  if (cursor.value?.key === key) cursor.value.key = name;
  if (revealedKeys.value.has(key)) {
    const next = new Set(revealedKeys.value); next.delete(key); next.add(name); revealedKeys.value = next;
  }
}
function remove(key: string) {
  const next = { ...values.value }; delete next[key]; publish(next);
  if (cursor.value?.key === key) cursor.value = null;
  if (revealedKeys.value.has(key)) { const revealed = new Set(revealedKeys.value); revealed.delete(key); revealedKeys.value = revealed; }
}
function add() {
  const key = newKey.value.trim();
  if (!key) return;
  if (Object.prototype.hasOwnProperty.call(values.value, key)) { message.warning('参数名不能重复'); return; }
  publish({ ...values.value, [key]: newValue.value }); newKey.value = ''; newValue.value = ''; newValueRevealed.value = false; cursor.value = null;
}
function remember(key: string | null, event: Event) {
  const input = event.target as HTMLInputElement;
  cursor.value = { key, start: input.selectionStart ?? input.value.length, end: input.selectionEnd ?? input.value.length };
}
function insertVariable(reference: string) {
  const position = cursor.value;
  if (!position) { newValue.value += reference; return; }
  const value = position.key === null ? newValue.value : display(values.value[position.key] ?? '');
  const start = Math.min(position.start, value.length);
  const end = Math.min(position.end, value.length);
  const next = value.slice(0, start) + reference + value.slice(end);
  if (position.key === null) newValue.value = next; else update(position.key, next);
  cursor.value = { key: position.key, start: start + reference.length, end: start + reference.length };
}
defineExpose({ insertVariable });
</script>

<style scoped>
.parameter-table{border:1px solid #e2e8ef;border-radius:4px;max-height:360px;overflow:auto;margin:12px 0;scrollbar-gutter:stable}
.parameter-row{display:grid;grid-template-columns:26px minmax(120px,1fr) minmax(180px,1.5fr) 80px 34px;align-items:center;gap:8px;padding:8px 10px;min-height:40px;min-width:540px;box-sizing:border-box;border-bottom:1px solid #e8edf2}
.parameter-row:last-child{border-bottom:0}.table-heading{position:sticky;top:0;z-index:1;background:#f6f8fa;color:#6e7e91;font-size:12px}.parameter-row input{width:100%;min-width:0;box-sizing:border-box;border:1px solid transparent;background:transparent;padding:4px 3px;font-size:13px;color:#233448;border-radius:3px}.parameter-row input:focus{outline:none;border-color:#008d96}.source,.ordinal{font-size:11px;color:#788b9f}.parameter-row>svg{color:#008e97;font-size:18px}.icon-button{border:0;background:none;color:#6c8194;cursor:pointer;display:inline-flex;justify-content:center;align-items:center;width:28px;height:28px}.icon-button:hover{color:#008b95;background:#edf7f7;border-radius:4px}.icon-button:disabled{opacity:.3;cursor:default}.add-row input::placeholder{color:#a8b5c5}
.value-field{position:relative;min-width:0}.value-field input{display:block}.value-field.sensitive input{padding-right:32px}.reveal-button{position:absolute;top:50%;right:2px;display:grid;width:28px;height:28px;padding:0;transform:translateY(-50%);place-items:center;border:0;border-radius:4px;color:#6c8194;background:transparent;cursor:pointer}.reveal-button:hover{color:#008b95;background:rgba(0,139,149,.1)}.reveal-button svg{width:17px;height:17px}
</style>
