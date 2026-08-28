<template>
  <section class="parameter-panel">
    <div class="parameter-title">{{ title }}</div>
    <div class="parameter-row" @click="headersExpanded = !headersExpanded">
      <div class="parameter-row-main"><span class="chevron" :class="{ expanded: headersExpanded }">⌄</span><span>请求头（{{ Object.keys(headers || {}).length }}）</span></div>
      <span class="parameter-summary">{{ summary(headers) }}</span>
    </div>
    <div v-if="headersExpanded" class="parameter-detail"><n-input :value="headersText" type="textarea" :autosize="{ minRows: 3, maxRows: 8 }" placeholder='例如：{"x-token":"${token}"}' @update:value="update('headers', $event)" /></div>

    <div class="body-editor" :class="{ 'is-json': bodyType === 'json' }">
      <div class="body-editor-head"><span>{{ bodyType === 'json' ? 'JSON' : bodyType === 'data' ? 'Data（表单数据）' : 'Params（查询参数）' }}</span><n-select :value="bodyType" size="small" :options="bodyOptions" class="body-type-select" @update:value="changeBodyType" /></div>
      <div class="body-editor-content"><span class="line-number">1</span><n-input :value="bodyType === 'json' ? jsonText : bodyType === 'data' ? dataText : paramsText" type="textarea" :autosize="{ minRows: 8, maxRows: 16 }" placeholder="{ }" @update:value="update(bodyType, $event)" /></div>
      <div class="body-editor-note">{{ bodyType === 'json' ? 'JSON 请求体（Content-Type 自动处理）' : bodyType === 'data' ? '表单数据（Content-Type 自动处理）' : '查询参数（将拼接到 URL）' }}</div>
    </div>
  </section>
</template>

<script lang="ts" setup>
  import { computed, ref, watch } from 'vue';
  type JsonObject = Record<string, unknown>;
  const props = withDefaults(defineProps<{ title?: string; headers?: JsonObject; params?: JsonObject; data?: JsonObject; json?: JsonObject }>(), { title: '参数', headers: () => ({}), params: () => ({}), data: () => ({}), json: () => ({}) });
  const emit = defineEmits(['update:headers', 'update:params', 'update:data', 'update:json']);
  const headersExpanded = ref(false); const bodyType = ref<'json' | 'data' | 'params'>('json');
  const bodyOptions = [{ label: 'JSON', value: 'json' }, { label: 'Data', value: 'data' }, { label: 'Params', value: 'params' }];
  const stringify = (value: JsonObject) => JSON.stringify(value || {}, null, 2);
  const headersText = computed(() => stringify(props.headers)); const paramsText = computed(() => stringify(props.params)); const dataText = computed(() => stringify(props.data)); const jsonText = computed(() => stringify(props.json));
  const summary = (value: JsonObject) => Object.keys(value || {}).slice(0, 4).join('、') || '未配置';
  watch([() => props.data, () => props.json, () => props.params], () => { bodyType.value = Object.keys(props.json || {}).length ? 'json' : Object.keys(props.data || {}).length ? 'data' : Object.keys(props.params || {}).length ? 'params' : 'json'; }, { immediate: true, deep: true });
  function update(field: 'headers' | 'params' | 'data' | 'json', value: string) { try { const parsed = value.trim() ? JSON.parse(value) : {}; if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') return; emit(`update:${field}`, parsed); } catch { /* 编辑中的不完整 JSON 暂不覆盖原值 */ } }
  function changeBodyType(value: 'json' | 'data' | 'params') { bodyType.value = value; ['json','data','params'].filter(key => key !== value).forEach(key => emit(`update:${key}`, {})); }
</script>

<style lang="less" scoped>
  .parameter-panel{margin:24px 0 16px;padding:26px 24px 24px;border:1px solid #e7ebf3;border-radius:6px;background:#fff}.parameter-title{margin-bottom:18px;color:#1f2937;font-size:18px;font-weight:600}.parameter-row{display:flex;align-items:center;justify-content:space-between;min-height:50px;padding:0 16px;margin-top:10px;border:1px solid #e4e8f0;border-radius:4px;color:#303846;cursor:pointer;transition:.2s}.parameter-row:hover{border-color:#a9cdfd;background:#f8fbff}.parameter-row-main{display:flex;align-items:center;gap:10px;font-weight:500}.chevron{display:inline-block;color:#5f6b7b;font-size:19px;line-height:1;transform:rotate(-90deg);transition:.2s}.chevron.expanded{transform:rotate(0)}.parameter-summary{max-width:55%;overflow:hidden;color:#8b95a7;font-size:13px;text-overflow:ellipsis;white-space:nowrap}.parameter-detail{padding:12px 0 2px}.body-editor{margin-top:16px;overflow:hidden;border:1px solid #dfe5ee;border-radius:5px;background:#fff}.body-editor.is-json{border-color:#8dc0ff;box-shadow:0 0 0 2px rgba(24,144,255,.08)}.body-editor-head{display:flex;align-items:center;justify-content:space-between;height:52px;padding:0 16px;border-bottom:1px solid #eef1f5;color:#273142;font-weight:600}.body-type-select{width:128px}.body-editor-content{display:flex;min-height:230px;padding:12px 0;background:#fcfdff}.line-number{width:40px;padding-top:8px;color:#a0a9b8;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;text-align:center;user-select:none}.body-editor-content :deep(.n-input){flex:1;margin-right:12px}.body-editor-content :deep(.n-input-wrapper){min-height:205px;padding:0;background:transparent;box-shadow:none}.body-editor-content :deep(textarea){min-height:205px!important;padding:8px 4px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;line-height:1.7}.body-editor-note{padding:10px 16px;border-top:1px solid #eef1f5;color:#8b95a7;font-size:13px}
</style>
