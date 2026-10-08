<template>
  <div class="flow-item" :class="{ selected, disabled: !enabled }">
    <PhDotsSixVertical class="drag-handle" aria-label="拖拽排序" />
    <button class="flow-select" @click="$emit('select')">
      <span class="ordinal">{{ ordinal }}</span>
      <span class="flow-copy"><span class="flow-label"><PhDiamond v-if="condition" class="condition-icon" /><b v-else class="method" :class="method.toLowerCase()">{{ method }}</b><strong>{{ name }}</strong></span><small>{{ condition ? '按顺序匹配首个满足条件的分支' : `提取 ${extracts} · 断言 ${assertions}` }}</small></span>
    </button>
    <PhCheckCircle v-if="result?.passed === true" weight="fill" class="passed" />
    <PhXCircle v-else-if="result?.passed === false" weight="fill" class="failed" />
    <n-switch size="small" :value="enabled" :loading="busy" :aria-label="`${enabled ? '停用' : '启用'}${name}`" @update:value="$emit('toggle', $event)" />
  </div>
</template>
<script setup lang="ts">
import { PhCheckCircle, PhDiamond, PhDotsSixVertical, PhXCircle } from '@phosphor-icons/vue';
withDefaults(defineProps<{name: string; ordinal: string; method?: string; condition?: boolean; selected?: boolean; enabled?: boolean; busy?: boolean; extracts?: number; assertions?: number; result?: any}>(), {method: 'GET', enabled: true, extracts: 0, assertions: 0});
defineEmits(['select', 'toggle']);
</script>
<style scoped>
.flow-item{display:flex;align-items:center;gap:8px;min-height:78px;padding:10px 12px;border-left:3px solid transparent;border-radius:4px;box-sizing:border-box}.flow-item:hover{background:#f5f9fa}.flow-item.selected{background:#e6f5f5;border-left-color:#008c95}.flow-item.disabled .flow-select{opacity:.48}.drag-handle{flex:none;width:16px;height:20px;color:#758699;cursor:grab}.flow-select{display:flex;align-items:flex-start;gap:12px;min-width:0;flex:1;background:none;border:0;padding:0;cursor:pointer;text-align:left;color:#203044;font:inherit}.ordinal{font-size:13px;line-height:26px;font-variant-numeric:tabular-nums}.flow-copy{min-width:0;flex:1}.flow-label{display:flex;align-items:center;gap:9px;min-height:26px}.flow-label strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:14px;font-weight:600}.flow-copy small{display:block;margin-top:4px;color:#8090a5;font-size:12px;line-height:18px}.method{font-size:12px;line-height:24px;padding:0 5px;border:1px solid currentColor;border-radius:4px;color:#318357;font-weight:500}.method.post{color:#da820b}.method.put,.method.patch{color:#277bc5}.method.delete{color:#d44857}.condition-icon{color:#318afa;font-size:24px;flex:none}.passed,.failed{font-size:18px;flex:none}.passed{color:#23a54e}.failed{color:#d83b4a}.flow-item :deep(.n-switch){flex:none;--n-rail-width:32px!important;--n-rail-height:18px!important;--n-button-width:14px!important;--n-button-height:14px!important}
</style>
