"""可配置的通用页面语义词典。

词典只扩展候选名称并参与评分，不会直接指定或点击某个元素。项目或步骤可通过
``options.smart_locator.aliases`` 覆盖/补充，避免把业务词写死在执行器中。
"""

DEFAULT_SEMANTICS = {
    "email": {
        "aliases": ["邮箱", "电子邮箱", "邮箱地址", "email", "e-mail", "mail"],
        "input_types": ["email"],
    },
    "username": {
        "aliases": ["用户名", "用户名称", "账号", "账户", "username", "user name", "account"],
        "input_types": ["text"],
    },
    "password": {
        "aliases": ["密码", "password", "passcode", "passwd", "pwd"],
        "input_types": ["password"],
    },
    "submit": {
        "aliases": ["提交", "确认", "确定", "保存", "登录", "登陆", "submit", "confirm", "save", "sign in", "log in", "login"],
        "input_types": ["submit"],
    },
    "close": {
        "aliases": ["关闭", "关闭弹窗", "关闭提示", "x", "×", "close", "dismiss", "cancel"],
        "input_types": [],
        "context_tokens": ["modal", "dialog", "drawer", "popup", "弹窗", "对话框", "抽屉"],
    },
    "search": {
        "aliases": ["搜索", "查询", "search", "keyword", "关键词"],
        "input_types": ["search"],
    },
    "more": {
        "aliases": ["更多", "更多操作", "more", "more actions", "actions"],
        "input_types": [],
    },
    "delete": {
        "aliases": ["删除", "移除", "delete", "remove"],
        "input_types": [],
    },
}
