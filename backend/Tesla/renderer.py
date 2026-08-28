"""
@Filename:   Tesla/renderer
@Time:        2023/9/10 21:02
@Describe:    ...
"""
import json

from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response


class CodeResultMessageRenderer(JSONRenderer):
    page_query_param = "page"
    page_size_query_param = "pageSize"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response: Response = renderer_context.get("response")  # 视图的返回值

        # HTTP 204 明确规定不可携带响应体。此前仍被包装为 JSON，浏览器会将
        # “204 + body”判定为网络异常，造成删除成功却弹出网络错误。
        if response.status_code == 204:
            return b""

        response_dict = {  # 模板
            "code": response.status_code,
            "message": "ok",
            "result": data,
        }

        if 300 >= response.status_code >= 200:
            pass

        elif response.status_code >= 400:
            if "detail" in data:
                response_dict["message"] = data["detail"]
            elif isinstance(data, dict):
                try:
                    msg = list(data.values())[0][0]
                except Exception:
                    msg = json.dumps(data)
                response_dict["message"] = msg
            elif isinstance(data, list):
                msg = str(data[0])
                response_dict["message"] = msg

        return super().render(response_dict, accepted_media_type, renderer_context)
