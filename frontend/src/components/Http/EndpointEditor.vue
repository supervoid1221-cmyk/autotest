<template>
  <n-tabs type="line" animated>
    <n-tab-pane name="headers" tab="请求头">
      <DynamicInput :data="request.headers" @some-event="(vals) => update('headers', vals)" />
    </n-tab-pane>

    <n-tab-pane name="cookies" tab="Cookie">
      <DynamicInput :data="request.cookies" @some-event="(vals) => update('cookies', vals)" />
    </n-tab-pane>

    <n-tab-pane name="params" tab="查询字符串">
      <DynamicInput :data="request.params" @some-event="(vals) => update('params', vals)" />
    </n-tab-pane>

    <n-tab-pane name="data" tab="From表单">
      <DynamicInput :data="request.data" @some-event="(vals) => update('data', vals)" />
    </n-tab-pane>

    <n-tab-pane name="json" tab="JSON">
      <n-input
        :value="jsonText"
        type="textarea"
        :autosize="{ minRows: 12, maxRows: 24 }"
        placeholder='请输入合法 JSON，例如 {"name": "value"}'
        @update:value="jsonOnChange"
      />
    </n-tab-pane>
  </n-tabs>
</template>

<script lang="ts" setup>
  import { PropType, computed } from 'vue';
  import DynamicInput from './DynamicDict.vue';

  const props = defineProps({
    request: {
      type: Object as PropType<any>,
      required: true,
    },
  });

  console.log('request', props.request);
  const emit = defineEmits(['update']);

  const jsonText = computed(() => JSON.stringify(props.request.json || {}, null, 2));

  function update(attr, vals) {
    // console.log(attr, vals);
    emit('update', attr, vals);
  }

  function jsonOnChange(value: string) {
    try {
      emit('update', 'json', value.trim() ? JSON.parse(value) : {});
    } catch {
      // 输入尚未形成合法 JSON 时不更新父级数据，避免编辑过程导致页面异常。
    }
  }
</script>
