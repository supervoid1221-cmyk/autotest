import { http } from '@/utils/http/axios';

export interface AiMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

/** 调用后端 DeepSeek 代理接口进行多轮对话 */
export function aiChat(messages: AiMessage[]) {
  return http.request<{ reply: string }>({
    url: '/ai/chat/',
    method: 'POST',
    data: { messages },
    timeout: 120000,
  });
}
