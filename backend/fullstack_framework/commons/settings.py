"""
@Filename:   commons/settings.py
@Author:
@Time:
@Describe:    ...
"""
from selenium.webdriver.common.by import By

# 此文件不允许import 同项目的其他模块


driver_type = "chrome"
wait_max_time = 10
selenium_by = By.XPATH


test_case_path = ""
test_glob = "**/test_*.yaml"

extract_path = "extract.yaml"
rsa_pub_path = "api.pub"



