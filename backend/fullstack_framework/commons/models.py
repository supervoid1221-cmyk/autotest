"""
@Filename:   commons/models
@Author:
@Time:
@Describe:    ...
"""

from dataclasses import dataclass

@dataclass
class CaseInfo:
    test_name: str

    request: dict
    validate: dict
    parametrize: list = None
    extract: dict = None
    post_sql: list = None
    polling: dict = None
    # 套件运行时由 Suite.run 写入 epic=套件名称、feature=场景名称。
    epic: str = None
    feature: str = None
    title: str = None
    # 平台原生报告分组信息，由 Suite.run 在生成 YAML 时写入。
    scenario_id: int = None
    scenario_name: str = None
    source_step_id: int = None
    project_id: int = None
    environment_name: str = None
    # 场景步骤失败后是否继续；普通 API 执行项也会带上该配置。
    continue_on_failure: bool = True
    # 当前接口完整执行失败后的额外重试次数；默认关闭。
    retry_on_failure: bool = False
    failure_retry_count: int = 1

    def __repr__(self):
        return str(id(self))
