"""DeepSeek 对话代理接口。

API Key 不能下发到前端，统一由后端转发，前端只传 messages 历史。
"""
import logging
import os

import requests
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

# 多轮上下文与单条消息的长度上限，防止恶意/异常输入把 key 打爆。
MAX_MESSAGES = 40
MAX_CONTENT_LENGTH = 20000


def _resolve_api_key():
    """优先读 settings 常量，其次环境变量。"""
    key = getattr(settings, "DEEPSEEK_API_KEY", "")
    return key or os.environ.get("DEEPSEEK_API_KEY", "")


class AiChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["AI"], description="调用 DeepSeek 进行多轮对话")
    def post(self, request):
        messages = request.data.get("messages")

        # 1. 参数校验
        if not isinstance(messages, list) or not messages:
            return Response({"detail": "messages 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        if len(messages) > MAX_MESSAGES:
            return Response({"detail": f"对话轮次过多，最多支持 {MAX_MESSAGES} 条消息"}, status=status.HTTP_400_BAD_REQUEST)
        for msg in messages:
            if not isinstance(msg, dict) or not isinstance(msg.get("content"), str):
                return Response({"detail": "每条消息必须包含字符串类型的 content"}, status=status.HTTP_400_BAD_REQUEST)
            if len(msg["content"]) > MAX_CONTENT_LENGTH:
                return Response({"detail": f"单条消息过长，最多 {MAX_CONTENT_LENGTH} 字符"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. 校验 key
        api_key = _resolve_api_key()
        if not api_key:
            logger.error("DeepSeek API Key 未配置")
            return Response({"detail": "服务端未配置 DeepSeek API Key，请联系管理员"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        model = getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat")
        payload = {"model": model, "messages": messages, "stream": False}
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        # 3. 调用 DeepSeek
        try:
            resp = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=120)
        except requests.Timeout:
            return Response({"detail": "DeepSeek 响应超时，请稍后重试"}, status=status.HTTP_504_GATEWAY_TIMEOUT)
        except requests.RequestException as exc:
            logger.exception("调用 DeepSeek 失败")
            return Response({"detail": f"调用 DeepSeek 失败：{exc}"}, status=status.HTTP_502_BAD_GATEWAY)

        if resp.status_code != 200:
            try:
                err = resp.json().get("error", {}).get("message") or resp.text
            except Exception:
                err = resp.text
            logger.error("DeepSeek 返回非 200：%s %s", resp.status_code, err)
            return Response({"detail": f"DeepSeek 返回错误：{err}"}, status=status.HTTP_502_BAD_GATEWAY)

        # 4. 提取回复
        try:
            data = resp.json()
            reply = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError) as exc:
            logger.exception("解析 DeepSeek 响应失败")
            return Response({"detail": f"解析 DeepSeek 响应失败：{exc}"}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({"reply": reply})
