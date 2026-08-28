<template>
  <n-modal v-model:show="show" preset="card" :bordered="false" :style="{ width: '720px', maxWidth: '94vw', padding: 0 }" class="ai-chat-modal">
    <template #header>
      <div class="chat-head">
        <span class="chat-head__dot"></span>
        <span>AI 助手</span>
        <small>DeepSeek</small>
      </div>
    </template>

    <div class="chat-body">
      <div ref="listRef" class="chat-list">
        <div v-if="!messages.length && !errorMsg" class="chat-empty">
          <n-icon size="34"><PhSparkle /></n-icon>
          <p>你好，我是测试平台 AI 助手</p>
          <span>可以帮你生成测试用例、分析失败原因、优化接口参数</span>
        </div>

        <div v-for="(msg, index) in messages" :key="index" class="chat-msg" :class="msg.role">
          <div class="bubble">{{ msg.content }}</div>
        </div>

        <div v-if="errorMsg" class="chat-msg assistant">
          <div class="bubble bubble--error">{{ errorMsg }}</div>
        </div>

        <div v-if="loading" class="chat-msg assistant">
          <div class="bubble bubble--typing"><span></span><span></span><span></span></div>
        </div>
      </div>

      <div class="chat-input">
        <n-input v-model:value="draft" type="textarea" :autosize="{ minRows: 1, maxRows: 4 }" placeholder="输入你的问题，回车发送…" :disabled="loading" @keydown.enter.exact.prevent="send" />
        <n-button type="primary" :disabled="!draft.trim() || loading" :loading="loading" @click="send">
          <template #icon><PhPaperPlaneRight /></template>发送
        </n-button>
      </div>
    </div>
  </n-modal>
</template>

<script lang="ts" setup>
  import { nextTick, ref } from 'vue';
  import { PhPaperPlaneRight, PhSparkle } from '@phosphor-icons/vue';
  import { aiChat, type AiMessage } from '@/api/ai/http';

  const show = ref(false);
  const draft = ref('');
  const loading = ref(false);
  const errorMsg = ref('');
  const messages = ref<AiMessage[]>([]);
  const listRef = ref<HTMLElement>();

  const SYSTEM_PROMPT = '你是测试平台的 AI 助手，帮助用户生成接口测试用例、分析测试失败原因、优化接口参数。请使用简体中文，回答简洁专业。';

  async function scrollToBottom() {
    await nextTick();
    if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight;
  }

  function open() {
    show.value = true;
    errorMsg.value = '';
    scrollToBottom();
  }

  async function send() {
    const text = draft.value.trim();
    if (!text || loading.value) return;
    messages.value.push({ role: 'user', content: text });
    draft.value = '';
    errorMsg.value = '';
    loading.value = true;
    scrollToBottom();
    try {
      const history: AiMessage[] = [{ role: 'system', content: SYSTEM_PROMPT }, ...messages.value];
      const { reply } = await aiChat(history);
      messages.value.push({ role: 'assistant', content: reply });
    } catch (error: any) {
      errorMsg.value = error?.message || '请求失败，请稍后重试';
    } finally {
      loading.value = false;
      scrollToBottom();
    }
  }

  defineExpose({ open });
</script>

<style lang="less" scoped>
  .ai-chat-modal :deep(.n-card) { border-radius: 12px; overflow: hidden; }
  .chat-head { display: flex; align-items: center; gap: 8px; }
  .chat-head__dot { width: 9px; height: 9px; border-radius: 50%; background: linear-gradient(135deg, #2563eb, #7c3aed); }
  .chat-head small { margin-left: auto; padding: 2px 8px; border-radius: 10px; color: #667085; background: #f2f4f7; font-size: 11px; font-weight: 500; }

  .chat-body { display: flex; flex-direction: column; }
  .chat-list { height: 380px; padding: 16px 18px; overflow-y: auto; background: #f8fafc; display: flex; flex-direction: column; gap: 12px; }

  .chat-empty { display: grid; place-items: center; align-content: center; gap: 6px; height: 100%; color: #758195; text-align: center; }
  .chat-empty .n-icon { color: #2563eb; }
  .chat-empty p { margin: 4px 0 0; color: #273449; font-size: 14px; font-weight: 600; }
  .chat-empty span { font-size: 12px; }

  .chat-msg { display: flex; }
  .chat-msg.user { justify-content: flex-end; }
  .chat-msg.assistant { justify-content: flex-start; }
  .bubble { max-width: 78%; padding: 9px 13px; border-radius: 12px; font-size: 13px; line-height: 1.65; white-space: pre-wrap; word-break: break-word; }
  .chat-msg.user .bubble { color: #fff; background: #2563eb; border-bottom-right-radius: 4px; }
  .chat-msg.assistant .bubble { color: #273449; background: #fff; border: 1px solid #e5eaf1; border-bottom-left-radius: 4px; }
  .bubble--error { color: #c7353b !important; background: #fff0f1 !important; border-color: #f7d4d6 !important; }

  .bubble--typing { display: flex; align-items: center; gap: 4px; padding: 13px 15px; }
  .bubble--typing span { width: 6px; height: 6px; border-radius: 50%; background: #b5bfcc; animation: blink 1.2s infinite both; }
  .bubble--typing span:nth-child(2) { animation-delay: .2s; }
  .bubble--typing span:nth-child(3) { animation-delay: .4s; }
  @keyframes blink { 0%, 80%, 100% { opacity: .3; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-2px); } }

  .chat-input { display: flex; align-items: flex-end; gap: 10px; padding: 12px 14px; border-top: 1px solid #edf1f5; background: #fff; }
  .chat-input .n-input { flex: 1; }
</style>
