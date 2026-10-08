<template>
  <n-modal v-model:show="visible" :mask-closable="false">
    <section class="delete-module-dialog">
      <header class="delete-dialog-header">
        <div><h3>删除模块</h3><p>确定删除模块「{{ module?.name }}」吗？</p></div>
        <n-button text class="dialog-close" @click="visible = false">×</n-button>
      </header>
      <div class="delete-dialog-body">
        <div class="module-risk-count">
          该模块由接口、UI 元素、App 元素共用，当前关联
          <strong>{{ module?.endpoint_count || 0 }}</strong> 个接口、
          <strong>{{ module?.ui_element_count || 0 }}</strong> 个 UI 元素、
          <strong>{{ module?.app_element_count || 0 }}</strong> 个 App 元素。
        </div>
        <n-radio-group v-model:value="mode" class="delete-mode-list">
          <label class="delete-mode-item" :class="{ selected: mode === 'unassign' }">
            <n-radio value="unassign" />
            <span><strong>仅删除模块，关联内容移至未分组</strong><small>推荐选择，三个模块下的数据都会保留，可稍后重新分配模块。</small></span>
          </label>
          <label class="delete-mode-item danger" :class="{ selected: mode === 'cascade' }">
            <n-radio value="cascade" />
            <span><strong>删除模块及模块下全部内容</strong><small>该模块下的接口、UI 元素、App 元素都会被永久删除，此操作不可恢复。</small></span>
          </label>
        </n-radio-group>
        <div v-if="mode === 'cascade'" class="danger-confirm-area">
          <span>请输入 <strong>确认删除</strong> 继续</span>
          <n-input v-model:value="confirmText" placeholder="确认删除" />
        </div>
      </div>
      <footer class="delete-dialog-footer">
        <n-button @click="visible = false">取消</n-button>
        <n-button type="error" :loading="loading" :disabled="mode === 'cascade' && confirmText !== '确认删除'" @click="submit">确认删除</n-button>
      </footer>
    </section>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { NButton, NInput, NModal, NRadio, NRadioGroup, useMessage } from 'naive-ui';
import { ModuleAPI } from '@/api/project/http';
import type { Module } from '@/api/project/models';

/**
 * 共享模块的删除确认框。
 *
 * 模块现在被接口 / UI 元素 / App 元素三个页面共用，所以删除会同时影响三处，
 * 三个页面的确认文案与风险提示必须一致，统一由这个组件提供。
 */
const props = defineProps<{ show: boolean; module: Module | null }>();
const emit = defineEmits<{
  (event: 'update:show', value: boolean): void;
  (event: 'deleted'): void;
}>();

const message = useMessage();
const moduleApi = new ModuleAPI();
const loading = ref(false);
const mode = ref<'unassign' | 'cascade'>('unassign');
const confirmText = ref('');

const visible = computed({ get: () => props.show, set: (value: boolean) => emit('update:show', value) });

// 每次打开都回到默认的「仅删除模块」，避免上一次勾选的级联删除被继承下来。
watch(() => props.show, (value) => {
  if (value) { mode.value = 'unassign'; confirmText.value = ''; }
});

async function submit() {
  const target = props.module;
  if (!target?.id) return;
  if (mode.value === 'cascade' && confirmText.value !== '确认删除') {
    message.warning('请输入“确认删除”。');
    return;
  }
  loading.value = true;
  try {
    const result = await moduleApi.deleteModule(Number(target.id), mode.value === 'cascade');
    message.success(result?.detail || '模块已删除');
    visible.value = false;
    emit('deleted');
  } catch (error: any) {
    message.error(error?.message || '模块删除失败。');
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped lang="less">
.delete-module-dialog{width:min(520px,calc(100vw - 32px));overflow:hidden;border-radius:8px;background:#fff;box-shadow:0 18px 50px rgba(30,43,63,.2)}
.delete-dialog-header{display:flex;align-items:flex-start;justify-content:space-between;padding:20px 22px 16px;border-bottom:1px solid #edf0f4}
.delete-dialog-header h3{margin:0;color:#202b3c;font-size:18px;font-weight:650}
.delete-dialog-header p{margin:7px 0 0;color:#5f6c7e;font-size:13px}
.dialog-close{width:28px;color:#7c8796;font-size:22px;line-height:1}
.delete-dialog-body{padding:18px 22px 20px}
.module-risk-count{padding:11px 13px;border:1px solid #f1d49a;border-radius:6px;color:#76551c;background:#fffaf0;font-size:13px;line-height:1.6}
.module-risk-count strong{color:#a86500}
.delete-mode-list{display:grid;gap:10px;width:100%;margin-top:14px}
.delete-mode-item{display:flex;align-items:flex-start;gap:10px;padding:13px;border:1px solid #e2e7ee;border-radius:7px;cursor:pointer;transition:border-color .16s,background .16s}
.delete-mode-item:hover,.delete-mode-item.selected{border-color:#91baf0;background:#f7fbff}
.delete-mode-item.danger:hover,.delete-mode-item.danger.selected{border-color:#efb3b9;background:#fff8f8}
.delete-mode-item>span{display:grid;gap:4px}
.delete-mode-item strong{color:#303b4b;font-size:13px;font-weight:600}
.delete-mode-item small{color:#8995a5;font-size:12px;line-height:1.5}
.delete-mode-item.danger strong{color:#c13f4b}
.danger-confirm-area{display:grid;gap:7px;margin-top:12px;padding:12px 13px;border-radius:6px;background:#fff2f3;color:#b83b46;font-size:12px}
.delete-dialog-footer{display:flex;justify-content:flex-end;gap:10px;padding:14px 22px;border-top:1px solid #edf0f4;background:#fafbfc}
</style>
