"""
@Filename:   /yaml_util
@Time:        2023/5/7 21:14
@Describe:    ...
"""
import yaml


class YamlUtil:
    def __init__(self, path):
        self.path = path

    def write(self, data):  # 创建yaml文件
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True)

    def read(self):  # 读取yaml文件
        try:
            with open(self.path, encoding="utf-8") as f:
                d = yaml.safe_load(f)
        except FileNotFoundError:
            d = {}

        return d

    def clear(self):
        open(self.path, "w")
