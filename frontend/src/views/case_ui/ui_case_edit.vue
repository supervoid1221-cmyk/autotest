<template>
  <div class="ui-case-page" :class="{ 'smart-case-page': isPlaywright }">
    <header class="page-header" :class="{ 'smart-page-header': isPlaywright }">
      <div class="heading-block">
        <div class="breadcrumb"
          ><span>UI 自动化</span><i>/</i
          ><span>{{ isPlaywright ? 'Playwright 智能用例' : 'UI 用例' }}</span
          ><i>/</i><strong>{{ id ? '编辑用例' : '新增用例' }}</strong></div
        >
        <div v-if="!isPlaywright" class="title-line">
          <h1>{{
            id
              ? `编辑${isPlaywright ? ' Playwright 智能' : ''} UI 用例`
              : `新增${isPlaywright ? ' Playwright 智能' : ''} UI 用例`
          }}</h1>
          <p>配置浏览器操作步骤，严格按照步骤顺序执行</p>
        </div>
      </div>
      <n-space>
        <n-button size="large" @click="back">取消</n-button>
        <n-button type="primary" size="large" :loading="saving" @click="save">保存用例</n-button>
      </n-space>
    </header>

    <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
      <section class="basic-section smart-basic-section">
        <header class="basic-heading">
          <h2>基本信息</h2>
          <n-button text type="primary" @click="basicEditing = !basicEditing">
            {{ basicEditing ? '完成' : '编辑' }}
          </n-button>
        </header>
        <div v-if="!basicEditing" class="smart-basic-summary">
          <div
            ><span>用例名称</span><strong>{{ form.name || '未命名用例' }}</strong></div
          >
          <div
            ><span>所属项目</span><strong>{{ projectName }}</strong></div
          >
          <div
            ><span>执行环境</span><strong>{{ form.environment_name || '未选择' }}</strong></div
          >
          <div
            ><span>浏览器</span><strong>{{ browserLabel }}</strong></div
          >
          <div
            ><span>运行模式</span><strong>{{ runModeLabel }}</strong></div
          >
          <div
            ><span>状态</span
            ><strong class="case-status" :class="{ enabled: form.enabled }">{{
              form.enabled ? '已启用' : '已停用'
            }}</strong></div
          >
          <div
            ><span>更新时间</span
            ><strong>{{ formatDate(form.update_datetime || form.update_time) }}</strong></div
          >
        </div>
        <div v-else class="basic-grid">
          <n-form-item label="用例名称" path="name">
            <n-input v-model:value="form.name" placeholder="例如：后台登录流程" />
          </n-form-item>
          <n-form-item label="所属项目" path="project">
            <n-select
              v-model:value="form.project"
              :options="projectOptions"
              filterable
              placeholder="请选择项目"
              @update:value="projectChanged"
            />
          </n-form-item>
          <n-form-item label="执行环境">
            <n-select
              v-model:value="form.environment_name"
              :options="environmentNameOptions"
              :disabled="!form.project"
              clearable
              placeholder="请选择环境"
            />
          </n-form-item>
          <n-form-item label="浏览器">
            <n-select v-model:value="form.browser" :options="browserOptions" />
          </n-form-item>
          <n-form-item label="运行模式">
            <n-select v-model:value="form.run_mode" :options="runModeOptions" />
          </n-form-item>
          <n-form-item label="用例描述">
            <n-input
              v-model:value="form.description"
              maxlength="200"
              show-count
              placeholder="请输入用例描述（选填）"
            />
          </n-form-item>
          <n-form-item label="启用" class="enabled-field">
            <n-switch v-model:value="form.enabled" />
          </n-form-item>
        </div>
      </section>
    </n-form>

    <section
      class="steps-section"
      :class="{ 'smart-steps-section': isPlaywright, fullscreen: workbenchFullscreen }"
    >
      <div class="section-heading">
        <div>
          <h2>操作步骤</h2>
          <p>{{
            isPlaywright ? '按 Tab 组织页面操作，拖拽调整执行顺序' : '按顺序执行，可拖拽调整'
          }}</p>
        </div>
        <n-button
          v-if="isPlaywright"
          text
          class="fullscreen-button"
          :title="workbenchFullscreen ? '退出全屏' : '全屏编辑'"
          @click="workbenchFullscreen = !workbenchFullscreen"
        >
          <n-icon :component="workbenchFullscreen ? FullscreenExitOutlined : FullscreenOutlined" />
        </n-button>
      </div>

      <div class="tab-strip">
        <div
          v-for="(tab, tabIndex) in tabs"
          :key="tab.key"
          class="tab-item"
          :class="{ active: tab.key === activeTabKey }"
          @click="selectTab(tab.key)"
        >
          <n-icon :component="DesktopOutlined" />
          <template v-if="editingTabKey === tab.key">
            <n-input
              v-model:value="tab.name"
              size="small"
              maxlength="32"
              autofocus
              class="tab-name-input"
              @click.stop
              @blur="finishRename(tab)"
              @keyup.enter="finishRename(tab)"
            />
          </template>
          <span v-else
            >Tab {{ tabIndex + 1 }} · {{ tab.name
            }}<b v-if="isPlaywright" class="tab-step-count">{{ tab.steps.length }}</b></span
          >
          <button class="tab-mini-action" title="修改 Tab 名称" @click.stop="startRename(tab)">
            <n-icon :component="EditOutlined" />
          </button>
          <button
            v-if="tabs.length > 1"
            class="tab-mini-action danger"
            title="删除 Tab"
            @click.stop="removeTab(tab)"
          >
            <n-icon :component="CloseOutlined" />
          </button>
        </div>
        <button class="add-tab" @click="addTab"
          ><n-icon :component="PlusOutlined" />新增 Tab</button
        >
      </div>

      <div v-if="isPlaywright" class="playwright-workbench">
        <aside class="playwright-step-pane">
          <div class="pane-heading">
            <div>
              <strong>步骤编排</strong>
              <span>{{ activeTab.steps.length }} 个步骤</span>
            </div>
            <span>拖拽调整执行顺序</span>
          </div>

          <draggable
            v-model="activeTab.steps"
            item-key="localKey"
            handle=".playwright-drag-handle"
            class="playwright-step-list"
            ghost-class="playwright-step-ghost"
          >
            <template #item="{ element: step, index }">
              <article
                class="playwright-step-card"
                :class="{ selected: selectedPlaywrightStep?.localKey === step.localKey }"
                @click="selectStep(step)"
              >
                <button class="playwright-drag-handle" title="拖拽调整顺序" @click.stop>
                  <n-icon :component="MenuOutlined" />
                </button>
                <span class="playwright-step-number">{{ String(index + 1).padStart(2, '0') }}</span>
                <span class="playwright-action-icon" :class="actionTone(step.action)">
                  <n-icon :component="actionIcon(step.action)" />
                </span>
                <div class="playwright-step-copy">
                  <strong>{{ actionLabel(step.action) }}</strong>
                  <div class="step-summary-line"><span>{{ stepSummary(step) }}</span><button v-if="isPasswordStep(step) && step.value" type="button" class="step-summary-eye" :title="isStepValueRevealed(step) ? '隐藏具体信息' : '查看具体信息'" :aria-label="isStepValueRevealed(step) ? '隐藏密码步骤的操作值' : '查看密码步骤的操作值'" @click.stop="toggleStepValue(step)"><n-icon :component="isStepValueRevealed(step) ? EyeInvisibleOutlined : EyeOutlined"/></button></div>
                </div>
                <div class="playwright-card-actions">
                  <n-button text title="复制步骤" @click.stop="duplicateStep(index)"
                    ><n-icon :component="CopyOutlined"
                  /></n-button>
                  <n-button text type="error" title="删除步骤" @click.stop="removeStep(index)"
                    ><n-icon :component="DeleteOutlined"
                  /></n-button>
                </div>
              </article>
            </template>
          </draggable>

          <n-empty
            v-if="!activeTab.steps.length"
            description="当前 Tab 暂无操作步骤"
            class="playwright-step-empty"
          />
          <button class="playwright-add-step" @click="addStep"
            ><n-icon :component="PlusOutlined" />添加操作步骤</button
          >
        </aside>

        <div class="playwright-inspector-pane">
          <template v-if="selectedPlaywrightStep">
            <header class="inspector-heading">
              <div>
                <span>步骤 {{ String(selectedPlaywrightStepIndex + 1).padStart(2, '0') }}</span>
                <h3>{{ actionLabel(selectedPlaywrightStep.action) }}</h3>
              </div>
              <span
                class="inspector-status"
                :class="selectedPlaywrightStep.manual_fallback ? 'manual' : 'smart'"
              >
                {{ selectedPlaywrightStep.manual_fallback ? '手动兜底' : '智能定位' }}
              </span>
            </header>

            <div class="inspector-body">
              <div class="inspector-fields">
                <label class="inspector-field">
                  <span>操作方式</span>
                  <div
                    class="action-select inspector-action-select"
                    :class="actionTone(selectedPlaywrightStep.action)"
                  >
                    <n-icon
                      :component="actionIcon(selectedPlaywrightStep.action)"
                      class="action-select-icon"
                    />
                    <n-select
                      v-model:value="selectedPlaywrightStep.action"
                      :options="actionOptions"
                      :consistent-menu-width="false"
                      @update:value="(value) => actionChanged(selectedPlaywrightStep, value)"
                    />
                  </div>
                </label>
                <label v-if="needsElement(selectedPlaywrightStep.action)" class="inspector-field">
                  <span>页面元素</span>
                  <n-input
                    v-model:value="selectedPlaywrightStep.target"
                    :placeholder="
                      selectedPlaywrightStep.manual_fallback
                        ? '输入定位表达式'
                        : selectedPlaywrightStep.action === 'click'
                          ? '输入元素描述，连续点击用 -- 分隔，如：IP管理--测试连接'
                          : '输入元素描述，如：邮箱、创建用户'
                    "
                  />
                </label>
                <label
                  v-if="needsValue(selectedPlaywrightStep.action)"
                  class="inspector-field"
                  :class="{ wide: !needsElement(selectedPlaywrightStep.action) }"
                >
                  <span>操作值</span>
                  <n-input
                    v-model:value="selectedPlaywrightStep.value"
                    :type="isPasswordStep(selectedPlaywrightStep) ? 'password' : 'text'"
                    :placeholder="valuePlaceholder(selectedPlaywrightStep.action)"
                    show-password-on="click"
                  />
                </label>
                <label
                  v-else-if="selectedPlaywrightStep.action === 'upload_file'"
                  class="inspector-field wide"
                >
                  <span>测试文件</span>
                  <div class="upload-step-control">
                    <input
                      type="file"
                      multiple
                      @change="uploadUiFiles($event, selectedPlaywrightStep)"
                    />
                    <span>{{
                      selectedFileNames(selectedPlaywrightStep) || '选择一个或多个文件'
                    }}</span>
                  </div>
                </label>
              </div>

              <section v-if="needsElement(selectedPlaywrightStep.action)" class="inspector-section">
                <div class="inspector-section-title">
                  <div
                    ><strong>定位与范围</strong><span>控制智能定位的查找范围与兜底策略</span></div
                  >
                </div>
                <div class="inspector-option-grid">
                  <label class="inspector-toggle-row">
                    <div><strong>手动兜底</strong><span>智能定位失败时使用表达式</span></div>
                    <n-switch
                      :value="selectedPlaywrightStep.manual_fallback"
                      @update:value="
                        (checked) => toggleManualFallback(selectedPlaywrightStep, checked)
                      "
                    />
                  </label>
                  <label
                    v-if="!selectedPlaywrightStep.manual_fallback"
                    class="inspector-toggle-row"
                  >
                    <div
                      ><strong>限定数据行</strong><span>先锁定表格数据行，再查找操作元素</span></div
                    >
                    <n-switch
                      :value="selectedPlaywrightStep.row_locator_enabled"
                      @update:value="(checked) => toggleRowLocator(selectedPlaywrightStep, checked)"
                    />
                  </label>
                </div>
                <div v-if="selectedPlaywrightStep.manual_fallback" class="fallback-config">
                  <n-select
                    v-model:value="selectedPlaywrightStep.fallback_type"
                    :options="fallbackTypeOptions"
                  />
                  <span>当前“页面元素”内容将作为兜底定位表达式执行。</span>
                </div>
                <div
                  v-if="
                    selectedPlaywrightStep.row_locator_enabled &&
                    !selectedPlaywrightStep.manual_fallback
                  "
                  class="inspector-row-locator"
                >
                  <div class="row-locator-heading">
                    <div
                      ><strong>数据行条件</strong
                      ><span
                        >匹配唯一数据行后，在行内查找“{{
                          selectedPlaywrightStep.target || '页面元素'
                        }}”</span
                      ></div
                    >
                    <n-button text type="primary" @click="addRowCondition(selectedPlaywrightStep)"
                      >＋ 添加条件</n-button
                    >
                  </div>
                  <div class="table-title-row">
                    <span>表格名称</span>
                    <n-input
                      v-model:value="selectedPlaywrightStep.row_table_title"
                      clearable
                      placeholder="可选，如：用户列表"
                    />
                  </div>
                  <div class="condition-head"
                    ><span>列名</span><span>比较方式</span><span>期望值</span><span></span
                  ></div>
                  <div
                    v-for="(condition, conditionIndex) in selectedPlaywrightStep.row_conditions"
                    :key="condition.localKey"
                    class="condition-row"
                  >
                    <n-input v-model:value="condition.column" placeholder="如：邮箱" />
                    <n-select v-model:value="condition.operator" :options="rowOperatorOptions" />
                    <n-input v-model:value="condition.value" placeholder="支持 ${变量名}" />
                    <n-button
                      text
                      type="error"
                      :disabled="selectedPlaywrightStep.row_conditions.length === 1"
                      title="删除条件"
                      @click="removeRowCondition(selectedPlaywrightStep, conditionIndex)"
                    >
                      <n-icon :component="DeleteOutlined" />
                    </n-button>
                  </div>
                  <div class="row-locator-tip">匹配 0 行时等待至超时，匹配多行时直接失败。</div>
                </div>
              </section>

              <section class="inspector-section">
                <div class="inspector-section-title">
                  <div><strong>高级设置</strong><span>仅影响当前操作步骤</span></div>
                </div>
                <div class="advanced-option-list">
                  <label
                    v-if="selectedPlaywrightStep.action === 'input'"
                    class="inspector-toggle-row"
                  >
                    <div><strong>输入前清空</strong><span>填写内容前先清除输入框原值</span></div>
                    <n-switch v-model:value="selectedPlaywrightStep.options.clear_before_input" />
                  </label>
                  <label
                    v-if="
                      selectedPlaywrightStep.action === 'save_text' &&
                      !isPasswordStep(selectedPlaywrightStep)
                    "
                    class="inspector-toggle-row"
                  >
                    <div
                      ><strong>OCR 兜底识别</strong
                      ><span>DOM 无法读取内容时，识别当前元素截图中的文字</span></div
                    >
                    <n-switch v-model:value="selectedPlaywrightStep.options.ocr_fallback" />
                  </label>
                  <label
                    v-if="
                      selectedPlaywrightStep.action === 'save_text' &&
                      selectedPlaywrightStep.options.ocr_fallback &&
                      !isPasswordStep(selectedPlaywrightStep)
                    "
                    class="inspector-timeout-row"
                  >
                    <div><strong>OCR 识别语言</strong><span>自动识别支持中文与英文</span></div>
                    <n-select
                      v-model:value="selectedPlaywrightStep.options.ocr_language"
                      :options="ocrLanguageOptions"
                      style="width: 150px"
                    />
                  </label>
                  <label class="inspector-toggle-row">
                    <div
                      ><strong>执行后截图</strong><span>无论成功或失败，都将截图写入报告</span></div
                    >
                    <n-switch v-model:value="selectedPlaywrightStep.options.screenshot" />
                  </label>
                  <label class="inspector-toggle-row">
                    <div
                      ><strong>失败后继续</strong><span>当前步骤失败后继续执行后续步骤</span></div
                    >
                    <n-switch v-model:value="selectedPlaywrightStep.continue_on_failure" />
                  </label>
                  <label class="inspector-timeout-row">
                    <div><strong>查找超时</strong><span>等待页面元素出现的最长时间</span></div>
                    <n-input-number
                      v-model:value="selectedPlaywrightStep.options.timeout"
                      :min="1"
                      :max="120"
                    />
                    <em>秒</em>
                  </label>
                </div>
              </section>
            </div>

            <footer class="inspector-actions">
              <span class="inspector-hint">修改会实时保留在当前步骤中</span>
              <n-space>
                <n-button :loading="runningTab" @click="runCurrentTab"
                  ><n-icon :component="PlayCircleOutlined" />运行当前 Tab</n-button
                >
                <n-button type="primary" @click="applySelectedStep">应用配置</n-button>
              </n-space>
            </footer>
          </template>
          <n-empty v-else description="请先添加一个操作步骤" class="inspector-empty" />
        </div>
      </div>

      <div v-else class="step-table-wrap">
        <div class="step-table-head">
          <span>顺序</span><span>操作方式</span><span>页面元素</span><span>操作值</span
          ><span>操作</span>
        </div>

        <draggable
          v-model="activeTab.steps"
          item-key="localKey"
          handle=".drag-handle"
          class="step-list"
          ghost-class="step-ghost"
        >
          <template #item="{ element: step, index }">
            <div class="step-entry" :class="{ expanded: step.expanded }">
              <div class="step-row">
                <div class="order-cell">
                  <button class="drag-handle" title="拖拽调整顺序"
                    ><n-icon :component="MenuOutlined"
                  /></button>
                  <button
                    class="expand-button"
                    :class="{ open: step.expanded }"
                    title="展开高级配置"
                    @click="step.expanded = !step.expanded"
                  >
                    <n-icon :component="RightOutlined" />
                  </button>
                  <strong>{{ String(index + 1).padStart(2, '0') }}</strong>
                </div>
                <div class="action-select" :class="actionTone(step.action)">
                  <n-icon :component="actionIcon(step.action)" class="action-select-icon" />
                  <n-select
                    v-model:value="step.action"
                    :options="actionOptions"
                    :consistent-menu-width="false"
                    @update:value="(value) => actionChanged(step, value)"
                  />
                </div>
                <n-input
                  v-if="isPlaywright && needsElement(step.action)"
                  v-model:value="step.target"
                  :placeholder="
                    step.manual_fallback
                      ? '输入定位表达式'
                      : step.action === 'click'
                        ? '连续点击用 -- 分隔，如：IP管理--测试连接'
                        : '输入页面元素描述，如：密码、登录'
                  "
                  class="table-input"
                />
                <n-popover
                  v-else-if="needsElement(step.action)"
                  placement="bottom-start"
                  trigger="click"
                  :show="activeElementPickerKey === step.localKey"
                  :style="{ width: '760px' }"
                  @update:show="(visible) => handleElementPickerVisible(step, visible)"
                >
                  <template #trigger>
                    <button
                      type="button"
                      class="element-picker-trigger"
                      :class="{ empty: !step.element }"
                    >
                      <span>{{ selectedElementLabel(step.element) || '选择页面元素' }}</span>
                      <span v-if="step.element" class="element-picker-clear" @click.stop="clearElement(step)">×</span>
                    </button>
                  </template>
                  <div class="element-picker-dropdown">
                    <header>
                      <strong>选择页面元素</strong>
                      <n-input v-model:value="elementKeyword" clearable placeholder="搜索元素名称、定位方式或表达式" />
                    </header>
                    <div v-if="!form.project" class="element-picker-no-project">请先在基本信息中选择所属项目</div>
                    <div v-else class="element-picker-content">
                      <aside>
                        <button
                          type="button"
                          :class="{ active: selectedElementModule === 'all' }"
                          @click="selectedElementModule = 'all'"
                        >
                          <span>全部元素</span><em>{{ elementRecords.length }}</em>
                        </button>
                        <div class="element-project-node">
                          <span>{{ projectName }}</span><small>当前项目</small>
                        </div>
                        <button
                          v-for="module in elementModules"
                          :key="module.id"
                          type="button"
                          class="element-module-node"
                          :class="{ active: selectedElementModule === module.id }"
                          @click="selectedElementModule = module.id || null"
                        >
                          <span>{{ module.name }}</span><em>{{ elementCountByModule(module.id) }}</em>
                        </button>
                        <button
                          type="button"
                          class="element-module-node"
                          :class="{ active: selectedElementModule === 'unassigned' }"
                          @click="selectedElementModule = 'unassigned'"
                        >
                          <span>未分组</span><em>{{ elementCountByModule(null) }}</em>
                        </button>
                      </aside>
                      <main>
                        <div class="element-list-title">元素列表 <span>共 {{ filteredElementRecords.length }} 个</span></div>
                        <button
                          v-for="item in filteredElementRecords"
                          :key="item.id"
                          type="button"
                          class="element-option"
                          :class="{ selected: step.element === item.id }"
                          @click="selectElement(step, item)"
                        >
                          <div><strong>{{ item.name }}</strong><span>{{ item.module_name || '未分组' }}</span></div>
                          <code>{{ locatorLabel(item.by) }}</code>
                          <p>{{ item.value }}</p>
                        </button>
                        <n-empty v-if="!filteredElementRecords.length" size="small" description="未找到匹配的页面元素" />
                      </main>
                    </div>
                  </div>
                </n-popover>
                <span v-else class="empty-cell">——</span>
                <n-input
                  v-if="needsValue(step.action)"
                  v-model:value="step.value"
                  :type="isPasswordStep(step) ? 'password' : 'text'"
                  :placeholder="valuePlaceholder(step.action)"
                  show-password-on="click"
                  class="table-input"
                />
                <div
                  v-else-if="step.action === 'upload_file'"
                  class="upload-step-control table-upload-control"
                >
                  <input type="file" multiple @change="uploadUiFiles($event, step)" />
                  <span>{{ selectedFileNames(step) || '选择文件' }}</span>
                </div>
                <span v-else class="empty-cell">——</span>
                <div class="row-actions">
                  <n-button text title="复制步骤" @click="duplicateStep(index)"
                    ><n-icon :component="CopyOutlined"
                  /></n-button>
                  <n-button text type="error" title="删除步骤" @click="removeStep(index)"
                    ><n-icon :component="DeleteOutlined"
                  /></n-button>
                </div>
              </div>
              <div v-if="step.expanded" class="advanced-row">
                <div class="advanced-title">高级配置<span>仅影响当前步骤</span></div>
                <label
                  ><span>查找超时</span
                  ><n-input-number
                    v-model:value="step.options.timeout"
                    :min="1"
                    :max="120"
                    placeholder="10"
                  /><em>秒</em></label
                >
                <n-checkbox
                  v-if="isPlaywright && needsElement(step.action)"
                  :checked="step.manual_fallback"
                  @update:checked="(checked) => toggleManualFallback(step, checked)"
                  >手动兜底</n-checkbox
                >
                <n-select
                  v-if="isPlaywright && step.manual_fallback"
                  v-model:value="step.fallback_type"
                  :options="fallbackTypeOptions"
                  class="fallback-type-select"
                />
                <n-checkbox
                  v-if="isPlaywright && needsElement(step.action) && !step.manual_fallback"
                  :checked="step.row_locator_enabled"
                  @update:checked="(checked) => toggleRowLocator(step, checked)"
                  >限定数据行</n-checkbox
                >
                <n-checkbox
                  v-if="step.action === 'input'"
                  v-model:checked="step.options.clear_before_input"
                  >输入前清空</n-checkbox
                >
                <n-checkbox v-model:checked="step.options.screenshot">执行后截图</n-checkbox>
                <n-checkbox
                  v-if="isPlaywright && step.action === 'save_text' && !isPasswordStep(step)"
                  v-model:checked="step.options.ocr_fallback"
                  >OCR 兜底识别</n-checkbox
                >
                <n-checkbox v-model:checked="step.continue_on_failure">失败后继续执行</n-checkbox>
              </div>
              <div
                v-if="
                  step.expanded && isPlaywright && step.row_locator_enabled && !step.manual_fallback
                "
                class="row-locator-panel"
              >
                <div class="row-locator-heading">
                  <div
                    ><strong>数据行定位</strong
                    ><span
                      >先通过列条件锁定唯一数据行，再在该行内查找“{{
                        step.target || '页面元素'
                      }}”</span
                    ></div
                  >
                  <n-button text type="primary" @click="addRowCondition(step)"
                    >＋ 添加条件</n-button
                  >
                </div>
                <div class="table-title-row">
                  <span>表格名称</span>
                  <n-input
                    v-model:value="step.row_table_title"
                    clearable
                    placeholder="可选，多张表格时填写，如：用户列表"
                  />
                </div>
                <div class="condition-head"
                  ><span>列名</span><span>比较方式</span><span>期望值</span><span></span
                ></div>
                <div
                  v-for="(condition, conditionIndex) in step.row_conditions"
                  :key="condition.localKey"
                  class="condition-row"
                >
                  <n-input v-model:value="condition.column" placeholder="如：邮箱" />
                  <n-select v-model:value="condition.operator" :options="rowOperatorOptions" />
                  <n-input v-model:value="condition.value" placeholder="支持 ${变量名}" />
                  <n-button
                    text
                    type="error"
                    :disabled="step.row_conditions.length === 1"
                    title="删除条件"
                    @click="removeRowCondition(step, conditionIndex)"
                  >
                    <n-icon :component="DeleteOutlined" />
                  </n-button>
                </div>
                <div class="row-locator-tip"
                  >条件匹配 0 行时等待到超时，匹配多行时直接失败，不会默认选择第一行。</div
                >
              </div>
            </div>
          </template>
        </draggable>

        <n-empty
          v-if="!activeTab.steps.length"
          description="当前 Tab 暂无操作步骤"
          class="step-empty"
        />
        <button class="add-step" @click="addStep"
          ><n-icon :component="PlusOutlined" />添加操作步骤</button
        >
      </div>

      <div class="execution-rule">
        <n-icon :component="PlayCircleOutlined" />
        <span
          ><strong>执行规则：</strong>Tab 按从左到右的顺序依次执行，每个 Tab
          内的步骤按从上到下执行。</span
        >
      </div>
    </section>

    <footer v-if="!isPlaywright" class="sticky-actions">
      <n-button size="large" @click="back">取消</n-button>
      <n-button type="primary" size="large" :loading="runningCase" @click="runCaseNow">立即执行</n-button>
    </footer>
  </div>
</template>

<script lang="ts" setup>
import { asList } from '@/utils/list';

  // 路由开启 keepAlive 时，组件名必须与路由名一致，才能在平台多页签间保留编辑草稿。
  defineOptions({ name: 'case_ui_playwright_case_edit' });

  import { computed, onMounted, reactive, ref } from 'vue';
  import { useRoute, useRouter } from 'vue-router';
  import { useMessage } from 'naive-ui';
  import draggable from 'vuedraggable';
  import {
    AimOutlined,
    CheckCircleOutlined,
    ClearOutlined,
    ClockCircleOutlined,
    CloseOutlined,
    CodeOutlined,
    CopyOutlined,
    DeleteOutlined,
    DesktopOutlined,
    DownloadOutlined,
    EditOutlined,
    EyeInvisibleOutlined,
    EyeOutlined,
    FormOutlined,
    FullscreenExitOutlined,
    FullscreenOutlined,
    GlobalOutlined,
    MenuOutlined,
    PlusOutlined,
    PlayCircleOutlined,
    RightOutlined,
  } from '@vicons/antd';
  import {
    ElementAPI,
    PlaywrightCaseAPI,
    PlaywrightStepAPI,
    UiCaseAPI,
    UiStepAPI,
    UiUploadedFileAPI,
  } from '@/api/case_ui/http';
  import { EnvironmentAPI, ModuleAPI, ProjectAPI } from '@/api/project/http';
  import { environmentOptionsForProject } from '@/views/case_shared/catalog';
  import type { UiCaseTab, UiStep } from '@/api/case_ui/models';

  type RowCondition = { localKey: string; column: string; operator: string; value: string };
  type EditorStep = UiStep & {
    localKey: string;
    expanded?: boolean;
    target?: string;
    manual_fallback?: boolean;
    fallback_type?: string;
    fallback_value?: string;
    locator_mode?: string;
    row_locator_enabled: boolean;
    row_table_title: string;
    row_conditions: RowCondition[];
  };
  type EditorTab = UiCaseTab & { steps: EditorStep[] };

  const route = useRoute();
  const router = useRouter();
  const message = useMessage();
  const id = computed(() => Number(route.params.id) || 0);
  const formRef = ref<any>();
  const saving = ref(false);
  const runningCase = ref(false);
  const runningTab = ref(false);
  const workbenchFullscreen = ref(false);
  const basicEditing = ref(!Number(route.params.id));
  const isPlaywright = route.name === 'case_ui_playwright_case_edit';
  const caseApi: any = isPlaywright ? new PlaywrightCaseAPI() : new UiCaseAPI();
  const stepApi: any = isPlaywright ? new PlaywrightStepAPI() : new UiStepAPI();
  const elementApi = new ElementAPI();
  const elementModuleApi = new ModuleAPI();
  const projectApi = new ProjectAPI();
  const environmentApi = new EnvironmentAPI();
  const projectOptions = ref<any[]>([]);
  const environments = ref<any[]>([]);
  const elementOptions = ref<any[]>([]);
  const elementRecords = ref<any[]>([]);
  const elementModules = ref<any[]>([]);
  const activeElementPickerKey = ref('');
  const elementKeyword = ref('');
  const selectedElementModule = ref<number | 'all' | 'unassigned' | null>('all');
  const uploadedFiles = ref<any[]>([]);
  const uploadedFileApi = new UiUploadedFileAPI();
  const tabs = ref<EditorTab[]>([createTab('tab-1', '登录页', 1)]);
  const activeTabKey = ref('tab-1');
  const selectedStepKey = ref('');
  const editingTabKey = ref('');
  const revealedStepKeys = ref(new Set<string>());
  const form = reactive<any>({
    project: null,
    name: '',
    description: '',
    environment_name: '',
    browser: isPlaywright ? 'chromium' : 'chrome',
    run_mode: 'headless',
    enabled: true,
  });
  const rules = {
    project: { required: true, type: 'number', message: '请选择项目', trigger: 'change' },
    name: { required: true, message: '请输入用例名称', trigger: 'blur' },
  };
  const browserOptions = isPlaywright
    ? [
        { label: 'Chromium', value: 'chromium' },
        { label: 'Firefox', value: 'firefox' },
        { label: 'WebKit', value: 'webkit' },
      ]
    : [{ label: 'Chrome', value: 'chrome' }];
  const runModeOptions = [
    { label: '无头模式', value: 'headless' },
    { label: '有界面模式', value: 'headed' },
  ];
  const ocrLanguageOptions = [
    { label: '自动（中文 + 英文）', value: 'auto' },
    { label: '中文', value: 'zh' },
    { label: '英文', value: 'en' },
  ];
  const seleniumActionOptions = [
    ['goto', '打开页面'],
    ['input', '输入文本'],
    ['upload_file', '上传文件'],
    ['click', '点击元素'],
    ['select', '选择下拉项'],
    ['save_text', '提取文本'],
    ['assert_text', '断言文本'],
    ['assert_value', '断言值'],
    ['iframe_enter', '进入 IFrame'],
    ['iframe_exit', '退出 IFrame'],
    ['js_code', '执行 JavaScript'],
    ['sleep', '固定等待'],
  ].map(([value, label]) => ({ value, label }));
  const playwrightActionOptions = [
    ['goto', '打开页面'],
    ['input', '输入文本'],
    ['upload_file', '上传文件'],
    ['click', '点击元素'],
    ['select', '选择下拉项'],
    ['check', '勾选'],
    ['assert_visible', '断言可见'],
    ['assert_text', '断言文本'],
    ['save_text', '提取文本'],
    ['sleep', '固定等待'],
  ].map(([value, label]) => ({ value, label }));
  const actionOptions = isPlaywright ? playwrightActionOptions : seleniumActionOptions;
  const elementActions = new Set(
    isPlaywright
      ? [
          'click',
          'input',
          'upload_file',
          'save_text',
          'assert_text',
          'assert_visible',
          'select',
          'check',
        ]
      : [
          'click',
          'input',
          'upload_file',
          'clear',
          'save_text',
          'assert_text',
          'assert_value',
          'iframe_enter',
          'select',
        ]
  );
  const valueActions = new Set(
    isPlaywright
      ? ['goto', 'input', 'save_text', 'assert_text', 'select', 'sleep']
      : ['goto', 'input', 'save_text', 'assert_text', 'assert_value', 'select', 'js_code', 'sleep']
  );
  const fallbackTypeOptions = [
    { label: 'ID', value: 'id' },
    { label: 'Name', value: 'name' },
    { label: 'Class Name', value: 'class_name' },
    { label: 'Link Text', value: 'link_text' },
    { label: 'CSS', value: 'css_selector' },
    { label: 'XPath', value: 'xpath' },
  ];
  function normalizeFallbackType(value: string) {
    return (
      (
        { css: 'css_selector', testid: 'css_selector', test_id: 'css_selector' } as Record<
          string,
          string
        >
      )[value] ||
      value ||
      'xpath'
    );
  }
  const rowOperatorOptions = [
    { label: '等于', value: 'equals' },
    { label: '包含', value: 'contains' },
    { label: '不等于', value: 'not_equals' },
    { label: '开头是', value: 'starts_with' },
    { label: '正则匹配', value: 'regex' },
  ];
  const activeTab = computed(
    () => tabs.value.find((item) => item.key === activeTabKey.value) || tabs.value[0]
  );
  const selectedPlaywrightStep = computed(() => {
    const steps = activeTab.value?.steps || [];
    return steps.find((step) => step.localKey === selectedStepKey.value) || steps[0] || null;
  });
  const selectedPlaywrightStepIndex = computed(() => {
    if (!selectedPlaywrightStep.value) return -1;
    return activeTab.value.steps.findIndex(
      (step) => step.localKey === selectedPlaywrightStep.value?.localKey
    );
  });
  const projectName = computed(
    () =>
      projectOptions.value.find((item) => item.value === form.project)?.label ||
      form.project_name ||
      '未选择'
  );
  const environmentNameOptions = computed(() =>
    environmentOptionsForProject(environments.value, form.project).map((option) => ({
      label: option.label,
      value: option.label,
    }))
  );
  const browserLabel = computed(
    () =>
      browserOptions.find((item) => item.value === form.browser)?.label || form.browser || '未配置'
  );
  const runModeLabel = computed(
    () =>
      runModeOptions.find((item) => item.value === form.run_mode)?.label ||
      form.run_mode ||
      '未配置'
  );
  const filteredElementRecords = computed(() => {
    const keyword = elementKeyword.value.trim().toLowerCase();
    return elementRecords.value.filter((item) => {
      const moduleMatched =
        selectedElementModule.value === 'all' ||
        (selectedElementModule.value === 'unassigned' && !item.module) ||
        item.module === selectedElementModule.value;
      if (!moduleMatched) return false;
      if (!keyword) return true;
      return `${item.name || ''} ${item.by || ''} ${item.value || ''} ${item.module_name || ''}`
        .toLowerCase()
        .includes(keyword);
    });
  });

  
  function formatDate(value: any) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
      .format(date)
      .replaceAll('/', '-');
  }
  function createTab(key: string, name: string, order: number): EditorTab {
    return { key, name, order, steps: [] };
  }
  function newStep(): EditorStep {
    return {
      localKey: `${Date.now()}-${Math.random()}`,
      action: 'click',
      tab_key: activeTabKey.value,
      element: null,
      target: '',
      value: '',
      manual_fallback: false,
      locator_mode: 'auto',
      fallback_type: 'xpath',
      fallback_value: '',
      options: {
        timeout: 10,
        clear_before_input: true,
        screenshot: false,
        ocr_fallback: false,
        ocr_language: 'auto',
        smart_locator: {},
      },
      row_locator_enabled: false,
      row_table_title: '',
      row_conditions: [],
      continue_on_failure: true,
    };
  }
  function selectedFileNames(step: EditorStep) {
    const ids = (step.options || {}).file_ids || [];
    return ids
      .map(
        (id: number) =>
          uploadedFiles.value.find((item) => item.id === id)?.original_name || `文件 #${id}`
      )
      .join('、');
  }
  async function uploadUiFiles(event: Event, step: EditorStep) {
    const files = Array.from((event.target as HTMLInputElement).files || []);
    if (!files.length) return;
    if (!form.project) {
      message.warning('请先选择所属项目，再上传测试文件');
      return;
    }
    try {
      const uploaded = await Promise.all(
        files.map((file) => uploadedFileApi.upload(Number(form.project), file))
      );
      uploadedFiles.value = [...uploaded, ...uploadedFiles.value];
      step.options = step.options || {};
      step.options.file_ids = uploaded.map((item: any) => item.id);
      message.success(`已选择 ${uploaded.length} 个测试文件`);
    } finally {
      (event.target as HTMLInputElement).value = '';
    }
  }
  function createRowCondition(): RowCondition {
    return {
      localKey: `${Date.now()}-${Math.random()}`,
      column: '',
      operator: 'equals',
      value: '',
    };
  }
  function toggleRowLocator(step: EditorStep, checked: boolean) {
    step.row_locator_enabled = checked;
    if (checked && !step.row_conditions?.length) step.row_conditions = [createRowCondition()];
  }
  function toggleManualFallback(step: EditorStep, checked: boolean) {
    if (checked && isMultiTargetClick(step)) {
      message.warning('连续点击不支持共用手动兜底，请分别创建点击步骤');
      return;
    }
    const wasEnabled = Boolean(step.manual_fallback);
    step.manual_fallback = checked;
    if (checked && !wasEnabled) step.fallback_type = 'xpath';
  }
  function addRowCondition(step: EditorStep) {
    step.row_conditions = [...(step.row_conditions || []), createRowCondition()];
  }
  function removeRowCondition(step: EditorStep, index: number) {
    if ((step.row_conditions || []).length <= 1) return;
    step.row_conditions?.splice(index, 1);
  }
  function syncRowLocator(step: EditorStep) {
    step.options = step.options || {};
    const smart = { ...(step.options.smart_locator || {}) };
    if (!step.row_locator_enabled || step.manual_fallback) {
      delete smart.row;
      delete smart.table;
    } else {
      smart.row = {
        conditions: (step.row_conditions || []).map(({ column, operator, value }) => ({
          column: String(column || '').trim(),
          operator: operator || 'equals',
          value: String(value ?? '').trim(),
        })),
      };
      const title = String(step.row_table_title || '').trim();
      if (title) smart.table = { title };
      else delete smart.table;
    }
    step.options.smart_locator = smart;
  }
  function selectTab(key: string) {
    activeTabKey.value = key;
    editingTabKey.value = '';
    selectedStepKey.value = tabs.value.find((tab) => tab.key === key)?.steps[0]?.localKey || '';
  }
  function addTab() {
    const key = `tab-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const tab = createTab(key, '新页面', tabs.value.length + 1);
    tabs.value.push(tab);
    activeTabKey.value = key;
    selectedStepKey.value = '';
    editingTabKey.value = key;
  }
  function startRename(tab: EditorTab) {
    activeTabKey.value = tab.key;
    editingTabKey.value = tab.key;
  }
  function finishRename(tab: EditorTab) {
    tab.name = String(tab.name || '').trim() || '未命名页签';
    editingTabKey.value = '';
  }
  function removeTab(tab: EditorTab) {
    if (tab.steps.length) {
      message.warning('请先删除该 Tab 下的操作步骤');
      return;
    }
    const index = tabs.value.findIndex((item) => item.key === tab.key);
    tabs.value.splice(index, 1);
    tabs.value.forEach((item, tabIndex) => (item.order = tabIndex + 1));
    activeTabKey.value = tabs.value[Math.max(0, index - 1)].key;
    selectedStepKey.value = activeTab.value.steps[0]?.localKey || '';
    editingTabKey.value = '';
  }
  function selectStep(step: EditorStep) {
    selectedStepKey.value = step.localKey;
  }
  function addStep() {
    const step = newStep();
    activeTab.value.steps.push(step);
    selectedStepKey.value = step.localKey;
  }
  function removeStep(index: number) {
    const removed = activeTab.value.steps[index];
    activeTab.value.steps.splice(index, 1);
    if (removed?.localKey && revealedStepKeys.value.has(removed.localKey)) {
      const next = new Set(revealedStepKeys.value); next.delete(removed.localKey); revealedStepKeys.value = next;
    }
    if (removed?.localKey === selectedStepKey.value) {
      selectedStepKey.value =
        activeTab.value.steps[Math.min(index, activeTab.value.steps.length - 1)]?.localKey || '';
    }
  }
  function duplicateStep(index: number) {
    const source = activeTab.value.steps[index];
    const clone: EditorStep = {
      ...source,
      id: undefined,
      localKey: `${Date.now()}-${Math.random()}`,
      options: JSON.parse(JSON.stringify(source.options || {})),
      row_conditions: (source.row_conditions || []).map((item) => ({
        ...item,
        localKey: `${Date.now()}-${Math.random()}`,
      })),
      expanded: false,
    };
    activeTab.value.steps.splice(index + 1, 0, clone);
    selectedStepKey.value = clone.localKey;
  }
  function needsElement(action: string) {
    return elementActions.has(action);
  }
  function needsValue(action: string) {
    return valueActions.has(action);
  }
  function actionTone(action: string) {
    if (action === 'goto') return 'blue';
    if (action === 'input') return 'green';
    if (action === 'click') return 'orange';
    if (action === 'save_text') return 'teal';
    if (action === 'sleep') return 'purple';
    if (action.startsWith('assert')) return 'teal';
    if (action.startsWith('iframe')) return 'indigo';
    if (action === 'js_code') return 'pink';
    return 'slate';
  }
  function actionIcon(action: string) {
    if (action === 'goto') return GlobalOutlined;
    if (action === 'input') return FormOutlined;
    if (action === 'click') return AimOutlined;
    if (action === 'save_text') return DownloadOutlined;
    if (action === 'sleep') return ClockCircleOutlined;
    if (action.startsWith('assert')) return CheckCircleOutlined;
    if (action === 'js_code') return CodeOutlined;
    if (action === 'clear') return ClearOutlined;
    return DesktopOutlined;
  }
  function actionLabel(action: string) {
    return (
      actionOptions.find((item) => item.value === action)?.label ||
      ({ clear: '清空输入（历史步骤）' } as Record<string, string>)[action] ||
      action ||
      '未选择操作'
    );
  }
  function stepSummary(step: EditorStep) {
    if (step.action === 'goto') return step.value || '等待填写访问地址';
    if (step.action === 'sleep') return step.value ? `等待 ${step.value} 秒` : '等待填写时长';
    if (step.action === 'upload_file') return selectedFileNames(step) || '未选择测试文件';
    if (step.action === 'save_text')
      return `${step.target || '未填写元素'} → ${
        step.value ? `保存为 ${step.value}` : '未填写变量名'
      }`;
    if (needsElement(step.action)) {
      const target = step.target || '未填写页面元素';
      if (step.action === 'input')
        return `${target}：${
          step.value ? (isPasswordStep(step) && !isStepValueRevealed(step) ? '••••••••' : step.value) : '未填写内容'
        }`;
      if (needsValue(step.action)) return `${target} · ${step.value || '未填写操作值'}`;
      return target;
    }
    return step.value || '等待配置';
  }
  function isStepValueRevealed(step: EditorStep) {
    return revealedStepKeys.value.has(step.localKey);
  }
  function toggleStepValue(step: EditorStep) {
    const next = new Set(revealedStepKeys.value);
    if (next.has(step.localKey)) next.delete(step.localKey); else next.add(step.localKey);
    revealedStepKeys.value = next;
  }
  function applySelectedStep() {
    const step = selectedPlaywrightStep.value;
    if (!step) return;
    if (needsElement(step.action) && !String(step.target || '').trim()) {
      message.warning('请填写页面元素');
      return;
    }
    const clickError = validateClickTargets(step);
    if (clickError) {
      message.warning(clickError);
      return;
    }
    if (needsValue(step.action) && !String(step.value || '').trim()) {
      message.warning('请填写操作值');
      return;
    }
    message.success('当前步骤配置已应用');
  }
  function actionChanged(step: EditorStep, action: string) {
    step.action = action;
    if (!needsElement(action)) {
      step.element = null;
      step.target = '';
    }
    if (!needsValue(action)) step.value = '';
    if (action !== 'upload_file') delete step.options?.file_ids;
    if (action === 'input' && step.options.clear_before_input === undefined)
      step.options.clear_before_input = true;
  }
  function isMultiTargetClick(step: EditorStep) {
    return isPlaywright && step.action === 'click' && String(step.target || '').includes('--');
  }
  function validateClickTargets(step: EditorStep): string {
    if (!isMultiTargetClick(step)) return '';
    if (!String(step.target).split('--').every((target) => target.trim())) {
      return '连续点击的每个页面元素都不能为空，请用 -- 分隔';
    }
    if (step.manual_fallback) return '连续点击不支持共用手动兜底，请分别创建点击步骤';
    return '';
  }
  function valuePlaceholder(action: string) {
    return (
      (
        {
          goto: '如：/login',
          input: '输入内容，支持 ${变量名}',
          save_text: '变量名',
          assert_text: '期望文本',
          assert_value: '期望值',
          select: '下拉项显示文本',
          js_code: 'JavaScript 代码',
          sleep: '等待秒数，如：3',
        } as Record<string, string>
      )[action] || '操作值'
    );
  }
  function isPasswordStep(step: EditorStep) {
    const selected = elementOptions.value.find((item) => item.value === step.element);
    return /password|passwd|pwd|密码/i.test(`${step.target || ''} ${selected?.label || ''}`);
  }
  function back() {
    router.push({ name: isPlaywright ? 'case_ui_playwright_case' : 'case_ui_case' });
  }
  async function loadElements() {
    if (isPlaywright) {
      elementOptions.value = [];
      elementRecords.value = [];
      elementModules.value = [];
      return;
    }
    if (!form.project) {
      elementOptions.value = [];
      elementRecords.value = [];
      elementModules.value = [];
      await loadUploadedFiles();
      return;
    }
    const [elementResponse, moduleResponse] = await Promise.all([
      elementApi.getDataList({ project: form.project, pageSize: 1000 }),
      elementModuleApi.getDataList({ project: form.project, pageSize: 1000 }),
    ]);
    elementRecords.value = asList(elementResponse);
    elementModules.value = asList(moduleResponse);
    elementOptions.value = elementRecords.value.map((item: any) => ({
      label: `${item.name} · ${item.by} · ${item.value}`,
      value: item.id,
    }));
    await loadUploadedFiles();
  }
  function projectChanged() {
    form.environment_name = '';
    void loadElements();
  }
  function selectedElementLabel(elementId: number | null | undefined) {
    const selected = elementRecords.value.find((item) => item.id === elementId);
    return selected ? `${selected.name}${selected.module_name ? ` · ${selected.module_name}` : ''}` : '';
  }
  function locatorLabel(by: string) {
    return (
      ({
        id: 'ID',
        name: 'Name',
        class_name: 'Class Name',
        link_text: 'Link Text',
        css_selector: 'CSS',
        xpath: 'XPath',
      } as Record<string, string>)[by] || by || '定位表达式'
    );
  }
  function elementCountByModule(moduleId: number | null | undefined) {
    return elementRecords.value.filter((item) => (moduleId ? item.module === moduleId : !item.module)).length;
  }
  async function handleElementPickerVisible(step: EditorStep, visible: boolean) {
    if (!visible) {
      activeElementPickerKey.value = '';
      return;
    }
    if (!form.project) {
      message.warning('请先选择所属项目');
      return;
    }
    elementKeyword.value = '';
    selectedElementModule.value = 'all';
    await loadElements();
    activeElementPickerKey.value = step.localKey;
  }
  function selectElement(step: EditorStep, item: any) {
    step.element = item.id;
    activeElementPickerKey.value = '';
  }
  function clearElement(step: EditorStep) {
    step.element = null;
    activeElementPickerKey.value = '';
  }
  async function loadUploadedFiles() {
    if (!form.project) {
      uploadedFiles.value = [];
      return;
    }
    uploadedFiles.value = asList(await uploadedFileApi.list(Number(form.project)));
  }
  function validateTabsAndSteps() {
    if (!tabs.value.length) throw new Error('请至少保留一个 Tab');
    let total = 0;
    for (const [tabIndex, tab] of tabs.value.entries()) {
      if (!tab.name?.trim()) throw new Error(`Tab ${tabIndex + 1} 未填写名称`);
      for (const [stepIndex, step] of tab.steps.entries()) {
        total += 1;
        const prefix = `Tab ${tabIndex + 1} 的第 ${stepIndex + 1} 步`;
        if (
          needsElement(step.action) &&
          !(isPlaywright ? String(step.target || '').trim() : step.element)
        )
          throw new Error(`${prefix}未填写页面元素`);
        const clickError = validateClickTargets(step);
        if (clickError) throw new Error(`${prefix}：${clickError}`);
        if (needsValue(step.action) && !String(step.value || '').trim())
          throw new Error(`${prefix}未填写操作值`);
        if (step.action === 'upload_file' && !(step.options?.file_ids || []).length)
          throw new Error(`${prefix}未选择测试文件`);
        if (isPlaywright && step.row_locator_enabled && !step.manual_fallback) {
          if (!step.row_conditions?.length) throw new Error(`${prefix}至少需要一个数据行条件`);
          for (const [conditionIndex, condition] of step.row_conditions.entries()) {
            if (!condition.column.trim() || !condition.value.trim()) {
              throw new Error(`${prefix}的第 ${conditionIndex + 1} 个数据行条件未填写完整`);
            }
          }
        }
      }
    }
    if (!total) throw new Error('请至少添加一个操作步骤');
  }
  async function load() {
    const [projectResponse, environmentResponse] = await Promise.all([
      projectApi.getDataList({ pageSize: 1000 }),
      environmentApi.getDataList({ page: 1, pageSize: 1000 }),
    ]);
    projectOptions.value = asList(projectResponse).map(
      (item: any) => ({ label: item.name, value: item.id })
    );
    environments.value = asList(environmentResponse);
    if (!id.value) return;
    const data: any = await caseApi.getDataByID(id.value);
    Object.assign(form, data);
    basicEditing.value = false;
    await loadElements();
    const tabItems: UiCaseTab[] =
      Array.isArray(data.tabs) && data.tabs.length
        ? [...data.tabs].sort((a: UiCaseTab, b: UiCaseTab) => a.order - b.order)
        : [{ key: 'tab-1', name: '登录页', order: 1 }];
    tabs.value = tabItems.map((item) => createTab(item.key, item.name, item.order));
    const defaultTab = tabs.value[0];
    const stepItems = asList(
      await stepApi.getDataList(
        isPlaywright ? { case: id.value, pageSize: 1000 } : { ui_case: id.value, pageSize: 1000 }
      )
    );
    stepItems.forEach((step: any) => {
      const tab = tabs.value.find((item) => item.key === (step.tab_key || 'tab-1')) || defaultTab;
      const smartLocator = step.options?.smart_locator || {};
      const savedConditions = Array.isArray(smartLocator.row?.conditions)
        ? smartLocator.row.conditions
        : [];
      tab.steps.push({
        ...step,
        value:
          isPlaywright && step.action === 'goto' ? step.value || step.target || '' : step.value,
        tab_key: tab.key,
        localKey: `saved-${step.id}`,
        expanded: false,
        fallback_type: normalizeFallbackType(step.fallback_type),
        manual_fallback: step.locator_mode === 'manual',
        target:
          isPlaywright && step.locator_mode === 'manual'
            ? step.fallback_value || step.target
            : step.target,
        options: {
          timeout: 10,
          clear_before_input: true,
          screenshot: false,
          ocr_fallback: false,
          ocr_language: 'auto',
          ...(step.options || {}),
        },
        row_locator_enabled: savedConditions.length > 0,
        row_table_title: smartLocator.table?.title || '',
        row_conditions: savedConditions.map((condition: any) => ({
          localKey: `${Date.now()}-${Math.random()}`,
          column: condition.column || '',
          operator: condition.operator || 'equals',
          value: String(condition.value ?? ''),
        })),
      });
    });
    activeTabKey.value = defaultTab.key;
    selectedStepKey.value = defaultTab.steps[0]?.localKey || '';
  }
  async function persistCase() {
    await formRef.value?.validate();
    if (!String(form.name || '').trim()) throw new Error('请输入用例名称');
    if (!form.project) throw new Error('请选择项目');
    validateTabsAndSteps();
    const tabPayload = tabs.value.map((tab, index) => ({
      key: tab.key,
      name: tab.name.trim(),
      order: index + 1,
    }));
    const payload = {
      project: form.project,
      name: form.name,
      description: form.description,
      environment_name: form.environment_name || '',
      browser: form.browser,
      run_mode: form.run_mode,
      enabled: form.enabled,
      tabs: tabPayload,
    };
    const saved: any = id.value
      ? await caseApi.update(id.value, payload as any)
      : await caseApi.createData(payload as any);
    let globalOrder = 0;
    const stepPayload = tabs.value.flatMap((tab) =>
      tab.steps.map((source) => {
        globalOrder += 1;
        if (isPlaywright) {
          syncRowLocator(source);
        }
        const {
          localKey,
          action_name,
          element_name,
          element_by,
          element_value,
          expanded,
          manual_fallback,
          row_locator_enabled,
          row_table_title,
          row_conditions,
          ...step
        } = source as any;
        if (isPlaywright)
          return {
            ...step,
            case: saved.id,
            tab_key: tab.key,
            order: globalOrder,
            element: undefined,
            target: step.action === 'goto' ? step.value : step.target,
            locator_mode: manual_fallback ? 'manual' : 'auto',
            fallback_value: manual_fallback ? step.target : '',
          };
        return { ...step, ui_case: saved.id, tab_key: tab.key, order: globalOrder };
      })
    ) as UiStep[];
    await caseApi.syncSteps(saved.id, stepPayload);
    if (!id.value) {
      await router.replace({
        name: isPlaywright ? 'case_ui_playwright_case_edit' : 'case_ui_case_edit',
        params: { id: saved.id },
      });
    }
    return saved;
  }
  async function save() {
    try {
      saving.value = true;
      await persistCase();
      message.success(`${isPlaywright ? 'Playwright 智能 ' : ''}UI 用例保存成功`);
      router.push({ name: isPlaywright ? 'case_ui_playwright_case' : 'case_ui_case' });
    } catch (error: any) {
      message.error(error?.message || '保存失败，请检查配置');
    } finally {
      saving.value = false;
    }
  }
  async function runCaseNow() {
    if (isPlaywright) return;
    if (!form.environment_name) {
      message.warning('请先选择执行环境');
      return;
    }
    try {
      runningCase.value = true;
      const saved = await persistCase();
      await (caseApi as UiCaseAPI).run(saved.id);
      message.success(`UI 用例「${saved.name}」执行通过`);
    } catch (error: any) {
      message.error(error?.message || 'UI 用例执行失败');
    } finally {
      runningCase.value = false;
    }
  }
  async function runCurrentTab() {
    if (!isPlaywright) return;
    if (!activeTab.value.steps.length) {
      message.warning('当前 Tab 没有可执行步骤');
      return;
    }
    try {
      runningTab.value = true;
      const saved = await persistCase();
      const result = await (caseApi as PlaywrightCaseAPI).runTab(saved.id, activeTabKey.value);
      const passedCount = Array.isArray(result?.steps)
        ? result.steps.filter((item: any) => item.passed).length
        : 0;
      message.success(`Tab「${activeTab.value.name}」执行成功，共通过 ${passedCount} 个步骤`);
    } catch (error: any) {
      message.error(error?.message || `Tab「${activeTab.value.name}」执行失败`);
    } finally {
      runningTab.value = false;
    }
  }
  onMounted(load);
</script>

<style scoped lang="less">
  .ui-case-page {
    min-height: 100%;
    padding: 20px 28px 92px;
    color: #1d2738;
    background: #f7f9fc;
  }
  .ui-case-page.smart-case-page {
    padding-bottom: 28px;
    background: #f6f8fb;
  }
  .page-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    max-width: 1540px;
    margin: 0 auto 16px;
  }
  .smart-page-header {
    align-items: center;
    min-height: 72px;
    margin-bottom: 12px;
  }
  .smart-page-header .breadcrumb {
    margin-bottom: 12px;
  }
  .smart-title-line h1 {
    font-size: 24px;
  }
  .smart-page-header :deep(.n-button) {
    height: 40px;
  }
  .heading-block {
    min-width: 0;
  }
  .breadcrumb {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 14px;
    color: #748197;
    font-size: 13px;
  }
  .breadcrumb i {
    color: #aab3c0;
    font-style: normal;
  }
  .breadcrumb strong {
    color: #273348;
  }
  .title-line {
    display: flex;
    gap: 22px;
    align-items: baseline;
  }
  .title-line h1 {
    margin: 0;
    color: #172033;
    font-size: 26px;
    font-weight: 760;
  }
  .title-line p {
    margin: 0;
    color: #718096;
    font-size: 14px;
  }
  .page-header :deep(.n-button),
  .sticky-actions :deep(.n-button) {
    min-width: 112px;
    height: 44px;
    border-radius: 7px;
  }
  .basic-section,
  .steps-section {
    max-width: 1540px;
    margin: 0 auto 14px;
    border: 1px solid #dfe5ed;
    border-radius: 9px;
    background: #fff;
    box-shadow: 0 2px 8px rgba(24, 43, 72, 0.025);
  }
  .basic-section {
    padding: 18px 20px 8px;
  }
  .basic-section h2,
  .section-heading h2 {
    margin: 0;
    color: #1d2738;
    font-size: 18px;
    font-weight: 730;
  }
  .basic-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .smart-basic-section {
    padding: 0;
    overflow: hidden;
  }
  .smart-basic-section .basic-heading {
    min-height: 54px;
    padding: 0 22px;
    border-bottom: 1px solid #e7ebf1;
  }
  .smart-basic-section .basic-heading h2 {
    font-size: 16px;
  }
  .smart-basic-section .basic-heading :deep(.n-button) {
    font-weight: 650;
  }
  .smart-basic-summary {
    display: grid;
    grid-template-columns: 1.35fr 0.95fr 1fr 0.82fr 0.9fr 0.78fr 1.15fr;
    gap: 0;
    min-height: 86px;
    padding: 0 22px;
  }
  .smart-basic-summary > div {
    display: flex;
    min-width: 0;
    flex-direction: column;
    justify-content: center;
    padding-right: 20px;
  }
  .smart-basic-summary span,
  .smart-basic-summary strong {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .smart-basic-summary span {
    margin-bottom: 8px;
    color: #8a95a6;
    font-size: 11px;
  }
  .smart-basic-summary strong {
    color: #263247;
    font-size: 13px;
    font-weight: 650;
  }
  .smart-basic-summary .case-status {
    display: inline-flex;
    align-items: center;
    color: #7b8798;
  }
  .smart-basic-summary .case-status::before {
    width: 7px;
    height: 7px;
    margin-right: 7px;
    border-radius: 50%;
    background: #aab3c0;
    content: '';
  }
  .smart-basic-summary .case-status.enabled {
    color: #15975f;
  }
  .smart-basic-summary .case-status.enabled::before {
    background: #20b872;
  }
  .smart-basic-section .basic-grid {
    margin: 0;
    padding: 18px 22px 8px;
  }
  .basic-grid {
    display: grid;
    grid-template-columns: 1.2fr 1fr 0.9fr 0.82fr 0.9fr 1.35fr 86px;
    gap: 20px 32px;
    margin-top: 16px;
  }
  .basic-section :deep(.n-form-item-label) {
    color: #3d495a;
    font-size: 13px;
    font-weight: 600;
  }
  .basic-section :deep(.n-input),
  .basic-section :deep(.n-base-selection) {
    min-height: 44px;
  }
  .enabled-field :deep(.n-form-item-blank) {
    align-items: center;
    min-height: 44px;
  }
  .steps-section {
    padding: 18px 20px 20px;
  }
  .section-heading {
    display: flex;
    gap: 20px;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 15px;
  }
  .section-heading > div {
    display: flex;
    gap: 18px;
    align-items: baseline;
  }
  .section-heading p {
    margin: 0;
    color: #7b8798;
    font-size: 13px;
  }
  .fullscreen-button {
    margin-left: auto;
    color: #536176;
    font-size: 19px;
  }
  .smart-steps-section {
    padding: 0;
    overflow: hidden;
  }
  .smart-steps-section > .section-heading {
    min-height: 62px;
    margin: 0;
    padding: 0 22px;
    border-bottom: 1px solid #e7ebf1;
  }
  .smart-steps-section .section-heading h2 {
    font-size: 16px;
  }
  .smart-steps-section .section-heading p {
    font-size: 12px;
  }
  .smart-steps-section.fullscreen {
    position: fixed;
    z-index: 1000;
    inset: 10px;
    max-width: none;
    margin: 0;
    border-radius: 10px;
    box-shadow: 0 20px 60px rgba(26, 39, 61, 0.2);
  }
  .smart-steps-section.fullscreen .playwright-workbench {
    height: calc(100vh - 133px);
    min-height: 0;
  }
  .smart-steps-section.fullscreen .playwright-step-pane,
  .smart-steps-section.fullscreen .playwright-inspector-pane {
    overflow-y: auto;
  }
  .tab-strip {
    display: flex;
    align-items: stretch;
    min-height: 50px;
    overflow-x: auto;
    border-bottom: 1px solid #dfe5ed;
  }
  .tab-item,
  .add-tab {
    display: flex;
    flex: 0 0 auto;
    gap: 8px;
    align-items: center;
    min-width: 210px;
    height: 49px;
    padding: 0 14px;
    border: 1px solid #dfe5ed;
    border-bottom: 0;
    color: #344054;
    background: #fff;
    cursor: pointer;
  }
  .tab-item:first-child {
    border-radius: 7px 0 0 0;
  }
  .tab-item + .tab-item {
    margin-left: -1px;
  }
  .tab-item > .n-icon {
    font-size: 18px;
  }
  .tab-item > span {
    overflow: hidden;
    flex: 1;
    font-size: 14px;
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .tab-item.active {
    position: relative;
    z-index: 1;
    border-color: #a9c7fa;
    color: #1769e8;
    background: #f4f8ff;
  }
  .tab-item.active::after {
    position: absolute;
    right: 0;
    bottom: -1px;
    left: 0;
    height: 3px;
    background: #2475ef;
    content: '';
  }
  .smart-steps-section .tab-strip {
    min-height: 54px;
    padding: 0 22px;
    background: #fff;
  }
  .smart-steps-section .tab-item {
    min-width: auto;
    height: 53px;
    padding: 0 18px;
    border: 0;
    color: #536176;
    background: transparent;
  }
  .smart-steps-section .tab-item + .tab-item {
    margin-left: 0;
  }
  .smart-steps-section .tab-item.active {
    color: #1769e8;
    background: transparent;
  }
  .smart-steps-section .tab-item > span {
    overflow: visible;
  }
  .smart-steps-section .add-tab {
    min-width: 130px;
    height: 34px;
    margin: 10px 0 10px 14px;
    border: 0;
    border-left: 1px solid #e1e6ed;
    border-radius: 0;
    background: transparent;
  }
  .tab-mini-action {
    display: none;
    flex: none;
    width: 24px;
    height: 24px;
    padding: 0;
    border: 0;
    border-radius: 4px;
    color: #718096;
    background: transparent;
    cursor: pointer;
  }
  .tab-item:hover .tab-mini-action,
  .tab-item.active .tab-mini-action {
    display: grid;
    place-items: center;
  }
  .tab-mini-action:hover {
    color: #1769e8;
    background: #e9f1ff;
  }
  .tab-mini-action.danger:hover {
    color: #e54d5f;
    background: #fff0f2;
  }
  .tab-name-input {
    width: 118px;
  }
  .add-tab {
    min-width: 174px;
    margin-left: 16px;
    border-style: dashed;
    border-bottom: 1px dashed #bdc8d7;
    border-radius: 6px;
    justify-content: center;
    font-size: 14px;
  }
  .add-tab:hover {
    border-color: #2475ef;
    color: #1769e8;
    background: #f8fbff;
  }
  .tab-step-count {
    display: inline-grid;
    min-width: 22px;
    height: 22px;
    margin-left: 8px;
    padding: 0 6px;
    border-radius: 11px;
    color: #1769e8;
    font-size: 12px;
    line-height: 22px;
    text-align: center;
    background: #e8f1ff;
    place-items: center;
  }
  .playwright-workbench {
    display: grid;
    grid-template-columns: minmax(390px, 0.88fr) minmax(500px, 1.12fr);
    min-height: 680px;
    border: 1px solid #dfe5ed;
    border-top: 0;
    border-radius: 0 0 8px 8px;
    overflow: visible;
    background: #fff;
  }
  .playwright-step-pane {
    min-width: 0;
    border-right: 1px solid #e2e7ee;
    background: #fbfcfe;
  }
  .pane-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 64px;
    padding: 0 18px;
    border-bottom: 1px solid #e3e8ef;
    background: #fff;
  }
  .pane-heading > div {
    display: flex;
    gap: 10px;
    align-items: center;
  }
  .pane-heading strong {
    color: #202b3d;
    font-size: 15px;
  }
  .pane-heading div span {
    min-width: 24px;
    padding: 2px 8px;
    border-radius: 10px;
    color: #1769e8;
    font-size: 11px;
    background: #eaf2ff;
  }
  .pane-heading > span {
    color: #8a96a8;
    font-size: 11px;
  }
  .playwright-step-list {
    display: flex;
    flex-direction: column;
    gap: 9px;
    max-height: 683px;
    padding: 14px;
    overflow-x: hidden;
    overflow-y: auto;
    scrollbar-gutter: stable;
    overscroll-behavior: contain;
  }
  .playwright-step-list::-webkit-scrollbar {
    width: 6px;
  }
  .playwright-step-list::-webkit-scrollbar-track {
    background: transparent;
  }
  .playwright-step-list::-webkit-scrollbar-thumb {
    border-radius: 6px;
    background: #cbd5e1;
  }
  .playwright-step-list::-webkit-scrollbar-thumb:hover {
    background: #aebaca;
  }
  .playwright-step-card {
    position: relative;
    display: grid;
    grid-template-columns: 22px 34px 38px minmax(0, 1fr) 58px;
    gap: 9px;
    align-items: center;
    min-height: 74px;
    padding: 10px 10px 10px 8px;
    border: 1px solid #e0e6ee;
    border-radius: 8px;
    background: #fff;
    cursor: pointer;
    transition: border-color 0.16s, box-shadow 0.16s, background 0.16s;
  }
  .playwright-step-card:hover {
    border-color: #b9cdf0;
    box-shadow: 0 5px 14px rgba(38, 67, 108, 0.06);
  }
  .playwright-step-card.selected {
    border-color: #4f8df5;
    background: #f5f9ff;
    box-shadow: 0 0 0 2px rgba(58, 125, 237, 0.08);
  }
  .playwright-drag-handle {
    display: grid;
    width: 22px;
    height: 34px;
    padding: 0;
    border: 0;
    color: #a2adba;
    font-size: 16px;
    background: transparent;
    cursor: grab;
    place-items: center;
  }
  .playwright-drag-handle:active {
    cursor: grabbing;
  }
  .playwright-step-number {
    color: #354257;
    font-size: 14px;
    font-weight: 750;
    font-variant-numeric: tabular-nums;
  }
  .playwright-action-icon {
    display: grid;
    width: 36px;
    height: 36px;
    border: 1px solid #dbe3ed;
    border-radius: 8px;
    color: #66758b;
    font-size: 17px;
    background: #f6f8fb;
    place-items: center;
  }
  .playwright-action-icon.blue {
    border-color: #c8dcff;
    color: #1769e8;
    background: #eef5ff;
  }
  .playwright-action-icon.green {
    border-color: #c8ead6;
    color: #0b9a5b;
    background: #effaf4;
  }
  .playwright-action-icon.orange {
    border-color: #ffd9b8;
    color: #dc671b;
    background: #fff6ee;
  }
  .playwright-action-icon.purple {
    border-color: #e0d2fb;
    color: #7540d7;
    background: #f7f3ff;
  }
  .playwright-action-icon.teal {
    border-color: #bfe7e4;
    color: #087f79;
    background: #f0faf9;
  }
  .playwright-step-copy {
    min-width: 0;
  }
  .playwright-step-copy strong,
  .playwright-step-copy span {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .playwright-step-copy strong {
    margin-bottom: 5px;
    color: #263247;
    font-size: 13px;
    font-weight: 700;
  }
  .playwright-step-copy span {
    color: #7a8799;
    font-size: 12px;
  }
  .step-summary-line { display: flex; min-width: 0; align-items: center; gap: 5px; }
  .step-summary-line span { min-width: 0; flex: 1; }
  .step-summary-eye { display: inline-grid; width: 22px; height: 22px; padding: 0; flex: none; place-items: center; border: 0; border-radius: 4px; color: #7a8799; background: transparent; cursor: pointer; }
  .step-summary-eye:hover { color: #3f7ed8; background: rgba(63, 126, 216, .1); }
  .playwright-card-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    opacity: 0;
    transition: opacity 0.15s;
  }
  .playwright-step-card:hover .playwright-card-actions,
  .playwright-step-card.selected .playwright-card-actions {
    opacity: 1;
  }
  .playwright-card-actions :deep(.n-button) {
    font-size: 16px;
  }
  .playwright-step-ghost {
    border-color: #5f98f5;
    background: #eaf3ff;
    opacity: 0.65;
  }
  .playwright-step-empty {
    padding: 76px 0 54px;
  }
  .playwright-add-step {
    display: flex;
    gap: 8px;
    align-items: center;
    justify-content: center;
    width: calc(100% - 28px);
    height: 46px;
    margin: 0 14px 14px;
    border: 1px dashed #8db8fa;
    border-radius: 7px;
    color: #1769e8;
    font-size: 13px;
    font-weight: 650;
    background: #fff;
    cursor: pointer;
  }
  .playwright-add-step:hover {
    border-color: #1769e8;
    background: #f4f8ff;
  }
  .playwright-inspector-pane {
    position: relative;
    min-width: 0;
    background: #fff;
  }
  .inspector-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 64px;
    padding: 0 20px;
    border-bottom: 1px solid #e3e8ef;
  }
  .inspector-heading > div {
    display: flex;
    gap: 12px;
    align-items: baseline;
  }
  .inspector-heading span {
    color: #8190a4;
    font-size: 12px;
  }
  .inspector-heading h3 {
    margin: 0;
    color: #1f2a3d;
    font-size: 17px;
    font-weight: 740;
  }
  .inspector-status {
    padding: 5px 10px;
    border: 1px solid #c6ddff;
    border-radius: 12px;
    color: #1769e8 !important;
    background: #f0f6ff;
  }
  .inspector-status.manual {
    border-color: #e0d1fb;
    color: #7540d7 !important;
    background: #f8f4ff;
  }
  .inspector-body {
    padding: 20px 22px 86px;
  }
  .inspector-fields {
    display: grid;
    grid-template-columns: minmax(180px, 0.78fr) minmax(240px, 1.22fr);
    gap: 16px;
  }
  .inspector-field {
    display: block;
    min-width: 0;
  }
  .inspector-field > span {
    display: block;
    margin-bottom: 8px;
    color: #445166;
    font-size: 12px;
    font-weight: 650;
  }
  .inspector-field.wide {
    grid-column: span 1;
  }
  .upload-step-control {
    display: flex;
    min-height: 42px;
    align-items: center;
    gap: 10px;
    padding: 6px 10px;
    border: 1px dashed #a8c4ef;
    border-radius: 6px;
    color: #56657a;
    background: #f8fbff;
    font-size: 12px;
  }
  .upload-step-control input[type='file'] {
    width: 112px;
    max-width: 112px;
    color: transparent;
    font-size: 0;
  }
  .upload-step-control input[type='file']::file-selector-button {
    padding: 5px 8px;
    border: 0;
    border-radius: 4px;
    color: #1769e8;
    background: #eaf2ff;
    font-size: 12px;
    cursor: pointer;
  }
  .upload-step-control span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .inspector-action-select {
    width: 100%;
  }
  .inspector-fields :deep(.n-input),
  .inspector-fields :deep(.n-base-selection) {
    min-height: 42px;
    border-radius: 6px;
  }
  .inspector-section {
    margin-top: 20px;
    border: 1px solid #e1e6ed;
    border-radius: 8px;
    background: #fff;
    overflow: hidden;
  }
  .inspector-section-title {
    min-height: 58px;
    padding: 13px 16px;
    border-bottom: 1px solid #e7ebf1;
    background: #fafbfd;
  }
  .inspector-section-title strong,
  .inspector-section-title span {
    display: block;
  }
  .inspector-section-title strong {
    color: #263247;
    font-size: 14px;
  }
  .inspector-section-title span {
    margin-top: 3px;
    color: #8995a6;
    font-size: 11px;
  }
  .inspector-option-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .inspector-toggle-row,
  .inspector-timeout-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 64px;
    padding: 11px 15px;
    color: #405066;
  }
  .inspector-option-grid .inspector-toggle-row + .inspector-toggle-row {
    border-left: 1px solid #e7ebf1;
  }
  .inspector-toggle-row > div,
  .inspector-timeout-row > div {
    min-width: 0;
  }
  .inspector-toggle-row strong,
  .inspector-toggle-row span,
  .inspector-timeout-row strong,
  .inspector-timeout-row span {
    display: block;
  }
  .inspector-toggle-row strong,
  .inspector-timeout-row strong {
    font-size: 12px;
  }
  .inspector-toggle-row span,
  .inspector-timeout-row span {
    margin-top: 3px;
    color: #909bad;
    font-size: 10px;
    font-weight: 400;
  }
  .fallback-config {
    display: grid;
    grid-template-columns: 126px minmax(0, 1fr);
    gap: 12px;
    align-items: center;
    padding: 0 15px 14px;
  }
  .fallback-config span {
    color: #8290a3;
    font-size: 11px;
  }
  .inspector-row-locator {
    padding: 14px 15px 16px;
    border-top: 1px solid #e7ebf1;
    background: #fbfcfe;
  }
  .inspector-row-locator .row-locator-heading {
    margin-bottom: 12px;
  }
  .advanced-option-list {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .advanced-option-list > * {
    border-bottom: 1px solid #edf0f4;
  }
  .advanced-option-list > *:nth-child(even) {
    border-left: 1px solid #edf0f4;
  }
  .advanced-option-list > *:nth-last-child(-n + 2) {
    border-bottom: 0;
  }
  .inspector-timeout-row {
    justify-content: flex-start;
    gap: 9px;
  }
  .inspector-timeout-row > div {
    flex: 1;
  }
  .inspector-timeout-row :deep(.n-input-number) {
    width: 84px;
  }
  .inspector-timeout-row em {
    color: #7c899b;
    font-size: 11px;
    font-style: normal;
  }
  .inspector-actions {
    position: absolute;
    right: 0;
    bottom: 0;
    left: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 66px;
    padding: 0 22px;
    border-top: 1px solid #e1e6ed;
    background: rgba(255, 255, 255, 0.96);
  }
  /* 只命中左侧提示文案。写成 `.inspector-actions span` 会连按钮内部的
     `<span class="n-button__content">` 一起染色 —— 它会给「应用配置」盖上
     一层灰字，在蓝底上对比度只有 1.7，浅色深色都读不清。 */
  .inspector-actions .inspector-hint {
    color: #8a96a8;
    font-size: 11px;
  }
  .inspector-actions :deep(.n-button) {
    min-width: 104px;
  }
  .inspector-actions :deep(.n-button__content) {
    gap: 6px;
  }
  .inspector-empty {
    padding-top: 180px;
  }
  .step-table-wrap {
    min-width: 900px;
    border: 1px solid #dfe5ed;
    border-top: 0;
    border-radius: 0 0 7px 7px;
    overflow: hidden;
  }
  .step-table-head,
  .step-row {
    display: grid;
    grid-template-columns:
      118px minmax(150px, 1.05fr) 136px minmax(170px, 1.18fr) minmax(178px, 1.28fr)
      70px;
    gap: 10px;
    align-items: center;
  }
  .step-table-wrap.playwright-table .step-table-head,
  .step-table-wrap.playwright-table .step-row {
    grid-template-columns: 118px 156px minmax(240px, 1.45fr) minmax(220px, 1.3fr) 70px;
  }
  .step-table-head {
    min-height: 46px;
    padding: 0 14px;
    border-bottom: 1px solid #dfe5ed;
    color: #5e6b7e;
    font-size: 13px;
    font-weight: 650;
    background: #fafbfd;
  }
  .step-table-head span:last-child {
    text-align: center;
  }
  .step-entry {
    border-bottom: 1px solid #e7ebf1;
    background: #fff;
  }
  .step-entry:last-child {
    border-bottom: 0;
  }
  .step-entry.expanded {
    position: relative;
    z-index: 1;
    box-shadow: inset 0 0 0 1px #7cacfb;
  }
  .step-row {
    min-height: 62px;
    padding: 7px 14px;
  }
  .step-row:hover {
    background: #fbfcff;
  }
  .step-ghost {
    border: 1px dashed #2475ef;
    background: #edf5ff;
    opacity: 0.7;
  }
  .order-cell {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .order-cell strong {
    color: #253044;
    font-size: 14px;
  }
  .drag-handle,
  .expand-button {
    display: grid;
    width: 25px;
    height: 32px;
    padding: 0;
    border: 0;
    color: #98a3b2;
    background: transparent;
    cursor: pointer;
    place-items: center;
  }
  .drag-handle {
    font-size: 17px;
    cursor: grab;
  }
  .drag-handle:active {
    cursor: grabbing;
  }
  .expand-button {
    font-size: 12px;
    transition: transform 0.18s;
  }
  .expand-button.open {
    transform: rotate(90deg);
  }
  .table-input :deep(.n-input__border),
  .table-select :deep(.n-base-selection__border) {
    border-color: transparent;
  }
  .table-input:hover :deep(.n-input__border),
  .table-input.n-input--focus :deep(.n-input__border),
  .table-select:hover :deep(.n-base-selection__border) {
    border-color: #b8c8dd;
  }
  .element-picker-trigger {
    display: flex;
    gap: 8px;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    min-width: 0;
    height: 34px;
    margin: 0 8px;
    padding: 0 10px;
    overflow: hidden;
    border: 1px solid transparent;
    border-radius: 5px;
    color: #344054;
    font: inherit;
    text-align: left;
    background: transparent;
    cursor: pointer;
  }
  .element-picker-trigger:hover {
    border-color: #b8c8dd;
    background: #f8fbff;
  }
  .element-picker-trigger.empty { color: #9aa5b5; }
  .element-picker-trigger > span:first-child {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .element-picker-clear {
    flex: none;
    color: #8a96a8;
    font-size: 18px;
    line-height: 1;
  }
  .element-picker-clear:hover { color: #e24b4b; }
  .element-picker-dropdown { overflow: hidden; }
  .element-picker-dropdown header {
    display: flex;
    gap: 16px;
    align-items: center;
    padding: 13px 15px;
    border-bottom: 1px solid #e8edf4;
  }
  .element-picker-dropdown header strong {
    flex: none;
    color: #26344a;
    font-size: 15px;
  }
  .element-picker-dropdown header :deep(.n-input) { flex: 1; }
  .element-picker-no-project {
    padding: 42px 20px;
    color: #8a96a8;
    text-align: center;
    font-size: 13px;
  }
  .element-picker-content {
    display: grid;
    grid-template-columns: 210px minmax(0, 1fr);
    height: 360px;
  }
  .element-picker-content aside {
    padding: 10px;
    overflow-y: auto;
    border-right: 1px solid #e8edf4;
    background: #f8faff;
  }
  .element-picker-content aside button {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    min-height: 34px;
    padding: 0 10px;
    border: 0;
    border-radius: 5px;
    color: #526075;
    text-align: left;
    background: transparent;
    cursor: pointer;
  }
  .element-picker-content aside button:hover,
  .element-picker-content aside button.active {
    color: #1769e8;
    background: #eaf2ff;
  }
  .element-picker-content aside em {
    min-width: 20px;
    color: #8290a4;
    font-style: normal;
    text-align: center;
    font-size: 12px;
  }
  .element-project-node {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin: 13px 10px 5px;
    color: #344054;
    font-size: 13px;
    font-weight: 650;
  }
  .element-project-node small { color: #93a0b1; font-size: 11px; font-weight: 400; }
  .element-module-node { padding-left: 20px !important; }
  .element-picker-content main { min-width: 0; overflow-y: auto; padding: 11px 13px; }
  .element-list-title {
    margin: 0 0 8px 4px;
    color: #26344a;
    font-size: 13px;
    font-weight: 650;
  }
  .element-list-title span { margin-left: 7px; color: #93a0b1; font-size: 11px; font-weight: 400; }
  .element-option {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 3px 12px;
    width: 100%;
    padding: 10px 11px;
    border: 1px solid transparent;
    border-radius: 6px;
    color: #344054;
    text-align: left;
    background: #fff;
    cursor: pointer;
  }
  .element-option:hover,
  .element-option.selected { border-color: #b9d4ff; background: #f5f9ff; }
  .element-option > div { display: flex; gap: 8px; min-width: 0; align-items: baseline; }
  .element-option strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
  .element-option span { flex: none; color: #8d9aae; font-size: 11px; }
  .element-option code {
    padding: 2px 5px;
    border-radius: 3px;
    color: #1769e8;
    font-size: 10px;
    background: #eaf2ff;
  }
  .element-option p {
    grid-column: 1 / -1;
    margin: 0;
    overflow: hidden;
    color: #7a8799;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
  }
  .table-upload-control {
    min-width: 0;
    margin: 0 8px;
  }
  .action-select {
    position: relative;
    width: 136px;
    --action-border: #d5dbe4;
    --action-color: #526075;
    --action-bg: #f7f9fb;
  }
  .action-select-icon {
    position: absolute;
    z-index: 3;
    top: 50%;
    left: 10px;
    color: var(--action-color);
    font-size: 15px;
    pointer-events: none;
    transform: translateY(-50%);
  }
  .action-select :deep(.n-base-selection) {
    color: var(--action-color);
    background: var(--action-bg);
  }
  .action-select :deep(.n-base-selection__border),
  .action-select :deep(.n-base-selection__state-border) {
    border-color: var(--action-border) !important;
  }
  .action-select :deep(.n-base-selection-label) {
    padding-left: 30px;
    font-size: 13px;
    font-weight: 650;
  }
  .action-select :deep(.n-base-selection-input) {
    color: var(--action-color);
  }
  .action-select.blue {
    --action-border: #b9d4ff;
    --action-color: #1769e8;
    --action-bg: #f3f8ff;
  }
  .action-select.green {
    --action-border: #bde8d0;
    --action-color: #0c9b5d;
    --action-bg: #f1fbf6;
  }
  .action-select.orange {
    --action-border: #ffd3ad;
    --action-color: #e56a16;
    --action-bg: #fff7ef;
  }
  .action-select.purple {
    --action-border: #dbc7ff;
    --action-color: #7540d7;
    --action-bg: #f8f4ff;
  }
  .action-select.teal {
    --action-border: #aee3e0;
    --action-color: #087f79;
    --action-bg: #f0fbfa;
  }
  .action-select.indigo {
    --action-border: #c8ccfa;
    --action-color: #4d58cc;
    --action-bg: #f5f6ff;
  }
  .action-select.pink {
    --action-border: #f0c1dc;
    --action-color: #bd397f;
    --action-bg: #fff4fa;
  }
  .empty-cell {
    padding-left: 12px;
    color: #a3adba;
  }
  .row-actions {
    display: flex;
    justify-content: center;
    gap: 14px;
  }
  .row-actions :deep(.n-button) {
    font-size: 18px;
  }
  .advanced-row {
    display: flex;
    gap: 32px;
    align-items: center;
    min-height: 64px;
    padding: 10px 18px 10px 72px;
    border-top: 1px dashed #d7e1ef;
    background: #f8fbff;
  }
  .advanced-title {
    display: flex;
    flex-direction: column;
    color: #344054;
    font-size: 13px;
    font-weight: 650;
  }
  .advanced-title span {
    margin-top: 3px;
    color: #8a96a8;
    font-size: 11px;
    font-weight: 400;
  }
  .advanced-row label {
    display: flex;
    gap: 8px;
    align-items: center;
    color: #58667b;
    font-size: 12px;
  }
  .advanced-row label :deep(.n-input-number) {
    width: 100px;
  }
  .advanced-row em {
    color: #8b97a8;
    font-style: normal;
  }
  .fallback-type-select {
    width: 118px;
  }
  .row-locator-panel {
    padding: 14px 18px 16px 72px;
    border-top: 1px solid #dce7f5;
    background: #f8fbff;
  }
  .row-locator-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 13px;
  }
  .row-locator-heading > div {
    display: flex;
    gap: 12px;
    align-items: baseline;
  }
  .row-locator-heading strong {
    color: #26344a;
    font-size: 14px;
  }
  .row-locator-heading span {
    color: #7a8799;
    font-size: 12px;
  }
  .table-title-row {
    display: grid;
    grid-template-columns: 86px minmax(260px, 520px);
    gap: 10px;
    align-items: center;
    margin-bottom: 12px;
  }
  .table-title-row > span {
    color: #526075;
    font-size: 12px;
    font-weight: 600;
  }
  .condition-head,
  .condition-row {
    display: grid;
    grid-template-columns: minmax(150px, 0.8fr) 140px minmax(220px, 1.4fr) 36px;
    gap: 10px;
    align-items: center;
  }
  .condition-head {
    min-height: 30px;
    color: #7a8799;
    font-size: 12px;
  }
  .condition-row + .condition-row {
    margin-top: 8px;
  }
  .condition-row :deep(.n-button) {
    font-size: 17px;
  }
  .row-locator-tip {
    margin-top: 11px;
    color: #7a8799;
    font-size: 12px;
  }
  .step-empty {
    padding: 52px 0;
  }
  .add-step {
    display: flex;
    gap: 9px;
    align-items: center;
    justify-content: center;
    width: calc(100% - 20px);
    height: 44px;
    margin: 10px;
    border: 1px dashed #86b4fb;
    border-radius: 6px;
    color: #1769e8;
    font-size: 14px;
    font-weight: 600;
    background: #fff;
    cursor: pointer;
  }
  .add-step:hover {
    border-color: #1769e8;
    background: #f5f9ff;
  }
  .execution-rule {
    display: flex;
    gap: 10px;
    align-items: center;
    min-height: 48px;
    margin-top: 14px;
    padding: 0 14px;
    border: 1px solid #d8e8ff;
    border-radius: 7px;
    color: #3672c8;
    font-size: 12px;
    background: #eff6ff;
  }
  .execution-rule > .n-icon {
    flex: none;
    color: #1769e8;
    font-size: 22px;
  }
  .sticky-actions {
    position: fixed;
    z-index: 20;
    right: 0;
    bottom: 0;
    left: 0;
    display: flex;
    gap: 12px;
    align-items: center;
    justify-content: flex-end;
    padding: 12px 34px;
    border-top: 1px solid #dfe5ed;
    background: rgba(255, 255, 255, 0.97);
    box-shadow: 0 -4px 18px rgba(31, 48, 73, 0.05);
    backdrop-filter: blur(8px);
  }
  @media (max-width: 1260px) {
    .basic-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .smart-basic-summary {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      row-gap: 18px;
      padding-top: 18px;
      padding-bottom: 18px;
    }
    .enabled-field {
      grid-column: span 1;
    }
    .playwright-workbench {
      grid-template-columns: minmax(350px, 0.82fr) minmax(460px, 1.18fr);
    }
    .steps-section {
      overflow-x: auto;
    }
  }
  @media (max-width: 980px) {
    .playwright-workbench {
      grid-template-columns: 1fr;
    }
    .playwright-step-pane {
      border-right: 0;
      border-bottom: 1px solid #e2e7ee;
    }
    .playwright-inspector-pane {
      min-height: 620px;
    }
    .inspector-actions {
      position: static;
    }
    .inspector-body {
      padding-bottom: 20px;
    }
  }
  @media (max-width: 760px) {
    .ui-case-page {
      padding: 14px 14px 88px;
    }
    .ui-case-page.smart-case-page {
      padding-bottom: 14px;
    }
    .page-header,
    .title-line {
      align-items: flex-start;
      flex-direction: column;
    }
    .page-header {
      gap: 14px;
    }
    .basic-grid {
      grid-template-columns: 1fr;
    }
    .smart-basic-summary {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .tab-item {
      min-width: 190px;
    }
    .smart-steps-section .tab-item {
      min-width: 168px;
    }
    .sticky-actions {
      padding: 10px 14px;
    }
  }
</style>
