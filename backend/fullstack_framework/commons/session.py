"""
@Filename:   commons/session
@Time:        2023/5/12 22:11
@Describe:    ...
"""
import logging

import requests
from fullstack_framework.commons import settings
from case_api.file_utils import opened_request_files
from fullstack_framework.commons.helix_signature import prepare_helix_signed_request

logger = logging.getLogger("session")


class BeifanSession(requests.Session):
    def request(
        self,
        method,
        url,
        params=None,
        data=None,
        headers=None,
        cookies=None,
        files=None,
        auth=None,
        timeout=None,
        allow_redirects=True,
        proxies=None,
        hooks=None,
        stream=None,
        verify=None,
        cert=None,
        json=None,
        interface_name=None,
        body_type=None,
    ) -> requests.Response:
        # 记录请求

        if not url.startswith("http"):
            raise ValueError(
                f"接口地址必须是完整 URL，当前值为：{url}。"
                "请为所属项目配置项目地址，或在接口中填写完整地址。"
            )

        headers, data, json = prepare_helix_signed_request(
            method, url, headers=headers, params=params, json_body=json, data=data,
        )

        # 每个接口使用独立日志块，便于实时日志快速区分相邻步骤。
        logger.info("")
        logger.info("========== 接口：%s ==========", interface_name or "未命名接口")
        logger.info(f"请求方法: {method}")
        logger.info(f"接口地址: {url}")
        request_log_fields = (
            ("params", params or self.params),
            ("请求头", headers),
            ("cookies", cookies or self.cookies),
            ("json", json),
            ("data", data),
            ("files", files),
            ("请求体类型", body_type),
        )
        for field_name, field_value in request_log_fields:
            if field_value not in (None, "", {}, [], ()):
                logger.info("%s: %s", field_name, field_value)

        # requests 会把 json={} 序列化为 GET 请求体。部分网关/CloudFront 会将
        # 这类本应无请求体的 GET 判为 Bad Request，因此空参数不应下传。
        request_kwargs = {
            "headers": headers,
            "auth": auth,
            "allow_redirects": allow_redirects,
        }
        if params:
            request_kwargs["params"] = params
        if data:
            request_kwargs["data"] = data
        if json:
            request_kwargs["json"] = json
        if cookies:
            request_kwargs["cookies"] = cookies
        if timeout is not None:
            request_kwargs["timeout"] = timeout
        if proxies is not None:
            request_kwargs["proxies"] = proxies
        if hooks is not None:
            request_kwargs["hooks"] = hooks
        if stream is not None:
            request_kwargs["stream"] = stream
        if verify is not None:
            request_kwargs["verify"] = verify
        if cert is not None:
            request_kwargs["cert"] = cert

        # 文件由平台上传接口保存；这里按 multipart/form-data 自动编码，并确保句柄在请求后关闭。
        with opened_request_files(files) as request_files:
            if request_files:
                request_kwargs["files"] = request_files
            elif body_type == "form_data":
                # requests 只有收到 files 参数才会生成 multipart boundary。
                # 使用 (None, value) 表示纯文本 part，确保无文件的 form-data 也按 multipart 发送。
                text_parts = []
                for field_name, field_value in (data or {}).items():
                    values = field_value if isinstance(field_value, (list, tuple)) else [field_value]
                    text_parts.extend(
                        (str(field_name), (None, "" if value is None else str(value)))
                        for value in values
                    )
                request_kwargs.pop("data", None)
                request_kwargs["files"] = text_parts or [("_form_data", (None, ""))]
            resp = super().request(method=method, url=url, **request_kwargs)

        # 记录响应

        logger.info(f"状态码：{resp.status_code}")
        logger.info(f"响应头：{resp.headers}")
        logger.info(f"响应正文：{resp.text}")
        logger.info("========== 接口结束：%s ==========", interface_name or "未命名接口")

        # 返回接口响应结果

        return resp
