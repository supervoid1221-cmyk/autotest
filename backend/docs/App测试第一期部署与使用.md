# App 测试第一期部署与使用

## 执行节点准备

第一期支持 Android、Appium 2 和 UiAutomator2。执行节点需要安装 Node.js、Android SDK、ADB、Appium 2，以及 UiAutomator2 驱动：

```bash
npm install -g appium
appium driver install uiautomator2
appium --address 0.0.0.0 --port 4723
```

使用 `adb devices` 确认真机或模拟器已连接。网络设备可以先执行 `adb connect IP:PORT`。

如果 Appium 与平台后端不在同一台机器，第一期推荐使用设备上已经安装的 App。自动安装 APK 时，Appium 节点必须能够读取平台保存的 `app_uploads` 目录，可通过共享目录挂载实现。

## 平台配置顺序

1. 进入“App测试 > 设备管理 > 执行节点”，填写 Appium 地址并测试连接。
2. 在“设备”页新增设备，Device ID 填写 `adb devices` 返回的设备编号，然后测试连接。
3. 进入“应用管理”，填写应用名称、Package Name 和 Main Activity。
4. 如需自动安装，在应用版本中上传 APK，并开启“自动安装”。
5. 进入“App用例”，选择项目、应用和默认设备。
6. 在元素管理中维护 Resource ID、Accessibility ID、文本、UIAutomator、XPath 或坐标定位。
7. 编排步骤并保存，然后从用例列表发起执行。
8. 在“执行任务”或任务报告中查看实时状态、日志、失败截图和页面结构。

## 定位建议

优先使用 Accessibility ID 和 Resource ID，其次使用文本和 UIAutomator。XPath 和坐标只作为兜底。坐标表达式格式为 `x,y`，第一期仅支持坐标点击和坐标输入。

## 步骤值格式

- 固定等待：填写秒数。
- 提取文本：填写保存的变量名，后续可使用 `${变量名}`。
- 设置变量：填写 `变量名=变量值`。
- 属性断言：填写 `属性名=期望值`。
- 滑动：填写 `start_x,start_y,end_x,end_y`。

项目参数会在任务开始时自动注入运行变量，可直接通过 `${参数名}` 使用。失败重试次数可在用例基础配置中设置。

## 运行和清理

同一设备同一时间只允许一个任务占用。任务结束、失败或异常后会释放设备。App 报告及 `app_runs` 目录中的截图、页面结构等附件，沿用“系统管理 > 系统配置”中的报告保留天数自动清理。
