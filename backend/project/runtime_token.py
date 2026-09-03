"""单次场景/套件运行内的 Token 优先级管理。

项目参数是运行启动时的兜底值；接口成功提取出同名 Token 后，
只在当前运行内覆盖它。运行时 Token 被服务端判定失效时，再恢复项目兜底值。
"""


class RuntimeTokenState:
    def __init__(self, variables=None, project_fallbacks=None):
        self.variables = variables if variables is not None else {}
        # 必须保留运行开始时的快照，不能被后续接口提取覆盖。
        self.project_fallbacks = dict(self.variables)
        self.project_fallbacks_by_project = {
            int(project_id): dict(values or {})
            for project_id, values in dict(project_fallbacks or {}).items()
        }
        self.runtime_tokens = {}

    @staticmethod
    def _environment_key(environment):
        return environment.project_id, str(environment.name)

    @staticmethod
    def _format_header_value(environment, token):
        token = str(token or "")
        prefix = str(environment.token_prefix or "")
        # 兼容项目参数中已经存储了“Bearer xxx”的情况。
        if prefix and token.startswith(prefix):
            return token
        return f"{prefix}{token}"

    def observe_extracted(self, environment, values):
        """接口成功后接管同名 Token，失败或未提取时不改变当前状态。"""
        values = values or {}
        token_name = str(environment.token_name or "token")
        token = values.get(token_name)
        if token in (None, ""):
            return False
        self.runtime_tokens[self._environment_key(environment)] = str(token)
        return True

    def current_token(self, environment):
        """运行时提取值优先，否则使用运行启动时的项目参数。"""
        key = self._environment_key(environment)
        if key in self.runtime_tokens:
            return self.runtime_tokens[key], "api_extract"
        token_name = str(environment.token_name or "token")
        project_values = self.project_fallbacks_by_project.get(environment.project_id)
        token = (
            project_values.get(token_name)
            if project_values is not None
            else self.project_fallbacks.get(token_name)
        )
        if token not in (None, ""):
            return str(token), "project"
        return "", ""

    def apply(self, environment, request_data):
        """把当前 Token 自动写入环境配置的请求头。"""
        token, source = self.current_token(environment)
        if not token:
            return source
        headers = dict(request_data.get("headers") or {})
        headers[str(environment.token_header or "Authorization")] = self._format_header_value(
            environment, token
        )
        request_data["headers"] = headers
        return source

    def discard_runtime_token(self, environment):
        """运行时 Token 失效后恢复项目参数，供后续步骤继续使用。"""
        key = self._environment_key(environment)
        if key not in self.runtime_tokens:
            return False
        self.runtime_tokens.pop(key, None)
        token_name = str(environment.token_name or "token")
        project_values = self.project_fallbacks_by_project.get(environment.project_id)
        fallback = (
            project_values.get(token_name)
            if project_values is not None
            else self.project_fallbacks.get(token_name)
        )
        if fallback in (None, ""):
            self.variables.pop(token_name, None)
        else:
            self.variables[token_name] = fallback
        return True
