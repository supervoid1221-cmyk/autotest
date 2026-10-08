<template>
  <div class="endpoint-page api-workbench">
    <nav class="endpoint-directory">
      <n-button text class="directory-back" @click="back">← 返回接口列表</n-button>
      <n-input v-model:value="directorySearch" placeholder="搜索接口" clearable>
        <template #prefix><PhMagnifyingGlass /></template>
      </n-input>
      <section v-for="group in directoryGroups" :key="group.name" class="directory-group">
        <button type="button" class="directory-group-header" @click="toggleDirectoryGroup(group.name)">
          <PhFolderSimple :size="17" />
          <span>{{ group.name }}</span>
          <PhCaretDown :size="15" :class="{ collapsed: collapsedDirectoryGroups.has(group.name) }" />
        </button>
        <div v-show="!collapsedDirectoryGroups.has(group.name)" class="directory-items">
          <button
            v-for="item in group.items"
            :key="item.id"
            type="button"
            :class="{ selected: Number(item.id) === endpointId }"
            @click="switchEndpoint(item)"
          >
            <b :class="String(item.method).toLowerCase()">{{ item.method }}</b>
            <span>{{ item.name }}</span>
          </button>
        </div>
      </section>
    </nav>
    <div class="endpoint-page-inner">
      <div class="page-toolbar">
        <div class="breadcrumb-row"
          ><span>API测试</span><i>/</i><span>接口管理</span><i>/</i><b>接口详情</b></div
        >
      </div>

      <n-form
        :model="formValue"
        :rules="rules"
        label-placement="left"
        :show-require-mark="false"
        ref="formRef"
        class="endpoint-form"
      >
        <section class="basic-card">
          <div class="endpoint-title-row">
            <div class="endpoint-title-editor">
              <n-input ref="titleInputRef" v-model:value="formValue.name" placeholder="新建接口" />
              <button type="button" aria-label="编辑接口名称" @click="focusEndpointTitle"><PhPencilSimple /></button>
            </div>
            <div class="page-actions">
              <n-button
                class="save-button"
                :loading="submitMode === 'save'"
                :disabled="submitMode !== null"
                @click="formSubmit(false)"
                >保存</n-button
              >
              <n-select class="environment-selector" v-model:value="debugEnvironmentId" :options="debugEnvironmentOptions" :disabled="debugRunning" placeholder="选择执行环境" />
            </div>
          </div>
        </section>

        <div class="endpoint-workspace">
          <main class="workspace-main">
            <div class="basic-grid">
            <n-form-item label="项目" path="project"
              ><n-select
                v-model:value="formValue.project"
                size="small"
                :options="project_list"
                @update:value="handleProjectChange"
            /></n-form-item>
            <n-form-item label="模块" path="module"
              ><n-select
                v-model:value="formValue.module"
                size="small"
                :options="module_list"
                :disabled="!formValue.project"
                placeholder="请先选择项目"
            /></n-form-item>
            </div>
            <section class="request-card">
              <div class="request-card-head">
                <h2>请求配置</h2>
                <div class="request-run-control">
                  <n-button
                    type="primary"
                    class="request-debug-button"
                    :loading="submitMode === 'debug'"
                    :disabled="submitMode !== null"
                    @click="formSubmit(true)"
                  >
                    <template #icon><PhPlay :size="16" weight="fill" /></template>
                    {{ dataDrivenEnabled ? '运行数据集' : '发送请求' }}
                  </n-button>
                  <n-dropdown trigger="click" :options="runModeOptions" @select="selectRunMode">
                    <n-button
                      type="primary"
                      class="request-run-menu"
                      :disabled="submitMode !== null"
                      aria-label="选择执行模式"
                      title="选择执行模式"
                    >
                      <template #icon><PhCaretDown :size="17" /></template>
                    </n-button>
                  </n-dropdown>
                </div>
              </div>
              <div class="request-target">
                <n-form-item path="url" :show-label="false">
                  <div class="request-core-input">
                    <n-select
                      v-model:value="formValue.method"
                      size="small"
                      :options="methodOptions"
                      :render-label="renderMethodOption"
                      class="request-method-select"
                      :class="`method-${String(formValue.method || 'get').toLowerCase()}`"
                    />
                    <n-input
                      v-model:value="formValue.url"
                      size="small"
                      placeholder="例如 /api/v2/login"
                    />
                  </div>
                </n-form-item>
              </div>
              <div class="request-tabs">
                <button
                  v-for="tab in requestTabs"
                  :key="tab.value"
                  type="button"
                  :class="{ active: requestTab === tab.value, 'request-parameter-tab': ['params', 'headers'].includes(tab.value) }"
                  @click="selectRequestTab(tab.value)"
                >
                  <component v-if="!['params', 'headers'].includes(tab.value)" :is="tab.icon" :size="18" /><span>{{ tab.label }}</span
                  ><b v-if="typeof tab.count === 'number'">{{ tab.count }}</b>
                </button>
              </div>

              <template v-if="requestTab === 'headers' || requestTab === 'params'">
                <EndpointParameterTable
                  :key="requestTab"
                  ref="parameterTableRef"
                  :model-value="activeEditorText"
                  @update:model-value="updateActiveEditor"
                />
                <div class="editor-note"><span>i</span>逐行编辑参数，点击 + 添加；支持 <code>${变量名}</code>，修改后保存接口生效。</div>
              </template>
              <template v-else-if="requestTab === 'body'">
                <div class="editor-toolbar">
                  <div v-if="requestTab === 'body'" class="body-kind-tabs">
                    <button
                      type="button"
                      :class="{ active: bodyType === 'json' }"
                      @click="selectBodyType('json')"
                      >JSON</button
                    >
                    <button
                      type="button"
                      :class="{ active: bodyType === 'data' }"
                      @click="selectBodyType('data')"
                      >x-www-form-urlencoded</button
                    >
                    <button
                      type="button"
                      :class="{ active: bodyType === 'files' }"
                      @click="selectBodyType('files')"
                      >form-data</button
                    >
                  </div>
                  <strong v-else>{{ requestTab === 'headers' ? 'Headers' : 'Params' }}</strong>
                  <div class="editor-actions"
                    ><n-button text size="small" @click="formatActiveJson"><template #icon><PhSparkle /></template>格式化</n-button
                    ><n-button text circle size="small" aria-label="复制请求内容" @click="copyActiveEditor"><template #icon><PhCopy /></template></n-button></div
                  >
                </div>
                <div class="json-editor">
                  <pre class="editor-gutter">{{ activeEditorLineNumbers }}</pre>
                  <n-input
                    :value="activeEditorText"
                    type="textarea"
                    :autosize="{ minRows: 7, maxRows: 14 }"
                    :placeholder="activeEditorPlaceholder"
                    @update:value="updateActiveEditor"
                    @click="rememberActiveEditorCursor"
                    @keyup="rememberActiveEditorCursor"
                    @select="rememberActiveEditorCursor"
                  />
                </div>
                <div class="editor-note"
                  ><span>i</span>支持静态值、项目变量和环境变量；优先使用
                  <code>${变量名}</code></div
                >
              </template>

              <section v-else-if="requestTab === 'files'" class="files-panel">
                <div class="files-panel-head"
                  ><div
                    ><strong>Form-data</strong
                    ><p>每行可选择 Text 或 File，统一以 multipart/form-data 发送</p></div
                  ><n-button secondary @click="addFormDataTextEntry">添加 Text</n-button
                  ><n-upload :show-file-list="false" :custom-request="uploadEndpointFile"
                    ><n-button type="primary" secondary>添加 File</n-button></n-upload
                  ></div
                >
                <n-empty
                  v-if="!formDataTextEntries.length && !fileEntries.length"
                  size="small"
                  description="暂无 form-data 字段，请添加 Text 或 File"
                  class="file-empty"
                />
                <div v-else class="form-data-table-head">
                  <span>字段名</span><span>类型</span><span>值</span><span>操作</span>
                </div>
                <div
                  v-for="(entry, index) in formDataTextEntries"
                  :key="`text-${index}`"
                  class="file-entry form-data-entry"
                >
                  <n-input v-model:value="entry.field" size="small" placeholder="字段名" />
                  <n-tag size="small" :bordered="false">Text</n-tag>
                  <n-input v-model:value="entry.value" size="small" placeholder="文本值，支持变量引用" />
                  <n-button text type="error" size="small" @click="formDataTextEntries.splice(index, 1)">删除</n-button>
                </div>
                <div
                  v-for="(entry, index) in fileEntries"
                  :key="`${entry.path}-${index}`"
                  class="file-entry form-data-entry"
                >
                  <n-input
                    v-model:value="entry.field"
                    size="small"
                    placeholder="文件字段名，如 file"
                  />
                  <n-tag size="small" type="info" :bordered="false">File</n-tag>
                  <span class="form-data-file-value"
                    ><span class="file-name" :title="entry.name">{{ entry.name }}</span
                    ><span class="file-size">{{ formatFileSize(entry.size) }}</span></span
                  ><n-button text type="error" size="small" @click="fileEntries.splice(index, 1)"
                    >删除</n-button
                  >
                </div>
              </section>
            </section>

            <section v-show="['extract', 'validate'].includes(requestTab)" class="response-rules-card">
              <n-tabs v-model:value="requestTab" type="line" animated class="response-rule-tabs">
                <n-tab-pane name="extract" :tab="`数据提取 ${extractRules.length}`">
                  <div class="rule-actions">
                    <span>执行成功后提取响应数据，供请求参数或断言引用。</span>
                    <n-button type="primary" secondary size="small" @click="addExtractRule">＋ 添加提取规则</n-button>
                  </div>
                  <div class="extract-rule-table">
                    <div class="extract-rule-row extract-rule-header">
                      <span>变量名</span><span>提取方式</span><span>响应来源</span><span>表达式</span><span>索引 / 捕获组</span><span></span>
                    </div>
                    <div v-for="(rule, index) in extractRules" :key="index" class="extract-rule-row">
                      <n-input v-model:value="rule.name" size="small" placeholder="变量名" @update:value="handleExtractNameInput(rule, $event)" />
                      <n-select v-model:value="rule.mode" size="small" :options="extractModeOptions" @update:value="handleExtractModeChange(rule)" />
                      <n-select v-model:value="rule.source" size="small" :options="rule.mode === 'jsonpath' ? jsonPathSourceOptions : extractSourceOptions" />
                      <n-auto-complete
                        v-if="rule.mode === 'jsonpath'"
                        v-model:value="rule.expression"
                        :options="responseExpressionOptions(rule)"
                        :render-label="renderResponsePathLabel"
                        :get-show="() => true"
                        blur-after-select
                        clearable
                        size="small"
                        placeholder="调试接口后可选择响应路径"
                        @select="handleResponsePathSelect(rule, $event)"
                      />
                      <n-input v-else v-model:value="rule.expression" size="small" placeholder="如 token=(.*?)&" />
                      <n-input-number v-model:value="rule.index" :min="0" :show-button="false" size="small" />
                      <n-button text type="error" size="small" @click="extractRules.splice(index, 1)">删除</n-button>
                      <ExtractProcessorEditor v-model="rule.processors" />
                    </div>
                    <n-empty v-if="!extractRules.length" size="small" description="暂无提取规则" class="rule-empty" />
                  </div>
                  <div class="rule-tip">JSONPath 示例：<code>$.data.token</code>；正则的捕获组填写 <code>1</code> 可获取括号内容，<code>0</code> 表示完整匹配。</div>
                </n-tab-pane>

                <n-tab-pane name="validate" :tab="`断言 ${validateRules.length}`">
                  <div class="rule-actions">
                    <span>实际值使用 JSONPath；期望值支持引用项目参数、动态函数及当前接口提取变量。</span>
                    <n-button type="primary" secondary size="small" @click="addValidateRule">＋ 添加断言</n-button>
                  </div>
                  <div class="validate-rule-table">
                    <div class="validate-rule-row validate-rule-header"><span>实际值</span><span>断言方式</span><span>期望值</span><span></span></div>
                    <div v-for="(rule, index) in validateRules" :key="index" class="validate-rule-row">
                      <n-auto-complete v-model:value="rule.actual" :options="assertionExpressionOptions" :render-label="renderResponsePathLabel" :get-show="() => true" blur-after-select clearable size="small" placeholder="$.data.code" />
                      <n-select v-model:value="rule.type" :options="validateTypeOptions" size="small" />
                      <n-input v-model:value="rule.expected" size="small" placeholder="期望值或 ${变量名}" />
                      <n-button text type="error" size="small" @click="validateRules.splice(index, 1)">删除</n-button>
                    </div>
                    <n-empty v-if="!validateRules.length" size="small" description="暂无断言规则" class="rule-empty" />
                  </div>
                </n-tab-pane>
              </n-tabs>
            </section>

            <section v-if="dataDrivenEnabled" class="data-drive-card">
              <div class="data-drive-title"
                ><div><h2>数据驱动</h2><p>每行数据独立执行并生成单独结果</p></div
                ><div class="dataset-tools"><input ref="datasetInput" type="file" accept=".csv,.json,text/csv,application/json" hidden @change="importDataset" /><n-button size="small" :loading="importingDataset" @click="datasetInput?.click()">导入 CSV / JSON</n-button><span>{{ datasetFilename }}</span></div></div>
              <div v-if="dataDrivenEnabled" class="data-drive-content">
                <label class="data-drive-field-label"
                  ><span>字段名（英文逗号分隔）</span
                  ><n-input
                    v-model:value="dataDriveFieldsText"
                    size="small"
                    placeholder="email, password, expectedCode"
                    @blur="syncDataDriveFields"
                /></label>
                <div v-if="dataDriveFields.length" class="data-drive-table-wrap">
                  <div class="data-drive-table">
                    <div class="data-drive-row data-drive-header" :style="dataDriveGridStyle"
                      ><span>启用</span
                      ><span v-for="field in dataDriveFields" :key="field">{{ field }}</span
                      ><span>操作</span></div
                    >
                    <div
                      v-for="(row, rowIndex) in dataDriveRows"
                      :key="rowIndex"
                      class="data-drive-row"
                      :style="dataDriveGridStyle"
                      ><n-checkbox :checked="!disabledRows.includes(rowIndex)" @update:checked="toggleDataRow(rowIndex, $event)">{{ rowIndex + 1 }}</n-checkbox>
                      ><n-input
                        v-for="(_, columnIndex) in dataDriveFields"
                        :key="columnIndex"
                        v-model:value="row[columnIndex]"
                        size="small"
                        :placeholder="dataDriveFields[columnIndex]"
                      /><div class="data-drive-actions"
                        ><n-button
                          text
                          type="primary"
                          size="small"
                          circle
                          :aria-label="`复制第 ${rowIndex + 1} 行数据`"
                          title="复制数据"
                          @click="copyDataDriveRow(rowIndex)"
                          ><template #icon><PhCopy /></template></n-button
                        ><n-button
                          text
                          type="error"
                          size="small"
                          @click="removeDataRow(rowIndex)"
                          >删除</n-button
                        ></div
                      ></div
                    >
                  </div>
                  <n-button dashed block class="add-data-row" @click="addDataDriveRow"
                    >＋ 添加一行数据</n-button
                  >
                </div>
                <n-alert v-else type="warning" :show-icon="false" class="data-drive-warning"
                  >请先输入字段名，多个字段使用英文逗号分隔。</n-alert
                >
<div class="dataset-bindings"><h3>字段绑定</h3><p>数据列可绑定到请求字段；预期值请在断言中使用 <code>$ddt{expected_code}</code>。</p><div v-for="field in dataDriveFields" :key="field" class="binding-row"><code>{{ field }}</code><n-select :value="bindings[field]?.section || null" :options="bindingSections" placeholder="仅作为变量" clearable @update:value="setBinding(field, 'section', $event)" /><n-input :value="bindings[field]?.path || ''" placeholder="字段路径，如 user.email" @update:value="setBinding(field, 'path', $event)" /><n-button size="small" text @click="insertDatasetVariable(field)">引用</n-button></div></div>
              </div>
            </section>
<section class="inline-response">
<header class="response-heading"><h2>响应结果</h2><n-tag v-if="debugResult" :type="debugResult.passed ? 'success' : 'error'">{{ debugResult.status_code || (debugResult.passed ? '通过' : '失败') }}</n-tag><span v-if="debugResult">{{ debugResult.duration_ms }} ms</span><span v-if="debugResult">{{ responseSize }}</span><div class="response-heading-actions"><n-button text circle aria-label="复制响应内容" :disabled="!debugResult" @click="copyResponse"><template #icon><PhCopy /></template></n-button><n-button text circle aria-label="放大响应结果" @click="debugDialogVisible = true"><template #icon><PhArrowsOut /></template></n-button></div></header>
<n-spin :show="debugRunning"><div v-if="batchResults.length" class="batch-results"><div class="batch-summary">数据集执行：{{ batchResults.length }} / {{ batchTotal }} 行 · 通过 {{ batchResults.filter(r => r.result.passed).length }} 行</div><button v-for="(row, index) in batchResults" :key="row.row" :class="{ selected: selectedBatchRow === index }" @click="selectBatchRow(index)"><span>数据 {{ row.row + 1 }}</span><strong :class="row.result.passed ? 'passed' : 'failed'">{{ row.result.passed ? '通过' : '失败' }}</strong><span>{{ row.result.duration_ms || 0 }} ms</span></button></div>
<n-tabs v-model:value="resultTab" type="line"><n-tab-pane name="body" tab="响应体"><pre v-if="debugResult" class="response-code">{{ prettyResult(debugResult.response_json ?? debugResult.response_body) }}</pre><n-empty v-else description="发送请求后，响应结果将在这里展示" /></n-tab-pane><n-tab-pane name="headers" tab="响应头"><pre class="response-code">{{ prettyResult(debugResult?.response_headers) }}</pre></n-tab-pane><n-tab-pane name="assertions" tab="断言结果"><pre class="response-code">{{ prettyResult(debugResult?.assertions) }}</pre></n-tab-pane><n-tab-pane name="extracted" tab="提取结果"><pre class="response-code">{{ prettyResult(debugResult?.extracted) }}</pre></n-tab-pane><n-tab-pane name="request" tab="实际请求"><pre class="response-code">{{ prettyResult(debugResult?.request) }}</pre></n-tab-pane></n-tabs>
<n-alert v-if="debugResult?.errors?.length" type="error">{{ debugResult.errors.join('；') }}</n-alert>
</n-spin></section>
          </main>

          <aside class="workspace-sidebar">
            <section class="side-card variables-card">
              <header class="variable-card-header">
                <h2>可用变量</h2>
                <button type="button" class="variable-collapse-button" :aria-label="variablesCollapsed ? '展开可用变量' : '收起可用变量'" @click="variablesCollapsed = !variablesCollapsed">
                  <PhCaretUp :class="{ collapsed: variablesCollapsed }" />
                </button>
              </header>
              <div v-show="!variablesCollapsed" class="variable-card-content">
                <n-input v-model:value="variableSearch" clearable class="variable-search" placeholder="搜索变量名或来源">
                  <template #prefix><PhMagnifyingGlass /></template>
                </n-input>
                <div class="variable-tabs" role="tablist" aria-label="变量分类">
                  <button v-for="tab in variableTabs" :key="tab.key" type="button" role="tab" :aria-selected="variableCategory === tab.key" :class="{ active: variableCategory === tab.key }" @click="variableCategory = tab.key">
                    <span>{{ tab.label }}</span><b>{{ tab.count }}</b>
                  </button>
                </div>
                <div v-if="filteredVariableGroups.length" class="variable-groups">
                  <section v-for="group in filteredVariableGroups" :key="group.key" class="variable-group" :class="`is-${group.key}`">
                    <header><div><PhCircle weight="fill" /><strong>{{ group.label }}</strong><PhCircle weight="fill" /><span>{{ group.detail }}</span></div><b>{{ group.items.length }}</b></header>
                    <div class="variable-rows">
                      <div v-for="variable in group.items" :key="variable.key" class="variable-row">
                        <code>{{ variable.reference }}</code>
                        <span v-if="variable.category === 'project'" class="variable-value" :title="variableDisplayValue(variable)">
                          {{ variableDisplayValue(variable) }}
                          <button v-if="variable.sensitive" type="button" class="variable-eye-button" @click="toggleVariableVisibility(variable.key)">
                            <PhEyeSlash v-if="revealedVariableKeys.has(variable.key)" /><PhEye v-else />
                          </button>
                        </span>
                        <span class="variable-actions"><button type="button" class="variable-copy-button" aria-label="复制变量" title="复制变量" @click="copyVariable(variable)"><PhCopy /></button><button type="button" @click="referenceVariable(variable)">引用</button></span>
                      </div>
                    </div>
                  </section>
                </div>
                <div v-else class="variable-empty"><PhPackage /><span>{{ variableSearch ? '没有匹配的可用变量' : '暂无项目参数或动态函数' }}</span></div>
              </div>
            </section>
          </aside>
        </div>
      </n-form>

      <n-modal
        v-model:show="debugDialogVisible"
        preset="card"
        title="响应结果"
        class="endpoint-debug-modal"
        style="width: min(1440px, calc(100vw - 48px)); height: calc(100vh - 48px); margin: 0 auto"
        :mask-closable="!debugRunning"
      >
        <div class="debug-toolbar">
          <div class="debug-environment-control">
            <span>执行环境</span>
            <n-select
              v-model:value="debugEnvironmentId"
              :options="debugEnvironmentOptions"
              :disabled="debugRunning"
              placeholder="请选择执行环境"
            />
          </div>
          <div class="debug-toolbar-actions">
            <n-button secondary :disabled="!debugResult" @click="copyResponse">复制响应</n-button>
            <n-button
              type="primary"
              :loading="debugRunning"
              :disabled="!debugEnvironmentId"
              @click="executeDebug()"
              >重新执行</n-button
            >
          </div>
        </div>

        <n-spin :show="debugRunning">
          <div v-if="debugResult" class="debug-result">
            <div class="debug-summary">
              <n-tag :type="debugResult.passed ? 'success' : 'error'" :bordered="false">
                {{ debugResult.passed ? '执行成功' : '执行失败' }}
              </n-tag>
              <span class="debug-metric"><small>执行环境</small><strong>{{ debugResult.environment || debugEnvironmentName }}</strong></span>
              <span class="debug-metric"><small>状态码</small><strong>{{ debugResult.status_code ?? '—' }}</strong></span>
              <span class="debug-metric"><small>耗时</small><strong>{{ debugResult.duration_ms ?? 0 }} ms</strong></span>
              <span class="debug-metric"><small>响应大小</small><strong>{{ responseSize }}</strong></span>
              <span v-if="debugAttemptCount" class="debug-metric"><small>请求次数</small><strong>{{ debugAttemptCount }}</strong></span>
            </div>
            <n-alert
              v-if="debugResult.errors?.length"
              type="error"
              :show-icon="true"
              class="debug-errors"
            >
              <div v-for="(error, index) in debugResult.errors" :key="index">{{ error }}</div>
            </n-alert>
            <section class="debug-response">
              <n-tabs v-model:value="resultTab" type="line" animated class="debug-result-tabs">
                <n-tab-pane name="body" tab="响应体">
                  <pre class="debug-response-code">{{ prettyResult(debugResult.response_json ?? debugResult.response_body) }}</pre>
                </n-tab-pane>
                <n-tab-pane name="headers" tab="响应头">
                  <pre class="debug-response-code">{{ prettyResult(debugResult.response_headers) }}</pre>
                </n-tab-pane>
                <n-tab-pane name="assertions" tab="断言结果">
                  <pre class="debug-response-code">{{ prettyResult(debugResult.assertions) }}</pre>
                </n-tab-pane>
                <n-tab-pane name="extracted" tab="提取结果">
                  <pre class="debug-response-code">{{ prettyResult(debugResult.extracted) }}</pre>
                </n-tab-pane>
                <n-tab-pane name="request" tab="实际请求">
                  <pre class="debug-response-code">{{ prettyResult(debugResult.request) }}</pre>
                </n-tab-pane>
              </n-tabs>
            </section>
          </div>
          <n-empty v-else-if="!debugRunning" description="暂无执行结果" />
        </n-spin>
      </n-modal>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { asList } from '@/utils/list';

  import { computed, h, ref, reactive, onMounted, watch } from 'vue';
  import { FormRules, useMessage } from 'naive-ui';
  import { useRoute, useRouter } from 'vue-router';
  import { PhArrowsOut, PhBracketsCurly, PhCaretDown, PhCaretUp, PhCircle, PhCopy, PhEye, PhEyeSlash, PhFolderSimple, PhMagnifyingGlass, PhPackage, PhPaperclip, PhPencilSimple, PhPlay, PhQuestion, PhSparkle, PhStack } from '@phosphor-icons/vue';
  import { useSubmitRedirect } from '@/hooks/web/useSubmitRedirect';
  import { DynamicFunctionAPI, EnvironmentAPI, ModuleAPI, ProjectAPI, ProjectVariableAPI } from '@/api/project/http';
  import { Environment, ProjectVariable } from '@/api/project/models';
  import { EndpointAPI } from '@/api/case_api/http';
  import { Endpoint, EndpointRunResult, UploadedEndpointFile } from '@/api/case_api/models';
  import ExtractProcessorEditor from './components/ExtractProcessorEditor.vue';
  import EndpointParameterTable from './components/EndpointParameterTable.vue';
  import { defaultExtractRule, extractRuleFromConfig, extractRuleToConfig, type ExtractRule } from './extract-processors';

  // 组件名需与路由名一致，供多页签 KeepAlive 精确缓存每个接口详情实例。
  defineOptions({ name: 'case_api_endpoint_edit' });

  const route = useRoute();
  const router = useRouter();
  const { redirectAfterSubmit } = useSubmitRedirect();

  // 路由未携带 id 或携带非法值时按新增接口处理，避免请求 /endpoint/NaN/。
  const routeId = Number(route.params.id);
  const dataID = Number.isInteger(routeId) && routeId > 0 ? routeId : 0;
  const endpointId = ref(dataID);

  const api = new EndpointAPI();
  const moduleApi = new ModuleAPI();
  const project_api = new ProjectAPI();
  const projectVariableApi = new ProjectVariableAPI();
  const dynamicFunctionApi = new DynamicFunctionAPI();
  const environmentApi = new EnvironmentAPI();

  const formRef: any = ref(null);
  const titleInputRef: any = ref(null);
  const message = useMessage();
  type RequestTab = 'headers' | 'params' | 'body' | 'files' | 'extract' | 'validate';
  type JsonField = 'headers' | 'params' | 'data' | 'json';
  const requestTab = ref<RequestTab>('body');
  const parameterTableRef = ref<InstanceType<typeof EndpointParameterTable> | null>(null);
  const bodyType = ref<'json' | 'data' | 'files'>('json');
  const submitMode = ref<'save' | 'debug' | null>(null);
  const debugDialogVisible = ref(false);
  const debugRunning = ref(false);
  const debugEnvironmentId = ref<number | null>(null);
  const debugEnvironmentOptions = ref<Array<{ label: string; value: number }>>([]);
  const debugEnvironments = ref<Environment[]>([]);
  const debugResult = ref<EndpointRunResult | null>(null);
  type ValidateRule = { type: 'equals' | 'not_equals' | 'greater_than' | 'less_than' | 'contains'; actual: string; expected: string };
  type VariableCategory = 'project' | 'function' | 'dataset';
  type VariableItem = { key: string; name: string; reference: string; category: VariableCategory; value: string; source: string; sensitive?: boolean };
  const responseRuleTab = ref<'extract' | 'validate'>('extract');
  const extractRules = ref<ExtractRule[]>([]);
  const validateRules = ref<ValidateRule[]>([]);
  const dynamicFunctions = ref<any[]>([]);
  const variableSearch = ref('');
  const variableCategory = ref<'all' | VariableCategory>('all');
  const variablesCollapsed = ref(false);
  const revealedVariableKeys = ref(new Set<string>());
  const activeEditorCursor = ref<{ field: JsonField; start: number; end: number } | null>(null);
  const debugEnvironmentName = computed(
    () => debugEnvironments.value.find((item) => item.id === debugEnvironmentId.value)?.name || '—'
  );
  const methodOptions = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((value) => ({
    label: value,
    value,
  }));
  const renderMethodOption = (option: any) => h(
    'span',
    { class: ['request-method-option', `method-${String(option.value || 'get').toLowerCase()}`] },
    String(option.label || option.value || '')
  );

  const rules: FormRules = {
    project: {
      required: true,
      type: 'number',
      message: '请选择项目',
      trigger: 'blur',
    },
    module: {
      required: true,
      type: 'number',
      message: '请选择所属模块',
      trigger: 'blur',
    },
    name: {
      required: true,
      message: '请选择输入接口名称',
      trigger: 'blur',
    },
    method: {
      required: true,
      message: '请选择输入请求方法',
      trigger: 'blur',
    },
    url: {
      required: true,
      message: '请选择输入接口地址',
      trigger: 'blur',
    },
    test_headers: {
      trigger: 'input',
      validator(rule: unknown, value: string) {
        if (value.length >= 5) return new Error('最多输入四个字符');
        return true;
      },
    },
  };

  function createDefaultValue() {
    return {
      id: -1,
      project: null,
      module: null,
      name: '',
      method: 'GET',
      url: '',
      headers: {},
      params: {},
      data: {},
      json: {},
      body_type: 'json' as const,
      files: {},
      parametrize: [],
      dataset_options: {} as NonNullable<Endpoint['dataset_options']>,
      extract: {},
      validate: {},
    };
  }

  const project_list = ref<any[]>([]);
  const module_list = ref<any[]>([]);
  const projectVariables = ref<ProjectVariable[]>([]);
  const formValue = reactive(createDefaultValue());
  const fileEntries = ref<Array<UploadedEndpointFile & { field: string }>>([]);
  const formDataTextEntries = ref<Array<{ field: string; value: string }>>([]);
  const dataDrivenEnabled = ref(false);
  const runModeOptions = [
    { label: '单次调试', key: 'single' },
    { label: '数据驱动', key: 'dataset' },
  ];
  function selectRunMode(key: string | number) {
    dataDrivenEnabled.value = key === 'dataset';
  }
  const dataDriveFieldsText = ref('');
  const dataDriveFields = ref<string[]>([]);
  const dataDriveRows = ref<string[][]>([]);
  const dataDriveGridStyle = computed(() => ({
    gridTemplateColumns: `42px repeat(${Math.max(
      dataDriveFields.value.length,
      1
    )}, minmax(130px, 1fr)) 104px`,
  }));
  const jsonText = reactive({
    headers: '{}',
    params: '{}',
    data: '{}',
    json: '{}',
  });
  const extractModeOptions = [{ label: 'JSONPath', value: 'jsonpath' }, { label: '正则（re）', value: 're' }];
  const extractSourceOptions = [{ label: 'JSON', value: 'json' }, { label: '响应文本', value: 'text' }, { label: '响应头', value: 'headers' }];
  const jsonPathSourceOptions = [{ label: 'JSON', value: 'json' }, { label: '响应头', value: 'headers' }];
  const validateTypeOptions = [
    { label: '相等', value: 'equals' }, { label: '不等于', value: 'not_equals' },
    { label: '大于', value: 'greater_than' }, { label: '小于', value: 'less_than' },
    { label: '包含', value: 'contains' },
  ];
  const requestCount = (field: JsonField) => Object.keys(formValue[field] || {}).length;
  const requestTabs = computed(() => [
    { value: 'params' as const, label: 'Params', icon: PhQuestion, count: requestCount('params') },
    { value: 'headers' as const, label: 'Headers', icon: PhStack, count: requestCount('headers') },
    { value: 'body' as const, label: 'Body', icon: PhBracketsCurly },
    { value: 'files' as const, label: '文件', icon: PhPaperclip, count: fileEntries.value.length },
    { value: 'extract' as const, label: '数据提取', icon: PhStack, count: extractRules.value.length },
    { value: 'validate' as const, label: '断言', icon: PhQuestion, count: validateRules.value.length },
  ]);
  const activeEditorField = computed<JsonField>(() =>
    requestTab.value === 'headers'
      ? 'headers'
      : requestTab.value === 'params'
      ? 'params'
      : bodyType.value === 'data'
      ? 'data'
      : 'json'
  );
  const activeEditorText = computed(() => jsonText[activeEditorField.value]);
  const activeEditorLineNumbers = computed(() =>
    Array.from(
      { length: Math.max(activeEditorText.value.split('\n').length, 1) },
      (_, index) => index + 1
    ).join('\n')
  );
  const activeEditorPlaceholder = computed(() =>
    activeEditorField.value === 'headers' || activeEditorField.value === 'params'
      ? ''
      : activeEditorField.value === 'data'
      ? '{\n  "name": "demo"\n}'
      : '{\n  "email": "admin@example.com"\n}'
  );

  
  const defaultValidateRule = (): ValidateRule => ({ type: 'equals', actual: '$.', expected: '' });
  const normalizeJsonPathExpression = (value: unknown) => String(value || '').replace(/\s+·\s+.*$/, '').trim();
  const variableNameFromJsonPath = (path: unknown) => {
    const expression = normalizeJsonPathExpression(path);
    const bracketKey = expression.match(/\[['"]([^'"]+)['"]\]$/)?.[1];
    const dotKey = expression.match(/\.([A-Za-z_$][\w$]*)$/)?.[1];
    const indexedKey = expression.match(/\.([A-Za-z_$][\w$]*)\[(\d+)\]$/);
    const rawName = bracketKey || dotKey || (indexedKey ? `${indexedKey[1]}_${indexedKey[2]}` : '');
    const normalized = rawName.replace(/[^A-Za-z0-9_]/g, '_').replace(/^_+|_+$/g, '');
    if (!normalized) return '';
    return /^\d/.test(normalized) ? `value_${normalized}` : normalized;
  };
  const toExtractRules = (extract: Record<string, unknown> = {}) => Object.entries(extract || {}).flatMap(([name, value]) => {
    const rule = extractRuleFromConfig(name, value, normalizeJsonPathExpression, variableNameFromJsonPath);
    return rule ? [rule] : [];
  });
  const toExtractConfig = (rules: ExtractRule[] = []) => rules.reduce((result: Record<string, unknown>, rule) => {
    if (!rule.name.trim() || !rule.expression.trim()) return result;
    result[rule.name.trim()] = extractRuleToConfig(rule, normalizeJsonPathExpression);
    return result;
  }, {});
  const normalizeAssertReference = (value: unknown) => {
    const reference = String(value ?? '');
    if (reference.startsWith('$')) return reference;
    if (['status_code', 'text', 'json', 'headers'].includes(reference)) return `$.${reference}`;
    return reference ? `$.variables.${reference}` : '';
  };
  const toValidateRules = (validate: Record<string, unknown> = {}) => (['equals', 'not_equals', 'greater_than', 'less_than', 'contains'] as const).flatMap((type) => {
    const expressions = validate[type];
    if (!expressions || typeof expressions !== 'object' || Array.isArray(expressions)) return [];
    return Object.entries(expressions as Record<string, unknown>).flatMap(([, value]) => Array.isArray(value) && value.length >= 2
      ? [{ type, actual: normalizeAssertReference(value[0]), expected: String(value[1] ?? '') }]
      : []);
  });
  const toValidateConfig = (rules: ValidateRule[] = []) => {
    const result: Record<ValidateRule['type'], Record<string, [string, string]>> = { equals: {}, not_equals: {}, greater_than: {}, less_than: {}, contains: {} };
    const labels = { equals: '相等', not_equals: '不等于', greater_than: '大于', less_than: '小于', contains: '包含' } as const;
    rules.forEach((rule) => {
      if (rule.actual.trim()) result[rule.type][`${rule.actual.trim()} ${labels[rule.type]} ${rule.expected}`] = [rule.actual.trim(), rule.expected];
    });
    return Object.fromEntries(Object.entries(result).filter(([, expressions]) => Object.keys(expressions).length));
  };
  function syncResponseRules() {
    extractRules.value = toExtractRules(formValue.extract as Record<string, unknown>);
    validateRules.value = toValidateRules(formValue.validate as Record<string, unknown>);
  }
  function addExtractRule() { extractRules.value.push(defaultExtractRule()); }
  function addValidateRule() { validateRules.value.push(defaultValidateRule()); }
  function handleExtractModeChange(rule: ExtractRule) { if (rule.mode === 'jsonpath' && rule.source === 'text') rule.source = 'json'; }
  function handleExtractNameInput(rule: ExtractRule, value: string) { rule.name = value; if (value.trim() !== rule.autoVariableName) rule.autoVariableName = undefined; }

  const appendJsonPath = (prefix: string, key: string) => /^[A-Za-z_$][\w$]*$/.test(key) ? `${prefix}.${key}` : `${prefix}[${JSON.stringify(key)}]`;
  const selectableResponsePaths = (value: any) => {
    const result: Array<{ path: string; value: unknown }> = [];
    const seen = new Set<string>();
    const visit = (item: any, prefix: string, depth: number, includeCurrent: boolean) => {
      if (result.length >= 240 || depth > 6) return;
      if (includeCurrent && !seen.has(prefix)) { seen.add(prefix); result.push({ path: prefix, value: item }); }
      if (Array.isArray(item)) item.slice(0, 10).forEach((child, index) => visit(child, `${prefix}[${index}]`, depth + 1, true));
      else if (item && typeof item === 'object') Object.entries(item).slice(0, 80).forEach(([key, child]) => visit(child, appendJsonPath(prefix, key), depth + 1, true));
    };
    visit(value, '$', 0, value === null || typeof value !== 'object');
    return result;
  };
  const responseValuePreview = (value: unknown) => {
    if (Array.isArray(value)) return '数组';
    if (value && typeof value === 'object') return '对象';
    const text = String(value ?? 'null').replace(/\s+/g, ' ');
    return text.length > 48 ? `${text.slice(0, 48)}…` : text;
  };
  function responseValueFor(source: ExtractRule['source']) {
    if (!debugResult.value) return undefined;
    if (source === 'headers') return debugResult.value.response_headers;
    if (source === 'json') {
      if (debugResult.value.response_json !== undefined && debugResult.value.response_json !== null) return debugResult.value.response_json;
      try { return JSON.parse(debugResult.value.response_body || ''); } catch { return undefined; }
    }
    return debugResult.value.response_body;
  }
  const pathOptions = (source: ExtractRule['source'], keyword = '') => {
    const responseValue = responseValueFor(source);
    if (responseValue === undefined || responseValue === null) return [];
    return selectableResponsePaths(responseValue)
      .map((item) => ({ label: item.path, value: item.path, preview: responseValuePreview(item.value) }))
      .filter((item) => !keyword || item.value.toLowerCase().includes(keyword) || item.preview.toLowerCase().includes(keyword));
  };
  const responseExpressionOptions = (rule: ExtractRule) => rule.mode === 'jsonpath' ? pathOptions(rule.source, rule.expression.trim().toLowerCase()) : [];
  const assertionExpressionOptions = computed(() => [
    { label: '$.status_code', value: '$.status_code', preview: String(debugResult.value?.status_code ?? '状态码') },
    ...pathOptions('json'),
  ]);
  const renderResponsePathLabel = (option: any) => h('span', { class: 'response-path-option' }, [h('code', option.value), h('span', `· ${option.preview || ''}`)]);
  function handleResponsePathSelect(rule: ExtractRule, selectedPath: string) {
    const nextAutoName = variableNameFromJsonPath(selectedPath);
    if (nextAutoName && (!rule.name.trim() || rule.name.trim() === rule.autoVariableName)) { rule.name = nextAutoName; rule.autoVariableName = nextAutoName; }
  }

  function normalizeEndpoint(data?: Partial<Endpoint>) {
    const defaults = createDefaultValue();
    return {
      ...defaults,
      ...data,
      headers: data?.headers || defaults.headers,
      params: data?.params || defaults.params,
      data: data?.data || defaults.data,
      json: data?.json || defaults.json,
      files: data?.files || defaults.files,
      parametrize: data?.parametrize || defaults.parametrize,
    };
  }

  async function formSubmit(runAfterSave = false) {
    if (submitMode.value) return;
    submitMode.value = runAfterSave ? 'debug' : 'save';
    try {
      await formRef.value.validate();
      let data: Endpoint;
      try {
        // 请求体以当前选择的类型为准，避免 data 与 json 同时发送造成语义不明确。
        data = {
          ...formValue,
          data:
            bodyType.value === 'files'
              ? serializeFormDataText()
              : bodyType.value === 'data'
              ? parseJson(jsonText.data, '表单参数')
              : {},
          json: bodyType.value === 'json' ? parseJson(jsonText.json, 'JSON 请求体') : {},
          body_type: bodyType.value === 'files' ? 'form_data' : bodyType.value,
          headers: parseJson(jsonText.headers, '请求头'),
          params: parseJson(jsonText.params, '查询参数'),
          cookies: {},
          files: serializeFiles(),
          parametrize: serializeDataDrive(),
          dataset_options: { enabled: dataDrivenEnabled.value, disabled_rows: disabledRows.value, bindings: bindings.value, filename: datasetFilename.value },
          extract: toExtractConfig(extractRules.value),
          validate: toValidateConfig(validateRules.value),
        } as Endpoint;
      } catch (error: any) {
        message.error(error.message);
        return;
      }

      applyBindings(data);
      const isCreate = endpointId.value === 0;
      const saved = isCreate
        ? await api.createData(data as Endpoint)
        : await api.update(endpointId.value, data as Endpoint);
      const savedId = Number((saved as Endpoint)?.id || endpointId.value);
      if (!savedId) throw new Error('接口保存成功，但未获取到接口 ID。');
      endpointId.value = savedId;
      Object.assign(formValue, normalizeEndpoint(saved || { ...data, id: savedId }));

      if (isCreate) {
        await router.replace({
          name: 'case_api_endpoint_edit',
          params: { id: savedId },
        });
      }

      if (runAfterSave) {
        await prepareDebugRun(savedId, Number(formValue.project));
      } else {
        message.success('保存成功');
        await loadDirectory();
      }
    } catch (error: any) {
      if (Array.isArray(error)) message.error('验证失败，请填写完整信息');
      else message.error(error?.message || '保存接口失败');
    } finally {
      submitMode.value = null;
    }
  }

  async function prepareDebugRun(savedId: number, projectId: number) {
    if (!projectId) throw new Error('接口未关联有效项目，无法执行。');
    const response: any = await environmentApi.getDataList({ project: projectId, pageSize: 999 });
    setDebugEnvironments(response);
    if (!debugEnvironments.value.length) throw new Error('当前项目尚未配置执行环境。');

    if (!debugEnvironmentId.value) {
      const preferred = debugEnvironments.value.find((item) => item.name === 'Dev') || debugEnvironments.value[0];
      debugEnvironmentId.value = Number(preferred.id);
    }
    debugDialogVisible.value = false;
    await executeDebug(savedId);
  }

  async function executeDebug(savedId: number = endpointId.value) {
    const targetEndpointId = Number(savedId);
    if (!Number.isInteger(targetEndpointId) || targetEndpointId <= 0) {
      message.error('未获取到有效的接口 ID，无法执行。');
      return;
    }
    if (!debugEnvironmentId.value || debugRunning.value) return;
    debugRunning.value = true;
    debugResult.value = null;
    try {
      batchResults.value = []; selectedBatchRow.value = 0;
      if (dataDrivenEnabled.value) {
        const indices = dataDriveRows.value.map((_, i) => i).filter(i => !disabledRows.value.includes(i));
        batchTotal.value = indices.length;
        for (const row of indices) {
          let result: EndpointRunResult;
          try { result = await api.runById(targetEndpointId, debugEnvironmentId.value, row); }
          catch (error: any) { result = { environment: debugEnvironmentName.value, passed: false, errors: [error?.message || '执行失败'] }; }
          batchResults.value.push({ row, result });
          if (batchResults.value.length === 1) debugResult.value = result;
        }
        if (batchResults.value.some(r => !r.result.passed)) message.warning('数据集执行完成，存在失败行');
        else message.success('数据集全部执行通过');
      } else {
        debugResult.value = await api.runById(targetEndpointId, debugEnvironmentId.value);
        if (debugResult.value?.passed) message.success('接口执行成功');
        else message.error('接口执行失败');
      }
    } catch (error: any) {
      debugResult.value = {
        environment: debugEnvironmentName.value,
        passed: false,
        errors: [error?.message || '接口执行失败'],
        response_body: '',
      };
    } finally {
      debugRunning.value = false;
    }
  }

  function back() {
    router.push({ name: 'case_api_endpoint' });
  }

  async function get_data_by_api() {
    // 加载项目列表
    const project_by_api = await project_api.getDataList({});
    project_list.value = project_by_api.map((project) => {
      return { label: project.name, value: project.id };
    });

    if (dataID == 0) {
      Object.assign(formValue, normalizeEndpoint());
      const projectId = Number(route.query.project);
      const moduleId = Number(route.query.module);
      if (Number.isInteger(projectId) && projectId > 0) {
        formValue.project = projectId;
        await loadModuleOptions(projectId);
        if (module_list.value.some((module) => module.value === moduleId))
          formValue.module = moduleId;
      }
    } else {
      const data_by_api = await api.getDataByID(dataID); // 修改默认值
      Object.assign(formValue, normalizeEndpoint(data_by_api));
      if (formValue.project) await loadModuleOptions(formValue.project);
    }
    syncJsonText();
    syncResponseRules();
    if (formValue.project) await Promise.all([
      loadProjectVariables(Number(formValue.project)),
      loadDynamicFunctions(Number(formValue.project)),
    ]);
  }

  async function loadModuleOptions(projectId: number) {
    const data = await moduleApi.getDataList({ project: projectId, pageSize: 999 });
    const modules = Array.isArray(data) ? data : data?.list || data?.results || [];
    module_list.value = modules.map((module: any) => ({ label: module.name, value: module.id }));
  }

  async function handleProjectChange(projectId: number) {
    formValue.module = null;
    module_list.value = [];
    projectVariables.value = [];
    dynamicFunctions.value = [];
    if (projectId)
      await Promise.all([loadModuleOptions(projectId), loadProjectVariables(projectId), loadDynamicFunctions(projectId)]);
  }

  async function loadProjectVariables(projectId: number) {
    const data: any = await projectVariableApi.getDataList({ project: projectId, pageSize: 999 });
    projectVariables.value = Array.isArray(data) ? data : data?.list || data?.results || [];
  }

  async function loadDynamicFunctions(projectId: number) {
    const data: any = await dynamicFunctionApi.getDataList({ projects: String(projectId), page: 1, pageSize: 999 });
    dynamicFunctions.value = asList(data).filter((item: any) => item.enabled !== false);
  }

  function formatJson(value: unknown) {
    return JSON.stringify(value || {}, null, 2);
  }

  function syncJsonText() {
    jsonText.headers = formatJson(formValue.headers);
    jsonText.params = formatJson(formValue.params);
    jsonText.data = formatJson(formValue.data);
    jsonText.json = formatJson(formValue.json);
    fileEntries.value = Object.entries(formValue.files || {}).flatMap(([field, entries]) =>
      (Array.isArray(entries) ? entries : []).map((entry) => ({ ...entry, field }))
    );
    formDataTextEntries.value = Object.entries(formValue.data || {}).map(([field, value]) => ({
      field,
      value: typeof value === 'string' ? value : JSON.stringify(value),
    }));
    const parametrize = Array.isArray(formValue.parametrize) ? formValue.parametrize : [];
    // 打开详情默认进入单次调试；已有数据集仍完整保留，选择“数据驱动”后即可继续使用。
    dataDrivenEnabled.value = false;
    disabledRows.value = formValue.dataset_options?.disabled_rows || [];
    bindings.value = formValue.dataset_options?.bindings || {};
    datasetFilename.value = formValue.dataset_options?.filename || '';
    dataDriveFields.value =
      Array.isArray(parametrize[0])
        ? parametrize[0].map((field) => String(field).trim()).filter(Boolean)
        : [];
    dataDriveFieldsText.value = dataDriveFields.value.join(', ');
    dataDriveRows.value = parametrize.length >= 2
      ? parametrize
          .slice(1)
          .filter((row) => Array.isArray(row))
          .map((row) => row.map(encodeCell))
      : [];
    bodyType.value =
      formValue.body_type === 'form_data' || fileEntries.value.length > 0
        ? 'files'
        : formValue.body_type === 'data' ||
          (Object.keys(formValue.data || {}).length > 0 &&
          Object.keys(formValue.json || {}).length === 0)
        ? 'data'
        : 'json';
    requestTab.value =
      bodyType.value === 'files'
        ? 'files'
        : Object.keys(formValue.params || {}).length > 0 &&
          Object.keys(formValue.json || {}).length === 0 &&
          Object.keys(formValue.data || {}).length === 0
        ? 'params'
        : 'body';
  }

  function selectRequestTab(tab: RequestTab) {
    requestTab.value = tab;
    if (tab === 'files') bodyType.value = 'files';
    else if (tab === 'body' && bodyType.value === 'files') bodyType.value = 'json';
  }

  function selectBodyType(type: 'json' | 'data' | 'files') {
    bodyType.value = type;
    requestTab.value = type === 'files' ? 'files' : 'body';
  }

  function updateActiveEditor(value: string) {
    const field = activeEditorField.value;
    jsonText[field] = value;
    updateJsonField(field, value);
  }

  function formatActiveJson() {
    const field = activeEditorField.value;
    try {
      jsonText[field] = JSON.stringify(parseJson(jsonText[field], '当前参数'), null, 2);
      updateJsonField(field, jsonText[field]);
    } catch (error: any) {
      message.error(error.message);
    }
  }

  function variableReference(name: string) {
    return `\${${name}}`;
  }

  const variableItems = computed<VariableItem[]>(() => {
    const projectItems = projectVariables.value.filter((variable) => String(variable.name || '').trim()).map((variable) => {
      const name = String(variable.name).trim();
      return {
        key: `project-${variable.id || name}`, name, reference: variableReference(name), category: 'project' as const,
        value: String(variable.value ?? ''), source: `项目参数${(variable as any).project_name ? ` · ${(variable as any).project_name}` : ''}${(variable as any).description ? ` · ${(variable as any).description}` : ''}`,
        sensitive: /(?:secret|password|passwd|token|credential|private[_-]?key|api[_-]?key)/i.test(name),
      };
    });
    const names = new Set<string>();
    const functionItems = dynamicFunctions.value.flatMap((item: any) => asList(item.function_names).flatMap((rawName: any) => {
      const name = String(rawName || '').trim();
      if (!name || names.has(name)) return [];
      names.add(name);
      return [{ key: `function-${item.id || 'custom'}-${name}`, name, reference: `\${${name}()}`, category: 'function' as const, value: '', source: '动态函数' }];
    }));
    const datasetItems = dataDrivenEnabled.value ? dataDriveFields.value.map(name => ({ key: 'dataset-' + name, name, reference: '$ddt{' + name + '}', category: 'dataset' as const, value: '', source: '数据集参数' })) : [];
    return [...projectItems, ...functionItems, ...datasetItems];
  });
  const variableTabs = computed(() => {
    const count = (category?: VariableCategory) => category ? variableItems.value.filter((item) => item.category === category).length : variableItems.value.length;
    return [{ key: 'all' as const, label: '全部', count: count() }, { key: 'project' as const, label: '项目参数', count: count('project') }, { key: 'function' as const, label: '动态函数', count: count('function') }, ...(dataDrivenEnabled.value ? [{ key: 'dataset' as const, label: '数据集', count: count('dataset') }] : [])];
  });
  const filteredVariableGroups = computed(() => {
    const keyword = variableSearch.value.trim().toLowerCase();
    const items = variableItems.value.filter((item) => {
      if (variableCategory.value !== 'all' && item.category !== variableCategory.value) return false;
      return !keyword || [item.name, item.reference, item.value, item.source].some((value) => String(value).toLowerCase().includes(keyword));
    });
    const projectName = project_list.value.find((item) => item.value === formValue.project)?.label || '当前项目';
    return [
      { key: 'project' as const, label: '项目参数', detail: `项目：${projectName}`, items: items.filter((item) => item.category === 'project') },
      { key: 'function' as const, label: '动态函数', detail: '函数', items: items.filter((item) => item.category === 'function') },
      { key: 'dataset' as const, label: '数据集参数', detail: '逐行取值', items: items.filter(item => item.category === 'dataset') },
    ].filter((group) => group.items.length);
  });
  function variableDisplayValue(variable: VariableItem) {
    if (variable.sensitive && !revealedVariableKeys.value.has(variable.key)) return '******';
    return variable.value || '-';
  }
  function toggleVariableVisibility(key: string) {
    const next = new Set(revealedVariableKeys.value);
    if (next.has(key)) next.delete(key); else next.add(key);
    revealedVariableKeys.value = next;
  }
  async function copyVariable(variable: VariableItem, notify = true) {
    try {
      await navigator.clipboard.writeText(variable.reference);
      if (notify) message.success(`已复制 ${variable.reference}`);
      return true;
    } catch {
      message.error('复制失败，请手动选择变量表达式');
      return false;
    }
  }
  function rememberActiveEditorCursor(event: Event) {
    const target = event.target as HTMLTextAreaElement | null;
    if (!target || typeof target.selectionStart !== 'number') return;
    activeEditorCursor.value = { field: activeEditorField.value, start: target.selectionStart, end: target.selectionEnd };
  }
  async function referenceVariable(variable: VariableItem) {
    if ((requestTab.value === 'headers' || requestTab.value === 'params') && parameterTableRef.value) {
      parameterTableRef.value.insertVariable(variable.reference);
      message.success(`已引用 ${variable.reference}`);
      return;
    }
    const cursor = activeEditorCursor.value;
    if (!cursor) {
      if (await copyVariable(variable, false)) message.info('已复制变量，请在请求参数中粘贴');
      return;
    }
    const current = jsonText[cursor.field] || '';
    const start = Math.min(cursor.start, current.length);
    const end = Math.min(cursor.end, current.length);
    jsonText[cursor.field] = `${current.slice(0, start)}${variable.reference}${current.slice(end)}`;
    activeEditorCursor.value = { field: cursor.field, start: start + variable.reference.length, end: start + variable.reference.length };
    updateJsonField(cursor.field, jsonText[cursor.field]);
    message.success(`已引用 ${variable.reference}`);
  }

  function updateJsonField(field: 'headers' | 'params' | 'data' | 'json', value: string) {
    try {
      formValue[field] = value.trim() ? JSON.parse(value) : {};
    } catch {
      // 输入尚未形成完整 JSON 时保留原值，避免编辑过程破坏表单。
    }
  }

  function parseJson(value: string, fieldName: string) {
    try {
      const result = value.trim() ? JSON.parse(value) : {};
      if (!result || Array.isArray(result) || typeof result !== 'object') {
        throw new Error();
      }
      return result;
    } catch {
      throw new Error(`${fieldName}必须填写合法的 JSON 对象。`);
    }
  }

  function focusEndpointTitle() {
    titleInputRef.value?.focus?.();
  }

  async function copyActiveEditor() {
    try {
      await navigator.clipboard.writeText(activeEditorText.value);
      message.success('请求内容已复制');
    } catch {
      message.error('复制失败，请手动选择内容');
    }
  }

  async function copyResponse() {
    if (!debugResult.value) return;
    try {
      await navigator.clipboard.writeText(prettyResult(debugResult.value.response_json ?? debugResult.value.response_body));
      message.success('响应内容已复制');
    } catch {
      message.error('复制失败，请手动选择内容');
    }
  }

  function serializeFiles(): Record<string, UploadedEndpointFile[]> {
    return fileEntries.value.reduce((result: Record<string, UploadedEndpointFile[]>, entry) => {
      const field = entry.field.trim();
      if (!field) return result;
      (result[field] ||= []).push({ name: entry.name, path: entry.path, size: entry.size });
      return result;
    }, {});
  }

  function addFormDataTextEntry() {
    formDataTextEntries.value.push({ field: '', value: '' });
  }

  function serializeFormDataText(): Record<string, string> {
    const result: Record<string, string> = {};
    for (const entry of formDataTextEntries.value) {
      const field = entry.field.trim();
      if (!field && entry.value) throw new Error('Form-data Text 字段名不能为空。');
      if (!field) continue;
      if (Object.prototype.hasOwnProperty.call(result, field))
        throw new Error(`Form-data Text 字段名「${field}」重复。`);
      result[field] = entry.value;
    }
    return result;
  }

  function syncDataDriveFields() {
    const nextFields = dataDriveFieldsText.value
      .split(/[,，、]/)
      .map((field) => field.trim())
      .filter(Boolean);
    if (new Set(nextFields).size !== nextFields.length) {
      message.warning('数据驱动字段名不能重复。');
      return;
    }
    const previousFields = dataDriveFields.value;
    dataDriveRows.value = dataDriveRows.value.map((row) =>
      nextFields.map((field) => {
        const oldIndex = previousFields.indexOf(field);
        return oldIndex >= 0 ? row[oldIndex] || '' : '';
      })
    );
    dataDriveFields.value = nextFields;
    dataDriveFieldsText.value = nextFields.join(', ');
  }

  function addDataDriveRow() {
    if (!dataDriveFields.value.length) {
      message.warning('请先输入数据驱动字段名。');
      return;
    }
    dataDriveRows.value.push(dataDriveFields.value.map(() => ''));
  }

  function copyDataDriveRow(rowIndex: number) {
    const sourceRow = dataDriveRows.value[rowIndex];
    if (!sourceRow) return;
    dataDriveRows.value.splice(rowIndex + 1, 0, [...sourceRow]);
    disabledRows.value = disabledRows.value.map(i => i > rowIndex ? i + 1 : i);
    message.success(`第 ${rowIndex + 1} 行已复制`);
  }

  function serializeDataDrive() {
    if (!dataDrivenEnabled.value && !dataDriveFieldsText.value.trim() && !dataDriveRows.value.length) return [];
    syncDataDriveFields();
    if (!dataDriveFields.value.length) throw new Error('启用数据驱动后请填写字段名。');
    if (!dataDriveRows.value.length) throw new Error('启用数据驱动后请至少添加一行数据。');
    if (dataDrivenEnabled.value && disabledRows.value.length >= dataDriveRows.value.length) throw new Error('请至少启用一行数据。');
    const rows = dataDriveRows.value.map((row) =>
      dataDriveFields.value.map((_, index) => decodeCell(row[index] ?? ''))
    );
    return [dataDriveFields.value, ...rows];
  }

  async function uploadEndpointFile({ file, onFinish, onError }: any) {
    try {
      const nativeFile = file.file as File | null;
      if (!nativeFile) throw new Error('未读取到待上传文件。');
      const uploaded = await api.uploadFile(nativeFile);
      fileEntries.value.push({ ...uploaded, field: 'file' });
      message.success(`文件「${uploaded.name}」上传成功`);
      onFinish();
    } catch (error: any) {
      message.error(error.message || '文件上传失败');
      onError();
    }
  }

  function formatFileSize(size?: number) {
    if (!size) return '—';
    return size < 1024 * 1024
      ? `${Math.ceil(size / 1024)} KB`
      : `${(size / 1024 / 1024).toFixed(2)} MB`;
  }

  onMounted(async () => {
    await get_data_by_api();
  });

  const datasetInput = ref<HTMLInputElement | null>(null);
  // 单元格使用 JSON 字面量保留数字、布尔、对象类型；显式双引号可保留数字字符串。
  function decodeCell(value: string): any { try { return JSON.parse(value); } catch { return value; } }
  function encodeCell(value: unknown): string {
    if (typeof value === 'string') {
      try { JSON.parse(value); return JSON.stringify(value); } catch { return value; }
    }
    return JSON.stringify(value) ?? '';
  }
  const importingDataset = ref(false);
  const datasetFilename = ref('');
  const disabledRows = ref<number[]>([]);
  const bindings = ref<Record<string, { section?: string; path?: string }>>({});
  const batchResults = ref<Array<{ row: number; result: EndpointRunResult }>>([]);
  const batchTotal = ref(0);
  const selectedBatchRow = ref(0);
  const resultTab = ref('body');
  const directorySearch = ref('');
  const directoryItems = ref<any[]>([]);
  const collapsedDirectoryGroups = ref(new Set<string>());
  const directoryGroups = computed(() => {
    const groups = new Map<string, any[]>();
    directoryItems.value.filter(item => String(item.name).toLowerCase().includes(directorySearch.value.toLowerCase())).forEach(item => {
      const name = item.module_name || '未分组'; if (!groups.has(name)) groups.set(name, []); groups.get(name)!.push(item);
    });
    return [...groups].map(([name, items]) => ({ name, items }));
  });
  function toggleDirectoryGroup(name: string) {
    const next = new Set(collapsedDirectoryGroups.value);
    next.has(name) ? next.delete(name) : next.add(name);
    collapsedDirectoryGroups.value = next;
  }
  const environmentOrder = ['Dev', 'Test', 'Pre', 'Prod'];
  function uniqueProjectEnvironments(payload: any): Environment[] {
    const items: Environment[] = (Array.isArray(payload) ? payload : payload?.list || payload?.results || [])
      .filter((item: Environment) => Number(item.project) === Number(formValue.project));
    const byName = new Map<string, Environment>();
    items.forEach((item) => {
      const key = String(item.name || '').trim().toLowerCase();
      if (key && !byName.has(key)) byName.set(key, item);
    });
    return [...byName.values()].sort((left, right) => {
      const leftIndex = environmentOrder.indexOf(left.name);
      const rightIndex = environmentOrder.indexOf(right.name);
      const leftOrder = leftIndex < 0 ? environmentOrder.length : leftIndex;
      const rightOrder = rightIndex < 0 ? environmentOrder.length : rightIndex;
      return leftOrder - rightOrder || left.name.localeCompare(right.name, 'zh-CN');
    });
  }
  function setDebugEnvironments(payload: any) {
    const previousName = debugEnvironments.value.find(
      (item) => Number(item.id) === Number(debugEnvironmentId.value),
    )?.name;
    debugEnvironments.value = uniqueProjectEnvironments(payload);
    debugEnvironmentOptions.value = debugEnvironments.value.map((item) => ({
      label: item.name,
      value: Number(item.id),
    }));
    const replacement = previousName
      ? debugEnvironments.value.find((item) => item.name === previousName)
      : undefined;
    if (!debugEnvironmentOptions.value.some((item) => item.value === debugEnvironmentId.value)) {
      debugEnvironmentId.value = Number(replacement?.id || debugEnvironmentOptions.value[0]?.value) || null;
    }
  }
  async function loadDirectory() {
    if (!formValue.project) return;
    const result: any = await api.getDataList({ project: formValue.project, pageSize: 999 });
    directoryItems.value = Array.isArray(result) ? result : result?.list || result?.results || [];
    const env: any = await environmentApi.getDataList({ project: formValue.project, pageSize: 999 });
    setDebugEnvironments(env);
  }
  async function switchEndpoint(item: any) {
    if (debugRunning.value || submitMode.value) return;
    await router.push({ name: 'case_api_endpoint_edit', params: { id: item.id } });
  }
  watch(() => formValue.project, () => { void loadDirectory().catch(() => message.warning('接口目录或环境加载失败，请刷新重试')); });
  const bindingSections = [{ label: 'Headers', value: 'headers' }, { label: 'Params', value: 'params' }, { label: 'Body · JSON', value: 'json' }, { label: 'Body · Data', value: 'data' }];
  function setBinding(field: string, key: string, value: string | null) {
    bindings.value[field] = { ...bindings.value[field], [key]: value || '' };
  }
  function applyBindings(data: Endpoint) {
    for (const [field, binding] of Object.entries(bindings.value)) {
      if (!dataDrivenEnabled.value || !binding.section || !binding.path) continue;
      if (!dataDriveFields.value.includes(field)) continue;
      const path = binding.path.split('.');
      if (path.some(key => !key || ['__proto__', 'constructor', 'prototype'].includes(key))) throw new Error('字段映射路径无效');
      let target = (data as any)[binding.section];
      if (!target || typeof target !== 'object') throw new Error('字段映射目标必须为对象');
      for (const key of path.slice(0, -1)) { target[key] = target[key] && typeof target[key] === 'object' ? target[key] : {}; target = target[key]; }
      target[path[path.length - 1]] = '$ddt{' + field + '}';
    }
  }
  function toggleDataRow(index: number, enabled: boolean) { disabledRows.value = enabled ? disabledRows.value.filter(i => i !== index) : [...disabledRows.value, index]; }
  function removeDataRow(index: number) { dataDriveRows.value.splice(index, 1); disabledRows.value = disabledRows.value.filter(i => i !== index).map(i => i > index ? i - 1 : i); }
  function insertDatasetVariable(name: string) { void referenceVariable({ key: 'dataset-' + name, name, reference: '$ddt{' + name + '}', category: 'dataset', value: '', source: '数据集参数' }); }
  async function importDataset(event: Event) {
    const input = event.target as HTMLInputElement, file = input.files?.[0];
    if (!file) return;
    if (!/\.(csv|json)$/i.test(file.name)) {
      message.error('仅支持上传 CSV 或 JSON 格式文件');
      input.value = '';
      return;
    }
    importingDataset.value = true;
    try {
      const result = await api.importDataset(file);
      dataDriveFields.value = result.fields; dataDriveFieldsText.value = result.fields.join(', ');
      dataDriveRows.value = result.rows.map(row => row.map(encodeCell));
      datasetFilename.value = file.name; disabledRows.value = []; bindings.value = {}; dataDrivenEnabled.value = true;
      message.success('已导入 ' + result.rows.length + ' 行数据');
    } catch (error: any) { message.error(error?.message || error?.detail || '导入失败，请检查文件格式'); }
    finally { importingDataset.value = false; input.value = ''; }
  }
  function selectBatchRow(index: number) { selectedBatchRow.value = index; debugResult.value = batchResults.value[index].result; }
  function prettyResult(value: unknown) {
    if (value === undefined || value === null) return '暂无数据';
    if (typeof value === 'string') { try { return JSON.stringify(JSON.parse(value), null, 2); } catch { return value; } }
    return JSON.stringify(value, null, 2);
  }
  const responseSize = computed(() => ((new TextEncoder().encode(debugResult.value?.response_body || '').length) / 1024).toFixed(2) + ' KB');
  const debugAttemptCount = computed(() => {
    const attempts = (debugResult.value as (EndpointRunResult & { attempts?: unknown }) | null)?.attempts;
    if (Array.isArray(attempts)) return attempts.length;
    if (typeof attempts === 'number' && Number.isFinite(attempts)) return attempts;
    return 0;
  });

</script>

<style lang="less" scoped>
  .endpoint-page {
    min-height: 100%;
    padding: 12px 30px 38px;
    background: #f7f9fc;
    color: #172033;
  }
  .endpoint-page-inner {
    width: 100%;
  }
  .page-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 12px;
  }
  .breadcrumb-row {
    display: flex;
    align-items: center;
    gap: 10px;
    color: #8a96a8;
    font-size: 13px;
  }
  .breadcrumb-row i {
    color: #c1c9d6;
    font-style: normal;
  }
  .breadcrumb-row b {
    color: #536176;
    font-weight: 600;
  }
  .page-actions {
    display: flex;
    flex: none;
    gap: 8px;
  }
  .page-actions :deep(.n-button) {
    min-width: 72px;
    height: 34px;
    border-radius: 6px;
    font-size: 13px;
  }
  .save-button {
    color: #5267f5;
    background: #eef1ff;
    border-color: #eef1ff;
  }
  .endpoint-form {
    width: 100%;
  }
  .basic-card,
  .request-card,
  .response-rules-card,
  .data-drive-card,
  .side-card {
    border: 1px solid #dce3ee;
    border-radius: 10px;
    background: #fff;
  }
  .basic-card {
    margin-bottom: 16px;
    padding: 10px 18px;
  }
  .basic-card h2,
  .request-card-head h2,
  .side-card h2,
  .data-drive-title h2 {
    margin: 0;
    color: #1b2638;
    font-size: 15px;
    font-weight: 700;
  }
  .basic-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 22px;
    margin-top: 7px;
  }
  .basic-grid :deep(.n-form-item.n-form-item--left-labelled) {
    display: grid;
    grid-template-areas: 'label blank';
    grid-template-columns: max-content minmax(0, 1fr);
    grid-template-rows: 34px;
    align-items: center;
    gap: 12px;
    height: 34px;
    margin: 0;
    min-width: 0;
  }
  .basic-grid :deep(.n-form-item.n-form-item--left-labelled > .n-form-item-label) {
    display: flex !important;
    grid-area: label;
    width: auto !important;
    height: 34px !important;
    min-height: 34px !important;
    align-items: center;
    justify-content: flex-start;
    padding: 0;
    color: #59677b;
    font-size: 13px;
    font-weight: 500;
    line-height: 34px;
    white-space: nowrap;
  }
  .basic-grid :deep(.n-form-item.n-form-item--left-labelled > .n-form-item-blank) {
    display: flex;
    grid-area: blank;
    width: 100%;
    height: 34px;
    min-width: 0;
    min-height: 34px;
    align-items: center;
  }
  .basic-grid :deep(.n-form-item-feedback-wrapper) {
    display: none;
  }
  .basic-grid :deep(.n-base-selection-label),
  .basic-grid :deep(.n-input-wrapper) {
    height: 34px;
    min-height: 34px;
  }
  .basic-grid :deep(.n-input),
  .basic-grid :deep(.n-select),
  .basic-grid :deep(.n-base-selection) {
    width: 100%;
    min-width: 0;
    height: 34px;
  }
  .request-core-input {
    display: grid;
    grid-template-columns: 92px minmax(0, 1fr);
    width: 100%;
    height: 34px;
    overflow: hidden;
    box-sizing: border-box;
    border: 1px solid #dce3ee;
    border-radius: 6px;
    background: #fff;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .request-core-input:focus-within {
    border-color: #5267f5;
    box-shadow: 0 0 0 2px rgb(82 103 245 / 10%);
  }
  .request-core-input :deep(.n-base-selection) {
    border-right: 1px solid #e4e9f1;
  }
  .request-core-input :deep(.n-base-selection-label),
  .request-core-input :deep(.n-input-wrapper) {
    height: 32px;
    min-height: 32px;
    border: 0;
    border-radius: 0;
    box-shadow: none !important;
  }
  .request-core-input :deep(.n-input) {
    min-width: 0;
  }
  .request-method-select :deep(.n-base-selection-label) {
    color: #1d9b50;
    background: #f0faf4;
    font-weight: 700;
  }
  .endpoint-workspace {
    display: grid;
    grid-template-columns: minmax(0, 72fr) minmax(360px, 28fr);
    gap: 16px;
    align-items: start;
  }
  .workspace-main {
    display: grid;
    gap: 16px;
    min-width: 0;
  }
  .request-card {
    overflow: hidden;
  }
  .request-card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 58px;
    padding: 10px 18px;
  }
  .request-debug-button {
    min-width: 88px;
    height: 36px;
    border-radius: 6px;
    background: #5267f5;
  }
  .request-target {
    padding: 0 18px 16px;
    border-bottom: 1px solid #e8edf4;
  }
  .request-target :deep(.n-form-item.n-form-item--left-labelled) {
    display: grid;
    grid-template-areas: 'label blank';
    grid-template-columns: max-content minmax(0, 1fr);
    align-items: center;
    gap: 14px;
    margin: 0;
  }
  .request-target :deep(.n-form-item.n-form-item--left-labelled > .n-form-item-label) {
    grid-area: label;
    width: auto !important;
    min-height: 38px;
    align-items: center;
    padding: 0;
    color: #59677b;
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
  }
  .request-target :deep(.n-form-item.n-form-item--left-labelled > .n-form-item-blank) {
    grid-area: blank;
    min-width: 0;
    min-height: 38px;
  }
  .request-target :deep(.n-form-item-feedback-wrapper) {
    display: none;
  }
  .request-target .request-core-input {
    height: 38px;
  }
  .request-target .request-core-input :deep(.n-base-selection-label),
  .request-target .request-core-input :deep(.n-input-wrapper) {
    height: 36px;
    min-height: 36px;
  }
  .request-tabs {
    display: flex;
    align-items: center;
    height: 52px;
    padding: 0 18px;
    border-bottom: 1px solid #e8edf4;
  }
  .request-tabs button {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    align-self: stretch;
    min-width: 122px;
    padding: 0 16px;
    border: 0;
    color: #536176;
    background: transparent;
    cursor: pointer;
    font: inherit;
  }
  .request-tabs button::after {
    position: absolute;
    right: 14px;
    bottom: -1px;
    left: 14px;
    height: 3px;
    border-radius: 3px 3px 0 0;
    background: transparent;
    content: '';
  }
  .request-tabs button.active {
    color: #5267f5;
    font-weight: 600;
  }
  .request-tabs button.active::after {
    background: #5267f5;
  }
  .request-tabs button b {
    display: inline-flex;
    min-width: 20px;
    height: 20px;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
    color: #718096;
    background: #f1f4f8;
    font-size: 11px;
    font-weight: 600;
  }
  .editor-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 48px;
    padding: 0 18px;
  }
  .editor-toolbar > strong {
    color: #344157;
    font-size: 13px;
  }
  .body-kind-tabs {
    display: flex;
    gap: 8px;
  }
  .body-kind-tabs button {
    min-width: 88px;
    height: 30px;
    padding: 0 14px;
    border: 0;
    border-radius: 5px;
    color: #56647a;
    background: transparent;
    cursor: pointer;
  }
  .body-kind-tabs button.active {
    color: #3f5eea;
    background: #eef2ff;
    font-weight: 600;
  }
  .editor-actions {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .editor-actions :deep(.n-button) {
    color: #5f6e82;
  }
  .json-editor {
    display: grid;
    grid-template-columns: 48px minmax(0, 1fr);
    min-height: 226px;
    margin: 0 18px;
    overflow: hidden;
    border: 1px solid #202938;
    border-radius: 7px;
    background: #202733;
  }
  .editor-gutter {
    min-height: 100%;
    margin: 0;
    padding: 14px 0;
    border-right: 1px solid #3a4352;
    color: #929daf;
    background: #1b222d;
    font: 13px/1.75 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    text-align: center;
    user-select: none;
  }
  .json-editor :deep(.n-input),
  .json-editor :deep(.n-input-wrapper),
  .json-editor :deep(.n-input__textarea-el) {
    min-height: 224px !important;
    color: #dce6f5;
    background: transparent !important;
    box-shadow: none !important;
  }
  .json-editor :deep(.n-input-wrapper) {
    padding: 0;
  }
  .json-editor :deep(textarea) {
    padding: 14px 18px;
    caret-color: #fff;
    font: 13px/1.75 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }
  .json-editor :deep(textarea::placeholder) {
    color: #788498;
  }
  .editor-note {
    display: flex;
    align-items: center;
    gap: 9px;
    min-height: 42px;
    margin: 12px 18px 18px;
    padding: 0 14px;
    border: 1px solid #dbe5f3;
    border-radius: 5px;
    color: #69788d;
    background: #f5f8fc;
    font-size: 12px;
  }
  .editor-note > span {
    display: inline-flex;
    width: 18px;
    height: 18px;
    align-items: center;
    justify-content: center;
    border: 1.5px solid #5267f5;
    border-radius: 50%;
    color: #5267f5;
    font-size: 11px;
    font-weight: 700;
  }
  .editor-note code,
  .variables-card code {
    color: #355be7;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .files-panel {
    min-height: 300px;
    padding: 20px 18px;
  }
  .files-panel-head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-bottom: 16px;
    border-bottom: 1px solid #edf1f6;
  }
  .files-panel-head > div:first-child {
    margin-right: auto;
  }
  .files-panel-head strong {
    color: #263348;
    font-size: 14px;
  }
  .files-panel-head p {
    margin: 5px 0 0;
    color: #7d8999;
    font-size: 12px;
  }
  .file-entry {
    display: grid;
    grid-template-columns: 180px minmax(160px, 1fr) 76px 48px;
    gap: 12px;
    align-items: center;
    min-height: 50px;
    padding: 8px 0;
    border-bottom: 1px solid #edf1f6;
  }
  .form-data-table-head,
  .form-data-entry {
    display: grid;
    grid-template-columns: minmax(140px, 0.8fr) 64px minmax(220px, 1.6fr) 48px;
    gap: 12px;
    align-items: center;
  }
  .form-data-table-head {
    padding: 12px 0 6px;
    color: #7d8999;
    font-size: 12px;
  }
  .form-data-entry :deep(.n-tag) {
    justify-self: start;
  }
  .form-data-file-value {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: 12px;
  }
  .form-data-file-value .file-name {
    flex: 1;
  }
  .file-name {
    overflow: hidden;
    color: #5b6676;
    font-size: 13px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .file-size {
    color: #97a0ad;
    font-size: 12px;
    text-align: right;
  }
  .file-empty {
    padding: 60px 0;
  }
  .workspace-sidebar {
    display: grid;
    gap: 12px;
  }
  .side-card {
    overflow: hidden;
  }
  .side-card h2 {
    padding: 16px 18px;
    border-bottom: 1px solid #e8edf4;
  }
  .overview-list {
    padding: 8px 18px 14px;
  }
  .overview-list > div {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 37px;
    color: #536176;
    font-size: 13px;
  }
  .overview-list span {
    display: inline-flex;
    align-items: center;
    gap: 10px;
  }
  .overview-list b {
    color: #263348;
    font-size: 13px;
  }
  .variables-card {
    padding-bottom: 16px;
  }
  .variable-list {
    display: grid;
    gap: 8px;
    padding: 14px 18px 8px;
  }
  .variable-list > div {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 12px;
  }
  .variable-list code {
    width: max-content;
    max-width: 100%;
    overflow: hidden;
    padding: 5px 9px;
    border-radius: 4px;
    background: #eef2ff;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .variable-list span {
    color: #66758a;
    font-size: 12px;
  }
  .variables-card > p {
    margin: 8px 18px 0;
    color: #7b8798;
    font-size: 12px;
    line-height: 1.7;
  }
  .response-rules-card { overflow: hidden; border: 1px solid #dce3ee; border-radius: 10px; background: #fff; }
  .response-rule-tabs :deep(.n-tabs-nav) { padding: 0 18px; border-bottom: 1px solid #e8edf4; }
  .response-rule-tabs :deep(.n-tabs-tab) { min-height: 50px; font-weight: 600; }
  .response-rule-tabs :deep(.n-tabs-pane-wrapper) { padding: 14px 18px 18px; }
  .rule-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; color: #7d8795; font-size: 12px; }
  .extract-rule-table, .validate-rule-table { overflow: hidden; border: 1px solid #e4e9f1; border-radius: 8px; }
  .extract-rule-row { display: grid; grid-template-columns: minmax(110px, 1.1fr) 120px 120px minmax(160px, 1.8fr) 96px 44px; gap: 10px; align-items: center; padding: 10px 14px; border-top: 1px solid #edf0f5; }
  .validate-rule-row { display: grid; grid-template-columns: minmax(170px, 1.4fr) 136px minmax(150px, 1fr) 44px; gap: 10px; align-items: center; padding: 10px 14px; border-top: 1px solid #edf0f5; }
  .extract-rule-row:first-child, .validate-rule-row:first-child { border-top: 0; }
  .extract-rule-header, .validate-rule-header { color: #687386; background: #f8fafc; font-size: 12px; font-weight: 600; }
  .rule-empty { padding: 22px 0; }
  .rule-tip { margin-top: 10px; color: #7d8795; font-size: 12px; line-height: 1.75; }
  .rule-tip code { padding: 1px 4px; border-radius: 3px; color: #536174; background: #f3f5f8; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  :global(.response-path-option) { display: flex; min-width: 0; align-items: center; gap: 7px; }
  :global(.response-path-option code) { overflow: hidden; color: #315fc9; font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; text-overflow: ellipsis; white-space: nowrap; }
  :global(.response-path-option span) { overflow: hidden; color: #8a96a8; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
  .variable-card-header { display: flex; min-height: 46px; padding: 0 12px; align-items: center; justify-content: space-between; }
  .variable-card-header h2 { padding: 0; border: 0; font-size: 14px; }
  .variable-collapse-button { display: inline-grid; width: 28px; height: 28px; padding: 0; border: 0; place-items: center; color: #617086; background: transparent; cursor: pointer; }
  .variable-collapse-button :deep(svg) { font-size: 16px; transition: transform .18s ease; }
  .variable-collapse-button :deep(svg.collapsed) { transform: rotate(180deg); }
  .variable-card-content { min-width: 0; padding: 0 0 12px; overflow: hidden; }
  .variable-search { width: auto; min-width: 0; max-width: calc(100% - 24px); margin: 0 12px 10px; box-sizing: border-box; }
  .variable-tabs { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); min-height: 42px; padding: 0 9px; border-bottom: 1px solid #e6eaf0; }
  .variable-tabs button { position: relative; display: inline-flex; min-width: 0; height: 42px; padding: 0 3px; border: 0; align-items: center; justify-content: center; gap: 4px; color: #66758b; background: transparent; font-size: 11px; font-weight: 600; white-space: nowrap; cursor: pointer; }
  .variable-tabs button::after { position: absolute; right: 4px; bottom: -1px; left: 4px; height: 2px; border-radius: 2px 2px 0 0; background: transparent; content: ''; }
  .variable-tabs button b { display: inline-grid; min-width: 18px; height: 18px; padding: 0 4px; border-radius: 5px; place-items: center; color: #7e8ca1; background: #f1f3f7; font-size: 10px; }
  .variable-tabs button.active { color: #2468f2; }
  .variable-tabs button.active::after { background: #2468f2; }
  .variable-tabs button.active b { color: #2468f2; background: #edf3ff; }
  .variable-groups { max-height: min(600px, calc(100vh - 170px)); padding-top: 4px; overflow: auto; }
  .variable-group { margin: 0 10px 10px; overflow: hidden; border: 1px solid #dfe5ed; border-radius: 5px; background: #fff; }
  .variable-group > header { display: flex; min-height: 38px; padding: 0 10px; border-bottom: 1px solid #e8ecf2; align-items: center; justify-content: space-between; background: #fbfcfe; }
  .variable-group > header > div { display: flex; min-width: 0; align-items: center; gap: 6px; }
  .variable-group > header :deep(svg) { width: 8px; height: 8px; flex: none; color: #18a058; }
  .variable-group > header strong { color: #18a058; font-size: 12px; }
  .variable-group > header span { overflow: hidden; color: #8a96a8; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
  .variable-group > header > b { color: #6d7b90; font-size: 11px; }
  .variable-group.is-function > header :deep(svg), .variable-group.is-function > header strong { color: #7c4ce0; }
  .variable-row { display: grid; min-height: 40px; padding: 0 9px; grid-template-columns: minmax(82px, .8fr) minmax(0, 1.35fr) auto; align-items: center; gap: 7px; border-bottom: 1px solid #edf0f5; }
  .variable-row:last-child { border-bottom: 0; }
  .variable-row code { min-width: 0; overflow: hidden; color: #34445a; font: 11px/24px ui-monospace, SFMono-Regular, Menlo, monospace; text-overflow: ellipsis; white-space: nowrap; }
  .variable-group.is-function .variable-row { grid-template-columns: minmax(0, 1fr) auto; }
  .variable-value { display: inline-flex; min-width: 0; overflow: hidden; align-items: center; gap: 4px; color: #7f8da2; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
  .variable-eye-button { display: inline-grid; width: 20px; height: 20px; padding: 0; border: 0; flex: none; place-items: center; color: #8794a7; background: transparent; cursor: pointer; }
  .variable-actions { display: inline-flex; align-items: center; gap: 6px; }
  .variable-actions button { padding: 2px 0; border: 0; color: #2468f2; background: transparent; font-size: 10px; font-weight: 600; cursor: pointer; }
  .variable-empty { display: grid; min-height: 148px; place-items: center; align-content: center; gap: 9px; color: #8a96a8; font-size: 12px; }
  .variable-empty :deep(svg) { font-size: 28px; }
  .data-drive-card {
    overflow: hidden;
  }
  .data-drive-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    min-height: 42px;
    padding: 0 16px;
    border-bottom: 1px solid #e8edf4;
  }
  .data-drive-title > div {
    display: flex;
    align-items: baseline;
    gap: 14px;
  }
  .data-drive-title p {
    margin: 0;
    color: #8290a3;
    font-size: 12px;
  }
  .data-drive-content {
    padding: 10px 16px 14px;
  }
  .data-drive-field-label {
    display: grid;
    grid-template-columns: 176px minmax(0, 1fr);
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
    color: #536176;
    font-size: 12px;
  }
  .data-drive-table-wrap {
    overflow-x: auto;
    border: 1px solid #dce3ee;
    border-radius: 4px;
  }
  .data-drive-table {
    min-width: 620px;
  }
  .data-drive-row {
    display: grid;
    align-items: center;
    gap: 0;
    min-height: 32px;
    padding: 0;
    border-top: 1px solid #e8edf4;
  }
  .data-drive-row > * {
    display: flex;
    height: 100%;
    min-width: 0;
    align-items: center;
    padding: 0 10px;
    border-right: 1px solid #e8edf4;
  }
  .data-drive-row > *:last-child {
    justify-content: center;
    border-right: 0;
  }
  .data-drive-row:first-child {
    border-top: 0;
  }
  .data-drive-header {
    min-height: 28px;
    color: #56647a;
    background: #f7f9fc;
    font-size: 12px;
    font-weight: 600;
  }
  .data-drive-index {
    justify-content: center;
    color: #7c899b;
    font-size: 12px;
    text-align: center;
  }
  .data-drive-actions {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    white-space: nowrap;
  }
  .data-drive-actions :deep(.n-button) {
    padding: 0;
  }
  .data-drive-row :deep(.n-input-wrapper) {
    min-height: 31px;
    padding: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
  }
  .data-drive-row :deep(.n-input) {
    height: 31px;
    background: transparent;
  }
  .data-drive-row :deep(.n-input:focus-within) {
    box-shadow: inset 0 0 0 1px #5267f5;
  }
  .add-data-row {
    height: 36px;
    border-width: 0;
    border-top: 1px dashed #aebcff;
    border-radius: 0;
    color: #5267f5;
  }
  .data-drive-warning {
    margin-top: 10px;
  }
  .endpoint-debug-modal {
    max-height: calc(100vh - 40px);
    overflow: hidden;
    border-radius: 10px;
  }
  .endpoint-debug-modal :deep(.n-card-header) {
    min-height: 64px;
    padding: 0 22px;
    border-bottom: 1px solid #e4e9f1;
  }
  .endpoint-debug-modal :deep(.n-card__content) {
    display: flex;
    height: calc(100% - 64px);
    min-height: 0;
    flex-direction: column;
    padding: 0 22px 22px;
    overflow: hidden;
  }
  .debug-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    min-height: 72px;
    padding: 12px 0;
    border-bottom: 1px solid #edf0f5;
  }
  .debug-environment-control {
    display: grid;
    grid-template-columns: 72px minmax(260px, 1fr);
    align-items: center;
    gap: 12px;
    width: min(480px, 100%);
  }
  .debug-toolbar span {
    color: #59677b;
    font-size: 13px;
    font-weight: 600;
  }
  .debug-toolbar-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .debug-result {
    display: grid;
    min-height: 0;
    grid-template-rows: auto auto minmax(0, 1fr);
    gap: 14px;
    padding-top: 14px;
  }
  .debug-summary {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    padding: 10px 12px;
    border-radius: 7px;
    background: #f5f7f9;
    color: #66758a;
    font-size: 13px;
  }
  .debug-metric {
    display: inline-flex;
    align-items: baseline;
    gap: 7px;
    min-height: 26px;
    padding: 3px 11px;
    border-left: 1px solid #dfe5eb;
    font-variant-numeric: tabular-nums;
  }
  .debug-metric small {
    color: #8490a0;
    font-size: 12px;
  }
  .debug-metric strong {
    color: #334155;
    font-size: 13px;
    font-weight: 600;
  }
  .debug-errors {
    font-size: 13px;
  }
  .debug-response {
    display: flex;
    min-height: 0;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid #dce3ee;
    border-radius: 8px;
  }
  .debug-result-tabs :deep(.n-tabs-nav) {
    flex: none;
    padding: 0 20px;
    border-bottom: 1px solid #e8edf4;
  }
  .debug-result-tabs :deep(.n-tabs-tab) {
    min-height: 50px;
    padding: 0 4px;
  }
  .debug-result-tabs,
  .debug-result-tabs :deep(.n-tabs-pane-wrapper),
  .debug-result-tabs :deep(.n-tab-pane) {
    min-height: 0;
  }
  .debug-result-tabs :deep(.n-tabs-pane-wrapper) {
    flex: 1;
  }
  .debug-result-tabs :deep(.n-tab-pane) {
    padding-top: 0;
  }
  .debug-response-code {
    overflow: auto;
    height: 100%;
    min-height: 320px;
    max-height: calc(100vh - 310px);
    margin: 0;
    padding: 20px;
    color: #dfe7f3;
    background: #202733;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
    font-size: 13px;
    line-height: 1.75;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    tab-size: 2;
  }
  @media (max-width: 760px) {
    .endpoint-debug-modal {
      width: calc(100vw - 20px) !important;
      height: calc(100vh - 20px) !important;
      max-height: calc(100vh - 20px);
    }
    .endpoint-debug-modal :deep(.n-card-header) {
      padding: 16px;
    }
    .endpoint-debug-modal :deep(.n-card__content) {
      padding: 0 16px 16px;
    }
    .debug-toolbar {
      align-items: stretch;
      flex-direction: column;
    }
    .debug-environment-control {
      grid-template-columns: 1fr;
      gap: 6px;
      width: 100%;
    }
    .debug-toolbar-actions {
      justify-content: flex-end;
    }
    .debug-response-code {
      min-height: 280px;
      padding: 14px;
      font-size: 12px;
    }
    .debug-summary {
      align-items: stretch;
    }
    .debug-metric {
      border-left: 0;
      padding-right: 6px;
      padding-left: 6px;
    }
  }
  @media (max-width: 1400px) {
    .endpoint-page {
      padding-right: 20px;
      padding-left: 20px;
    }
    .endpoint-workspace {
      grid-template-columns: minmax(0, 72fr) minmax(300px, 28fr);
    }
  }
  @media (max-width: 980px) {
    .endpoint-workspace {
      grid-template-columns: 1fr;
    }
    .workspace-sidebar {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .request-tabs {
      overflow-x: auto;
    }
  }
  @media (max-width: 680px) {
    .endpoint-page {
      padding: 16px 12px 28px;
    }
    .page-toolbar {
      align-items: flex-start;
      flex-wrap: wrap;
    }
    .basic-grid,
    .workspace-sidebar {
      grid-template-columns: 1fr;
    }
    .basic-grid :deep(.n-form-item.n-form-item--left-labelled) {
      grid-template-areas:
        'label'
        'blank';
      grid-template-columns: 1fr;
      grid-template-rows: 34px 34px;
      align-items: stretch;
      height: auto;
      gap: 6px;
    }
    .request-tabs button {
      min-width: 108px;
    }
    .data-drive-title,
    .data-drive-title > div {
      align-items: flex-start;
      flex-direction: column;
    }
    .data-drive-title {
      padding: 12px 16px;
    }
    .data-drive-field-label {
      grid-template-columns: 1fr;
    }
    .debug-toolbar {
      align-items: stretch;
      flex-direction: column;
    }
    .debug-toolbar > div {
      grid-template-columns: 1fr;
    }
    .rule-actions { align-items: flex-start; flex-direction: column; }
    .extract-rule-row, .validate-rule-row { grid-template-columns: 1fr; }
    .extract-rule-header, .validate-rule-header { display: none; }
    .extract-rule-row, .validate-rule-row { padding: 12px; }
  }
</style>

<style scoped lang="less">
.api-workbench{--n-primary-color:#087f74;display:grid;grid-template-columns:200px minmax(0,1fr);padding:0!important;background:#fff!important;min-height:calc(100vh - 90px);color:#263238}
.endpoint-directory{padding:22px 12px;border-right:1px solid #e3e6e8;background:#fff}.endpoint-directory>.n-input{margin:24px 0}.directory-back{font-size:14px}.directory-group{margin:0 0 12px}.directory-group-header{display:grid;width:100%;grid-template-columns:20px minmax(0,1fr) 18px;align-items:center;gap:8px;padding:10px 8px;border:0;background:transparent;color:#263238;font-size:14px;text-align:left;cursor:pointer}.directory-group-header>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.directory-group-header>svg:last-child{transition:transform .18s ease}.directory-group-header>svg:last-child.collapsed{transform:rotate(-90deg)}.directory-items{display:flex;flex-direction:column;gap:2px}.directory-items>button{display:grid;width:100%;grid-template-columns:54px minmax(0,1fr);align-items:center;gap:8px;padding:11px 10px 11px 16px;border:0;border-radius:4px;background:none;text-align:left;cursor:pointer}.directory-items>button:hover{background:#f2f8f7}.directory-items>button.selected{background:#e2f5f3;color:#087f74}.directory-items b{font:600 12px/1 ui-monospace,monospace;color:#c17818}.directory-items b.get{color:#158354}.directory-items b.put,.directory-items b.patch{color:#356fd0}.directory-items b.delete{color:#d1455b}.directory-items button span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.endpoint-page-inner{max-width:none!important;width:100%;min-width:0;padding:22px!important}.page-toolbar{margin:0!important}.basic-card{border:0!important;padding:12px 0 18px!important;box-shadow:none!important}.basic-card h1{font-size:30px;margin:0 0 14px;color:#192626;font-weight:650}.basic-grid{grid-template-columns:1.1fr 1fr 1fr!important;max-width:880px}.basic-grid :deep(.n-form-item){margin:0}.execution-modes{display:flex;gap:2px;margin-bottom:18px}.execution-modes button{padding:8px 16px;border:0;background:#f5f7f7;color:#647473;cursor:pointer}.execution-modes .active{color:#087f74;background:#e1f2ef;border-bottom:2px solid #087f74}.environment-selector{width:200px}.endpoint-workspace{grid-template-columns:minmax(0,1fr) 310px!important;gap:20px!important;align-items:start}.workspace-main{display:flex;flex-direction:column;gap:0!important;min-width:0}.request-card{display:grid;grid-template-columns:minmax(0,1fr) auto;border:0!important;border-radius:0!important;box-shadow:none!important;padding:0!important}.request-card-head{grid-column:2;grid-row:1;padding:0 0 12px 10px!important;border:0!important}.request-card-head h2{display:none}.request-target{grid-column:1;grid-row:1;padding:0!important}.request-target :deep(.n-form-item-feedback-wrapper){display:none}.request-tabs,.editor-toolbar,.json-editor,.editor-note,.files-panel{grid-column:1/-1}.request-tabs{padding:0!important;gap:18px!important}.request-tabs button{padding:14px 2px!important;color:#62716f!important;font-size:13px!important}.request-tabs button.active{color:#087f74!important;border-color:#087f74!important}.request-tabs button svg{display:none}.request-debug-button{height:36px;background:#087f74!important;border-color:#087f74!important;border-radius:4px!important}.request-tabs button.active::after{background:#087f74!important}.json-editor{background:#202725!important;border-radius:4px!important;margin:0!important}.json-editor :deep(textarea){color:#d4eee8!important;font-family:ui-monospace,monospace!important;font-size:14px!important}.editor-note{padding:10px 0!important}.response-rules-card{border:0!important;border-radius:0!important}.response-rules-card :deep(.n-tabs-nav){display:none}.data-drive-card{order:-1;border:1px solid #dfe8e5!important;background:#f9fcfb!important;margin-bottom:18px!important;border-radius:5px!important}.data-drive-title{padding:12px 16px!important}.dataset-tools{display:flex;align-items:center;gap:10px;font-size:12px}.dataset-bindings h3{margin:18px 0 8px}.dataset-bindings p{font-size:12px;color:#687e76}.binding-row{display:grid;grid-template-columns:120px 150px minmax(120px,1fr) 40px;gap:8px;align-items:center;margin:8px 0}.inline-response{border-top:1px solid #dce5e1;margin-top:18px;min-width:0}.response-heading{display:flex;align-items:center;gap:16px;padding:16px 0}.response-heading h2{margin:0;font-size:17px}.response-heading>span{font-size:12px;color:#687570}.response-heading .n-button{margin-left:auto}.response-code{background:#202725;color:#d2e9e3;padding:18px;border-radius:4px;font:13px/1.8 ui-monospace,monospace;min-height:190px;max-height:480px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere}.batch-results{max-height:190px;overflow:auto;border:1px solid #e1ebe7}.batch-results>button{width:100%;display:flex;justify-content:space-between;padding:9px 14px;background:#fff;border:0;border-top:1px solid #edf3ef;cursor:pointer}.batch-results>.selected{background:#e9f7f2}.batch-summary{padding:10px;background:#f4faf7}.passed{color:#16834e}.failed{color:#cb4242}.workspace-sidebar{position:sticky;top:12px;min-width:0}.variables-card{box-shadow:none!important;border-radius:5px!important;padding:16px 12px!important}.variable-tabs{overflow:auto;gap:12px!important}.variable-tabs button{flex:none}.variable-row{grid-template-columns:minmax(0,1fr) auto!important;padding:12px 8px!important}.variable-row code{grid-column:1;font-size:12px!important;white-space:normal!important;overflow-wrap:anywhere}.variable-value{grid-column:1;font-size:12px!important}.variable-actions{grid-column:2;grid-row:1/3}.variable-actions button{color:#087f74!important}.variable-group header{background:white!important}.variable-group{border:0!important;border-bottom:1px solid #e6eeeb!important}.variable-row{border-top:1px solid #edf2ef!important}.side-card h2{font-size:16px!important}.save-button{color:#087f74!important;border-color:#087f74!important;background:white!important}
@media(max-width:1250px){.api-workbench{grid-template-columns:160px minmax(0,1fr)}.endpoint-workspace{grid-template-columns:minmax(0,1fr) 270px!important}.request-tabs{gap:10px!important}.endpoint-page-inner{padding:16px!important}}
@media(max-width:980px){.endpoint-directory{display:none}.api-workbench{display:block}.endpoint-workspace{grid-template-columns:1fr!important}.workspace-sidebar{position:static}.basic-grid{grid-template-columns:1fr!important}.binding-row{grid-template-columns:1fr 1fr}.page-actions{flex-wrap:wrap}.request-tabs{overflow:auto}}

/* 与接口工作台原型统一的最终视觉覆盖 */
.endpoint-page-inner{padding:22px 28px!important}
.page-actions{gap:18px}
.endpoint-title-row{display:flex;align-items:center;justify-content:space-between;gap:20px;margin:0 0 16px}
.endpoint-title-editor{display:flex;min-width:260px;max-width:560px;align-items:center;gap:8px}
.endpoint-title-editor :deep(.n-input){background:transparent}
.endpoint-title-editor :deep(.n-input-wrapper){padding:0 10px;background:transparent;box-shadow:none!important;transition:box-shadow .18s ease,background-color .18s ease}
.endpoint-title-editor:focus-within :deep(.n-input-wrapper){background:#fff;box-shadow:0 0 0 1px #087f74 inset,0 0 0 2px rgba(8,127,116,.12)!important}
.endpoint-title-editor :deep(input){height:42px;color:#182322;font-size:30px;font-weight:650;line-height:42px}
.endpoint-title-editor>button{display:grid;width:30px;height:30px;padding:0;border:0;color:#485655;background:transparent;cursor:pointer;opacity:0;pointer-events:none;transition:opacity .18s ease;place-items:center}
.endpoint-title-editor:focus-within>button{opacity:1;pointer-events:auto}
.endpoint-title-editor>button svg{width:19px;height:19px}
.basic-grid{grid-template-columns:240px 240px!important;max-width:540px;gap:28px!important}
.execution-modes{flex:none;align-self:center;margin:0}
.environment-selector{width:260px}
.save-button{width:118px;height:46px}
.endpoint-workspace{grid-template-columns:minmax(0,1fr) 380px!important;gap:20px!important}
.request-core-input{grid-template-columns:130px minmax(0,1fr)!important}
.request-core-input{height:48px!important}
.request-core-input :deep(.n-base-selection),.request-core-input :deep(.n-base-selection-label),.request-core-input :deep(.n-input),.request-core-input :deep(.n-input-wrapper){height:46px!important;min-height:46px!important}
.request-tabs{height:58px!important;padding:0!important;gap:26px!important}
.request-tabs button{min-width:auto!important;padding:14px 12px!important;color:#4f5c5a!important;font-size:14px!important}
.request-tabs button.active::after{right:4px!important;left:4px!important}
.request-tabs button.request-parameter-tab{flex:none;gap:7px;padding:9px 2px!important;color:#78869b!important;font-size:13px!important;font-weight:400;line-height:normal}
.request-tabs button.request-parameter-tab.active{color:#008993!important;font-weight:400}
.request-tabs button.request-parameter-tab::after{left:0!important;right:0!important;bottom:-1px;height:2px;border-radius:0}
.request-tabs button.request-parameter-tab.active::after{background:#008993!important}
.request-tabs button.request-parameter-tab b{min-width:0;height:auto;padding:0 5px;border-radius:12px;background:#f1f5f8;color:inherit;font-size:11px;font-weight:400;line-height:normal}
.request-run-control{display:flex;height:48px;overflow:visible;border-radius:4px;box-shadow:0 6px 14px rgba(8,127,116,.16)}
.request-debug-button{width:154px!important;min-width:154px!important;height:48px!important;font-size:15px!important;border-radius:4px 0 0 4px!important}
.request-run-menu{width:48px!important;min-width:48px!important;height:48px!important;padding:0!important;border-left:1px solid rgba(255,255,255,.4)!important;border-radius:0 4px 4px 0!important;background:#087f74!important}
.request-run-menu :deep(.n-button__icon){margin:0!important}
.editor-toolbar{height:64px!important;padding:0!important}
.body-kind-tabs{overflow:visible;gap:20px!important;border:0!important;border-bottom:1px solid #dce5e1!important;border-radius:0!important}
.body-kind-tabs button{position:relative;min-width:auto!important;height:42px!important;padding:0 4px!important;border:0!important;border-radius:0!important;background:transparent!important}
.body-kind-tabs button::after{position:absolute;right:4px;bottom:-1px;left:4px;height:2px;border-radius:2px 2px 0 0;background:transparent;content:''}
.body-kind-tabs button.active{color:#087f74!important;background:transparent!important}
.body-kind-tabs button.active::after{background:#087f74!important}
.execution-modes button.active,.request-tabs button.active,.variable-tabs button.active{background:transparent!important}
.request-core-input{display:flex!important;gap:8px!important;height:42px!important;overflow:visible!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important}
.request-core-input:focus-within{border:0!important;box-shadow:none!important}
.request-core-input>.request-method-select{width:110px!important;flex:none}
.request-core-input>.n-input{min-width:0;flex:1}
.request-core-input :deep(.n-base-selection),.request-core-input :deep(.n-input-wrapper){height:42px!important;min-height:42px!important;border:0!important;border-radius:6px!important;box-shadow:0 0 0 1px #e1e7f0 inset!important;transition:box-shadow .18s ease,background-color .18s ease}
.request-core-input :deep(.n-base-selection:hover),.request-core-input :deep(.n-input-wrapper:hover){box-shadow:0 0 0 1px #a9c3bf inset!important}
.request-core-input :deep(.n-base-selection.n-base-selection--active),.request-core-input :deep(.n-input.n-input--focus .n-input-wrapper){box-shadow:0 0 0 1px #087f74 inset,0 0 0 3px rgb(8 127 116 / 9%)!important}
.request-core-input :deep(.n-input__input-el){color:#5f6f86;font:13px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}
.request-method-select :deep(.n-base-selection-label){background:transparent!important;font-weight:600}
.request-method-select.method-get :deep(.n-base-selection-label){color:#318357!important}
.request-method-select.method-post :deep(.n-base-selection-label){color:#da820b!important}
.request-method-select.method-put :deep(.n-base-selection-label),.request-method-select.method-patch :deep(.n-base-selection-label){color:#277bc5!important}
.request-method-select.method-delete :deep(.n-base-selection-label){color:#d44857!important}
.json-editor{min-height:160px!important}
.json-editor :deep(.n-input),.json-editor :deep(.n-input-wrapper),.json-editor :deep(.n-input__textarea-el){min-height:158px!important}
.editor-note{display:none!important}
.inline-response{margin-top:14px}
.response-heading .n-button{margin:0}
.response-heading .response-heading-actions{display:flex;align-items:center;gap:8px;margin-left:auto}
.response-code{min-height:240px}
.workspace-sidebar{margin-top:0}
.variables-card{padding:0 0 16px!important;border:1px solid #d7dfdc!important}
.variable-card-header{min-height:58px!important;padding:0 18px!important}
.variable-search{max-width:calc(100% - 28px)!important;margin:0 14px 8px!important}
.variable-tabs{min-height:48px!important;padding:0 14px!important;gap:8px!important}
.variable-tabs button{height:48px!important;flex:1;font-size:13px!important}
.variable-group{margin:0 12px 14px!important;border:1px solid #dfe5ed!important;border-radius:4px!important}
.variable-group>header{min-height:44px!important}
.variable-row{min-height:58px!important;padding:7px 12px!important}
.variable-row code{font-size:13px!important}
.variable-actions{gap:12px!important}
.variable-actions button{font-size:12px!important}
/* 接口名称与页面操作同排，项目/模块与右侧可用变量同一水平 */
.endpoint-title-row{margin:0!important}
.workspace-main{gap:18px!important}
.basic-grid{grid-template-columns:220px 220px!important;max-width:468px;gap:28px!important;align-self:start}

/* 收窄请求方式、URL 和发送请求组合，编辑器等下方区域仍保持全宽 */
.request-card{grid-template-columns:minmax(0,680px) auto minmax(0,1fr)!important;align-self:stretch;margin:6px 0 0!important}
.request-card :deep(.parameter-table){grid-column:1/-1;width:100%}
.request-core-input{grid-template-columns:110px minmax(0,1fr)!important;height:44px!important}
.request-core-input :deep(.n-base-selection),.request-core-input :deep(.n-base-selection-label),.request-core-input :deep(.n-input),.request-core-input :deep(.n-input-wrapper){height:42px!important;min-height:42px!important}
.request-core-input :deep(.n-input-wrapper){display:flex;align-items:center!important}
.request-core-input :deep(.n-input__input){display:flex;align-items:center;height:100%!important}
.request-core-input :deep(.n-input__input-el){height:42px!important;line-height:42px!important}
.request-run-control{height:44px;box-shadow:0 5px 12px rgba(8,127,116,.14)}
.request-debug-button{width:132px!important;min-width:132px!important;height:44px!important;font-size:14px!important}
.request-run-menu{width:42px!important;min-width:42px!important;height:44px!important}
@media(max-width:1400px){.endpoint-workspace{grid-template-columns:minmax(0,1fr) 340px!important}.environment-selector{width:220px}.request-tabs{gap:12px!important}.request-card{grid-template-columns:minmax(0,580px) auto minmax(0,1fr)!important}}
@media(max-width:1250px){.endpoint-page-inner{padding:16px!important}.request-tabs{gap:6px!important}.basic-grid{grid-template-columns:200px 200px!important}.workspace-sidebar{margin-top:0}}
@media(max-width:980px){.endpoint-workspace{grid-template-columns:1fr!important}.workspace-sidebar{position:static;margin-top:0}.basic-grid{grid-template-columns:1fr 1fr!important;max-width:none;width:100%}.endpoint-title-row{align-items:center;flex-wrap:wrap}.endpoint-title-editor{min-width:280px;flex:1}.request-card{grid-template-columns:minmax(0,1fr) auto!important}.request-card-head{grid-column:2}.request-target{grid-column:1}.request-debug-button{width:124px!important;min-width:124px!important}}

/* 接口详情工作台：重建页面节奏，减少横线和嵌套外框。 */
.api-workbench{grid-template-columns:260px minmax(0,1fr);background:#f4f6f5!important}
.endpoint-directory{border-right-color:#e2e7e5;background:#f8faf9}
.endpoint-page-inner{width:min(100%,1720px);margin:0 auto;padding:22px 26px 32px!important}
.page-toolbar{min-height:24px;margin-bottom:10px!important}
.breadcrumb-row{font-size:12px;letter-spacing:.01em}
.basic-card{margin-bottom:14px!important;padding:0!important;background:transparent!important}
.endpoint-title-row{min-height:58px;margin:0!important}
.endpoint-title-editor{max-width:640px}
.endpoint-title-editor :deep(.n-input),.endpoint-title-editor :deep(.n-input-wrapper){background:transparent!important}
.endpoint-title-editor :deep(input){height:44px;font-size:27px;line-height:44px;letter-spacing:-.02em}
.page-actions{gap:10px}
.save-button{width:104px;height:40px;border-radius:6px}
.environment-selector{width:230px}
.endpoint-workspace{grid-template-columns:minmax(0,1fr) 350px!important;gap:16px!important}
.workspace-main{gap:14px!important}
.basic-grid{width:100%;max-width:none;grid-template-columns:minmax(220px,280px) minmax(220px,280px)!important;gap:18px!important;padding:13px 16px 2px;border:1px solid #e2e7e5;border-radius:9px;background:#fff}
.request-card{grid-template-columns:minmax(0,1fr) auto!important;align-items:start;gap:0 12px;margin:0!important;padding:16px 16px 18px!important;border:1px solid #e2e7e5!important;border-radius:10px!important;background:#fff!important}
.request-card-head{grid-column:2;grid-row:1;align-self:start;padding:0!important}
.request-target{grid-column:1;grid-row:1;align-self:start;padding:0!important;border:0!important}
.request-target :deep(.n-form-item){margin:0!important}
.request-target :deep(.n-form-item-blank){min-height:44px!important}
.request-core-input{width:100%;height:44px!important}
.request-tabs{grid-column:1/-1;height:54px!important;margin-top:12px;padding:0!important;border-bottom:1px solid #e8ecea!important;gap:22px!important}
.request-tabs button{padding:0 4px!important;font-size:13px!important}
.editor-toolbar{height:54px!important}
.body-kind-tabs{border-bottom-color:#e8ecea!important}
.json-editor{margin:0!important;border-color:#29312f!important;border-radius:7px!important;background:#202624!important}
.inline-response{margin:0!important;padding:0 16px 18px;border:1px solid #e2e7e5!important;border-radius:10px;background:#fff}
.response-heading{min-height:58px;padding:0;border-bottom:1px solid #e8ecea}
.inline-response :deep(.n-tabs-nav){border-bottom-color:#e8ecea}
.inline-response :deep(.n-tab-pane){padding-top:14px}
.response-code{border:1px solid #29312f;border-radius:7px;background:#202624}
.workspace-sidebar{top:14px}
.variables-card{overflow:hidden;padding:0 0 12px!important;border:1px solid #e2e7e5!important;border-radius:10px!important;background:#fff}
.variable-card-header{min-height:58px!important;padding:0 16px!important;border-bottom:0!important}
.variable-search{max-width:calc(100% - 32px)!important;margin:0 16px 6px!important}
.variable-tabs{margin:0 16px!important;padding:0!important;border-bottom:1px solid #e8ecea!important;gap:12px!important}
.variable-group{margin:12px 16px 0!important;border:0!important;border-radius:0!important}
.variable-group>header{min-height:38px!important;padding:0 4px!important;border-bottom:1px solid #edf0ef!important;background:transparent!important}
.variable-row{min-height:54px!important;padding:7px 4px!important;border-top:1px solid #edf0ef!important;background:transparent!important}
.variable-rows .variable-row:first-child{border-top:0!important}
.variable-row:hover{background:#f7f9f8!important}
@media(max-width:1400px){.endpoint-workspace{grid-template-columns:minmax(0,1fr) 320px!important}}
@media(max-width:980px){.api-workbench{display:block}.endpoint-page-inner{padding:18px!important}.endpoint-workspace{grid-template-columns:1fr!important}.request-card{grid-template-columns:minmax(0,1fr) auto!important}.workspace-sidebar{position:static}.basic-grid{grid-template-columns:1fr 1fr!important}}

/* 请求栏最终对齐：方法、URL 与执行按钮共用同一基线和高度。 */
.request-card .request-core-input,
.request-card .request-run-control,
.request-card .request-debug-button,
.request-card .request-run-menu,
.request-card .request-core-input :deep(.n-base-selection),
.request-card .request-core-input :deep(.n-base-selection-label),
.request-card .request-core-input :deep(.n-input),
.request-card .request-core-input :deep(.n-input-wrapper),
.request-card .request-core-input :deep(.n-input__input-el){height:44px!important;min-height:44px!important}
.request-card .request-core-input :deep(.n-input__input-el){line-height:44px!important}
.request-card .request-run-control{align-self:start}
.directory-items>button.selected{position:relative;overflow:hidden}
.directory-items>button.selected::before{position:absolute;top:0;bottom:0;left:0;width:3px;border-radius:0 3px 3px 0;background:#4fbba5;content:''}
</style>
