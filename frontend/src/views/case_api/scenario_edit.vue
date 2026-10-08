<template>
 <n-config-provider class="scenario-studio" :theme-overrides="studioTheme">
  <div class="scene-page studio-page">
   <header class="studio-header">
    <div class="studio-breadcrumb"><button @click="back">API测试</button><span>/</span><button @click="back">场景管理</button></div>
    <n-form ref="formRef" :model="form" :rules="rules" class="studio-form">
     <div class="studio-title-row"><div class="studio-name" :style="{ '--scenario-name-width': Math.min(440, Math.max(130, form.name.length * 26 + 12)) + 'px' }"><n-input v-model:value="form.name" placeholder="请输入场景名称" aria-label="场景名称"/><span class="studio-saved"><PhCheckCircle weight="fill"/>{{ scenarioCreated && savedFormSignature === formSignature ? '已保存' : '未保存' }}</span></div><div class="studio-actions"><n-select v-model:value="runEnvironment" :options="environmentOptions" :placeholder="environmentPlaceholder" :disabled="!form.projects.length" aria-label="执行环境"/><n-button type="primary" ghost @click="saveScenario"><template #icon><PhFloppyDisk/></template>保存场景</n-button><n-button type="primary" :disabled="!scenarioCreated || !runEnvironment" :loading="scenarioRunning" @click="runScenario"><template #icon><PhPlay weight="fill"/></template>运行场景</n-button></div></div>
     <div class="studio-metadata"><div class="studio-project-field"><span>关联项目</span><n-select v-model:value="form.projects" :options="projectOptions" multiple filterable :max-tag-count="2" placeholder="请选择项目" aria-label="关联项目"/></div><i></i><n-input v-model:value="form.description" placeholder="描述此场景的业务目标" aria-label="场景描述"/></div>
    </n-form>
   </header>
   <div class="studio-workspace">
    <aside class="studio-flow">
     <div class="studio-flow-heading"><strong>流程步骤</strong><span>{{ sceneStats.steps }} 个接口</span></div>
     <div class="studio-flow-tools"><n-popover trigger="click" placement="bottom-start" :show="endpointPickerVisible" :style="{ padding: '0' }" @update:show="handleEndpointPickerVisible">
          <template #trigger>
            <n-button class="endpoint-select-trigger" :class="{ 'endpoint-select-trigger--active': selectedEndpoints.length }">
              <PhPlus />
              <span class="endpoint-select-text">添加接口</span>
            </n-button>
          </template>
          <div class="endpoint-picker-dropdown">
            <div class="picker-toolbar">
              <span class="picker-title">选择接口</span>
              <div class="picker-actions">
                <n-input v-model:value="endpointSearch" size="small" clearable placeholder="搜索接口名称或路径..." class="picker-search">
                  <template #prefix>⌕</template>
                </n-input>
                <n-button size="small" @click="selectAllVisibleEndpoints">全选</n-button>
                <n-button size="small" @click="invertVisibleEndpoints">反选</n-button>
                <n-button size="small" type="error" secondary :disabled="!selectedEndpoints.length" @click="selectedEndpoints = []">清空已选</n-button>
                <n-button size="small" type="primary" :disabled="!selectedEndpoints.length" @click="addStep">添加所选接口</n-button>
              </div>
            </div>
            <n-empty v-if="!endpointTree.length" size="small" description="请选择关联项目后添加接口" class="picker-empty" />
            <div v-else class="endpoint-picker-content">
              <aside class="endpoint-browser">
                <div class="browser-heading">浏览结构</div>
                <div v-for="project in endpointTree" :key="project.id" class="browser-project">
                  <div class="browser-node browser-project-node" :class="{ active: isActiveScope('project', project.id) }" @click="selectProjectScopeAndToggle(project.id)">
                    <n-checkbox :checked="isGroupChecked(project.modules)" :indeterminate="isGroupIndeterminate(project.modules)" @click.stop @update:checked="(checked) => toggleGroup(project.modules, checked)" />
                    <span class="browser-node-name">{{ project.name }}</span>
                    <span class="browser-node-count">{{ endpointCount(project.modules) }}</span>
                    <span class="browser-expand">{{ expandedProjects.includes(project.id) ? '⌄' : '›' }}</span>
                  </div>
                  <div v-show="expandedProjects.includes(project.id)" class="browser-module-list">
                    <div v-for="module in project.modules" :key="String(module.id)" class="browser-node browser-module-node" :class="{ active: isActiveScope('module', project.id, module.id) }" @click="selectScope('module', project.id, module.id)">
                      <n-checkbox :checked="isGroupChecked([module])" :indeterminate="isGroupIndeterminate([module])" @click.stop @update:checked="(checked) => toggleGroup([module], checked)" />
                      <span class="browser-node-name">{{ module.name }}</span>
                      <span class="browser-node-count">{{ module.endpoints.length }}</span>
                      <span class="browser-expand browser-expand-placeholder">·</span>
                    </div>
                  </div>
                </div>
              </aside>
              <section class="endpoint-list-panel">
                <div class="endpoint-list-head">
                  <span>接口列表</span>
                  <div><n-select v-model:value="endpointMethodFilter" :options="endpointMethodOptions" size="small" class="endpoint-method-filter" /><span class="loaded-count">已加载：{{ filteredEndpoints.length }} 个接口</span></div>
                </div>
                <div class="endpoint-table">
                  <div class="endpoint-table-row endpoint-table-header">
                    <n-checkbox :checked="isAllVisibleSelected" :indeterminate="isVisibleIndeterminate" @update:checked="toggleAllVisibleEndpoints" />
                    <span>接口名称</span><span>方法</span><span>路径</span><span>操作</span>
                  </div>
                  <div v-for="endpoint in filteredEndpoints" :key="endpoint.id" class="endpoint-table-row">
                    <n-checkbox :checked="selectedEndpoints.includes(endpoint.id)" @update:checked="(checked) => toggleEndpoint(endpoint.id, checked)" />
                    <span class="endpoint-table-name">{{ endpoint.name }}</span>
                    <span><span class="picker-method-tag" :style="methodStyle(endpoint.method)">{{ formatMethod(endpoint.method) }}</span></span>
                    <span class="endpoint-table-url">{{ endpoint.url }}</span>
                    <n-button text size="small" type="primary" @click="toggleEndpoint(endpoint.id, !selectedEndpoints.includes(endpoint.id))">{{ selectedEndpoints.includes(endpoint.id) ? '已选择' : '选择' }}</n-button>
                  </div>
                  <n-empty v-if="!filteredEndpoints.length" size="small" description="未找到匹配的接口" class="picker-table-empty" />
                </div>
              </section>
            </div>
          </div>
        </n-popover><n-button @click="addConditionNode"><template #icon><PhPlus/></template>判断分支</n-button></div>
     <div class="studio-tree">
      <draggable v-if="hasFlowNodes" v-model="steps" :item-key="flowNodeKey" handle=".drag-handle" @end="saveOrder">
       <template #item="{element,index}">
        <div class="studio-tree-node">
         <ScenarioFlowItem :name="element.node_type === 'condition' ? element.name : element.endpoint_name || '未命名接口'" :ordinal="String(index+1).padStart(2,'0')" :condition="element.node_type === 'condition'" :method="stepMethod(element)" :selected="element.node_type === 'condition' ? selectedConditionId === element.node_id : expandedId === element.id" :extracts="extractRuleCount(element.id)" :assertions="validateRuleCount(element.id)" :enabled="element.enabled !== false" :busy="togglingNodeId === element.node_id" :result="element.node_type === 'endpoint' ? runResults[element.id] : undefined" @select="selectStudioNode(element)" @toggle="toggleNodeEnabled(element, $event)" />
         <div v-if="element.node_type === 'condition'" class="studio-branches">
          <div v-for="branch in element.branches || []" :key="branch.id" class="studio-branch">
           <button class="studio-condition-chip" @click="selectStudioNode(element); openBranchEditor(element,branch)"><PhGitBranch/><span>{{ branchConditionSummary(branch) }}</span></button>
           <draggable v-model="branch.nodes" item-key="id" handle=".drag-handle" @end="saveBranchOrder(branch)"><template #item="{element:child,index:childIndex}">
            <ScenarioFlowItem :name="child.step_info?.endpoint_name || '未命名接口'" :ordinal="index+1+'.'+(childIndex+1)" :method="stepMethod(child.step_info)" :selected="expandedId === child.step_info?.id" :extracts="extractRuleCount(child.step_info?.id)" :assertions="validateRuleCount(child.step_info?.id)" :enabled="child.enabled !== false" :busy="togglingNodeId === child.id" :result="runResults[child.step_info?.id]" @select="selectStudioStep(child.step_info)" @toggle="toggleNodeEnabled(child,$event)"/>
           </template></draggable>
           <button class="studio-branch-add" @click="openBranchEndpointPicker(branch)"><PhPlus/>添加分支接口</button>
          </div>
         </div>
        </div>
       </template>
      </draggable>
      <n-empty v-else description="添加接口开始编排" class="studio-empty"/>
      <n-button block class="studio-add-bottom" @click="openEndpointPicker"><template #icon><PhPlus/></template>添加步骤</n-button>
     </div>
     <div class="studio-flow-footer"><PhDotsSixVertical/>拖动调整执行顺序</div>
    </aside>
    <main class="studio-main">
     <template v-for="element in selectedStudioSteps" :key="element.id">
      <section class="studio-editor">
       <header class="studio-editor-heading"><h2><span>{{ studioStepOrdinal(element.id) }}</span>{{ element.endpoint_name || '未命名接口' }}</h2><span class="studio-snapshot">场景独立配置</span><div class="studio-step-actions"><button class="studio-icon" title="复制步骤" @click="copyStudioStep(element)"><PhCopy/></button><n-dropdown :options="[{label:'删除步骤',key:'delete'}]" @select="removeStudioStep(element)"><button class="studio-icon" aria-label="更多步骤操作"><PhDotsThree/></button></n-dropdown><n-button type="primary" ghost :loading="runningStepId === element.id" @click="runStep(element)"><template #icon><PhPlay weight="fill"/></template>调试此步</n-button></div></header>
       <div class="studio-source"><span>来源：{{ studioStepSource(element) }}</span><button @click="openSourceEndpoint(element)">查看原接口 <PhArrowUpRight/></button></div>
       <div class="studio-request-target"><n-select class="request-method-select" :style="methodCssVars(stepMethod(element))" :value="stepMethod(element)" :options="requestMethodOptions" :render-label="renderRequestMethodLabel" aria-label="请求方式" @update:value="updateRequestMethod(element,$event)"/><n-input :value="stepUrl(element)" placeholder="请输入请求 URL" aria-label="请求 URL" @update:value="updateRequestUrl(element,$event)" @blur="saveStep(element)"/></div>
       <n-tabs v-model:value="activeConfigTabs[element.id]" type="line" class="step-config-tabs">
                <n-tab-pane name="request_override" tab="请求参数">
 <ScenarioRequestEditor :key="element.id" ref="requestPanel" :model-value="editText[element.id].request_override" :endpoint="element.endpoint_info" :suggestions="variableSuggestions(element)" @update:model-value="editText[element.id].request_override = $event" @save="saveStep(element)" @suggest="applySuggestion(element, $event)" />
 <div class="studio-policy-shell"><button class="studio-policy" @click="activeConfigTabs[element.id] = 'execution'"><PhCaretRight /><strong>执行策略</strong><span>{{ element.continue_on_failure !== false ? '失败后继续' : '失败后停止' }}</span><i></i><span>重试：{{ element.retry_on_failure ? element.failure_retry_count + ' 次' : '关闭' }}</span><i></i><span>轮询：{{ pollingConfigs[element.id]?.enabled ? '开启' : '关闭' }}</span><PhGear /></button></div>
 </n-tab-pane>
                <n-tab-pane name="extract" :tab="tabTitle(PhDatabase, '数据提取', extractRuleCount(element.id))">
                  <div class="extract-actions">
                    <span>执行后保存变量，后续接口优先使用 <code>${变量名}</code>，同时兼容 <code v-pre>{{变量名}}</code></span>
                    <n-button type="primary" @click.stop="addExtractRule(element)">＋ 添加提取规则</n-button>
                  </div>
                  <div class="extract-rule-table">
                    <div class="extract-rule-row extract-rule-header">
                      <span>变量名</span><span>提取方式</span><span>响应来源</span><span>表达式</span><span>结果索引 / 捕获组</span><span></span>
                    </div>
                    <div v-for="(rule, ruleIndex) in extractRules[element.id] || []" :key="`${element.id}-${ruleIndex}`" class="extract-rule-row">
                      <n-input v-model:value="rule.name" placeholder="如：token" size="small" @update:value="handleExtractNameInput(rule, $event)" @blur="saveStep(element)" />
                      <n-select v-model:value="rule.mode" :options="extractModeOptions" size="small" @update:value="handleExtractModeChange(element, rule)" />
                      <n-select v-model:value="rule.source" :options="rule.mode === 'jsonpath' ? jsonPathSourceOptions : extractSourceOptions" size="small" @update:value="saveStep(element)" />
                      <n-auto-complete v-if="rule.mode === 'jsonpath'" v-model:value="rule.expression" :options="responseExpressionOptions(element, rule)" :render-label="renderResponsePathLabel" :get-show="() => true" blur-after-select clearable size="small" placeholder="运行接口后可选择响应路径" @select="handleResponsePathSelect(rule, $event)" @blur="saveStep(element)" />
                      <n-input v-else v-model:value="rule.expression" placeholder="如：token=(.*?)& 或 code=(.+?)$" size="small" @blur="saveStep(element)" />
                      <n-input-number v-model:value="rule.index" :min="0" :show-button="false" size="small" @update:value="saveStep(element)" />
                      <n-button text type="error" class="delete-button" size="small" @click.stop="removeExtractRule(element, ruleIndex)">删除</n-button>
                      <ExtractProcessorEditor v-model="rule.processors" @change="saveStep(element)" />
                    </div>
                    <n-empty v-if="!(extractRules[element.id] || []).length" size="small" description="暂无提取规则" class="extract-empty" />
                  </div>
                  <div class="extract-tip">
                    JSONPath 示例：<code>$.data.token</code>；正则示例：<code>token=(.*?)&amp;</code>、<code>code=(.+?)$</code>。正则的“捕获组”填 <code>1</code> 可取得括号中的内容，<code>0</code> 表示完整匹配。
                  </div>
                </n-tab-pane>
                <n-tab-pane name="validate" :tab="tabTitle(PhShieldCheck, '断言', validateRuleCount(element.id))">
                  <div class="extract-actions">
                    <span>实际值使用 JSONPath：<code>$.data.code</code>、<code>$.status_code</code>；期望值支持 <code>${变量名}</code>，可引用前序及当前接口提取的变量</span>
                    <n-button type="primary" @click.stop="addValidateRule(element)">＋ 添加断言</n-button>
                  </div>
                  <div class="validate-rule-table">
                    <div class="validate-rule-row validate-rule-header">
                      <span>实际值</span><span>断言方式</span><span>期望值</span><span></span>
                    </div>
                    <div v-for="(rule, ruleIndex) in validateRules[element.id] || []" :key="`${element.id}-validate-${ruleIndex}`" class="validate-rule-row">
                      <n-input v-model:value="rule.actual" placeholder="如：$.data.code" size="small" @blur="saveStep(element)" />
                      <n-select v-model:value="rule.type" :options="validateTypeOptions" size="small" @update:value="saveStep(element)" />
                      <n-input v-model:value="rule.expected" placeholder="如：200 或 ${token}" size="small" @blur="saveStep(element)" />
                      <n-button text type="error" class="delete-button" size="small" @click.stop="removeValidateRule(element, ruleIndex)">删除</n-button>
                    </div>
                    <n-empty v-if="!(validateRules[element.id] || []).length" size="small" description="暂无断言规则" class="extract-empty" />
                  </div>
                </n-tab-pane>
                <n-tab-pane name="post_sql" :tab="tabTitle(PhDatabase, '后置数据库', postSqlCount(element.id))">
                  <div class="extract-actions">
                    <span>仅在接口响应、断言、数据提取均成功后执行。UPDATE 需在数据库连接中开启写入权限。</span>
                    <n-button type="primary" @click.stop="addPostSql(element)">＋ 添加数据库操作</n-button>
                  </div>
                  <div class="post-sql-list">
                    <div v-for="(_sql, sqlIndex) in postSqlRules[element.id] || []" :key="`${element.id}-post-sql-${sqlIndex}`" class="post-sql-row">
                      <n-input v-model:value="postSqlRules[element.id][sqlIndex]" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" placeholder='${execute_sql_mysql("UPDATE orders SET status=%s WHERE order_id=%s")}' @blur="saveStep(element)" />
                      <n-button text type="error" class="delete-button" size="small" @click.stop="removePostSql(element, sqlIndex)">删除</n-button>
                    </div>
                    <n-empty v-if="!(postSqlRules[element.id] || []).length" size="small" description="暂无后置数据库操作" class="extract-empty" />
                  </div>
                  <div class="extract-tip">每个 <code>%s</code> 前须写成 <code>字段=%s</code>，平台按字段名寻找已提取变量。例如：<code>${execute_sql_mysql("UPDATE orders SET status=%s WHERE order_id=%s")}</code>。</div>
                </n-tab-pane>
                <n-tab-pane name="polling" :tab="tabTitle(PhClock, '轮询', undefined, pollingConfigs[element.id]?.enabled)">
                  <div class="polling-config">
                    <div class="polling-tab-title"><span>轮询等待</span><n-switch v-model:value="pollingConfigs[element.id].enabled" @update:value="saveStep(element)" /></div>
                    <template v-if="pollingConfigs[element.id]?.enabled">
                      <div class="polling-grid">
                        <label>总超时时间（秒）<n-input-number v-model:value="pollingConfigs[element.id].timeout" :min="1" :show-button="false" @update:value="saveStep(element)" /></label>
                        <label>轮询间隔（秒）<n-input-number v-model:value="pollingConfigs[element.id].interval" :min="1" :show-button="false" @update:value="saveStep(element)" /></label>
                        <label>首次等待（秒）<n-input-number v-model:value="pollingConfigs[element.id].initial_delay" :min="0" :show-button="false" @update:value="saveStep(element)" /></label>
                      </div>
                      <div class="polling-checkboxes">
                        <n-checkbox v-model:checked="pollingConfigs[element.id].retry_http_error" @update:checked="saveStep(element)">HTTP 4xx/5xx 时继续重试</n-checkbox>
                        <n-checkbox v-model:checked="pollingConfigs[element.id].retry_assertion" :disabled="validateRuleCount(element.id) === 0" @update:checked="saveStep(element)">断言不满足时继续重试</n-checkbox>
                      </div>
                      <n-alert type="info" :show-icon="false" class="polling-tip">{{ validateRuleCount(element.id) ? '已配置的断言为轮询成功条件，满足全部断言即停止。' : '当前未配置断言，HTTP 2xx/3xx 响应即视为轮询成功。' }} HTTP 4xx/5xx 是否继续轮询由上方选项控制；仅成功响应的数据提取会写入后续变量。</n-alert>
                    </template>
                  </div>
                </n-tab-pane>
                <n-tab-pane name="execution" :tab="tabTitle(PhShieldCheck, '执行控制', undefined, element.continue_on_failure !== false || element.retry_on_failure)">
                  <section class="execution-control-list">
                    <div class="execution-control-card">
                      <div><strong>接口失败后继续执行</strong><span>开启后，本接口最终失败仍会执行后续接口；场景最终结果仍会标记为失败。</span></div>
                      <n-switch v-model:value="element.continue_on_failure" @update:value="saveStep(element)" />
                    </div>
                    <div class="execution-control-card">
                      <div><strong>失败后重试</strong><span>当前接口完整执行失败后重新执行；重试结束后再判断是否继续后续步骤。</span></div>
                      <div class="execution-control-actions">
                        <template v-if="element.retry_on_failure"><n-input-number v-model:value="element.failure_retry_count" :min="1" :max="5" :precision="0" size="small" @update:value="saveStep(element)" /><span>次</span></template>
                        <n-switch v-model:value="element.retry_on_failure" @update:value="handleRetryToggle(element)" />
                      </div>
                    </div>
                  </section>
                </n-tab-pane>
              </n-tabs>
      </section>
      <ScenarioResultPanel :result="runResults[element.id]" :running="scenarioRunning || runningStepId === element.id" :finished-at="latestScenarioRun?.finishedAt" :summary="sceneRunState" :duration="latestScenarioRun ? formatDuration(latestScenarioRun.durationMs) : ''" :logs="studioRunLogs"/>
     </template>
     <section v-if="selectedStudioCondition" class="studio-editor studio-condition-editor">
      <header class="studio-editor-heading"><h2><PhDiamond/>{{ selectedStudioCondition.name }}</h2><n-button @click="openConditionEditor(selectedStudioCondition)">编辑条件</n-button></header><p>从上到下匹配，第一个满足条件的分支进入执行，完成后继续主流程。</p>
      <section v-for="branch in selectedStudioCondition.branches || []" :key="branch.id" class="studio-condition-detail"><header><strong>{{ branch.name }}</strong><n-space><n-button text type="primary" @click="openBranchEditor(selectedStudioCondition,branch)">编辑</n-button><n-button text type="error" @click="removeBranch(branch)">删除</n-button></n-space></header><p>{{ branchConditionSummary(branch) }}</p><n-button @click="openBranchEndpointPicker(branch)">添加分支接口</n-button></section>
      <n-space><n-button type="primary" ghost @click="addBranch(selectedStudioCondition)">添加分支</n-button><n-button class="condition-delete-button" type="error" @click="removeFlowNode(selectedStudioCondition)">删除判断节点</n-button></n-space>
     </section>
     <section v-if="!selectedStudioSteps.length && !selectedStudioCondition" class="studio-editor studio-start"><PhTreeStructure/><h2>编排你的接口场景</h2><p>从左侧添加接口或选择步骤，配置请求、提取与断言。</p><n-button type="primary" @click="openEndpointPicker">添加接口</n-button></section>
    </main>
    <aside class="studio-variables">
     <header><strong>可用变量</strong><button class="studio-icon" :aria-label="sceneVariablesCollapsed ? '展开可用变量' : '收起可用变量'" @click="sceneVariablesCollapsed = !sceneVariablesCollapsed"><PhCaretUp :class="{collapsed:sceneVariablesCollapsed}"/></button></header>
     <div v-show="!sceneVariablesCollapsed" class="studio-variable-content">
      <n-input v-model:value="sceneVariableSearch" clearable placeholder="搜索变量名或来源"><template #prefix><PhMagnifyingGlass/></template></n-input>
      <nav class="studio-variable-tabs"><button v-for="tab in studioVariableTabs" :key="tab.key" :class="{active:sceneVariableCategory === tab.key}" @click="sceneVariableCategory = tab.key">{{ tab.label }}<b>{{ tab.count }}</b></button></nav>
      <div class="studio-variable-groups"><section v-for="group in studioVariableGroups" :key="group.key" class="studio-variable-group">
       <h3><PhCircle weight="fill" :class="'dot-'+group.key"/>{{ group.label }}</h3>
       <div v-for="variable in group.items" :key="variable.key" class="studio-variable-row"><div class="studio-variable-name"><code>{{ variable.reference }}</code><button class="studio-icon" title="复制变量" @click="copySceneVariable(variable)"><PhCopy/></button><button class="studio-reference" @click="referenceStudioVariable(variable)">引用</button></div><p v-if="variable.category === 'extract'" class="studio-variable-source">{{ variable.source }}</p><div class="studio-variable-value"><span>{{ sceneVariableDisplayValue(variable) }}</span><button v-if="variable.sensitive" class="studio-icon" :aria-label="revealedVariableKeys.has(variable.key) ? '隐藏变量值' : '显示变量值'" @click="toggleVariableVisibility(variable.key)"><PhEyeSlash v-if="revealedVariableKeys.has(variable.key)"/><PhEye v-else/></button></div></div>
      </section><n-empty v-if="!studioVariableGroups.length" size="small" description="暂无可用变量"/></div>
     </div><footer><PhInfo/>仅显示当前步骤可用的上游变量</footer>
    </aside>
   </div>
   <n-modal v-model:show="branchEditorVisible" preset="card" :title="editingConditionOnly ? '编辑判断节点' : (editingBranch?.id ? '编辑分支' : '新增分支')" class="branch-editor-modal" :style="{ width: 'min(760px, calc(100vw - 32px))' }">
      <n-form label-placement="top">
        <div class="branch-editor-top"><n-form-item :label="editingConditionOnly ? '判断名称' : '分支名称'"><n-input v-model:value="branchForm.name" /></n-form-item></div>
        <n-form-item label="条件关系"><n-radio-group v-model:value="branchForm.logic"><n-radio value="and">满足全部条件</n-radio><n-radio value="or">满足任一条件</n-radio></n-radio-group></n-form-item>
        <template v-if="!editingConditionOnly"><div v-for="(condition, conditionIndex) in branchForm.conditions" :key="conditionIndex" class="condition-editor-row"><n-select v-model:value="condition.source" :options="conditionSourceOptions" /><n-select v-if="condition.source === 'step'" v-model:value="condition.step_id" :options="upstreamStepOptions" filterable placeholder="选择上游接口" /><n-input v-else v-model:value="condition.variable" placeholder="变量名，如 orderStatus" /><n-input v-if="condition.source === 'step'" v-model:value="condition.path" placeholder="JSONPath，如 $.data.status" /><n-select v-model:value="condition.operator" :options="conditionOperatorOptions" /><n-input v-if="!['exists', 'not_exists'].includes(condition.operator)" v-model:value="condition.expected" placeholder="期望值" /><n-button class="condition-row-delete" text type="error" :disabled="branchForm.conditions.length === 1" @click="branchForm.conditions.splice(conditionIndex, 1)">删除</n-button></div><n-button class="branch-condition-add" dashed size="small" @click="addConditionRule">＋ 添加条件</n-button></template>
      </n-form>
      <template #footer><n-space justify="end"><n-button class="branch-editor-cancel" @click="branchEditorVisible = false">取消</n-button><n-button class="branch-editor-save" type="primary" :loading="branchSaving" @click="saveBranch">保存</n-button></n-space></template>
    </n-modal>

    <n-modal v-model:show="branchEndpointPickerVisible" preset="card" title="添加分支接口" :style="{ width: 'min(980px, calc(100vw - 32px))' }">
      <div class="picker-toolbar"><span class="picker-title">选择接口</span><div class="picker-actions"><n-input v-model:value="branchEndpointSearch" size="small" clearable placeholder="搜索接口名称或路径..." class="picker-search"><template #prefix>⌕</template></n-input><n-button size="small" @click="toggleAllBranchEndpoints(true)">全选</n-button><n-button size="small" @click="invertBranchVisibleEndpoints">反选</n-button><n-button size="small" type="error" secondary :disabled="!branchEndpointIds.length" @click="branchEndpointIds = []">清空已选</n-button></div></div>
      <div class="endpoint-picker-content"><aside class="endpoint-browser"><div class="browser-heading">浏览结构</div><div v-for="project in endpointTree" :key="project.id" class="browser-project"><div class="browser-node browser-project-node" :class="{ active: isBranchScope('project', project.id) }" @click="selectBranchProjectScopeAndToggle(project.id)"><n-checkbox :checked="isBranchGroupChecked(project.modules)" :indeterminate="isBranchGroupIndeterminate(project.modules)" @click.stop @update:checked="(checked) => toggleBranchGroup(project.modules, checked)" /><span class="browser-node-name">{{ project.name }}</span><span class="browser-node-count">{{ endpointCount(project.modules) }}</span><span class="browser-expand">{{ expandedBranchProjects.includes(project.id) ? '⌄' : '›' }}</span></div><div v-show="expandedBranchProjects.includes(project.id)" class="browser-module-list"><div v-for="module in project.modules" :key="String(module.id)" class="browser-node browser-module-node" :class="{ active: isBranchScope('module', project.id, module.id) }" @click="selectBranchScope('module', project.id, module.id)"><n-checkbox :checked="isBranchGroupChecked([module])" :indeterminate="isBranchGroupIndeterminate([module])" @click.stop @update:checked="(checked) => toggleBranchGroup([module], checked)" /><span class="browser-node-name">{{ module.name }}</span><span class="browser-node-count">{{ module.endpoints.length }}</span><span class="browser-expand browser-expand-placeholder">·</span></div></div></div></aside><section class="endpoint-list-panel"><div class="endpoint-list-head"><span>接口列表</span><div><n-select v-model:value="branchEndpointMethodFilter" :options="endpointMethodOptions" size="small" class="endpoint-method-filter" /><span class="loaded-count">已加载：{{ branchFilteredEndpoints.length }} 个接口</span></div></div><div class="endpoint-table"><div class="endpoint-table-row endpoint-table-header"><n-checkbox :checked="isAllBranchVisibleSelected" :indeterminate="isBranchVisibleIndeterminate" @update:checked="toggleAllBranchEndpoints" /><span>接口名称</span><span>方法</span><span>路径</span><span>操作</span></div><div v-for="endpoint in branchFilteredEndpoints" :key="endpoint.id" class="endpoint-table-row"><n-checkbox :checked="branchEndpointIds.includes(endpoint.id)" @update:checked="(checked) => toggleBranchEndpoint(endpoint.id, checked)" /><span class="endpoint-table-name">{{ endpoint.name }}</span><span><span class="picker-method-tag" :style="methodStyle(endpoint.method)">{{ formatMethod(endpoint.method) }}</span></span><span class="endpoint-table-url">{{ endpoint.url }}</span><n-button text size="small" type="primary" @click="toggleBranchEndpoint(endpoint.id, !branchEndpointIds.includes(endpoint.id))">{{ branchEndpointIds.includes(endpoint.id) ? '已选择' : '选择' }}</n-button></div><n-empty v-if="!branchFilteredEndpoints.length" size="small" description="未找到匹配的接口" class="picker-table-empty" /></div></section></div>
      <template #footer><n-space justify="end"><n-button @click="branchEndpointPickerVisible = false">取消</n-button><n-button type="primary" :disabled="!branchEndpointIds.length" @click="addEndpointsToBranch">添加接口</n-button></n-space></template>
    </n-modal>

    <n-modal v-model:show="branchStepEditorVisible" preset="card" :title="`编辑分支接口 · ${branchEditingStep?.endpoint_name || ''}`" :style="{ width: 'min(920px, calc(100vw - 32px))' }">
      <template v-if="branchEditingStep"><div class="branch-step-editor-info"><span class="method-pill" :style="methodStyle(branchEditingStep.endpoint_info?.method)">{{ formatMethod(branchEditingStep.endpoint_info?.method) }}</span><strong>{{ branchEditingStep.endpoint_name }}</strong><code>{{ branchEditingStep.endpoint_info?.url }}</code></div><n-tabs v-model:value="activeConfigTabs[branchEditingStep.id]" type="line">
        <n-tab-pane name="request_override" tab="参数覆盖"><div class="editor-modal-actions"><span>支持静态值、变量和函数。</span><n-space><n-button size="small" @click="formatOverride(branchEditingStep)">格式化</n-button><n-button size="small" @click="restoreOverride(branchEditingStep)">从接口默认值恢复</n-button></n-space></div><div class="json-editor compact-editor"><pre class="editor-gutter">{{ lineNumbers(editText[branchEditingStep.id]?.request_override) }}</pre><n-input v-model:value="editText[branchEditingStep.id].request_override" type="textarea" :autosize="{ minRows: 12, maxRows: 20 }" @focus="rememberRequestEditorCursor(branchEditingStep, $event)" @click="rememberRequestEditorCursor(branchEditingStep, $event)" @keyup="rememberRequestEditorCursor(branchEditingStep, $event)" @blur="saveStep(branchEditingStep)" /></div></n-tab-pane>
        <n-tab-pane name="extract" tab="数据提取"><div class="extract-actions"><span>执行后保存变量，供之后接口引用。</span><n-button size="small" @click="addExtractRule(branchEditingStep)">＋ 添加提取规则</n-button></div><div class="extract-rule-table"><div v-for="(rule, ruleIndex) in extractRules[branchEditingStep.id] || []" :key="ruleIndex" class="extract-rule-row"><n-input v-model:value="rule.name" placeholder="变量名" size="small" @update:value="handleExtractNameInput(rule, $event)" @blur="saveStep(branchEditingStep)" /><n-select v-model:value="rule.mode" :options="extractModeOptions" size="small" @update:value="handleExtractModeChange(branchEditingStep, rule)" /><n-select v-model:value="rule.source" :options="rule.mode === 'jsonpath' ? jsonPathSourceOptions : extractSourceOptions" size="small" @update:value="saveStep(branchEditingStep)" /><n-auto-complete v-if="rule.mode === 'jsonpath'" v-model:value="rule.expression" :options="responseExpressionOptions(branchEditingStep, rule)" :render-label="renderResponsePathLabel" :get-show="() => true" blur-after-select clearable size="small" placeholder="运行接口后可选择响应路径" @select="handleResponsePathSelect(rule, $event)" @blur="saveStep(branchEditingStep)" /><n-input v-else v-model:value="rule.expression" placeholder="如：token=(.*?)& 或 code=(.+?)$" size="small" @blur="saveStep(branchEditingStep)" /><n-input-number v-model:value="rule.index" :min="0" :show-button="false" size="small" @update:value="saveStep(branchEditingStep)" /><n-button text type="error" @click="removeExtractRule(branchEditingStep, ruleIndex)">删除</n-button><ExtractProcessorEditor v-model="rule.processors" @change="saveStep(branchEditingStep)" /></div></div></n-tab-pane>
        <n-tab-pane name="validate" tab="断言"><div class="extract-actions"><span>使用 JSONPath 或变量进行断言。</span><n-button size="small" @click="addValidateRule(branchEditingStep)">＋ 添加断言</n-button></div><div class="validate-rule-table"><div v-for="(rule, ruleIndex) in validateRules[branchEditingStep.id] || []" :key="ruleIndex" class="validate-rule-row"><n-input v-model:value="rule.actual" placeholder="$.data.code" size="small" @blur="saveStep(branchEditingStep)" /><n-select v-model:value="rule.type" :options="validateTypeOptions" size="small" @update:value="saveStep(branchEditingStep)" /><n-input v-model:value="rule.expected" placeholder="期望值" size="small" @blur="saveStep(branchEditingStep)" /><n-button text type="error" @click="removeValidateRule(branchEditingStep, ruleIndex)">删除</n-button></div></div></n-tab-pane>
        <n-tab-pane name="post_sql" tab="后置数据库"><div class="extract-actions"><span>接口成功后执行数据库操作。</span><n-button size="small" @click="addPostSql(branchEditingStep)">＋ 添加数据库操作</n-button></div><div class="post-sql-list"><div v-for="(_sql, sqlIndex) in postSqlRules[branchEditingStep.id] || []" :key="sqlIndex" class="post-sql-row"><n-input v-model:value="postSqlRules[branchEditingStep.id][sqlIndex]" type="textarea" placeholder="${execute_sql_mysql(...)}" @blur="saveStep(branchEditingStep)" /><n-button text type="error" @click="removePostSql(branchEditingStep, sqlIndex)">删除</n-button></div></div></n-tab-pane>
        <n-tab-pane name="polling" tab="轮询"><n-form label-placement="left" label-width="120"><n-form-item label="开启轮询"><n-switch v-model:value="pollingConfigs[branchEditingStep.id].enabled" @update:value="saveStep(branchEditingStep)" /></n-form-item><template v-if="pollingConfigs[branchEditingStep.id].enabled"><n-form-item label="超时时间（秒）"><n-input-number v-model:value="pollingConfigs[branchEditingStep.id].timeout" :min="1" @update:value="saveStep(branchEditingStep)" /></n-form-item><n-form-item label="轮询间隔（秒）"><n-input-number v-model:value="pollingConfigs[branchEditingStep.id].interval" :min="1" @update:value="saveStep(branchEditingStep)" /></n-form-item><n-form-item label="首次等待（秒）"><n-input-number v-model:value="pollingConfigs[branchEditingStep.id].initial_delay" :min="0" @update:value="saveStep(branchEditingStep)" /></n-form-item><n-checkbox v-model:checked="pollingConfigs[branchEditingStep.id].retry_http_error" @update:checked="saveStep(branchEditingStep)">HTTP 4xx/5xx 时继续重试</n-checkbox><n-checkbox v-model:checked="pollingConfigs[branchEditingStep.id].retry_assertion" :disabled="validateRuleCount(branchEditingStep.id) === 0" @update:checked="saveStep(branchEditingStep)">断言不满足时继续重试</n-checkbox><n-alert type="info" :show-icon="false" class="polling-tip">{{ validateRuleCount(branchEditingStep.id) ? '已配置的断言为轮询成功条件，满足全部断言即停止。' : '当前未配置断言，HTTP 2xx/3xx 响应即视为轮询成功。' }} HTTP 4xx/5xx 是否继续轮询由上方选项控制。</n-alert></template></n-form></n-tab-pane>
        <n-tab-pane name="execution" tab="执行控制"><section class="execution-control-list"><div class="execution-control-card"><div><strong>接口失败后继续执行</strong><span>开启后，本接口最终失败仍会执行后续接口；场景最终结果仍会标记为失败。</span></div><n-switch v-model:value="branchEditingStep.continue_on_failure" @update:value="saveStep(branchEditingStep)" /></div><div class="execution-control-card"><div><strong>失败后重试</strong><span>当前接口完整执行失败后重新执行；重试结束后再判断是否继续后续步骤。</span></div><div class="execution-control-actions"><template v-if="branchEditingStep.retry_on_failure"><n-input-number v-model:value="branchEditingStep.failure_retry_count" :min="1" :max="5" :precision="0" size="small" @update:value="saveStep(branchEditingStep)" /><span>次</span></template><n-switch v-model:value="branchEditingStep.retry_on_failure" @update:value="handleRetryToggle(branchEditingStep)" /></div></div></section></n-tab-pane>
      </n-tabs></template>
      <template #footer><n-space justify="end"><n-button @click="branchStepEditorVisible = false">关闭</n-button><n-button type="primary" @click="saveBranchStep">保存</n-button></n-space></template>
    </n-modal>

    <n-card v-if="!scenarioCreated" :bordered="false" class="scene-card save-tip">
      填写场景基本信息后，可直接选择接口并添加步骤，系统会自动保存场景。
    </n-card>
  </div></n-config-provider>
</template>

<script lang="ts" setup>
import { asList } from '@/utils/list';
import { formatDurationMilliseconds as formatDuration } from '@/utils/time';

  defineOptions({ name: 'case_api_scenario_edit' });
  import { computed, h, nextTick, onMounted, reactive, ref, watch } from 'vue';
  import draggable from 'vuedraggable';
  import { useMessage } from 'naive-ui';
  import { useRoute, useRouter } from 'vue-router';
  import { PhArrowClockwise, PhBracketsCurly, PhCaretUp, PhCircle, PhClock, PhDatabase, PhEye, PhEyeSlash, PhFileText, PhInfo, PhMagnifyingGlass, PhPackage, PhPlay, PhShieldCheck, PhSlidersHorizontal, PhSparkle } from '@phosphor-icons/vue';
  import { EndpointAPI, ScenarioAPI, ScenarioBranchAPI, ScenarioFlowNodeAPI, ScenarioStepAPI } from '@/api/case_api/http';
  import type { ScenarioBranch, ScenarioBranchCondition } from '@/api/case_api/models';
  import { DynamicFunctionAPI, EnvironmentAPI, ModuleAPI, ProjectAPI, ProjectVariableAPI } from '@/api/project/http';
  import { useSubmitRedirect } from '@/hooks/web/useSubmitRedirect';
  import ExtractProcessorEditor from './components/ExtractProcessorEditor.vue';
  import ScenarioFlowItem from './components/ScenarioFlowItem.vue';
  import ScenarioRequestEditor from './components/ScenarioRequestEditor.vue';
  import ScenarioResultPanel from './components/ScenarioResultPanel.vue';
  import { PhArrowUpRight, PhCaretRight, PhCheckCircle, PhCopy, PhDiamond, PhDotsSixVertical, PhDotsThree, PhFloppyDisk, PhGear, PhGitBranch, PhPlus, PhTreeStructure } from '@phosphor-icons/vue';
  import { defaultExtractRule, extractRuleFromConfig, extractRuleToConfig, type ExtractRule } from './extract-processors';

  const route = useRoute();
  const router = useRouter();
  let id = Number(route.params.id) || 0;
  const message = useMessage();
  const { redirectAfterSubmit } = useSubmitRedirect();
  const formRef = ref<any>();
  const scenarioApi = new ScenarioAPI();
  const stepApi = new ScenarioStepAPI();
  const flowNodeApi = new ScenarioFlowNodeAPI();
  const branchApi = new ScenarioBranchAPI();
  const endpointApi = new EndpointAPI();
  const endpointModuleApi = new ModuleAPI();
  const projectApi = new ProjectAPI();
  const projectVariableApi = new ProjectVariableAPI();
  const dynamicFunctionApi = new DynamicFunctionAPI();
  const environmentApi = new EnvironmentAPI();
  const projectOptions = ref<any[]>([]);
  const projectVariables = ref<Array<{ id?: number; name: string; value: string; description?: string; project_name?: string }>>([]);
  const dynamicFunctions = ref<any[]>([]);
  const sceneVariableSearch = ref('');
  const sceneVariableCategory = ref<'all' | 'project' | 'function' | 'extract'>('all');
  const sceneVariablesCollapsed = ref(false);
  const revealedVariableKeys = ref(new Set<string>());
  const requestEditorCursor = ref<{ stepId: number; start: number; end: number } | null>(null);
  const availableEndpoints = ref<any[]>([]);
  const endpointModules = ref<any[]>([]);
  const steps = ref<any[]>([]);
  const branchEditorVisible = ref(false);
  const branchEndpointPickerVisible = ref(false);
  const branchSaving = ref(false);
  const editingConditionNode = ref<any>(null);
  const editingBranch = ref<any>(null);
  const editingConditionOnly = ref(false);
  const targetBranch = ref<any>(null);
  const collapsedConditionIds = ref(new Set<number>());
  const collapsedBranchIds = ref(new Set<number>());
  const branchEndpointIds = ref<number[]>([]);
  const branchEndpointSearch = ref('');
  const branchEndpointMethodFilter = ref('all');
  const expandedBranchProjects = ref<number[]>([]);
  const branchActiveScope = ref<{ type: 'all' | 'project' | 'module'; projectId?: number; moduleId?: number | null }>({ type: 'all' });
  const branchStepEditorVisible = ref(false);
  const branchEditingStep = ref<any>(null);
  const branchForm = reactive<{ name: string; logic: 'and' | 'or'; conditions: ScenarioBranchCondition[] }>({ name: '', logic: 'and', conditions: [] });
  const conditionSourceOptions = [{ label: '上游接口响应', value: 'step' }, { label: '已提取变量', value: 'variable' }];
  const conditionOperatorOptions = [
    ['equals', '等于'], ['not_equals', '不等于'], ['gt', '大于'], ['gte', '大于等于'], ['lt', '小于'], ['lte', '小于等于'], ['contains', '包含'], ['not_contains', '不包含'], ['exists', '存在'], ['not_exists', '不存在'], ['regex', '正则匹配'], ['in', '属于列表'],
  ].map(([value, label]) => ({ value, label }));
  const selectedEndpoints = ref<number[]>([]);
  const endpointPickerVisible = ref(false);
  const endpointSearch = ref('');
  const endpointMethodFilter = ref('all');
  const expandedProjects = ref<number[]>([]);
  const activeScope = ref<{ type: 'all' | 'project' | 'module'; projectId?: number; moduleId?: number | null }>({ type: 'all' });
  const expandedId = ref<number | null>(null);
  const scenarioCreated = ref(Boolean(id));
  const editingRequestTargetIds = reactive(new Set<number>());
  const runEnvironment = ref<number | null>(null);
  const environmentOptions = ref<any[]>([]);
  const allEnvironments = ref<any[]>([]);
  const scenarioRunning = ref(false);
  const latestScenarioRun = ref<{ durationMs: number; finishedAt: string } | null>(null);
  const runningStepId = ref<number | null>(null);
  const runResults = reactive<Record<number, any>>({});
  const responseSearch = reactive<Record<number, string>>({});
  const responseSearchIndex = reactive<Record<number, number>>({});
  const responseBodyRefs = new Map<number, HTMLElement>();
  const environmentNames = ['Dev', 'Test', 'Pre', 'Prod'];
  const normalizeId = (value: unknown) => {
    const normalized = Number(value);
    return Number.isFinite(normalized) ? normalized : null;
  };
  const buildProjectEnvironmentOptions = (environments: any[], projectIds: number[]) => {
    const selectedProjectIds = Array.from(new Set(projectIds.map(normalizeId).filter((value): value is number => value !== null)));
    if (!selectedProjectIds.length) return [];

    // 多项目场景只能选择所有项目都已配置的同名环境。选项值取首个项目对应的
    // Environment ID，执行器再依据环境名称为每个项目解析各自的环境配置。
    const sharedNames = environmentNames.filter((name) => selectedProjectIds.every((projectId) =>
      environments.some((item) => normalizeId(item.project) === projectId && item.name === name),
    ));
    const primaryProjectId = selectedProjectIds[0];
    return sharedNames.map((name) => {
      const environment = environments.find((item) => normalizeId(item.project) === primaryProjectId && item.name === name);
      return { label: name, value: Number(environment.id) };
    });
  };
  const refreshEnvironmentOptions = (notifyWhenCleared = false) => {
    const previousEnvironmentId = runEnvironment.value;
    const previousEnvironmentName = allEnvironments.value.find((item) => Number(item.id) === Number(previousEnvironmentId))?.name;
    const nextOptions = buildProjectEnvironmentOptions(allEnvironments.value, form.projects);
    environmentOptions.value = nextOptions;

    if (!previousEnvironmentId) return;
    const replacement = nextOptions.find((item) => item.label === previousEnvironmentName);
    if (replacement) {
      // 关联项目的顺序变化时，同名环境仍然保留，但要切换为首个项目对应的环境 ID。
      runEnvironment.value = replacement.value;
      return;
    }
    runEnvironment.value = null;
    if (notifyWhenCleared) message.warning('当前执行环境不属于所选项目，请重新选择');
  };
  type ValidateRule = { type: 'equals' | 'not_equals' | 'greater_than' | 'less_than' | 'contains'; actual: string; expected: string };
  type PollingConfig = { enabled: boolean; timeout: number; interval: number; initial_delay: number; retry_http_error: boolean; retry_assertion: boolean };
  type AvailableVariable = { name: string; stepId: number; stepOrder: number; stepName: string; expression: string; scope?: 'project' | 'step'; projectName?: string };
  type SceneVariableCategory = 'project' | 'function' | 'extract';
  type SceneVariableItem = {
    key: string;
    name: string;
    reference: string;
    category: SceneVariableCategory;
    value: string;
    source: string;
    sensitive?: boolean;
  };
  type SceneVariableGroup = {
    key: SceneVariableCategory;
    label: string;
    detail: string;
    items: SceneVariableItem[];
  };
  type VariableSuggestion = {
    key: string; sourceLabel: string; field: 'headers' | 'params' | 'data' | 'json'; fieldLabel: string;
    parameter: string; variableName: string; reference: string; extract?: ExtractRule; extractStepId?: number; extractLabel?: string;
  };
  const editText = reactive<Record<number, { request_override: string }>>({});
  const extractRules = reactive<Record<number, ExtractRule[]>>({});
  const validateRules = reactive<Record<number, ValidateRule[]>>({});
  const postSqlRules = reactive<Record<number, string[]>>({});
  const pollingConfigs = reactive<Record<number, PollingConfig>>({});
  const activeConfigTabs = reactive<Record<number, string>>({});
  const extractModeOptions = [
    { label: 'JSONPath', value: 'jsonpath' },
    { label: '正则（re）', value: 're' },
  ];
  const extractSourceOptions = [
    { label: 'JSON', value: 'json' },
    { label: '响应文本', value: 'text' },
    { label: '响应头', value: 'headers' },
  ];
  const jsonPathSourceOptions = [
    { label: 'JSON', value: 'json' },
    { label: '响应头', value: 'headers' },
  ];
  const validateTypeOptions = [
    { label: '相等', value: 'equals' },
    { label: '不等于', value: 'not_equals' },
    { label: '大于', value: 'greater_than' },
    { label: '小于', value: 'less_than' },
    { label: '包含', value: 'contains' },
  ];
  const requestMethodOptions = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'].map((value) => ({ label: value, value }));
  const tabTitle = (icon: any, label: string, count?: number, enabled = false) => () => h('span', { class: 'tab-title' }, [
    h(icon, { size: 18, weight: 'bold' }), h('span', label),
    typeof count === 'number' ? h('b', { class: count > 0 ? 'on' : undefined }, String(count)) : null,
    enabled ? h('i', { class: 'tab-status-dot', title: '已启用' }) : null,
  ]);
  const form = reactive({ projects: [] as number[], name: '', description: '' });
  const savedFormSignature = ref('');
  const formSignature = computed(() => JSON.stringify([form.name, form.description, form.projects]));
  const rules = {
    projects: { required: true, type: 'array', min: 1, message: '请至少选择一个项目', trigger: 'change' },
    name: { required: true, message: '请输入场景名称', trigger: 'blur' },
  };

  const selectedProjectLabels = computed(() => {
    const selected = new Set(form.projects);
    return projectOptions.value.filter((item) => selected.has(item.value)).map((item) => item.label).join('、');
  });
  const selectedEnvironmentLabel = computed(() => environmentOptions.value.find((item) => item.value === runEnvironment.value)?.label || '');
  const environmentPlaceholder = computed(() => {
    if (!form.projects.length) return '请先选择关联项目';
    if (!environmentOptions.value.length) return form.projects.length > 1 ? '所选项目没有共同环境' : '该项目暂未配置环境';
    return '请选择环境';
  });
  const hasFlowNodes = computed(() => steps.value.length > 0);
  const flowNodeKey = (node: any) => {
    const flowNodeId = Number(node?.node_id);
    if (Number.isFinite(flowNodeId) && flowNodeId > 0) return `flow-${flowNodeId}`;
    const type = node?.node_type || 'endpoint';
    const sourceId = node?.step_id || node?.step || node?.id || node?.name || 'new';
    return `${type}-${sourceId}`;
  };
  const allEndpointSteps = computed(() => steps.value.flatMap((node: any) => {
    if (node.node_type === 'condition') {
      return (node.branches || []).flatMap((branch: any) => (branch.nodes || []).map((child: any) => child.step_info).filter(Boolean));
    }
    return [node];
  }));
  const sceneStats = computed(() => ({
    steps: allEndpointSteps.value.length,
    branches: steps.value
      .filter((node: any) => node.node_type === 'condition')
      .reduce((total: number, node: any) => total + (node.branches || []).length, 0),
    extracts: allEndpointSteps.value.reduce((total: number, step: any) => total + (extractRules[step.id]?.filter((rule) => rule.name.trim()).length || Object.keys(step.extract || {}).length), 0),
    assertions: allEndpointSteps.value.reduce((total: number, step: any) => total + (validateRules[step.id]?.length || Object.keys(step.validate || {}).length), 0),
  }));
  const sceneVariableItems = computed<SceneVariableItem[]>(() => {
    const projectItems = projectVariables.value
      .filter((variable) => variable.name.trim())
      .map((variable) => ({
        key: `project-${variable.id || variable.name}`,
        name: variable.name.trim(),
        reference: variableReference(variable.name.trim()),
        category: 'project' as const,
        value: String(variable.value ?? ''),
        source: `项目参数${variable.project_name ? ` · ${variable.project_name}` : ''}${variable.description ? ` · ${variable.description}` : ''}`,
        sensitive: /(?:secret|password|passwd|token|credential|private[_-]?key|api[_-]?key)/i.test(variable.name),
      }));

    const functionNames = new Set<string>();
    const functionItems = dynamicFunctions.value.flatMap((item: any) => asList(item.function_names).flatMap((rawName: any) => {
      const name = String(rawName || '').trim();
      if (!name || functionNames.has(name)) return [];
      functionNames.add(name);
      return [{
        key: `function-${item.id || 'custom'}-${name}`,
        name,
        reference: `\${${name}()}`,
        category: 'function' as const,
        value: '',
        source: `动态函数${asList(item.project_names).length ? ` · ${asList(item.project_names).join('、')}` : ''}`,
      }];
    }));

    const extractNames = new Set<string>();
    const extractItems: SceneVariableItem[] = [];
    allEndpointSteps.value.forEach((step: any, index: number) => {
      (extractRules[step.id] || []).filter((rule) => rule.name.trim() && rule.expression.trim()).forEach((rule) => {
        const name = rule.name.trim();
        if (extractNames.has(name)) return;
        extractNames.add(name);
        const stepName = step.endpoint_name || '未命名接口';
        const source = `步骤 ${index + 1} · ${stepName} · ${rule.expression}`;
        extractItems.push({
          key: `extract-${step.id}-${name}`,
          name,
          reference: variableReference(name),
          category: 'extract',
          value: source,
          source,
        });
      });
    });
    return [...projectItems, ...functionItems, ...extractItems];
  });
  const sceneVariableTabs = computed(() => {
    const count = (category?: SceneVariableCategory) => category
      ? sceneVariableItems.value.filter((item) => item.category === category).length
      : sceneVariableItems.value.length;
    return [
      { key: 'all' as const, label: '全部', count: count() },
      { key: 'project' as const, label: '项目参数', count: count('project') },
      { key: 'function' as const, label: '动态函数', count: count('function') },
      { key: 'extract' as const, label: '接口提取', count: count('extract') },
    ];
  });
  const filteredSceneVariableGroups = computed<SceneVariableGroup[]>(() => {
    const keyword = sceneVariableSearch.value.trim().toLowerCase();
    const filtered = sceneVariableItems.value.filter((item) => {
      if (sceneVariableCategory.value !== 'all' && item.category !== sceneVariableCategory.value) return false;
      if (!keyword) return true;
      return [item.name, item.reference, item.value, item.source].some((value) => String(value).toLowerCase().includes(keyword));
    });
    const projectName = selectedProjectLabels.value || '当前项目';
    const groups: Array<Omit<SceneVariableGroup, 'items'>> = [
      { key: 'project', label: '项目参数', detail: `项目：${projectName}` },
      { key: 'function', label: '动态函数', detail: '函数' },
      { key: 'extract', label: '上游接口提取', detail: '来自步骤' },
    ];
    return groups
      .map((group) => ({ ...group, items: filtered.filter((item) => item.category === group.key) }))
      .filter((group) => group.items.length);
  });
  const sceneRunState = computed(() => {
    const results = Object.values(runResults);
    const passed = results.filter((result: any) => result?.passed === true).length;
    const failed = results.filter((result: any) => result?.passed === false).length;
    if (scenarioRunning.value) return { label: '运行中', shortLabel: '运行中', type: 'warning' as const, executed: results.length, passed, failed };
    if (failed) return { label: '执行失败', shortLabel: '失败', type: 'error' as const, executed: results.length, passed, failed };
    if (results.length) return { label: '执行完成', shortLabel: '通过', type: 'success' as const, executed: results.length, passed, failed };
    return { label: '尚未运行', shortLabel: '未运行', type: 'default' as const, executed: 0, passed: 0, failed: 0 };
  });
  const formatRunTime = () => new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).format(new Date()).replaceAll('/', '-');

  const endpointTree = computed(() => {
    const selectedProjectIds = new Set(form.projects);
    if (!selectedProjectIds.size) return [];
    const projectNames = new Map(projectOptions.value.map((project) => [project.value, project.label]));
    const projects = form.projects.map((projectId) => ({
      id: projectId,
      name: projectNames.get(projectId) || `项目 ${projectId}`,
      modules: [] as Array<{ id: number | null; name: string; endpoints: any[] }>,
    }));
    const projectMap = new Map(projects.map((project) => [project.id, project]));
    const moduleMap = new Map<number, { id: number | null; name: string; endpoints: any[] }>();
    endpointModules.value.filter((module) => selectedProjectIds.has(module.project)).forEach((module) => {
      const project = projectMap.get(module.project);
      if (!project) return;
      const node = { id: module.id, name: module.name, endpoints: [] as any[] };
      project.modules.push(node);
      moduleMap.set(module.id, node);
    });
    availableEndpoints.value.filter((endpoint) => selectedProjectIds.has(endpoint.project)).forEach((endpoint) => {
      const project = projectMap.get(endpoint.project);
      if (!project) return;
      let module = endpoint.module ? moduleMap.get(endpoint.module) : undefined;
      if (!module) {
        module = project.modules.find((item) => item.id === null);
        if (!module) {
          module = { id: null, name: '未分组接口', endpoints: [] };
          project.modules.push(module);
        }
      }
      module.endpoints.push(endpoint);
    });
    return projects.filter((project) => project.modules.length);
  });
  const endpointMethodOptions = [
    { label: '所有方法（GET、POST…）', value: 'all' },
    { label: 'GET', value: 'GET' }, { label: 'POST', value: 'POST' }, { label: 'PUT', value: 'PUT' },
    { label: 'PATCH', value: 'PATCH' }, { label: 'DELETE', value: 'DELETE' },
  ];
  const branchFilteredEndpoints = computed(() => {
    const keyword = branchEndpointSearch.value.trim().toLocaleLowerCase();
    return availableEndpoints.value.filter((endpoint: any) => {
      if (branchActiveScope.value.type === 'project' && endpoint.project !== branchActiveScope.value.projectId) return false;
      if (branchActiveScope.value.type === 'module' && (endpoint.project !== branchActiveScope.value.projectId || (endpoint.module || null) !== branchActiveScope.value.moduleId)) return false;
      if (branchEndpointMethodFilter.value !== 'all' && formatMethod(endpoint.method) !== branchEndpointMethodFilter.value) return false;
      return !keyword || `${endpoint.name || ''} ${endpoint.url || ''}`.toLocaleLowerCase().includes(keyword);
    });
  });
  const isAllBranchVisibleSelected = computed(() => branchFilteredEndpoints.value.length > 0 && branchFilteredEndpoints.value.every((endpoint: any) => branchEndpointIds.value.includes(endpoint.id)));
  const isBranchVisibleIndeterminate = computed(() => {
    const count = branchFilteredEndpoints.value.filter((endpoint: any) => branchEndpointIds.value.includes(endpoint.id)).length;
    return count > 0 && count < branchFilteredEndpoints.value.length;
  });
  const filteredEndpoints = computed(() => {
    const keyword = endpointSearch.value.trim().toLocaleLowerCase();
    return availableEndpoints.value.filter((endpoint) => {
      if (activeScope.value.type === 'project' && endpoint.project !== activeScope.value.projectId) return false;
      if (activeScope.value.type === 'module' && (endpoint.project !== activeScope.value.projectId || (endpoint.module || null) !== activeScope.value.moduleId)) return false;
      if (endpointMethodFilter.value !== 'all' && formatMethod(endpoint.method) !== endpointMethodFilter.value) return false;
      return !keyword || `${endpoint.name || ''} ${endpoint.url || ''}`.toLocaleLowerCase().includes(keyword);
    });
  });
  const visibleEndpointIds = computed(() => filteredEndpoints.value.map((endpoint) => endpoint.id));
  const isAllVisibleSelected = computed(() => visibleEndpointIds.value.length > 0 && visibleEndpointIds.value.every((endpointId) => selectedEndpoints.value.includes(endpointId)));
  const isVisibleIndeterminate = computed(() => {
    const selectedCount = visibleEndpointIds.value.filter((endpointId) => selectedEndpoints.value.includes(endpointId)).length;
    return selectedCount > 0 && selectedCount < visibleEndpointIds.value.length;
  });

  // 参数覆盖允许把变量作为原始占位符书写："memberId": ${member_id}，并兼容 {{member_id}}。
  // 保存时会转为字符串给后端，运行阶段再由变量替换逻辑注入实际值。
  const rawVariablePrefix = '__platform_raw_variable__';
  const variableOnly = /^(?:\$\{[^{}\r\n]+\}|\{\{[^{}\r\n]+\}\})$/;
  const toEditorJson = (value: unknown, source?: unknown) => {
    const markRawNumberVariables = (current: any, original: any): any => {
      if (typeof current === 'string' && variableOnly.test(current) && (typeof original === 'number' || typeof original === 'boolean')) {
        return `${rawVariablePrefix}${current}`;
      }
      if (Array.isArray(current)) return current.map((item, index) => markRawNumberVariables(item, Array.isArray(original) ? original[index] : undefined));
      if (current && typeof current === 'object') return Object.fromEntries(Object.entries(current).map(([key, item]) => [key, markRawNumberVariables(item, original && typeof original === 'object' ? (original as any)[key] : undefined)]));
      return current;
    };
    return JSON.stringify(markRawNumberVariables(value || {}, source), null, 2)
      .replace(new RegExp(`"${rawVariablePrefix}(\\$\\{[^{}\\r\\n]+\\}|\\{\\{[^{}\\r\\n]+\\}\\})"`, 'g'), '$1');
  };
  const normalizeBareVariables = (value: string) => value.replace(
    /(:\s*)(\$\{[^{}\r\n]+\}|\{\{[^{}\r\n]+\}\})(?=\s*[,}\]])/g,
    (_matched, prefix, variable) => `${prefix}${JSON.stringify(variable)}`,
  );
  const json = (value: unknown) => JSON.stringify(value || {}, null, 2);
  const parse = (value: string) => {
    try { return JSON.parse(normalizeBareVariables(value || '{}')); } catch { throw Error('请填写合法 JSON'); }
  };
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
  const defaultValidateRule = (): ValidateRule => ({ type: 'equals', actual: '$.', expected: '' });
  const defaultPollingConfig = (): PollingConfig => ({ enabled: false, timeout: 60, interval: 3, initial_delay: 0, retry_http_error: true, retry_assertion: true });
  const normalizePollingConfig = (value?: Record<string, any>): PollingConfig => ({ ...defaultPollingConfig(), ...(value || {}) });
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
    return Object.entries(expressions as Record<string, unknown>).flatMap(([, value]) => (
      Array.isArray(value) && value.length >= 2
        ? [{ type, actual: normalizeAssertReference(value[0]), expected: String(value[1] ?? '') }]
        : []
    ));
  });
  const toValidateConfig = (rules: ValidateRule[] = []) => {
    const result: Record<ValidateRule['type'], Record<string, [string, string]>> = {
      equals: {}, not_equals: {}, greater_than: {}, less_than: {}, contains: {},
    };
    rules.forEach((rule) => {
      if (rule.actual.trim()) {
        const operator = ({ equals: '相等', not_equals: '不等于', greater_than: '大于', less_than: '小于', contains: '包含' } as const)[rule.type];
        result[rule.type][`${rule.actual.trim()} ${operator} ${rule.expected}`] = [rule.actual.trim(), rule.expected];
      }
    });
    return Object.fromEntries(Object.entries(result).filter(([, expressions]) => Object.keys(expressions).length));
  };
  const jsonItemCount = (text?: string) => {
    try {
      const value = parse(text || '{}');
      if (!value || typeof value !== 'object' || Array.isArray(value)) return 0;
      return Object.values(value).reduce((count, item) => count + (item && typeof item === 'object' && !Array.isArray(item) ? Object.keys(item as object).length : 1), 0);
    } catch { return 0; }
  };
  const extractRuleCount = (stepId: number) => (extractRules[stepId] || []).filter((rule) => rule.name.trim() && rule.expression.trim()).length;
  const validateRuleCount = (stepId: number) => (validateRules[stepId] || []).filter((rule) => rule.actual.trim()).length;
  const postSqlCount = (stepId: number) => (postSqlRules[stepId] || []).filter((item) => item.trim()).length;
  const lineNumbers = (text?: string) => Array.from({ length: Math.max((text || '').split('\n').length, 1) }, (_, index) => index + 1).join('\n');
  const responseText = (stepId: number) => runResults[stepId]?.response_body || '无响应内容';
  const escapeHtml = (value: string) => value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
  const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const responseMatchCount = (stepId: number) => {
    const keyword = (responseSearch[stepId] || '').trim();
    if (!keyword) return 0;
    return Array.from(responseText(stepId).matchAll(new RegExp(escapeRegExp(keyword), 'gi'))).length;
  };
  const setResponseBodyRef = (stepId: number, element: Element | null) => {
    if (element instanceof HTMLElement) responseBodyRefs.set(stepId, element);
    else responseBodyRefs.delete(stepId);
  };
  const scrollActiveResponseMatch = async (stepId: number) => {
    await nextTick();
    responseBodyRefs.get(stepId)?.querySelector('.response-match.is-active')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };
  const highlightedResponse = (stepId: number) => {
    const response = responseText(stepId);
    const keyword = (responseSearch[stepId] || '').trim();
    if (!keyword) return escapeHtml(response);
    const matches = responseMatchCount(stepId);
    if (!matches) return escapeHtml(response);
    const activeIndex = Math.min(responseSearchIndex[stepId] || 0, matches - 1);
    const pattern = new RegExp(escapeRegExp(keyword), 'gi');
    let lastIndex = 0;
    let matchIndex = 0;
    let html = '';
    response.replace(pattern, (matched, offset: number) => {
      html += escapeHtml(response.slice(lastIndex, offset));
      html += `<mark class="response-match${matchIndex === activeIndex ? ' is-active' : ''}" data-match-index="${matchIndex}">${escapeHtml(matched)}</mark>`;
      lastIndex = offset + matched.length;
      matchIndex += 1;
      return matched;
    });
    return html + escapeHtml(response.slice(lastIndex));
  };
  const handleResponseSearch = (stepId: number, value: string) => {
    responseSearch[stepId] = value;
    responseSearchIndex[stepId] = 0;
    if (value.trim()) scrollActiveResponseMatch(stepId);
  };
  const focusNextResponseMatch = (stepId: number) => {
    const count = responseMatchCount(stepId);
    if (!count) return;
    responseSearchIndex[stepId] = ((responseSearchIndex[stepId] || 0) + 1) % count;
    scrollActiveResponseMatch(stepId);
  };
  const parameterField = (endpoint: any) => {
    if (Object.keys(endpoint?.params || {}).length) return 'params';
    if (Object.keys(endpoint?.data || {}).length) return 'data';
    if (Object.keys(endpoint?.json || {}).length) return 'json';
    return endpoint?.method?.toUpperCase() === 'GET' ? 'params' : 'json';
  };
  const formatMethod = (method?: string) => String(method || 'API').toUpperCase();
  const stepMethod = (step: any) => formatMethod(step?.request_method || step?.endpoint_info?.method);
  const stepUrl = (step: any) => step?.request_url || step?.endpoint_info?.url || '';
  const methodStyle = (method?: string) => {
    const styles: Record<string, { color: string; background: string }> = {
      GET: { color: '#318357', background: '#eef8f2' },
      POST: { color: '#da820b', background: '#fff6e8' },
      PUT: { color: '#277bc5', background: '#eef5fb' },
      PATCH: { color: '#277bc5', background: '#eef5fb' },
      DELETE: { color: '#d44857', background: '#fff0f2' },
    };
    return styles[formatMethod(method)] || { color: '#667085', background: '#f2f4f7' };
  };
  const methodCssVars = (method?: string) => {
    const style = methodStyle(method);
    return { '--method-color': style.color, '--method-background': style.background } as Record<string, string>;
  };
  const renderRequestMethodLabel = (option: any) => h('span', {
    class: ['request-method-option', `method-${formatMethod(String(option.value)).toLowerCase()}`],
    style: { color: methodStyle(String(option.value)).color, fontWeight: '600' },
  }, String(option.label));
  const hasRequestTargetOverride = (step: any) => Boolean(step?.request_method || step?.request_url);
  const isRequestTargetEditing = (step: any) => editingRequestTargetIds.has(Number(step?.id));
  const requestDefaults = (endpoint: any, override: Record<string, unknown> = {}) => {
    const field = parameterField(endpoint);
    const isLegacyOverride = ['headers', 'params', 'data', 'json'].some((key) => key in override);
    // 智能关联可能同时覆盖 Headers、Params、Data、JSON；此格式必须原样保留，
    // 否则页面重新打开后会丢失非默认请求区域的关联。
    if (isLegacyOverride) return override;
    return { ...(endpoint?.[field] || {}), ...override };
  };

  const requestOverrideJson = (override: Record<string, unknown>, endpoint: any) => {
    const isStructured = requestFields.some((field) => field in (override || {}));
    const source = isStructured ? endpoint : endpoint?.[parameterField(endpoint)] || {};
    return toEditorJson(override, source);
  };

  const requestFields = ['headers', 'params', 'data', 'json'] as const;
  const requestFieldCount = (step: any, field: typeof requestFields[number]) => {
    const override = structuredOverride(step);
    return Object.keys(override[field] || (field === parameterField(step.endpoint_info) ? override : {})).length;
  };
  const aliasGroups = [
    ['token', 'access_token', 'accesstoken', 'authorization', 'x_token', 'xtoken'],
    ['user_id', 'userid', 'userId', 'member_id', 'memberid'],
    ['order_id', 'orderid'], ['account_id', 'accountid'], ['mobile', 'phone', 'phone_number', 'phonenumber'],
  ];
  const normalName = (value: unknown) => String(value || '').replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
  const namesRelated = (left: unknown, right: unknown) => {
    const a = normalName(left); const b = normalName(right);
    if (!a || !b) return false;
    if (a === b) return true;
    return aliasGroups.some((group) => group.map(normalName).includes(a) && group.map(normalName).includes(b));
  };
  const fieldDisplayName: Record<VariableSuggestion['field'], string> = { headers: '请求头', params: 'Params', data: 'Data', json: 'JSON' };
  const variableReference = (name: string) => `\${${name}}`;
  const sceneVariableDisplayValue = (variable: SceneVariableItem) => {
    if (variable.sensitive && !revealedVariableKeys.value.has(variable.key)) return '******';
    if (variable.category === 'function' && !variable.value) return '';
    return variable.value || '-';
  };
  const toggleVariableVisibility = (key: string) => {
    const next = new Set(revealedVariableKeys.value);
    if (next.has(key)) next.delete(key); else next.add(key);
    revealedVariableKeys.value = next;
  };
  const copySceneVariable = async (variable: SceneVariableItem, notify = true) => {
    try {
      await navigator.clipboard.writeText(variable.reference);
      if (notify) message.success(`已复制 ${variable.reference}`);
      return true;
    } catch {
      message.error('复制失败，请手动选择变量表达式');
      return false;
    }
  };
  const rememberRequestEditorCursor = (step: any, event: Event) => {
    const target = event.target as HTMLTextAreaElement | null;
    if (!target || typeof target.selectionStart !== 'number') return;
    requestEditorCursor.value = {
      stepId: Number(step?.id),
      start: target.selectionStart,
      end: target.selectionEnd,
    };
  };
  const referenceSceneVariable = async (variable: SceneVariableItem) => {
    const cursor = requestEditorCursor.value;
    const fallbackStepId = Number(expandedId.value || branchEditingStep.value?.id || 0);
    const stepId = Number(cursor?.stepId || fallbackStepId);
    const editor = editText[stepId];
    if (!stepId || !editor) {
      const copied = await copySceneVariable(variable, false);
      if (copied) message.info('请在步骤参数中粘贴变量表达式');
      return;
    }
    const current = editor.request_override || '';
    const start = cursor?.stepId === stepId ? Math.min(cursor.start, current.length) : current.length;
    const end = cursor?.stepId === stepId ? Math.min(cursor.end, current.length) : current.length;
    editor.request_override = `${current.slice(0, start)}${variable.reference}${current.slice(end)}`;
    requestEditorCursor.value = { stepId, start: start + variable.reference.length, end: start + variable.reference.length };
    await nextTick();
    message.success(`已引用 ${variable.reference}`);
  };
  const precedingSteps = (targetStep: any) => {
    const mainIndex = steps.value.findIndex((step: any) => step.id === targetStep.id);
    if (mainIndex >= 0) return steps.value.slice(0, mainIndex).filter((step: any) => step.node_type === 'endpoint');
    for (let mainIndex = 0; mainIndex < steps.value.length; mainIndex += 1) {
      const node = steps.value[mainIndex];
      if (node.node_type !== 'condition') continue;
      for (const branch of node.branches || []) {
        const childIndex = (branch.nodes || []).findIndex((child: any) => child.step_info?.id === targetStep.id);
        if (childIndex < 0) continue;
        const mainSteps = steps.value.slice(0, mainIndex).filter((step: any) => step.node_type === 'endpoint');
        return [...mainSteps, ...(branch.nodes || []).slice(0, childIndex).map((child: any) => child.step_info)];
      }
    }
    return [];
  };
  const availableVariables = (targetStep: any): AvailableVariable[] => {
    const upstreamSteps = precedingSteps(targetStep);
    const names = new Set<string>();
    const upstreamVariables = upstreamSteps.flatMap((step, index) => (extractRules[step.id] || []).flatMap((rule) => {
      const name = rule.name.trim();
      if (!name || !rule.expression.trim() || names.has(name)) return [];
      names.add(name);
      return [{ name, stepId: step.id, stepOrder: index + 1, stepName: step.endpoint_name || '未命名接口', expression: rule.expression, scope: 'step' as const }];
    }));
    const projectScopedVariables = projectVariables.value.flatMap((variable) => {
      const name = variable.name.trim();
      if (!name || names.has(name)) return [];
      names.add(name);
      return [{ name, stepId: -(Number(variable.id) || 1), stepOrder: 0, stepName: '项目参数', expression: '项目级参数', scope: 'project' as const, projectName: variable.project_name }];
    });
    return [...upstreamVariables, ...projectScopedVariables];
  };
  // 智能关联不能只读取接口定义的默认参数：用户在“参数覆盖”中新增加的字段
  // （例如截图中的 aa）同样是下游待填参数，也应该参与变量名匹配。
  const endpointParameterEntries = (endpoint: any, override: Record<string, any> = {}) => requestFields.flatMap((field) => {
    const parameters = { ...(endpoint?.[field] || {}), ...(override?.[field] || {}) };
    return Object.entries(parameters).map(([parameter, value]) => ({ field, parameter, value }));
  });
  const referenceFor = (field: VariableSuggestion['field'], parameter: string, variableName: string, sourceValue: unknown) => {
    if (field === 'headers' && /authorization/i.test(parameter) && !/^\s*(?:bearer|token)\s+(?:\$\{|\{\{)/.test(String(sourceValue || ''))) return `Bearer \${${variableName}}`;
    return `\${${variableName}}`;
  };
  const appendJsonPath = (prefix: string, key: string) => /^[A-Za-z_$][\w$]*$/.test(key)
    ? `${prefix}.${key}`
    : `${prefix}[${JSON.stringify(key)}]`;
  const leafResponsePaths = (value: any, prefix = '$', depth = 0): Array<{ path: string; key: string }> => {
    if (depth > 6 || value === null || value === undefined) return [];
    if (Array.isArray(value)) return value.slice(0, 10).flatMap((item, index) => leafResponsePaths(item, `${prefix}[${index}]`, depth + 1));
    if (typeof value === 'object') return Object.entries(value).slice(0, 80).flatMap(([key, item]) => leafResponsePaths(item, appendJsonPath(prefix, key), depth + 1));
    const key = prefix.replace(/\[[0-9]+\]/g, '').split('.').filter(Boolean).pop() || '';
    return [{ path: prefix, key }];
  };
  const selectableResponsePaths = (value: any): Array<{ path: string; value: unknown }> => {
    const result: Array<{ path: string; value: unknown }> = [];
    const seen = new Set<string>();
    const add = (path: string, item: unknown) => {
      if (result.length >= 240 || seen.has(path)) return;
      seen.add(path);
      result.push({ path, value: item });
    };
    const visit = (item: any, prefix: string, depth: number, includeCurrent: boolean) => {
      if (result.length >= 240 || depth > 6) return;
      if (includeCurrent) add(prefix, item);
      if (item === null || item === undefined) return;
      if (Array.isArray(item)) {
        for (const [index, child] of item.slice(0, 10).entries()) {
          if (result.length >= 240) break;
          visit(child, `${prefix}[${index}]`, depth + 1, true);
        }
      } else if (typeof item === 'object') {
        for (const [key, child] of Object.entries(item).slice(0, 80)) {
          if (result.length >= 240) break;
          visit(child, appendJsonPath(prefix, key), depth + 1, true);
        }
      }
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
  const responseExpressionOptions = (step: any, rule: ExtractRule) => {
    if (rule.mode !== 'jsonpath') return [];
    const stepId = Number(step?.step_id || step?.id);
    const result = runResults[stepId];
    if (!result) return [];
    let responseValue = rule.source === 'headers' ? result.response_headers : result.response_json;
    const responseJsonIsEmpty = responseValue === undefined
      || responseValue === null
      || (Array.isArray(responseValue) && responseValue.length === 0)
      || (typeof responseValue === 'object' && !Array.isArray(responseValue) && Object.keys(responseValue).length === 0);
    if (rule.source === 'json' && responseJsonIsEmpty) {
      try { responseValue = JSON.parse(result.response_body || ''); } catch { return []; }
    }
    const keyword = String(rule.expression || '').trim().toLowerCase();
    return selectableResponsePaths(responseValue)
      .map((item) => ({ label: item.path, value: item.path, preview: responseValuePreview(item.value) }))
      .filter((item) => !keyword || item.value.toLowerCase().includes(keyword) || item.preview.toLowerCase().includes(keyword));
  };
  const renderResponsePathLabel = (option: any) => h('span', { class: 'response-path-option' }, [
    h('code', option.value),
    h('span', `· ${option.preview || ''}`),
  ]);
  const handleResponsePathSelect = (rule: ExtractRule, selectedPath: string) => {
    const nextAutoName = variableNameFromJsonPath(selectedPath);
    if (nextAutoName && (!rule.name.trim() || rule.name.trim() === rule.autoVariableName)) {
      rule.name = nextAutoName;
      rule.autoVariableName = nextAutoName;
    }
  };
  const handleExtractNameInput = (rule: ExtractRule, value: string) => {
    rule.name = value;
    if (value.trim() !== rule.autoVariableName) rule.autoVariableName = undefined;
  };
  const variableNameFor = (baseName: string, sourceStep: any, usedNames: Set<string>) => {
    const cleaned = String(baseName || 'value').replace(/[^a-zA-Z0-9_]/g, '_') || 'value';
    if (!usedNames.has(cleaned)) return cleaned;
    const prefixed = `${String(sourceStep.endpoint_name || 'step').replace(/[^a-zA-Z0-9_]/g, '_')}_${cleaned}`.replace(/^_+/, '');
    if (!usedNames.has(prefixed)) return prefixed;
    let serial = 2;
    while (usedNames.has(`${prefixed}_${serial}`)) serial += 1;
    return `${prefixed}_${serial}`;
  };
  const variableSuggestions = (targetStep: any): VariableSuggestion[] => {
    const endpoint = targetStep.endpoint_info || {};
    const upstreamSteps = precedingSteps(targetStep);
    const targets = endpointParameterEntries(endpoint, structuredOverride(targetStep));
    const variables = availableVariables(targetStep);
    const suggestions: VariableSuggestion[] = [];
    const usedTargets = new Set<string>();
    const usedNames = new Set(variables.map((item) => item.name));
    targets.forEach((target) => {
      const targetKey = `${target.field}.${target.parameter}`;
      const variable = variables.find((item) => namesRelated(item.name, target.parameter));
      if (!variable || usedTargets.has(targetKey)) return;
      usedTargets.add(targetKey);
      suggestions.push({
        key: `variable-${targetKey}-${variable.scope || 'step'}-${variable.stepId}`, sourceLabel: variable.scope === 'project' ? `项目参数${variable.projectName ? ` · ${variable.projectName}` : ''}` : `第 ${variable.stepOrder} 步 · ${variable.stepName}`, field: target.field,
        fieldLabel: `${fieldDisplayName[target.field]} · ${target.parameter}`, parameter: target.parameter, variableName: variable.name,
        reference: referenceFor(target.field, target.parameter, variable.name, target.value),
      });
    });
    // 上游接口已运行时，从其 JSON 响应中寻找同名/别名字段，并把“提取 + 引用”作为一条可确认建议。
    upstreamSteps.forEach((sourceStep, sourceIndex) => {
      const responseJson = runResults[sourceStep.id]?.response_json;
      if (!responseJson || typeof responseJson !== 'object') return;
      const paths = leafResponsePaths(responseJson);
      targets.forEach((target) => {
        const targetKey = `${target.field}.${target.parameter}`;
        if (usedTargets.has(targetKey)) return;
        const matched = paths.find((item) => namesRelated(item.key, target.parameter));
        if (!matched) return;
        const variableName = variableNameFor(matched.key, sourceStep, usedNames);
        usedNames.add(variableName); usedTargets.add(targetKey);
        const extract: ExtractRule = { name: variableName, mode: 'jsonpath', source: 'json', expression: matched.path, index: 0, processors: [] };
        suggestions.push({
          key: `response-${targetKey}-${sourceStep.id}-${matched.path}`, sourceLabel: `第 ${sourceIndex + 1} 步 · ${sourceStep.endpoint_name || '未命名接口'} 的最近响应`, field: target.field,
          fieldLabel: `${fieldDisplayName[target.field]} · ${target.parameter}`, parameter: target.parameter, variableName,
          reference: referenceFor(target.field, target.parameter, variableName, target.value), extract, extractStepId: sourceStep.id,
          extractLabel: `${variableName} ← ${matched.path}`,
        });
      });
    });
    return suggestions;
  };
  const structuredOverride = (step: any) => {
    const current = parse(editText[step.id].request_override);
    if (requestFields.some((field) => field in current)) return { ...current };
    return { [parameterField(step.endpoint_info)]: current };
  };
  async function applySuggestion(step: any, suggestion: VariableSuggestion) {
    const rawOverride = parse(editText[step.id].request_override);
    const wasStructured = requestFields.some((field) => field in rawOverride);
    const primaryField = parameterField(step.endpoint_info);
    const typedSource = Object.fromEntries(requestFields.map((field) => [field, {
      ...(step.endpoint_info?.[field] || {}),
      ...((wasStructured ? rawOverride[field] : field === primaryField ? rawOverride : {}) || {}),
    }]));
    const override = structuredOverride(step);
    override[suggestion.field] = { ...(override[suggestion.field] || {}), [suggestion.parameter]: suggestion.reference };
    // 保留简洁对象结构，同时根据引用前的值决定变量是否带引号：数字/布尔值使用裸变量。
    editText[step.id].request_override = !wasStructured && suggestion.field === primaryField
      ? toEditorJson(override[suggestion.field], typedSource[suggestion.field])
      : toEditorJson(override, typedSource);
    if (suggestion.extract && suggestion.extractStepId) {
      const rules = extractRules[suggestion.extractStepId] ||= [];
      if (!rules.some((rule) => rule.name === suggestion.extract?.name)) rules.push(suggestion.extract);
      const sourceStep = steps.value.find((item) => item.id === suggestion.extractStepId);
      if (sourceStep) await saveStep(sourceStep, true);
    }
    await saveStep(step, true);
    message.success('变量关联已应用');
  }
  async function applyAllSuggestions(step: any) {
    const suggestions = variableSuggestions(step);
    if (!suggestions.length) return;
    for (const suggestion of suggestions) await applySuggestion(step, suggestion);
  }

  
  const initializeStep = (item: any) => {
    if (!item?.id) return;
    if (typeof item.continue_on_failure !== 'boolean') item.continue_on_failure = true;
    if (typeof item.retry_on_failure !== 'boolean') item.retry_on_failure = false;
    item.failure_retry_count = Math.min(5, Math.max(1, Number(item.failure_retry_count) || 1));
    editText[item.id] = { request_override: requestOverrideJson(requestDefaults(item.endpoint_info, item.request_override), item.endpoint_info) };
    // 场景步骤是添加接口时的独立快照；空规则也是有效的场景覆盖。
    extractRules[item.id] = toExtractRules(item.extract || {});
    validateRules[item.id] = toValidateRules(item.validate || {});
    postSqlRules[item.id] = Array.isArray(item.post_sql) ? item.post_sql : [];
    pollingConfigs[item.id] = normalizePollingConfig(item.polling);
    activeConfigTabs[item.id] ||= 'request_override';
  };

  async function loadInterfaceTree() {
    if (!form.projects.length) {
      availableEndpoints.value = [];
      endpointModules.value = [];
      selectedEndpoints.value = [];
      endpointPickerVisible.value = false;
      return;
    }
    const [endpoints, modules] = await Promise.all([
      endpointApi.getDataList({ pageSize: 999 }),
      endpointModuleApi.getDataList({ pageSize: 999 }),
    ]);
    const selectedProjectIds = new Set(form.projects);
    availableEndpoints.value = asList(endpoints).filter((endpoint: any) => selectedProjectIds.has(endpoint.project));
    endpointModules.value = asList(modules).filter((module: any) => selectedProjectIds.has(module.project));
    const selectableIds = new Set(availableEndpoints.value.map((endpoint: any) => endpoint.id));
    selectedEndpoints.value = selectedEndpoints.value.filter((endpointId) => selectableIds.has(endpointId));
    branchEndpointIds.value = branchEndpointIds.value.filter((endpointId) => selectableIds.has(endpointId));
    const currentProjectIds = endpointTree.value.map((project) => project.id);
    expandedProjects.value = currentProjectIds;
    if (!currentProjectIds.includes(activeScope.value.projectId || -1)) activeScope.value = { type: 'all' };
  }

  /** 每次打开选择器都重新读取接口，避免接口管理更新后场景页仍使用首次加载的旧快照。 */
  async function openEndpointPicker() {
    if (!form.projects.length) {
      message.warning('请先选择关联项目');
      return;
    }
    try {
      await loadInterfaceTree();
      endpointPickerVisible.value = true;
    } catch (error: any) {
      message.error(error.message || '接口列表加载失败，请稍后重试');
    }
  }

  function handleEndpointPickerVisible(visible: boolean) {
    if (!visible) {
      endpointPickerVisible.value = false;
      return;
    }
    void openEndpointPicker();
  }

  /**
   * 选择弹窗打开期间接口可能已被其他人删除。提交前重新加载列表，避免将
   * 已失效的主键提交给后端而出现 “Invalid pk” 的技术错误。
   */
  async function validateSelectedEndpointIds(source: 'main' | 'branch') {
    const original = source === 'main' ? [...selectedEndpoints.value] : [...branchEndpointIds.value];
    await Promise.all([loadInterfaceTree(), loadProjectVariables(), loadDynamicFunctions()]);
    const selectableIds = new Set(availableEndpoints.value.map((endpoint: any) => Number(endpoint.id)));
    const valid = Array.from(new Set(original.map(Number).filter((endpointId) => selectableIds.has(endpointId))));
    const removedCount = original.length - valid.length;
    if (source === 'main') selectedEndpoints.value = valid;
    else branchEndpointIds.value = valid;
    if (removedCount) message.warning(`已移除 ${removedCount} 个不存在或无权限访问的接口，请确认后重新添加。`);
    if (!valid.length) throw new Error('所选接口已被删除或无权限访问，请刷新接口列表后重新选择。');
    return valid;
  }

  const endpointCount = (modules: Array<{ endpoints: any[] }>) => modules.reduce((count, module) => count + module.endpoints.length, 0);
  const groupEndpointIds = (modules: Array<{ endpoints: any[] }>) => modules.flatMap((module) => module.endpoints.map((endpoint) => endpoint.id));
  const isGroupChecked = (modules: Array<{ endpoints: any[] }>) => {
    const endpointIds = groupEndpointIds(modules);
    return endpointIds.length > 0 && endpointIds.every((endpointId) => selectedEndpoints.value.includes(endpointId));
  };
  const isGroupIndeterminate = (modules: Array<{ endpoints: any[] }>) => {
    const endpointIds = groupEndpointIds(modules);
    const selectedCount = endpointIds.filter((endpointId) => selectedEndpoints.value.includes(endpointId)).length;
    return selectedCount > 0 && selectedCount < endpointIds.length;
  };
  function toggleEndpoint(endpointId: number, checked: boolean) {
    const selected = new Set(selectedEndpoints.value);
    if (checked) selected.add(endpointId);
    else selected.delete(endpointId);
    selectedEndpoints.value = Array.from(selected);
  }
  function toggleGroup(modules: Array<{ endpoints: any[] }>, checked: boolean) {
    const selected = new Set(selectedEndpoints.value);
    groupEndpointIds(modules).forEach((endpointId) => checked ? selected.add(endpointId) : selected.delete(endpointId));
    selectedEndpoints.value = Array.from(selected);
  }
  function selectScope(type: 'project' | 'module', projectId: number, moduleId?: number | null) {
    activeScope.value = { type, projectId, ...(type === 'module' ? { moduleId: moduleId ?? null } : {}) };
  }
  function isActiveScope(type: 'project' | 'module', projectId: number, moduleId?: number | null) {
    return activeScope.value.type === type
      && activeScope.value.projectId === projectId
      && (type !== 'module' || activeScope.value.moduleId === (moduleId ?? null));
  }
  function toggleProject(projectId: number) {
    expandedProjects.value = expandedProjects.value.includes(projectId)
      ? expandedProjects.value.filter((id) => id !== projectId)
      : [...expandedProjects.value, projectId];
  }
  function selectProjectScopeAndToggle(projectId: number) {
    selectScope('project', projectId);
    toggleProject(projectId);
  }
  function toggleAllVisibleEndpoints(checked: boolean) {
    const selected = new Set(selectedEndpoints.value);
    visibleEndpointIds.value.forEach((endpointId) => checked ? selected.add(endpointId) : selected.delete(endpointId));
    selectedEndpoints.value = Array.from(selected);
  }
  function selectAllVisibleEndpoints() { toggleAllVisibleEndpoints(true); }
  function invertVisibleEndpoints() {
    const selected = new Set(selectedEndpoints.value);
    visibleEndpointIds.value.forEach((endpointId) => selected.has(endpointId) ? selected.delete(endpointId) : selected.add(endpointId));
    selectedEndpoints.value = Array.from(selected);
  }
  async function loadSteps() {
    const nodes = asList(await flowNodeApi.getDataList({ scenario: id, main: true }));
    steps.value = nodes.map((node: any) => node.node_type === 'endpoint'
      ? { ...node.step_info, id: node.step, step_id: node.step, node_id: node.id, node_type: 'endpoint', enabled: node.enabled !== false }
      : { ...node, node_id: node.id, node_type: 'condition' });
    steps.value.forEach((item: any) => {
      if (item.node_type === 'endpoint') initializeStep({ ...item, id: item.step_id });
      else (item.branches || []).forEach((branch: any) => (branch.nodes || []).forEach((node: any) => initializeStep(node.step_info)));
    });
    if (!allEndpointSteps.value.some((step: any) => step.id === expandedId.value) && !selectedConditionId.value) {
      expandedId.value = allEndpointSteps.value[0]?.id || null;
    }
  }
  async function load() {
    projectOptions.value = (await projectApi.getDataList({})).map((item: any) => ({ label: item.name, value: item.id }));
    allEnvironments.value = await environmentApi.getDataList({});
    if (id) {
      const scenario = await scenarioApi.getDataByID(id);
      Object.assign(form, scenario, { projects: scenario.projects?.length ? scenario.projects : [scenario.project] });
      savedFormSignature.value = formSignature.value;
      await loadSteps();
    }
    refreshEnvironmentOptions();
    await loadInterfaceTree();
  }
  function generateScenarioNameFromSelectedEndpoints() {
    const firstEndpoint = availableEndpoints.value.find((endpoint: any) => selectedEndpoints.value.includes(endpoint.id));
    return firstEndpoint?.name ? `${firstEndpoint.name}场景` : '新建接口场景';
  }

  async function ensureScenarioSaved(options: { autoGenerateName?: boolean } = {}) {
    if (!form.projects.length) throw new Error('请先选择关联项目');
    if (!form.name.trim()) {
      if (!options.autoGenerateName) throw new Error('请先填写场景名称');
      form.name = generateScenarioNameFromSelectedEndpoints();
    }
    if (id) {
      await scenarioApi.update(id, form as any);
      savedFormSignature.value = formSignature.value;
      scenarioCreated.value = true;
      return id;
    }
    const errors = await new Promise<unknown>((resolve) => formRef.value?.validate((validationErrors: unknown) => resolve(validationErrors)));
    if (errors) throw new Error('场景基本信息校验失败，请检查后重试');
    const created: any = await scenarioApi.createData(form as any);
    const createdId = Number(created?.id || created?.pk);
    if (!createdId) throw new Error('场景创建成功但未返回场景 ID，请刷新后重试');
    id = createdId;
    savedFormSignature.value = formSignature.value;
    scenarioCreated.value = true;
    message.success('场景已自动保存');
    return id;
  }
  async function saveScenario() {
    if (!form.name.trim()) { message.warning('请输入场景名称'); return; }
    if (!form.projects.length) { message.warning('请至少选择一个项目'); return; }
    try {
      await ensureScenarioSaved();
      const saved = await Promise.all(allEndpointSteps.value.map((step: any) => saveStep(step, true)));
      if (saved.some((success) => !success)) return;
      message.success('场景已保存');
    } catch (error: any) {
      message.error(error.message || '场景保存失败');
    }
  }
  async function addStep() {
    if (!selectedEndpoints.value.length) return;
    try {
      const endpointIds = await validateSelectedEndpointIds('main');
      // 新增场景无需先手动保存：首次添加时由所选接口自动生成场景名称并创建场景。
      await ensureScenarioSaved({ autoGenerateName: true });
      let order = steps.value.filter((item: any) => item.node_type === 'endpoint').length + 1;
      for (const endpoint of endpointIds) {
        await stepApi.createData({ scenario: id, endpoint, order, request_override: {}, extract: {}, validate: {}, post_sql: [], polling: {}, continue_on_failure: true, retry_on_failure: false, failure_retry_count: 1 });
        order += 1;
      }
      selectedEndpoints.value = [];
      endpointPickerVisible.value = false;
      await loadSteps();
    } catch (error: any) {
      message.error(error.message || '添加接口失败，请确认场景信息已填写完整');
    }
  }
  async function saveStep(step: any, silent = false) {
    try {
      const payload = {
        request_method: step.request_method || '',
        request_url: step.request_url || '',
        request_override: parse(editText[step.id].request_override),
        extract: toExtractConfig(extractRules[step.id]),
        validate: toValidateConfig(validateRules[step.id]),
        post_sql: (postSqlRules[step.id] || []).map((item) => item.trim()).filter(Boolean),
        polling: pollingConfigs[step.id],
        continue_on_failure: step.continue_on_failure !== false,
        retry_on_failure: Boolean(step.retry_on_failure),
        failure_retry_count: Math.min(5, Math.max(1, Number(step.failure_retry_count) || 1)),
      };
      await stepApi.update(step.id, payload);
      Object.assign(step, payload);
      const stored = allEndpointSteps.value.find((item: any) => Number(item.id) === Number(step.id));
      if (stored) Object.assign(stored, payload);
      return true;
    } catch (error: any) {
      message.error(error.message || '步骤保存失败');
      return false;
    }
  }
  async function handleRetryToggle(step: any) {
    step.failure_retry_count = Math.min(5, Math.max(1, Number(step.failure_retry_count) || 1));
    await saveStep(step);
  }
  function formatOverride(step: any) {
    try { editText[step.id].request_override = requestOverrideJson(parse(editText[step.id].request_override), step.endpoint_info); }
    catch { message.warning('请先填写合法 JSON 后再格式化'); }
  }
  function restoreOverride(step: any) {
    editText[step.id].request_override = requestOverrideJson(requestDefaults(step.endpoint_info), step.endpoint_info);
    saveStep(step, true);
  }
  function beginRequestTargetEdit(step: any) {
    editingRequestTargetIds.add(Number(step.id));
  }
  async function finishRequestTargetEdit(step: any) {
    await saveStep(step, true);
    editingRequestTargetIds.delete(Number(step.id));
  }
  async function updateRequestMethod(step: any, value: string) {
    step.request_method = value || '';
    await saveStep(step, true);
  }
  function updateRequestUrl(step: any, value: string) {
    step.request_url = value || '';
  }
  async function resetRequestTarget(step: any) {
    step.request_method = '';
    step.request_url = '';
    await saveStep(step);
  }
  function addExtractRule(step: any) {
    (extractRules[step.id] ||= []).push(defaultExtractRule());
  }
  async function handleExtractModeChange(step: any, rule: ExtractRule) {
    if (rule.mode === 'jsonpath' && rule.source === 'text') rule.source = 'json';
    await saveStep(step);
  }
  async function removeExtractRule(step: any, index: number) {
    extractRules[step.id].splice(index, 1);
    await saveStep(step);
  }
  function addValidateRule(step: any) {
    (validateRules[step.id] ||= []).push(defaultValidateRule());
  }
  async function removeValidateRule(step: any, index: number) {
    validateRules[step.id].splice(index, 1);
    await saveStep(step);
  }
  function addPostSql(step: any) { (postSqlRules[step.id] ||= []).push(''); }
  async function removePostSql(step: any, index: number) { postSqlRules[step.id].splice(index, 1); await saveStep(step); }
  async function saveOrder() {
    await flowNodeApi.reorder(id, steps.value.map((step) => step.node_id || step.id));
    message.success('步骤顺序已更新');
  }
  async function removeStep(stepId: number) {
    const node = steps.value.find((item: any) => item.step_id === stepId || item.id === stepId);
    if (node) await flowNodeApi.DeleteDataByID(node.node_id || node.id);
    if (expandedId.value === stepId) expandedId.value = null;
    await loadSteps();
  }
  async function copyStep(element: any) {
    try {
      if (!element.endpoint) { message.warning('该步骤未关联接口，无法复制'); return; }
      // 先同步场景基本信息，避免未保存时无法创建步骤。
      await scenarioApi.update(id, form as any);
      const created: any = await stepApi.createData({
        scenario: id,
        endpoint: element.endpoint,
        order: element.order ?? 1,
        request_method: element.request_method || '',
        request_url: element.request_url || '',
        request_override: JSON.parse(JSON.stringify(element.request_override ?? {})),
        extract: JSON.parse(JSON.stringify(element.extract ?? {})),
        validate: JSON.parse(JSON.stringify(element.validate ?? {})),
        post_sql: JSON.parse(JSON.stringify(element.post_sql ?? [])),
        polling: JSON.parse(JSON.stringify(element.polling ?? {})),
        continue_on_failure: element.continue_on_failure !== false,
        retry_on_failure: Boolean(element.retry_on_failure),
        failure_retry_count: Math.min(5, Math.max(1, Number(element.failure_retry_count) || 1)),
      });
      await loadSteps();
      // 克隆出的步骤默认追加到主流程末尾，这里把它移动到原步骤之后，符合“复制”直觉。
      const arr = steps.value.slice();
      const origIdx = arr.findIndex((s: any) => s.step_id === element.step_id || s.id === element.id);
      const newIdx = arr.findIndex((s: any) => s.step_id === created.id);
      if (origIdx !== -1 && newIdx !== -1) {
        const [copied] = arr.splice(newIdx, 1);
        arr.splice(origIdx + 1, 0, copied);
        await flowNodeApi.reorder(id, arr.map((s: any) => s.node_id || s.id));
      }
      message.success('已复制接口步骤');
    } catch (error: any) {
      message.error(error.message || '复制接口步骤失败');
    }
  }
  async function runStep(step: any) {
    if (!runEnvironment.value) { message.warning('请先选择运行环境'); return; }
    try {
      const stepId = step.step_id || step.id;
      if (!await saveStep({ ...step, id: stepId }, true)) return;
      runningStepId.value = stepId;
      const result = await stepApi.runById(stepId, runEnvironment.value);
      runResults[stepId] = result;
      expandedId.value = stepId;
      message[result.passed ? 'success' : 'error'](result.passed ? '接口运行通过' : '接口运行失败');
    } catch (error: any) { message.error(error.message || '接口运行失败'); }
    finally { runningStepId.value = null; }
  }
  async function runScenario() {
    if (!runEnvironment.value) { message.warning('请先选择运行环境'); return; }
    const startedAt = performance.now();
    try {
      scenarioRunning.value = true;
      // 场景运行前先写入当前页面已编辑的步骤配置，保证调试内容与页面一致。
      const saved = await Promise.all(allEndpointSteps.value.map((step: any) => saveStep({ ...step, id: step.step_id || step.id }, true)));
      if (saved.some((success) => !success)) return;
      const response = await scenarioApi.runById(id, runEnvironment.value);
      (response.results || []).forEach((result: any) => { runResults[result.step_id] = result; });
      latestScenarioRun.value = { durationMs: performance.now() - startedAt, finishedAt: formatRunTime() };
      const failed = (response.results || []).find((result: any) => result.passed === false);
      const noMatch = (response.decisions || []).find((decision: any) => decision.status === 'no_match');
      if (failed) expandedId.value = failed.step_id;
      else if (response.results?.length) expandedId.value = response.results[0].step_id;
      if (response.passed) message.success('场景运行通过');
      else if (noMatch) message.error(`判断分支「${noMatch.name || noMatch.node_id}」未命中，请检查 JSONPath 和期望值`);
      else message.error((response.errors || []).join('；') || '场景运行存在失败接口');
    } catch (error: any) { message.error(error.message || '场景运行失败'); }
    finally { scenarioRunning.value = false; }
  }
  async function viewRunResult() {
    const failedStepId = Number(Object.entries(runResults).find(([, result]: any) => result?.passed === false)?.[0]);
    const firstStepId = Number(Object.keys(runResults)[0]);
    const stepId = failedStepId || firstStepId;
    if (!stepId) return;
    expandedId.value = stepId;
    await nextTick();
    document.querySelector(`[data-step-id="${stepId}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  // 分支条件在进入分支前计算，只能读取判断节点之前已执行完成的主流程接口响应。
  // 判断节点之后的接口及分支内接口尚未执行，不能作为条件的数据来源。
  const upstreamStepOptions = computed(() => {
    const conditionIndex = editingConditionNode.value
      ? steps.value.findIndex((item: any) => item.node_id === editingConditionNode.value.node_id || item.id === editingConditionNode.value.id)
      : steps.value.length;
    return steps.value
      .slice(0, conditionIndex < 0 ? steps.value.length : conditionIndex)
      .filter((item: any) => item.node_type === 'endpoint')
      .map((item: any, index: number) => ({ label: `上游第 ${index + 1} 步 · ${item.endpoint_name || '未命名接口'}`, value: item.step_id || item.id }));
  });
  function projectModuleName(endpoint: any) {
    const project = projectOptions.value.find((item: any) => item.value === endpoint.project)?.label || '未归属项目';
    const module = endpointModules.value.find((item: any) => item.id === endpoint.module)?.name || '未分组';
    return `${project} / ${module}`;
  }
  function toggleBranchEndpoint(endpointId: number, checked: boolean) {
    const selected = new Set(branchEndpointIds.value);
    if (checked) selected.add(endpointId); else selected.delete(endpointId);
    branchEndpointIds.value = Array.from(selected);
  }
  function toggleAllBranchEndpoints(checked: boolean) {
    const selected = new Set(branchEndpointIds.value);
    branchFilteredEndpoints.value.forEach((endpoint: any) => checked ? selected.add(endpoint.id) : selected.delete(endpoint.id));
    branchEndpointIds.value = Array.from(selected);
  }
  function invertBranchVisibleEndpoints() {
    const selected = new Set(branchEndpointIds.value);
    branchFilteredEndpoints.value.forEach((endpoint: any) => selected.has(endpoint.id) ? selected.delete(endpoint.id) : selected.add(endpoint.id));
    branchEndpointIds.value = Array.from(selected);
  }
  function branchGroupEndpointIds(modules: Array<{ endpoints: any[] }>) { return modules.flatMap((module) => module.endpoints.map((endpoint) => endpoint.id)); }
  function isBranchGroupChecked(modules: Array<{ endpoints: any[] }>) {
    const ids = branchGroupEndpointIds(modules);
    return ids.length > 0 && ids.every((endpointId) => branchEndpointIds.value.includes(endpointId));
  }
  function isBranchGroupIndeterminate(modules: Array<{ endpoints: any[] }>) {
    const ids = branchGroupEndpointIds(modules);
    const count = ids.filter((endpointId) => branchEndpointIds.value.includes(endpointId)).length;
    return count > 0 && count < ids.length;
  }
  function toggleBranchGroup(modules: Array<{ endpoints: any[] }>, checked: boolean) {
    const selected = new Set(branchEndpointIds.value);
    branchGroupEndpointIds(modules).forEach((endpointId) => checked ? selected.add(endpointId) : selected.delete(endpointId));
    branchEndpointIds.value = Array.from(selected);
  }
  function selectBranchScope(type: 'project' | 'module', projectId: number, moduleId?: number | null) {
    branchActiveScope.value = { type, projectId, ...(type === 'module' ? { moduleId: moduleId ?? null } : {}) };
  }
  function isBranchScope(type: 'project' | 'module', projectId: number, moduleId?: number | null) {
    return branchActiveScope.value.type === type && branchActiveScope.value.projectId === projectId
      && (type !== 'module' || branchActiveScope.value.moduleId === (moduleId ?? null));
  }
  function selectBranchProjectScopeAndToggle(projectId: number) {
    selectBranchScope('project', projectId);
    expandedBranchProjects.value = expandedBranchProjects.value.includes(projectId)
      ? expandedBranchProjects.value.filter((item) => item !== projectId)
      : [...expandedBranchProjects.value, projectId];
  }
  const emptyCondition = (): ScenarioBranchCondition => ({ source: 'step', step_id: null, path: '$.code', operator: 'equals', expected: '' });
  function addConditionRule() { branchForm.conditions.push(emptyCondition()); }
  function resetBranchForm() { branchForm.name = ''; branchForm.logic = 'or'; branchForm.conditions = [emptyCondition()]; }
  function branchConditionSummary(branch: any) {
    const conditions = branch.conditions || [];
    if (!conditions.length) return '未配置条件';
    return conditions.map((item: any) => item.source === 'step' ? `${item.path || '$'} ${operatorLabel(item.operator)} ${item.expected || ''}` : `${item.variable || '变量'} ${operatorLabel(item.operator)} ${item.expected || ''}`).join(branchForm.logic === 'or' ? ' 或 ' : ' 且 ');
  }
  function operatorLabel(operator: string) { return conditionOperatorOptions.find((item) => item.value === operator)?.label || operator; }
  async function addConditionNode() {
    try {
      await ensureScenarioSaved();
      const node: any = await flowNodeApi.createData({ scenario: id, node_type: 'condition', name: '判断分支', order: steps.value.length + 1, condition_logic: 'or', step: null, parent_branch: null } as any);
      await loadSteps();
      message.success('判断分支已添加');
    } catch (error: any) { message.error(error.message || '添加判断分支失败'); }
  }
  function openConditionEditor(node: any) { editingConditionNode.value = node; editingBranch.value = null; editingConditionOnly.value = true; resetBranchForm(); branchForm.name = node.name; branchForm.logic = node.condition_logic || 'and'; branchEditorVisible.value = true; }
  function openBranchEditor(node: any, branch: any) {
    editingConditionNode.value = node; editingBranch.value = branch; editingConditionOnly.value = false; branchForm.name = branch.name; branchForm.logic = node.condition_logic || 'and'; branchForm.conditions = JSON.parse(JSON.stringify(branch.conditions || [emptyCondition()])); branchEditorVisible.value = true;
  }
  async function addBranch(node: any) { editingConditionNode.value = node; editingBranch.value = null; editingConditionOnly.value = false; resetBranchForm(); branchForm.name = '新分支'; branchEditorVisible.value = true; }
  async function saveBranch() {
    if (!editingConditionNode.value || !branchForm.name.trim()) { message.warning('请填写分支名称'); return; }
    if (editingConditionOnly.value) {
      try {
        branchSaving.value = true;
        await flowNodeApi.update(editingConditionNode.value.id, { ...editingConditionNode.value, name: branchForm.name.trim(), condition_logic: branchForm.logic, step: null, parent_branch: null } as any);
        branchEditorVisible.value = false; await loadSteps(); message.success('判断节点已保存');
      } catch (error: any) { message.error(error.message || '判断节点保存失败'); }
      finally { branchSaving.value = false; }
      return;
    }
    if (!editingBranch.value) {
      // 判断节点编辑与新增分支共享弹窗，新建分支时名称属于分支。
      try {
        branchSaving.value = true;
        await branchApi.createData({ condition_node: editingConditionNode.value.id, name: branchForm.name.trim(), order: (editingConditionNode.value.branches || []).length + 1, conditions: branchForm.conditions } as any);
        await flowNodeApi.update(editingConditionNode.value.id, { ...editingConditionNode.value, condition_logic: branchForm.logic, step: null, parent_branch: null } as any);
        branchEditorVisible.value = false; await loadSteps(); message.success('分支已保存');
      } catch (error: any) { message.error(error.message || '分支保存失败'); }
      finally { branchSaving.value = false; }
      return;
    }
    try {
      branchSaving.value = true;
      await branchApi.update(editingBranch.value.id, { ...editingBranch.value, name: branchForm.name.trim(), conditions: branchForm.conditions } as any);
      await flowNodeApi.update(editingConditionNode.value.id, { ...editingConditionNode.value, name: editingConditionNode.value.name, condition_logic: branchForm.logic, step: null, parent_branch: null } as any);
      branchEditorVisible.value = false; await loadSteps(); message.success('分支已保存');
    } catch (error: any) { message.error(error.message || '分支保存失败'); }
    finally { branchSaving.value = false; }
  }
  async function removeBranch(branch: any) { await branchApi.DeleteDataByID(branch.id); await loadSteps(); }
  function toggleBranchCollapsed(branchId: number) {
    const next = new Set(collapsedBranchIds.value);
    if (next.has(branchId)) next.delete(branchId); else next.add(branchId);
    collapsedBranchIds.value = next;
  }
  function toggleConditionCollapsed(nodeId: number) {
    const next = new Set(collapsedConditionIds.value);
    if (next.has(nodeId)) next.delete(nodeId); else next.add(nodeId);
    collapsedConditionIds.value = next;
  }
  async function removeFlowNode(node: any) { await flowNodeApi.DeleteDataByID(node.node_id || node.id); await loadSteps(); }
  async function openBranchEndpointPicker(branch: any) {
    targetBranch.value = branch; branchEndpointIds.value = []; branchEndpointSearch.value = '';
    branchEndpointMethodFilter.value = 'all'; branchActiveScope.value = { type: 'all' };
    try {
      await loadInterfaceTree();
      expandedBranchProjects.value = endpointTree.value.map((project) => project.id);
      branchEndpointPickerVisible.value = true;
    } catch (error: any) {
      message.error(error.message || '接口列表加载失败，请稍后重试');
    }
  }
  async function addEndpointsToBranch() {
    if (!targetBranch.value || !branchEndpointIds.value.length) return;
    try {
      const endpointIds = await validateSelectedEndpointIds('branch');
      let order = (targetBranch.value.nodes || []).length + 1;
      for (const endpoint of endpointIds) {
        const created: any = await stepApi.createData({ scenario: id, endpoint, order: 100000 + order, request_override: {}, extract: {}, validate: {}, post_sql: [], polling: {}, continue_on_failure: true, retry_on_failure: false, failure_retry_count: 1 });
        const nodes = asList(await flowNodeApi.getDataList({ scenario: id, main: true }));
        const node = nodes.find((item: any) => item.step === created.id);
        if (node) await flowNodeApi.update(node.id, { ...node, parent_branch: targetBranch.value.id, order, node_type: 'endpoint' } as any);
        order += 1;
      }
      branchEndpointPickerVisible.value = false; await loadSteps(); message.success('接口已添加到分支');
    } catch (error: any) { message.error(error.message || '添加分支接口失败'); }
  }
  async function copyBranchStep(child: any, branch: any) {
    try {
      const stepInfo = child.step_info || {};
      if (!stepInfo.endpoint) { message.warning('该步骤未关联接口，无法复制'); return; }
      const branchId = branch.id;
      const origStepId = child.step_info?.id;
      // 克隆步骤配置；signal 会在主流程末尾自动生成一个 flow node，随后移动到目标分支。
      const created: any = await stepApi.createData({
        scenario: id,
        endpoint: stepInfo.endpoint,
        order: 100000 + ((branch.nodes || []).length + 1),
        request_method: stepInfo.request_method || '',
        request_url: stepInfo.request_url || '',
        request_override: JSON.parse(JSON.stringify(stepInfo.request_override ?? {})),
        extract: JSON.parse(JSON.stringify(stepInfo.extract ?? {})),
        validate: JSON.parse(JSON.stringify(stepInfo.validate ?? {})),
        post_sql: JSON.parse(JSON.stringify(stepInfo.post_sql ?? [])),
        polling: JSON.parse(JSON.stringify(stepInfo.polling ?? {})),
        continue_on_failure: stepInfo.continue_on_failure !== false,
        retry_on_failure: Boolean(stepInfo.retry_on_failure),
        failure_retry_count: Math.min(5, Math.max(1, Number(stepInfo.failure_retry_count) || 1)),
      });
      const nodes = asList(await flowNodeApi.getDataList({ scenario: id, main: true }));
      const node = nodes.find((item: any) => item.step === created.id);
      if (node) {
        await flowNodeApi.update(node.id, { ...node, parent_branch: branchId, order: 100000 + ((branch.nodes || []).length + 1), node_type: 'endpoint' } as any);
      }
      await loadSteps();
      // 复制体默认追加到分支末尾，这里把它移动到原步骤之后。
      const freshBranch = steps.value
        .filter((s: any) => s.node_type === 'condition')
        .flatMap((s: any) => s.branches || [])
        .find((b: any) => b.id === branchId);
      if (freshBranch) {
        const arr = freshBranch.nodes.slice();
        const origIdx = arr.findIndex((c: any) => c.id === child.id || c.step === child.step || c.step_info?.id === origStepId);
        const newIdx = arr.findIndex((c: any) => c.step_info?.id === created.id);
        if (origIdx !== -1 && newIdx !== -1) {
          const [copied] = arr.splice(newIdx, 1);
          arr.splice(origIdx + 1, 0, copied);
          await flowNodeApi.reorder(id, arr.map((c: any) => c.id), branchId);
        }
      }
      await loadSteps();
      message.success('已复制分支接口');
    } catch (error: any) {
      message.error(error.message || '复制分支接口失败');
    }
  }
  function openBranchStepEditor(step: any) {
    initializeStep(step);
    branchEditingStep.value = step;
    activeConfigTabs[step.id] ||= 'request_override';
    branchStepEditorVisible.value = true;
  }
  function toggleBranchStep(step: any) {
    if (!step?.id) return;
    initializeStep(step);
    expandedId.value = expandedId.value === step.id ? null : step.id;
  }
  function openStepConfig(step: any, tab: 'extract' | 'validate') {
    const stepId = Number(step?.id);
    if (!stepId) return;
    initializeStep(step);
    expandedId.value = stepId;
    activeConfigTabs[stepId] = tab;
  }
  async function saveBranchStep() {
    if (!branchEditingStep.value) return;
    await saveStep(branchEditingStep.value);
    branchStepEditorVisible.value = false;
    await loadSteps();
  }
  async function saveBranchOrder(branch: any) {
    try {
      await flowNodeApi.reorder(id, (branch.nodes || []).map((node: any) => node.id), branch.id);
      await loadSteps();
      message.success('分支接口顺序已更新');
    } catch (error: any) { message.error(error.message || '更新分支接口顺序失败'); await loadSteps(); }
  }
  function toggleStep(stepId: number) { expandedId.value = expandedId.value === stepId ? null : stepId; }
  function back() { router.push({ name: 'case_api_scenario' }); }

  async function loadProjectVariables() {
    if (!form.projects.length) {
      projectVariables.value = [];
      return;
    }
    try {
      const payload = await projectVariableApi.getDataList({ project: form.projects.join(',') });
      projectVariables.value = asList(payload).map((variable: any) => ({
        id: variable.id, name: variable.name || '', value: variable.value ?? '', description: variable.description || '', project_name: variable.project_name,
      }));
    } catch {
      projectVariables.value = [];
    }
  }

  async function loadDynamicFunctions() {
    if (!form.projects.length) {
      dynamicFunctions.value = [];
      return;
    }
    try {
      const payload = await dynamicFunctionApi.getDataList({ projects: form.projects.join(','), page: 1, pageSize: 999 });
      dynamicFunctions.value = asList(payload).filter((item: any) => item.enabled !== false);
    } catch {
      dynamicFunctions.value = [];
    }
  }

  watch(() => form.projects, async () => {
    refreshEnvironmentOptions(Boolean(runEnvironment.value));
    await Promise.all([loadInterfaceTree(), loadProjectVariables(), loadDynamicFunctions()]);
  }, { deep: true });
  const studioTheme = { common: { primaryColor: '#008b95', primaryColorHover: '#009da6', primaryColorPressed: '#00747d', primaryColorSuppl: '#008b95', borderRadius: '5px', textColorBase: '#203044' }, Button: {fontWeight: '500'}, Tabs: {tabTextColorActiveLine: '#008b95',barColor:'#008b95'} };
  const selectedConditionId = ref<number | null>(null);
  const requestPanel = ref<any>();
  const togglingNodeId = ref<number | null>(null);
  const selectedStudioSteps = computed(() => selectedConditionId.value ? [] : allEndpointSteps.value.filter((step: any) => step.id === expandedId.value));
  const selectedStudioCondition = computed(() => steps.value.find((node: any) => node.node_type === 'condition' && node.node_id === selectedConditionId.value));
  const studioRunLogs = computed(() => allEndpointSteps.value.filter((step: any) => runResults[step.id]).map((step: any) => ({id:step.id,name:step.endpoint_name || '未命名接口',result:runResults[step.id]})));
  const studioVariableItems = computed(() => {
    const current = selectedStudioSteps.value[0];
    const allowed = new Set(current ? availableVariables(current).filter((item: any) => item.scope !== 'project').map((item: any) => `extract-${item.stepId}-${item.name}`) : []);
    return sceneVariableItems.value.filter(item => item.category !== 'extract' || allowed.has(item.key)).map(item => {
      if (item.category !== 'extract') return item;
      const match = item.key.match(/^extract-(\d+)-/); const result = match ? runResults[Number(match[1])]?.extracted : undefined;
      const hasValue = result && Object.prototype.hasOwnProperty.call(result,item.name);
      return {...item, source:item.source.replace(/ · \$.*$/, ''), value:hasValue ? (typeof result[item.name] === 'string' ? result[item.name] : JSON.stringify(result[item.name])) : '执行后提取', sensitive:/token|secret|password|authorization/i.test(item.name)};
    });
  });
  const studioVariableTabs = computed(() => [{key:'all',label:'全部'},{key:'extract',label:'上游提取'},{key:'project',label:'项目参数'},{key:'function',label:'函数'}].map(item => ({...item,count:studioVariableItems.value.filter(v=>item.key === 'all' || v.category === item.key).length})));
  const studioVariableGroups = computed(() => {
    const query = sceneVariableSearch.value.toLowerCase().trim();
    return [{key:'extract',label:'上游提取'},{key:'project',label:'项目参数'},{key:'function',label:'动态函数'}].map(group=>({...group,items:studioVariableItems.value.filter(v=>v.category === group.key && (sceneVariableCategory.value === 'all' || v.category === sceneVariableCategory.value) && (!query || [v.name,v.reference,v.source].some(text=>text.toLowerCase().includes(query))))})).filter(group=>group.items.length);
  });
  function selectStudioStep(step: any) { if (!step?.id) return; if (!editText[step.id]) initializeStep(step); selectedConditionId.value = null; expandedId.value = step.id; }
  function selectStudioNode(node: any) { if (node.node_type === 'condition') {selectedConditionId.value = node.node_id; expandedId.value = null;} else selectStudioStep(node); }
  function studioStepOrdinal(stepId: number) { for (let i=0;i<steps.value.length;i++) {const node=steps.value[i];if (node.node_type === 'endpoint' && node.id === stepId) return String(i+1).padStart(2,'0');for (const branch of node.branches || []) {const index=(branch.nodes || []).findIndex((child:any)=>child.step_info?.id === stepId);if(index>=0)return `${i+1}.${index+1}`;}}return ''; }
  function studioStepSource(step: any) { const endpoint=step.endpoint_info || {}; const project=projectOptions.value.find(item=>item.value === endpoint.project)?.label;return [project,endpoint.module_name,step.endpoint_name].filter(Boolean).join(' / '); }
  function openSourceEndpoint(step: any) { if(step.endpoint) router.push({name:'case_api_endpoint_edit',params:{id:step.endpoint}});else message.warning('原接口已不存在'); }
  function studioBranchFor(step: any) { for(const node of steps.value)for(const branch of node.branches || []){const child=(branch.nodes || []).find((child:any)=>child.step_info?.id === step.id);if(child)return {branch,child};}return null; }
  function copyStudioStep(step: any) { const located=studioBranchFor(step); if(located) return copyBranchStep(located.child,located.branch);return copyStep(step); }
  function removeStudioStep(step: any) { const located=studioBranchFor(step); if(located) return removeFlowNode(located.child);return removeStep(step.id); }
  function referenceStudioVariable(variable: SceneVariableItem) {const panel=Array.isArray(requestPanel.value) ? requestPanel.value[0] : requestPanel.value;if(!panel){copySceneVariable(variable);return;}panel.insertVariable(variable.reference);message.success('已插入变量');}
  async function toggleNodeEnabled(node: any, enabled: boolean) {const nodeId=node.node_id || node.id;togglingNodeId.value=nodeId;try{await flowNodeApi.update(nodeId,{scenario:id,node_type:node.node_type,step:node.node_type === 'endpoint' ? node.step_id || node.step : null,name:node.node_type === 'condition' ? node.name : '',enabled} as any);node.enabled=enabled;}catch(error:any){message.error(error.message || '更新启用状态失败');}finally{togglingNodeId.value=null;}}
  onMounted(load);
</script>

<style scoped>
  .post-sql-list { display: grid; gap: 12px; }
  .post-sql-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: 10px; padding: 12px 14px; border: 1px solid #e4e9f1; border-radius: 8px; background: #fbfcfe; }
  .post-sql-row :deep(textarea) { font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; line-height: 1.6; }
  .scene-page { max-width: 1240px; margin: 16px auto 32px; }
  .scene-card { margin-bottom: 16px; border: 1px solid #edf0f5; border-radius: 8px; box-shadow: 0 1px 3px rgb(31 35 41 / 4%); }
  .card-title { color: #1f2329; font-size: 18px; font-weight: 600; }
  .page-actions { display: flex; gap: 10px; }
  .steps-actions { display: flex; align-items: center; gap: 12px; }
  .run-environment { width: 190px; }
  .basic-card :deep(.n-card-header) { padding: 22px 28px 10px; }
  .basic-card :deep(.n-card__content) { padding: 4px 28px 22px; }
  .basic-fields { display: grid; grid-template-columns: 1fr 1fr 1.35fr; gap: 20px; }
  .basic-fields :deep(.n-form-item) { margin-bottom: 0; }
  .basic-fields :deep(.n-form-item-label) { padding-bottom: 8px; color: #4e5969; font-weight: 500; }
  .steps-card :deep(.n-card-header) { padding: 22px 28px 16px; }
  .steps-card :deep(.n-card__content) { padding: 0 28px 28px; }
  .add-row { display: grid; grid-template-columns: minmax(360px, 1fr) auto; gap: 12px; align-items: center; margin-bottom: 18px; }
  .endpoint-select-trigger { width: 100%; min-height: 40px; padding: 0 13px; border: 1px solid #d7dee8 !important; border-radius: 6px; color: #667085; text-align: left; background: #fff !important; box-shadow: 0 1px 2px rgb(31 35 41 / 3%); transition: border-color .16s, box-shadow .16s, background .16s; }
  .endpoint-select-trigger:hover, .endpoint-select-trigger:focus { border-color: #78aef8 !important; background: #fbfdff !important; box-shadow: 0 0 0 3px rgb(22 119 255 / 8%); }
  .endpoint-select-trigger--active { border-color: #91c2ff !important; color: #1677ff; background: #f6faff !important; }
  .endpoint-select-trigger :deep(.n-button__content) { display: flex; width: 100%; min-width: 0; align-items: center; justify-content: space-between; }
  .endpoint-select-text { overflow: hidden; font-size: 14px; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
  .select-arrow { margin-left: 18px; color: #8c9aae; font-size: 17px; line-height: 1; }
  .endpoint-picker-dropdown { display: flex; flex-direction: column; width: min(960px, calc(100vw - 48px)); height: min(460px, calc(100vh - 120px)); max-height: calc(100vh - 120px); overflow: hidden; border: 1px solid #d8dee8; border-radius: 9px; background: #fff; box-shadow: 0 12px 30px rgb(31 47 70 / 16%); }
  .picker-toolbar { display: flex; flex: none; align-items: center; justify-content: space-between; gap: 16px; min-height: 64px; padding: 0 20px; border-bottom: 1px solid #e6eaf0; background: #fff; }
  .picker-title { flex: none; color: #1f2937; font-size: 18px; font-weight: 700; }
  .picker-actions { display: flex; flex: 1; align-items: center; justify-content: flex-end; gap: 10px; }
  .picker-search { width: 300px; }
  .picker-empty { padding: 40px 0; }
  .endpoint-picker-content { display: grid; flex: 1; grid-template-columns: 310px minmax(0, 1fr); min-height: 0; overflow: hidden; background: #fff; }
  .endpoint-browser { min-height: 0; overflow: auto; border-right: 1px solid #e0e6ee; background: #f7f9fc; }
  .browser-heading { padding: 20px 20px 12px; color: #303b4c; font-size: 16px; font-weight: 700; }
  .browser-project { padding: 0 12px; }
  .browser-node { display: flex; align-items: center; gap: 9px; min-height: 42px; padding: 0 10px; border-radius: 7px; }
  .browser-project-node { background: #edf2f8; }
  .browser-node.active { background: #e6f0ff; }
  .browser-node :deep(.n-checkbox) { flex: none; }
  .browser-node-name { min-width: 0; flex: 1; overflow: hidden; border: 0; color: #344054; font: inherit; font-size: 15px; font-weight: 600; text-align: left; text-overflow: ellipsis; white-space: nowrap; background: transparent; cursor: pointer; }
  .browser-module-list { margin: 4px 0 4px 21px; padding-left: 12px; border-left: 1px solid #e0e6ee; }
  .browser-module-node { min-height: 38px; margin: 2px 0; }
  .browser-module-node .browser-node-name { font-weight: 500; }
  .browser-node-count { display: inline-grid; flex: none; place-items: center; min-width: 24px; height: 24px; padding: 0 5px; border-radius: 5px; color: #526174; font-size: 12px; font-weight: 700; background: #e2e7ef; }
  .browser-expand { display: inline-grid; flex: none; place-items: center; width: 22px; height: 28px; padding: 0; border: 0; color: #536174; font-size: 20px; line-height: 1; background: transparent; cursor: pointer; }
  .browser-expand-placeholder { color: transparent; cursor: default; }
  .endpoint-list-panel { min-width: 0; min-height: 0; padding: 16px; overflow: auto; background: #fbfcfe; }
  .endpoint-list-head { position: sticky; top: -16px; z-index: 1; display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 16px 2px 12px; color: #263244; font-size: 18px; font-weight: 700; background: #fbfcfe; }
  .endpoint-list-head > div { display: flex; align-items: center; gap: 12px; }
  .endpoint-method-filter { width: 190px; }
  .loaded-count { color: #526174; font-size: 13px; font-weight: 500; white-space: nowrap; }
  .endpoint-table { overflow: hidden; border: 1px solid #dfe5ed; border-radius: 8px; background: #fff; }
  .endpoint-table-row { display: grid; grid-template-columns: 38px minmax(120px, 1fr) 90px minmax(180px, 1.65fr) 62px; gap: 10px; align-items: center; min-height: 48px; padding: 0 14px; border-top: 1px solid #e8ecf1; color: #344054; font-size: 14px; }
  .endpoint-table-row:first-child { border-top: 0; }
  .endpoint-table-row:not(.endpoint-table-header):hover { background: #f7faff; }
  .endpoint-table-header { min-height: 42px; color: #475467; font-size: 13px; font-weight: 700; background: #f3f5f8; }
  .endpoint-table-name { overflow: hidden; color: #1f2937; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
  .endpoint-table-url { overflow: hidden; color: #526174; font: 13px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; text-overflow: ellipsis; white-space: nowrap; }
  .picker-method-tag { display: inline-block; min-width: 46px; padding: 3px 7px; border-radius: 4px; font-size: 12px; font-weight: 700; text-align: center; }
  .picker-table-empty { padding: 36px 0; }
  @media (max-width: 760px) {
    .picker-toolbar { align-items: flex-start; flex-direction: column; padding: 14px; }
    .picker-actions { width: 100%; justify-content: flex-start; flex-wrap: wrap; }
    .picker-search { width: min(300px, 100%); }
    .endpoint-picker-content { grid-template-columns: 1fr; }
    .endpoint-browser { max-height: 190px; border-right: 0; border-bottom: 1px solid #e0e6ee; }
    .endpoint-table-row { grid-template-columns: 30px minmax(100px, 1fr) 70px minmax(150px, 1.3fr) 54px; gap: 6px; padding: 0 8px; }
  }
  .step-card { margin-top: 12px; overflow: hidden; border: 1px solid #e3e8f0; border-radius: 7px; background: #fff; transition: border-color .18s, box-shadow .18s; }
  .condition-card { position: relative; margin-top: 14px; overflow: hidden; border: 1px solid #8eb8ff; border-radius: 12px; background: #fbfdff; box-shadow: 0 8px 24px rgb(36 104 242 / 7%); }
  .condition-head { display: flex; align-items: center; min-height: 70px; gap: 12px; padding: 0 20px; border-bottom: 1px solid #dce9ff; background: linear-gradient(90deg, #f1f6ff, #fbfdff); }.condition-head--collapsible { cursor: pointer; user-select: none; }.condition-chevron { width: 18px; color: #718198; font-size: 18px; text-align: center; }
  .condition-marker { display: grid; place-items: center; width: 30px; height: 30px; color: #2468f2; font-size: 24px; }.condition-subtitle { margin-top: 5px; color: #718198; font-size: 13px; }
  .branch-list { position: relative; display: grid; gap: 12px; margin: 16px 20px 12px 62px; padding-left: 20px; border-left: 2px solid #8eb8ff; }.branch-lane { padding: 12px; border: 1px solid #cfe1ff; border-radius: 8px; background: #fff; }.branch-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 9px; color: #26344a; }.branch-head--collapsible { cursor: pointer; user-select: none; }.branch-head > div { display: flex; gap: 8px; align-items: center; min-width: 0; }.branch-chevron { width: 18px; color: #7d8795; font-size: 16px; text-align: center; }.condition-chip { overflow: hidden; max-width: 520px; padding: 2px 7px; border-radius: 4px; color: #33734c; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; background: #eaf8ef; }.branch-step-card { margin-top: 8px; }.branch-step-head { min-height: 58px; padding: 0 12px; }.branch-step-order { color: #4975c9; font-variant-numeric: tabular-nums; }.branch-drag-handle { color: #8b95a7; font-size: 16px; letter-spacing: -4px; cursor: grab; }.branch-step-body { padding-left: 48px; }.branch-step-tools { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; color: #7d8795; font-size: 12px; }.branch-add-button { width: 100%; margin-top: 10px; border-color: #b8d1fa !important; color: #2468f2 !important; background: #f8fbff !important; }.add-branch-button { justify-self: start; margin: 2px 0 0; }.branch-merge { margin: 0 20px 16px 62px; padding: 7px 14px; border: 1px solid #c6dcff; border-radius: 5px; color: #2468f2; font-size: 13px; font-weight: 600; text-align: center; background: #eef5ff; }
  .branch-picker-toolbar { display: grid; grid-template-columns: minmax(220px, 1fr) 180px 180px auto; align-items: center; gap: 10px; margin-bottom: 14px; color: #667085; font-size: 13px; }.branch-picker-table { max-height: min(520px, calc(100vh - 300px)); overflow: auto; border: 1px solid #dfe5ed; border-radius: 8px; }.branch-picker-table .endpoint-table-row { grid-template-columns: 38px minmax(150px, 1fr) minmax(160px, .9fr) 80px minmax(180px, 1.2fr); }.editor-modal-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; color: #7d8795; font-size: 12px; }.branch-step-editor-info { display: flex; align-items: center; gap: 9px; margin-bottom: 14px; padding: 10px 12px; border: 1px solid #e4eaf2; border-radius: 7px; color: #475467; background: #f8fafc; }.branch-step-editor-info code { overflow: hidden; color: #778399; text-overflow: ellipsis; white-space: nowrap; }
  .branch-editor-top { display: grid; grid-template-columns: minmax(0, 1fr) 180px; gap: 16px; }.form-inline-tip { display: block; margin-top: 6px; color: #8a96a8; font-size: 12px; }.condition-editor-row { display: grid; grid-template-columns: 120px minmax(0, 1fr) minmax(0, 1fr) 110px minmax(0, 1fr) auto; gap: 8px; align-items: center; margin-bottom: 10px; padding: 10px; border: 1px solid #e5eaf1; border-radius: 7px; background: #fbfcfe; }.condition-editor-row > * { min-width: 0; }
  .step-card.expanded { border-color: #bad6ff; box-shadow: 0 3px 12px rgb(22 119 255 / 8%); }
  .step-card.passed { border-left: 4px solid #36a269; }
  .step-card.failed { border-left: 4px solid #e4555b; }
  .step-head { display: flex; align-items: center; min-height: 64px; padding: 0 18px; gap: 12px; cursor: pointer; }
  .drag-handle { cursor: grab; color: #8b95a7; font-size: 19px; letter-spacing: -4px; }
  .step-no { display: grid; flex: none; place-items: center; width: 30px; height: 30px; border: 1px solid #b9d8ff; border-radius: 50%; color: #1677ff; font-size: 14px; }
  .step-summary { min-width: 0; flex: 1; }
  .step-name { overflow: hidden; color: #1f2329; font-size: 15px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
  .step-url { display: flex; align-items: center; gap: 8px; margin-top: 5px; overflow: hidden; color: #8b95a7; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
  .method-pill { display: inline-block; min-width: 38px; padding: 2px 6px; border-radius: 3px; background: #f2f4f7; color: #667085; font-size: 11px; font-weight: 700; text-align: center; }
  .delete-button { margin-left: 2px; }
  .chevron { width: 16px; color: #8b95a7; font-size: 18px; text-align: center; }
  .step-body { padding: 0 18px 18px 72px; border-top: 1px solid #edf0f5; background: #fff; }
  .json-editor { display: grid; grid-template-columns: 42px minmax(0, 1fr); min-height: 182px; background: #fff; }
  .editor-gutter { margin: 0; padding: 14px 8px 14px 0; overflow: hidden; border-right: 1px solid #edf0f4; color: #a1a9b5; font: 13px/20px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; text-align: right; user-select: none; }
  .json-editor :deep(.n-input) { height: 100%; }
  .json-editor :deep(.n-input-wrapper) { height: 100%; padding: 0; border: 0; border-radius: 0; box-shadow: none !important; background: transparent; }
  .json-editor :deep(.n-input__textarea-el) { min-height: 100% !important; padding: 14px 16px; color: #364152; font: 13px/20px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background: transparent; }
  .compact-editor { min-height: 96px; border: 1px solid #e4e9f1; border-radius: 5px; overflow: hidden; }
  .extract-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; color: #7d8795; font-size: 12px; }
  .extract-rule-table { border: 1px solid #e4e9f1; border-radius: 12px; overflow: hidden; }
  .extract-rule-row { display: grid; grid-template-columns: minmax(110px, 1.1fr) 120px 120px minmax(160px, 1.8fr) 96px 44px; gap: 10px; align-items: center; padding: 10px 14px; border-top: 1px solid #edf0f5; }
  .extract-rule-row:first-child { border-top: 0; }
  .extract-rule-header { color: #687386; background: #f8fafc; font-size: 12px; font-weight: 600; }
  .extract-rule-header span:last-child { text-align: center; }
  .extract-empty { padding: 18px 0; }
  .validate-rule-table { border: 1px solid #e4e9f1; border-radius: 12px; overflow: hidden; }
  .validate-rule-row { display: grid; grid-template-columns: minmax(160px, 1fr) 130px minmax(160px, 1fr) 44px; gap: 10px; align-items: center; padding: 10px 14px; border-top: 1px solid #edf0f5; }
  .validate-rule-row:first-child { border-top: 0; }
  .validate-rule-header { color: #687386; background: #f8fafc; font-size: 12px; font-weight: 600; }
  .validate-rule-header span:last-child { text-align: center; }
  .extract-tip { margin-top: 10px; color: #7d8795; font-size: 12px; line-height: 1.75; }
  .extract-tip code { padding: 1px 4px; border-radius: 3px; background: #f3f5f8; color: #536174; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  .advanced-collapse { border: 1px solid #dfe5ed; border-radius: 6px; background: #fff; overflow: hidden; }
  .config-collapse { margin-top: 10px; box-shadow: 0 1px 2px rgb(31 35 41 / 2%); }
  .request-collapse { margin-top: 0; }
  .step-config-tabs { margin-top: 10px; }
  .step-config-tabs :deep(.n-tabs-nav) { margin-bottom: 10px; }
  .step-config-tabs :deep(.n-tabs-tab) { font-weight: 600; }
  .step-config-tabs :deep(.n-tab-pane) { min-height: 96px; }
  .variable-assistant { margin-bottom: 12px; overflow: hidden; border: 1px solid #dce8f8; border-radius: 7px; background: #f8fbff; }
  .variable-assistant-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 52px; padding: 0 14px; border-bottom: 1px solid #e3edf9; background: #f2f7ff; }
  .variable-assistant-head > div { display: flex; align-items: baseline; gap: 10px; min-width: 0; }
  .variable-assistant-head strong { color: #294466; font-size: 14px; }
  .variable-assistant-head span { overflow: hidden; color: #8190a4; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
  .available-variables { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; padding: 10px 14px; }
  .variable-label { margin-right: 2px; color: #6f7f94; font-size: 12px; }
  .variable-chip { display: inline-flex; align-items: center; gap: 5px; padding: 3px 7px; border: 1px solid #cee0f8; border-radius: 4px; background: #fff; }
  .variable-chip code { color: #216fd2; font: 12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
  .variable-chip em { color: #8996a8; font-size: 11px; font-style: normal; }
  .variable-suggestion-list { display: grid; gap: 4px; margin: 0 14px 10px; padding: 7px 9px; border: 1px solid #e3eaf7; border-radius: 6px; background: #fbfcff; }
  .variable-suggestion-item { display: grid; min-width: 0; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 12px; min-height: 34px; color: #66758a; font-size: 12px; }
  .variable-suggestion-item > span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .variable-suggestion-item :deep(.n-button) { width: auto; flex: none; margin: 0; }
  .variable-suggestion-item code { display: block; min-width: 0; overflow: hidden; color: #376bff; font: 12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
  .variable-empty { padding: 11px 14px; color: #8895a6; font-size: 12px; }
  .suggestion-list { border-top: 1px solid #e3edf9; background: #fff; }
  .suggestion-row { display: grid; grid-template-columns: minmax(150px, .9fr) 16px minmax(190px, 1fr) minmax(180px, 1fr) auto; align-items: center; gap: 8px; min-height: 42px; padding: 7px 14px; border-top: 1px solid #eff3f8; color: #536174; font-size: 12px; }
  .suggestion-row:first-child { border-top: 0; }
  .suggestion-source { overflow: hidden; color: #526f92; text-overflow: ellipsis; white-space: nowrap; }
  .suggestion-arrow { color: #8ea1b8; text-align: center; }
  .suggestion-target { overflow: hidden; color: #435368; text-overflow: ellipsis; white-space: nowrap; }
  .suggestion-target code { color: #236fce; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
  .suggestion-extract { overflow: hidden; color: #718096; text-overflow: ellipsis; white-space: nowrap; }
  .override-tip { margin-top: 8px; color: #8a96a6; font-size: 12px; line-height: 1.6; }
  .advanced-collapse :deep(.n-collapse-item__header),
  .advanced-collapse :deep(.n-collapse-item__header-main) { color: #303844; font-size: 15px; font-weight: 700; line-height: 22px; }
  .advanced-collapse :deep(.n-collapse-item__header) { min-height: 56px; padding: 0 18px; background: #f6f8fa; }
  .advanced-collapse :deep(.n-collapse-item__content-wrapper) { padding: 0; background: #fff; }
  .advanced-collapse :deep(.n-collapse-item__content-inner) { padding: 0 !important; }
  .response-panel { margin-top: 16px; overflow: hidden; border: 1px solid #dfe6ee; border-radius: 12px; background: #fff; }
  .response-passed { border-color: #b8e0c6; }
  .response-failed { border-color: #f0c2c5; }
  .response-title { display: flex; justify-content: space-between; min-height: 48px; padding: 0 16px; align-items: center; gap: 12px; color: #303844; background: #f6f8fa; font-size: 15px; font-weight: 700; }
  .response-title .response-label { color: inherit; font-size: inherit; font-weight: inherit; }
  .response-title-actions { display: flex; align-items: center; gap: 10px; }
  .response-title-actions > span { color: #7d8795; font-size: 12px; font-weight: 400; white-space: nowrap; }
  .response-search-box { display: inline-flex; align-items: center; gap: 7px; }
  .response-search { width: 230px; }
  .response-search-count { min-width: 42px; color: #376bff; font-size: 12px; font-weight: 600; text-align: center; }
  .response-passed .response-title { color: #287b47; background: #f1fbf4; }
  .response-failed .response-title { color: #bd3d44; background: #fff6f6; }
  .response-errors { margin: 12px 16px 0; padding: 9px 10px; border-radius: 4px; color: #bd3d44; background: #fff0f0; font-size: 12px; line-height: 1.55; }
  .response-search-empty { margin: 12px 16px 0; padding: 8px 10px; border: 1px solid #f3d6a4; border-radius: 5px; color: #9a6700; background: #fffaf0; font-size: 12px; }
  .response-attempts { display: grid; gap: 4px; margin: 12px 16px 0; padding: 9px 10px; border-left: 3px solid #94c1f9; color: #607087; background: #f7faff; font-size: 12px; line-height: 1.55; }
  .data-driven-run-results { display: flex; flex-wrap: wrap; gap: 7px; margin: 12px 16px 0; }
  .data-driven-run-results span { padding: 5px 8px; border-radius: 4px; font-size: 12px; line-height: 1.45; }
  .data-driven-run-passed { color: #287b47; background: #effaf2; }
  .data-driven-run-failed { color: #bd3d44; background: #fff0f1; }
  .response-body { max-height: 320px; margin: 12px 16px 16px; padding: 11px 12px; overflow: auto; border: 1px solid #e4e9ef; border-radius: 4px; color: #344254; background: #f8fafc; font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; white-space: pre-wrap; }
  .response-body :deep(.response-match) { padding: 1px 2px; border-radius: 3px; color: #8a4b00; background: #ffe3a3; }
  .response-body :deep(.response-match.is-active) { outline: 2px solid #376bff; color: #102a6b; background: #a9c7ff; }
  .polling-config { margin-top: 2px; padding: 18px; border: 1px solid #e4e9f1; border-radius: 12px; background: #fff; }
  .polling-tab-title { display: flex; align-items: center; justify-content: space-between; padding-bottom: 14px; border-bottom: 1px solid #edf0f5; color: #303844; font-size: 15px; font-weight: 700; }
  .polling-header { display: flex; align-items: center; justify-content: space-between; width: 100%; padding-right: 8px; }
  .polling-grid { display: grid; grid-template-columns: repeat(3, minmax(130px, 1fr)); gap: 14px; margin-top: 16px; }
  .polling-grid label { display: grid; gap: 7px; color: #687386; font-size: 12px; }
  .polling-checkboxes { display: flex; flex-wrap: wrap; gap: 20px; margin-top: 16px; }
  .polling-tip { margin-top: 14px; padding: 11px 13px; border: 1px solid #dbe6ff; border-radius: 7px; background: #f8faff; line-height: 1.65; }
  .execution-control-list { display: grid; gap: 12px; }
  .execution-control-card { display: flex; min-height: 92px; align-items: center; justify-content: space-between; gap: 24px; padding: 20px 22px; border: 1px solid #dfe5ee; border-radius: 8px; background: #fff; }
  .execution-control-card > div { display: grid; gap: 7px; }
  .execution-control-card strong { color: #24344b; font-size: 14px; }
  .execution-control-card span { color: #7d899a; font-size: 12px; line-height: 1.6; }
  .execution-control-card .execution-control-actions { display: flex; flex: 0 0 auto; align-items: center; gap: 9px; }
  .execution-control-actions :deep(.n-input-number) { width: 92px; }
  .empty-state { padding: 42px 0 24px; }
  .save-tip { padding: 2px 10px; color: #8b95a7; }
  /* 原型工作台布局：轻量外框 + 深色编辑器 + 信息型右侧栏。 */
  .scene-page { max-width: 1440px; margin: 14px auto 32px; }
  .steps-card { border-color: #e7ebf2; border-radius: 12px; box-shadow: 0 8px 28px rgb(20 38 72 / 4%); }
  .steps-card :deep(.n-card-header) { padding: 18px 24px 12px; }
  .steps-card :deep(.n-card__content) { padding: 0 24px 24px; }
  .step-card { margin-top: 14px; border-color: #e5eaf1; border-radius: 12px; box-shadow: none; }
  .step-card.expanded { border-color: #c9d9ff; box-shadow: 0 10px 28px rgb(55 107 255 / 7%); }
  .step-head { min-height: 76px; padding: 0 22px; gap: 14px; }
  .step-no { width: 42px; height: 42px; border-color: #b8d0ff; color: #376bff; font-size: 16px; font-weight: 600; }
  .step-name { font-size: 18px; font-weight: 700; letter-spacing: -.01em; }.step-url { margin-top: 6px; color: #748197; font-size: 14px; }
  .method-pill { min-width: 46px; padding: 3px 8px; border-radius: 6px; font-size: 12px; }
  .step-body { padding: 0 24px 24px 76px; border-top-color: #edf0f5; background: #fff; }
  .request-target-inline { display: flex; align-items: center; gap: 7px; width: min(100%, 660px); margin-top: 6px; cursor: default; }
  .request-target-display { width: fit-content; max-width: min(100%, 660px); cursor: text; }
  .request-target-display .request-url-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .request-target-display:hover .request-url-text { color: #526784; }
  .inline-method-select { width: 92px; flex: none; }
  .inline-url-input { min-width: 150px; max-width: 540px; flex: 1; }
  .request-target-inline :deep(.n-base-selection),
  .request-target-inline :deep(.n-input-wrapper) { border-radius: 6px; box-shadow: 0 0 0 1px #e1e7f0 inset; transition: box-shadow .18s ease, background-color .18s ease; }
  .request-target-inline :deep(.n-base-selection:hover),
  .request-target-inline :deep(.n-input-wrapper:hover) { box-shadow: 0 0 0 1px #a9c3fb inset; }
  .request-target-inline :deep(.n-base-selection.n-base-selection--active),
  .request-target-inline :deep(.n-input.n-input--focus .n-input-wrapper) { box-shadow: 0 0 0 1px #376bff inset, 0 0 0 3px rgb(55 107 255 / 9%); }
  .inline-method-select :deep(.n-base-selection) { color: var(--method-color); background: var(--method-background); }
  .inline-method-select :deep(.n-base-selection-label) { font-size: 12px; font-weight: 700; }
  .inline-url-input :deep(.n-input-wrapper) { background: #fbfcfe; }
  .inline-url-input :deep(.n-input__input-el) { color: #5f6f86; font: 13px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
  .request-target-reset { flex: none; color: #8390a4; transition: color .18s ease, transform .18s ease; }
  .request-target-reset:hover { color: #376bff; transform: rotate(-18deg); }
  .request-target-done { flex: none; font-weight: 600; }
  .step-config-tabs { margin: 0 -24px 20px; padding: 12px 24px 0; border-bottom: 1px solid #edf0f5; background: #fbfcff; }
  .step-config-tabs :deep(.n-tabs-nav) { margin-bottom: 0; }.step-config-tabs :deep(.n-tabs-tab) { height: 64px; color: #58677d; font-size: 15px; font-weight: 600; }
  .step-config-tabs :deep(.n-tabs-tab--active) { color: #376bff; }.step-config-tabs :deep(.n-tabs-bar) { height: 3px; border-radius: 3px; background: #376bff; }
  :deep(.tab-title) { display: inline-flex; align-items: center; gap: 8px; }.tab-title :deep(svg) { color: currentcolor; }.tab-title :deep(b) { display: inline-grid; place-items: center; min-width: 24px; height: 24px; border-radius: 999px; color: #59687e; background: #eef1f6; font-size: 12px; }.tab-title :deep(b.on) { color: #18a058; background: #e9f7ef; }.step-config-tabs :deep(.n-tabs-tab--active .tab-title b) { color: #376bff; background: #eaf0ff; }:deep(.tab-status-dot) { width: 8px; height: 8px; border: 2px solid #dff7e9; border-radius: 50%; background: #18a058; box-shadow: 0 0 0 2px rgba(24, 160, 88, .12); }
  .step-workspace { display: grid; grid-template-columns: minmax(0, 1fr) 330px; gap: 22px; align-items: start; }
  .editor-panel { min-width: 0; overflow: hidden; border: 1px solid #e2e7ef; border-radius: 12px; background: #fff; }
  .workspace-panel-head { display: flex; align-items: center; justify-content: space-between; gap: 18px; min-height: 76px; padding: 0 18px 0 20px; border-bottom: 1px solid #edf0f5; }
  .workspace-panel-head > div { display: grid; gap: 4px; }.workspace-panel-head strong { color: #172033; font-size: 17px; }.workspace-panel-head span { color: #8290a5; font-size: 12px; }
  .workspace-panel-head :deep(.n-button) { border-color: #e1e7f0; border-radius: 7px; color: #40506a; }.workspace-panel-head :deep(.n-button .n-icon) { color: #64748b; }
  .json-editor { min-height: 360px; }
  .editor-panel .override-tip { display: flex; align-items: center; gap: 8px; margin: 0; padding: 14px 16px; border-top: 1px solid #edf0f5; color: #758398; background: #f8faff; font-size: 12px; }.editor-panel .override-tip :deep(svg) { flex: none; color: #376bff; font-size: 17px; }
  .workspace-sidebar { display: grid; gap: 16px; }.side-panel { border: 1px solid #e1e7ef; border-radius: 12px; background: #fff; }.side-panel > header { display: flex; align-items: center; gap: 7px; min-height: 60px; padding: 0 18px; border-bottom: 1px solid #edf0f5; color: #182236; }.side-panel > header strong { font-size: 16px; }.side-panel > header :deep(svg) { color: #8b98ab; font-size: 17px; }
  .variable-panel { min-height: 278px; padding-bottom: 18px; text-align: center; }.variable-panel > p { margin: 14px 18px; color: #8794a7; font-size: 13px; line-height: 1.65; text-align: left; }.variable-panel > :deep(.n-button) { width: calc(100% - 36px); margin: 8px 18px 0; border-radius: 7px; }.variable-suggestion-item :deep(.n-button) { width: auto !important; min-width: 44px; margin: 0 !important; }
  .variable-empty-icon { display: grid; place-items: center; width: 52px; height: 52px; margin: 26px auto 14px; border: 1px solid #dce7ff; border-radius: 14px; color: #5e88ff; background: #f4f7ff; font-size: 28px; }.variable-panel h4 { margin: 0; color: #2c374b; font-size: 14px; }.variable-panel h4 + p { margin: 8px 28px 10px; text-align: center; }
  .variable-panel .available-variables { justify-content: center; padding: 4px 16px 4px; }.variable-chip { border-color: #d7e2fb; border-radius: 6px; background: #f8faff; }.variable-chip code { color: #376bff; }
  .request-overview { padding-bottom: 8px; }.request-overview > div { display: flex; align-items: center; justify-content: space-between; min-height: 48px; padding: 0 18px; }.request-overview > div span { display: flex; align-items: center; gap: 10px; color: #69768a; font-size: 14px; }.request-overview > div span :deep(svg) { color: #73829a; font-size: 18px; }.request-overview > div b { display: inline-grid; place-items: center; min-width: 25px; height: 25px; border-radius: 999px; color: #376bff; background: #eef3ff; font-size: 12px; }
  /* 实底主操作按钮（添加接口）：仅作用于显式标记按钮，避免污染文字按钮 */
  .steps-card :deep(.n-button.solid-primary-btn) { border-color: #2468f2; border-radius: 7px; color: #fff; background: #2468f2; box-shadow: 0 2px 5px rgb(36 104 242 / 18%); transition: transform .16s ease, background .16s ease, box-shadow .16s ease; }
  .steps-card :deep(.n-button.solid-primary-btn:hover), .steps-card :deep(.n-button.solid-primary-btn:focus) { border-color: #1958d6; color: #fff; background: #1958d6; box-shadow: 0 4px 10px rgb(36 104 242 / 24%); }
  .steps-card :deep(.n-button.solid-primary-btn:active) { transform: translateY(1px); }
  .steps-card :deep(.n-button.solid-primary-btn.n-button--disabled) { border-color: #d7dfef; color: #9aa8bd; background: #edf1f7; box-shadow: none; }
  /* 文字操作按钮（编辑条件/编辑/运行）：无背景，保留 type 蓝/红字 */
  .steps-card :deep(.n-button.text-action) { background: transparent !important; box-shadow: none !important; }
  .steps-card :deep(.n-button.text-action:hover), .steps-card :deep(.n-button.text-action:focus), .steps-card :deep(.n-button.text-action:active) { background: transparent !important; }
  /* 删除按钮：红字无背景 */
  .steps-card :deep(.n-button.delete-button) { border-color: transparent !important; color: #d03050 !important; background: transparent !important; box-shadow: none !important; }
  .steps-card :deep(.n-button.delete-button:hover), .steps-card :deep(.n-button.delete-button:focus), .steps-card :deep(.n-button.delete-button:active) { border-color: transparent !important; color: #ad1f3d !important; background: transparent !important; }
  /* 运行步骤按钮：蓝字无背景 */
  .steps-card :deep(.n-button.run-step-button) { border-color: transparent !important; color: #2468f2 !important; background: transparent !important; box-shadow: none !important; }
  .steps-card :deep(.n-button.run-step-button:hover), .steps-card :deep(.n-button.run-step-button:focus), .steps-card :deep(.n-button.run-step-button:active) { border-color: transparent !important; color: #1958d6 !important; background: transparent !important; }
  /* 编辑工具按钮（保留原有白底样式） */
  .steps-card :deep(.editor-tool-button) { border-color: #dce3ee; color: #40506a; background: #fff; box-shadow: none; }.steps-card :deep(.editor-tool-button:hover), .steps-card :deep(.editor-tool-button:focus) { border-color: #afc5f7; color: #2468f2; background: #f7faff; box-shadow: none; }
  @media (max-width: 900px) { .scene-page { margin: 12px; } .basic-fields, .polling-grid, .add-row { grid-template-columns: 1fr; gap: 12px; } .picker-toolbar { align-items: flex-start; flex-direction: column; } .picker-actions { align-self: flex-end; } .endpoint-check-meta { display: none; } .step-body { padding-left: 18px; } .configure-link, .step-url { display: none; } .request-target-inline { max-width: 380px; }.inline-url-input { max-width: 250px; }.response-title { align-items: flex-start; padding: 10px 12px; } .response-title-actions { flex-wrap: wrap; justify-content: flex-end; } .response-search { width: 150px; } .variable-assistant-head { align-items: flex-start; flex-direction: column; padding: 10px 12px; } .variable-assistant-head > div { align-items: flex-start; flex-direction: column; gap: 3px; } .suggestion-row { grid-template-columns: 1fr auto; } .suggestion-arrow, .suggestion-extract { display: none; } .condition-editor-row, .branch-step-row { grid-template-columns: 1fr; }.branch-list, .branch-merge { margin-left: 18px; } }
  @media (max-width: 1120px) { .step-workspace { grid-template-columns: 1fr; }.workspace-sidebar { grid-template-columns: repeat(2, minmax(0, 1fr)); }.variable-panel { min-height: 0; } }
  @media (max-width: 700px) { .steps-card :deep(.n-card__content) { padding: 0 12px 16px; }.step-head { min-height: 66px; padding: 0 12px; }.step-no { width: 34px; height: 34px; font-size: 14px; }.step-body { padding: 0 12px 16px; }.request-target-inline { display: none; }.step-config-tabs { margin: 0 -12px 16px; padding: 0 12px; overflow-x: auto; }.step-config-tabs :deep(.n-tabs-nav-scroll-content) { min-width: 640px; }.workspace-panel-head { align-items: flex-start; flex-direction: column; padding: 14px; }.workspace-panel-head :deep(.n-space) { flex-wrap: wrap; }.workspace-sidebar { grid-template-columns: 1fr; }.json-editor { min-height: 300px; }.extract-rule-row, .validate-rule-row { grid-template-columns: 1fr; } }

  /* 场景详情新版布局：顶部场景信息、流程编排主区、运行上下文侧栏。 */
  .scene-page { width: min(1680px, calc(100% - 36px)); max-width: none; margin: 0 auto 40px; color: #172033; }
  .scene-header { padding: 22px 2px 18px; }
  .scene-breadcrumb { display: flex; align-items: center; gap: 9px; margin-bottom: 16px; color: #8a96a8; font-size: 13px; }
  .scene-breadcrumb i { color: #c2c9d4; font-style: normal; }
  .scene-breadcrumb strong { color: #526176; font-weight: 600; }
  .scene-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; }
  .scene-heading-copy { min-width: 0; }
  .scene-heading h1 { overflow: hidden; margin: 0; color: #111827; font-size: 28px; font-weight: 700; letter-spacing: -.025em; line-height: 1.2; text-overflow: ellipsis; white-space: nowrap; }
  .scene-heading p { display: flex; align-items: center; gap: 0; margin: 9px 0 0; color: #7a8799; font-size: 13px; }
  .scene-heading p span { display: inline-flex; align-items: center; }
  .scene-heading p span + span::before { width: 3px; height: 3px; margin: 0 10px; border-radius: 50%; background: #b7c0cd; content: ''; }
  .page-actions { display: flex; align-items: center; gap: 10px; flex: none; }
  .page-actions :deep(.n-button) { min-width: 92px; border-radius: 7px; }

  .scene-basic-strip { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: 24px; margin-bottom: 16px; padding: 18px 20px 16px; border: 1px solid #e2e7ef; border-radius: 12px; background: #fff; box-shadow: 0 4px 18px rgb(23 32 51 / 3%); }
  .scene-form { min-width: 0; }
  .basic-fields { grid-template-columns: minmax(180px, .9fr) minmax(220px, 1fr) minmax(260px, 1.4fr); gap: 16px; }
  .basic-fields :deep(.n-form-item-label) { padding-bottom: 6px; color: #66748a; font-size: 12px; }
  .basic-fields :deep(.n-base-selection), .basic-fields :deep(.n-input-wrapper) { border-radius: 7px; background: #fbfcfe; }
  .scene-save-state { display: flex; align-items: center; gap: 10px; min-width: 162px; padding: 8px 0 5px; color: #8a96a8; }
  .scene-save-state.created { color: #238653; }
  .save-state-dot { width: 9px; height: 9px; flex: none; border: 2px solid #cbd3df; border-radius: 50%; background: #fff; }
  .scene-save-state.created .save-state-dot { border-color: #b8ead0; background: #18a058; box-shadow: 0 0 0 3px #eef9f3; }
  .scene-save-state div { display: grid; gap: 2px; }
  .scene-save-state strong { font-size: 12px; font-weight: 650; }
  .scene-save-state small { color: #98a3b2; font-size: 11px; }

  .scene-workspace-layout { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 16px; align-items: start; }
  .scene-flow-column { min-width: 0; }
  .steps-card { margin: 0; border: 1px solid #e1e7ef; border-radius: 12px; box-shadow: 0 6px 24px rgb(23 32 51 / 4%); }
  .steps-card :deep(.n-card-header) { min-height: 72px; padding: 15px 20px; border-bottom: 1px solid #edf0f5; }
  .steps-card :deep(.n-card__content) { padding: 16px 20px 22px; }
  .flow-card-heading { display: grid; gap: 4px; }
  .flow-card-heading .card-title { color: #172033; font-size: 18px; font-weight: 700; }
  .flow-card-heading small { color: #8a96a8; font-size: 12px; font-weight: 400; }
  .steps-actions { min-width: 176px; }
  .run-environment { width: 176px; }
  .add-row { grid-template-columns: minmax(320px, 1fr) auto; margin-bottom: 10px; padding: 12px; border: 1px dashed #dce3ed; border-radius: 9px; background: #fafbfd; }
  .endpoint-select-trigger { min-height: 36px; border-radius: 7px; background: #fff; }

  .step-card { margin-top: 10px; border-color: #e1e6ed; border-radius: 9px; }
  .step-card.expanded { border-color: #adc7ff; box-shadow: 0 8px 24px rgb(55 107 255 / 7%); }
  .step-card.passed { border-left: 3px solid #2aa66a; }
  .step-card.failed { border-left: 3px solid #d84953; }
  .step-head { min-height: 66px; padding: 0 16px; gap: 12px; }
  .step-no { width: 36px; height: 36px; border-color: #c9d9f8; font-size: 14px; }
  .step-name { font-size: 15px; font-weight: 650; }
  .step-url { margin-top: 4px; font-size: 12px; }
  .step-body { padding: 0 18px 20px 64px; }

  .condition-card { margin-top: 10px; border-color: #eccb83; border-radius: 9px; background: #fffdf8; box-shadow: none; }
  .condition-head { min-height: 66px; padding: 0 16px; border-bottom-color: #f1dfb8; background: #fffaf0; }
  .condition-marker { color: #bd7a0c; background: #fff0c7; }
  .condition-card .step-no { border-color: #eac56f; color: #a96508; }
  .condition-subtitle { color: #9b7b49; }
  .branch-list { gap: 10px; margin: 14px 16px 10px 56px; padding-left: 16px; border-left-color: #e8c46d; }
  .branch-lane { border-color: #eadfc7; border-radius: 8px; background: #fff; }
  .condition-chip { color: #287747; background: #edf8f1; }
  .branch-merge { margin: 0 16px 14px 56px; border-color: #ead8ad; color: #a56d10; background: #fff9eb; }

  .scene-context-column { position: sticky; top: 14px; display: grid; gap: 12px; min-width: 0; }
  .context-panel { overflow: hidden; border: 1px solid #e1e7ef; border-radius: 11px; background: #fff; box-shadow: 0 4px 18px rgb(23 32 51 / 3%); }
  .context-panel > header { display: flex; align-items: center; justify-content: space-between; min-height: 50px; padding: 0 15px; border-bottom: 1px solid #edf0f5; }
  .context-panel > header strong { color: #253045; font-size: 14px; }
  .context-panel > header > span { color: #95a0af; font-size: 11px; }
  .scene-stat-grid { display: grid; grid-template-columns: repeat(2, 1fr); }
  .scene-stat-grid div { display: grid; gap: 3px; padding: 14px 15px; }
  .scene-stat-grid div:nth-child(odd) { border-right: 1px solid #edf0f5; }
  .scene-stat-grid div:nth-child(-n + 2) { border-bottom: 1px solid #edf0f5; }
  .scene-stat-grid b { color: #1d4ed8; font-size: 21px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .scene-stat-grid span { color: #8390a2; font-size: 11px; }
  .scene-variable-list { display: grid; max-height: 260px; overflow: auto; }
  .scene-variable-list div { display: grid; grid-template-columns: minmax(0, auto) minmax(0, 1fr); align-items: center; gap: 10px; min-height: 45px; padding: 0 14px; border-bottom: 1px solid #f0f2f6; }
  .scene-variable-list div:last-child { border-bottom: 0; }
  .scene-variable-list code { overflow: hidden; padding: 3px 6px; border-radius: 5px; color: #315fc9; background: #f0f4ff; font-size: 11px; text-overflow: ellipsis; }
  .scene-variable-list span { overflow: hidden; color: #8390a2; font-size: 11px; text-align: right; text-overflow: ellipsis; white-space: nowrap; }
  .context-empty { display: grid; place-items: center; gap: 8px; min-height: 112px; padding: 16px; color: #9aa5b4; font-size: 11px; text-align: center; }
  .context-empty :deep(svg) { color: #8facf2; font-size: 26px; }
  .run-context-body { display: grid; grid-template-columns: repeat(2, 1fr); padding: 7px 10px 11px; }
  .run-context-body div { display: grid; gap: 3px; padding: 8px; }
  .run-context-body span { color: #8a96a8; font-size: 11px; }
  .run-context-body strong { color: #3f4c61; font-size: 13px; font-variant-numeric: tabular-nums; }
  .run-context-body .run-success { color: #238653; }
  .run-context-body .run-failed { color: #c23d47; }
  .execution-rule-panel p { margin: 0; padding: 14px 18px 18px; color: #728096; font-size: 11px; line-height: 1.7; }
  .save-tip { margin-top: 14px; }

  @media (max-width: 1260px) {
    .scene-workspace-layout { grid-template-columns: minmax(0, 1fr) 270px; }
    .scene-basic-strip { grid-template-columns: 1fr; }
    .scene-save-state { padding-top: 0; }
  }
  @media (max-width: 1040px) {
    .scene-workspace-layout { grid-template-columns: 1fr; }
    .scene-context-column { position: static; grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .scene-variable-list { max-height: 220px; }
  }
  @media (max-width: 760px) {
    .scene-page { width: calc(100% - 20px); }
    .scene-heading { align-items: flex-start; flex-direction: column; }
    .page-actions { width: 100%; flex-wrap: wrap; }
    .page-actions :deep(.n-button) { flex: 1; }
    .basic-fields, .add-row { grid-template-columns: 1fr; }
    .scene-context-column { grid-template-columns: 1fr; }
    .steps-card :deep(.n-card-header) { align-items: flex-start; flex-direction: column; gap: 10px; }
    .steps-actions, .run-environment { width: 100%; }
    .flow-card-heading small { max-width: 36ch; }
  }

  /* 原型逐项校准。 */
  .scene-title-input { width: min(620px, 100%); }
  .scene-title-input :deep(.n-input-wrapper) { padding: 0; background: transparent; box-shadow: none !important; }
  .scene-title-input, .scene-title-input:hover, .scene-title-input:focus-within, .scene-title-input :deep(.n-input), .scene-title-input :deep(.n-input:hover), .scene-title-input :deep(.n-input.n-input--focus) { background: transparent !important; box-shadow: none !important; }
  .scene-title-input :deep(.n-input__border), .scene-title-input :deep(.n-input__state-border) { display: none !important; box-shadow: none !important; }
  .scene-title-input :deep(.n-input__input-el) { height: 36px; color: #111827; font-size: 28px; font-weight: 700; letter-spacing: -.025em; line-height: 36px; }
  .scene-title-input :deep(.n-input__placeholder) { color: #9aa5b4; }
  .scene-basic-strip { min-height: 56px; grid-template-columns: minmax(0, 1fr) 96px; align-items: center; padding: 7px 18px; border-radius: 5px; box-shadow: none; }
  .scene-form { margin: 0; }
  .basic-fields { grid-template-columns: minmax(210px, .8fr) minmax(160px, .6fr) minmax(360px, 1.5fr); gap: 18px; align-items: center; }
  .basic-field { display: grid; grid-template-columns: 64px minmax(0, 1fr); align-items: center; min-width: 0; min-height: 34px; }
  .basic-field-label { color: #738096; font-size: 12px; line-height: 34px; white-space: nowrap; }
  .basic-fields :deep(.n-input), .basic-fields :deep(.n-base-selection) { --n-border: 0 !important; --n-border-hover: 0 !important; --n-border-focus: 0 !important; --n-box-shadow-active: none !important; background: transparent; }
  .basic-fields :deep(.n-input:hover), .basic-fields :deep(.n-input.n-input--focus), .basic-fields :deep(.n-base-selection:hover), .basic-fields :deep(.n-base-selection.n-base-selection--active), .basic-fields :deep(.n-base-selection.n-base-selection--focus) { background: transparent !important; box-shadow: none !important; }
  .basic-fields :deep(.n-input-wrapper), .basic-fields :deep(.n-base-selection-label) { padding-right: 0; padding-left: 0; background: transparent; box-shadow: none !important; }
  .basic-fields :deep(.n-base-selection__border), .basic-fields :deep(.n-base-selection__state-border), .basic-fields :deep(.n-input__border), .basic-fields :deep(.n-input__state-border) { display: none !important; box-shadow: none !important; }
  .basic-fields :deep(.n-base-suffix) { opacity: 0; }
  .basic-fields :deep(.n-base-selection-tag-wrapper) { margin: 0 10px 0 0; padding: 0; background: transparent !important; box-shadow: none !important; }
  .basic-fields :deep(.n-tag) { --n-color: transparent !important; --n-color-checked: transparent !important; --n-border: transparent !important; --n-border-checked: transparent !important; padding: 0; border: 0 !important; outline: 0; color: #263247; background: transparent !important; box-shadow: none !important; font-size: 12px; }
  .basic-fields :deep(.n-tag::before), .basic-fields :deep(.n-tag::after), .basic-fields :deep(.n-tag__border) { display: none !important; border: 0 !important; box-shadow: none !important; }
  .basic-fields :deep(.n-tag__close) { display: none; }
  .scene-save-state { min-width: 86px; justify-content: flex-end; padding: 0; }
  .scene-save-state small { display: none; }
  .save-state-dot { position: relative; display: grid; place-items: center; width: 17px; height: 17px; border: 0; color: #fff; background: #9aa5b4; }
  .scene-save-state.created .save-state-dot { border: 0; background: #229657; box-shadow: none; }
  .scene-save-state.created .save-state-dot::after { font-size: 11px; font-weight: 700; content: '✓'; }
  .scene-save-state strong { color: #229657; font-size: 12px; }

  .scene-workspace-layout { grid-template-columns: minmax(0, 1fr) 400px; gap: 14px; }
  .steps-card { position: relative; border-radius: 5px; box-shadow: none; }
  .steps-card :deep(.n-card-header) { min-height: 62px; padding: 12px 20px; }
  .steps-card :deep(.n-card__content) { position: relative; padding: 8px 20px 18px; }
  .flow-card-heading { display: flex; align-items: baseline; gap: 22px; }
  .flow-card-heading small { max-width: 560px; }
  .flow-header-actions-host { display: flex; align-items: center; justify-content: flex-end; min-width: 264px; }
  .add-row { position: static; z-index: auto; display: flex; grid-template-columns: none; align-items: center; justify-content: flex-end; gap: 10px; margin: 0; padding: 0; border: 0; background: transparent; }
  .endpoint-select-trigger { width: 148px !important; min-width: 148px; max-width: 148px; min-height: 36px; flex: 0 0 148px; border-color: #2468f2; color: #2468f2; background: #fff; }
  .endpoint-select-trigger :deep(.n-button__content) { justify-content: center; gap: 8px; }
  .endpoint-select-trigger:hover { border-color: #1958d6; color: #1958d6; }
  .endpoint-select-plus { font-size: 20px; font-weight: 400; line-height: 1; }
  .condition-add-button { min-width: 142px; border-color: #dda13a !important; color: #b56e00 !important; background: #fff !important; }
  .condition-add-button:hover { border-color: #c48417 !important; color: #965b00 !important; }
  .condition-add-icon { color: #d58400; font-size: 17px; }
  .endpoint-picker-dropdown { width: min(820px, calc(100vw - 40px)); height: min(410px, calc(100vh - 100px)); max-height: calc(100vh - 100px); }
  .picker-toolbar { min-height: 52px; padding: 0 14px; }
  .picker-title { font-size: 15px; }
  .picker-actions { gap: 7px; }
  .picker-search { width: 230px; }
  .endpoint-picker-content { grid-template-columns: 230px minmax(0, 1fr); }
  .browser-heading { padding: 14px 14px 9px; font-size: 14px; }
  .browser-node { min-height: 36px; padding: 0 11px; }
  .endpoint-list-panel { padding: 12px; }

  .step-card { margin-top: 8px; border-radius: 5px; }
  .step-head { min-height: 58px; padding: 0 16px; gap: 12px; }
  .drag-handle, .branch-drag-handle { width: 18px; flex: none; text-align: center; }
  .step-no { width: 34px; height: 34px; flex: none; border-color: #cbd5e4; color: #26364d; font-size: 13px; font-variant-numeric: tabular-nums; background: #fff; }
  .step-name { font-size: 14px; line-height: 1.2; }
  .step-summary { min-width: 0; }
  .main-step-summary, .branch-step-summary { display: inline-flex; width: auto; min-width: 0; flex: 0 1 auto; align-items: center; gap: 14px; }
  .main-step-summary .step-name, .branch-step-summary .step-name { width: auto; min-width: 0; max-width: 240px; flex: 0 1 auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .branch-step-summary .step-name { max-width: 190px; }
  .main-step-summary .step-url, .branch-step-summary .step-url { width: auto; min-width: 0; max-width: 520px; flex: 0 1 auto; margin-top: 0; }
  .branch-step-summary .step-url { max-width: 430px; }
  .main-step-summary .request-target-display, .branch-step-summary .request-target-display { display: inline-flex; width: auto; }
  .main-step-summary .request-url-text, .branch-step-summary .request-url-text { min-width: 0; }
  .main-step-summary .request-target-inline, .branch-step-summary .request-target-inline { width: min(100%, 560px); margin-top: 0; }
  .step-url { display: flex; align-items: center; gap: 10px; margin-top: 2px; font-size: 12px; }
  .method-pill { min-width: 45px; padding: 2px 7px; border: 1px solid currentcolor; border-radius: 3px; line-height: 18px; text-align: center; }
  .step-header-meta { display: flex; flex: none; align-items: center; gap: 8px; margin-left: auto; }
  .step-header-meta span { display: inline-flex; min-height: 30px; align-items: center; padding: 0 10px; border: 1px solid #d6dde8; border-radius: 4px; color: #526176; background: #fbfcfe; font-size: 11px; white-space: nowrap; }
  .step-header-meta .step-meta-link { cursor: pointer; transition: border-color .16s, color .16s, background-color .16s; }
  .step-header-meta .step-meta-link:hover, .step-header-meta .step-meta-link:focus-visible { border-color: #9cb8ff; outline: none; color: #2468f2; background: #f3f6ff; }
  .step-head > :deep(.n-button) { flex: none; padding: 0 4px; font-size: 12px; }
  .run-step-button { margin-left: 0; }
  .branch-step-meta { margin-left: auto; }
  .step-body { padding: 0 14px 12px 24px; }
  .step-config-tabs { margin: 0 0 12px; padding: 0; }
  .step-config-tabs :deep(.n-tabs-tab) { height: 46px; padding: 0 24px; font-size: 12px; }
  .step-config-tabs :deep(.n-tabs-nav) { background: #fbfcfe; }
  .step-workspace { grid-template-columns: minmax(0, 1.65fr) minmax(280px, .95fr); gap: 0; border: 1px solid #dfe5ee; border-radius: 5px; }
  .editor-panel, .side-panel { border: 0; border-radius: 0; box-shadow: none; }
  .editor-panel { border-right: 1px solid #dfe5ee; }
  .workspace-panel-head { min-height: 48px; padding: 0 14px; }
  .workspace-panel-head > div { display: block; }
  .workspace-panel-head strong { font-size: 13px; }
  .workspace-panel-head span { display: none; }
  .json-editor { min-height: 250px; border-color: #202631; background: #202631; }
  .json-editor .editor-gutter { color: #8590a3; border-right-color: #353d4a; background: #1b212b; }
  .json-editor :deep(.n-input), .json-editor :deep(.n-input-wrapper), .json-editor :deep(.n-input__textarea), .json-editor :deep(.n-input__textarea-el) { background: #202631 !important; box-shadow: none !important; }
  .json-editor :deep(.n-input__textarea-el) { color: #d9e1ee !important; caret-color: #fff; }
  .json-editor :deep(.n-input__textarea-el::placeholder) { color: #6f7b8d !important; }
  .json-editor :deep(.n-input__border), .json-editor :deep(.n-input__state-border) { display: none !important; }
  .workspace-sidebar { gap: 0; }
  .workspace-sidebar .side-panel + .side-panel { border-top: 1px solid #dfe5ee; }
  .side-panel > header { min-height: 48px; padding: 0 14px; }
  .side-panel > header strong { font-size: 13px; }
  .variable-panel { min-height: 188px; padding-bottom: 10px; }
  .variable-panel > p { margin: 10px 14px; font-size: 11px; }
  .variable-suggestion-list { margin: 0 14px; padding: 0; gap: 7px; border: 0; border-radius: 0; background: transparent; }
  .variable-suggestion-item { min-height: 34px; padding: 0 10px; border: 1px solid #dce4f2; border-radius: 5px; background: #fff; }
  .variable-suggestion-item:hover { border-color: #b9c8f5; background: #f7f9ff; }
  .request-overview { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); padding: 0 12px 10px; }
  .request-overview > header { grid-column: 1 / -1; margin: 0 -12px 4px; }
  .request-overview > div { min-height: 34px; margin: 0 4px; padding: 0 10px; border: 1px solid #dfe5ee; border-radius: 4px; }
  .request-overview > div span { gap: 4px; font-size: 11px; }
  .request-overview > div span :deep(svg) { display: none; }
  .request-overview > div b { min-width: auto; height: auto; margin-left: 5px; color: #34445c; background: transparent; font-size: 11px; }
  .editor-panel .override-tip { display: none; }

  .condition-card { margin-top: 8px; overflow: visible; border: 0; border-radius: 0; background: transparent; }
  .condition-head { position: relative; min-height: 48px; padding: 0 10px 0 16px; border: 0; border-top: 1px solid #e7ebf1; border-bottom: 1px solid #e7ebf1; background: #fff; }
  .condition-head::before { position: absolute; top: -9px; bottom: -9px; left: 0; width: 1px; background: #b7c6dc; content: ''; }
  .condition-head::after { position: absolute; top: 50%; left: -5px; width: 9px; height: 9px; border: 1px solid #8fa2bd; border-radius: 50%; background: #fff; content: ''; transform: translateY(-50%); }
  .condition-marker { width: 19px; height: 19px; flex: none; border: 2px solid #d88400; color: transparent; background: transparent; transform: rotate(45deg); }
  .condition-card .step-no { width: auto; height: auto; border: 0; color: #344054; background: transparent; }
  .condition-step-no { min-width: 24px; font-variant-numeric: tabular-nums; }
  .condition-summary { display: flex; align-items: center; min-width: 0; flex: 1; gap: 20px; }
  .condition-summary .step-name { min-width: max-content; flex: none; }
  .condition-subtitle { min-width: 0; margin-top: 0; overflow: hidden; color: #7d899a; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
  .branch-list { gap: 8px; margin: 8px 0; padding: 0 0 0 24px; border-left: 1px solid #e4bd72; }
  .branch-lane { padding: 0 10px 8px; border-color: #edc77b; border-radius: 4px; background: #fffaf1; }
  .branch-head { min-height: 42px; margin: 0; }
  .condition-chip { border: 1px solid #a9ddbd; border-radius: 3px; }
  .branch-step-card { margin-top: 0; }
  .branch-step-head { min-height: 58px; }
  .branch-step-order { min-width: 42px; flex: none; white-space: nowrap; }
  .branch-merge { display: none; }
  .add-branch-button { margin: 0; }
  .add-next-step { min-height: 40px; margin-top: 12px; border-color: #b9c5d5 !important; border-radius: 3px; color: #2468f2 !important; background: #fbfcfe !important; }

  .context-panel { border-radius: 5px; box-shadow: none; }
  .context-panel > header { min-height: 54px; padding: 0 17px; }
  .context-panel > header strong { font-size: 16px; }
  .scene-stat-grid { margin: 12px 16px 16px; border: 1px solid #dfe5ee; border-radius: 4px; }
  .scene-stat-grid div { place-items: center; gap: 5px; padding: 12px 6px; }
  .scene-stat-grid b { color: #172033; font-size: 19px; }
  .scene-variable-list { padding: 8px 16px 14px; }
  .scene-variable-list div { min-height: 42px; padding: 0; border-bottom: 0; }
  .scene-variable-list code { border: 1px solid #d8dee8; color: #24344b; background: #f9fafc; }
  .scene-variable-panel { overflow: visible; }
  .scene-variable-panel > header { min-height: 46px; padding: 0 12px; border-bottom: 0; }
  .scene-variable-panel > header strong { font-size: 14px; }
  .variable-collapse-button { display: inline-grid; width: 28px; height: 28px; padding: 0; border: 0; place-items: center; color: #617086; background: transparent; cursor: pointer; }
  .variable-collapse-button :deep(svg) { font-size: 16px; transition: transform .18s ease; }
  .variable-collapse-button :deep(svg.collapsed) { transform: rotate(180deg); }
  .scene-variable-content { min-width: 0; padding: 0 0 12px; overflow: hidden; }
  .scene-variable-search { width: auto; min-width: 0; max-width: calc(100% - 24px); margin: 0 12px 10px; box-sizing: border-box; }
  .scene-variable-search :deep(.n-input-wrapper) { min-height: 38px; padding: 0 11px; border-radius: 5px; }
  .scene-variable-search :deep(.n-input__prefix) { margin-right: 7px; color: #9aa6b7; font-size: 16px; }
  .scene-variable-search :deep(.n-input__input-el) { font-size: 12px; }
  .scene-variable-tabs { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); min-height: 42px; padding: 0 9px; border-bottom: 1px solid #e6eaf0; }
  .scene-variable-tabs button { position: relative; display: inline-flex; min-width: 0; height: 42px; padding: 0 3px; border: 0; align-items: center; justify-content: center; gap: 4px; color: #66758b; background: transparent; font-size: 11px; font-weight: 600; white-space: nowrap; cursor: pointer; }
  .scene-variable-tabs button::after { position: absolute; right: 4px; bottom: -1px; left: 4px; height: 2px; border-radius: 2px 2px 0 0; background: transparent; content: ''; }
  .scene-variable-tabs button b { display: inline-grid; min-width: 18px; height: 18px; padding: 0 4px; border-radius: 5px; place-items: center; color: #7e8ca1; background: #f1f3f7; font-size: 10px; font-variant-numeric: tabular-nums; }
  .scene-variable-tabs button.active { color: #2468f2; }
  .scene-variable-tabs button.active::after { background: #2468f2; }
  .scene-variable-tabs button.active b { color: #2468f2; background: #edf3ff; }
  .scene-variable-groups { max-height: min(600px, calc(100vh - 170px)); padding: 4px 0 0; overflow: auto; scrollbar-width: thin; scrollbar-color: #c9d2df transparent; }
  .scene-variable-group { margin: 0 10px 10px; overflow: hidden; border: 1px solid #dfe5ed; border-radius: 5px; background: #fff; }
  .scene-variable-group > header { display: flex; min-height: 38px; padding: 0 10px; border-bottom: 1px solid #e8ecf2; align-items: center; justify-content: space-between; background: #fbfcfe; }
  .scene-variable-group > header > div { display: flex; min-width: 0; align-items: center; gap: 6px; }
  .scene-variable-group > header :deep(svg) { width: 8px; height: 8px; flex: none; color: #18a058; }
  .scene-variable-group > header :deep(svg:nth-of-type(2)) { width: 6px; height: 6px; color: #18a058; opacity: .9; }
  .scene-variable-group > header strong { color: #18a058; font-size: 12px; font-weight: 650; }
  .scene-variable-group > header span { overflow: hidden; color: #8a96a8; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
  .scene-variable-group > header > b { color: #6d7b90; font-size: 11px; font-weight: 600; font-variant-numeric: tabular-nums; }
  .scene-variable-group.is-function > header :deep(svg), .scene-variable-group.is-function > header :deep(svg:nth-of-type(2)), .scene-variable-group.is-function > header strong { color: #7c4ce0; }
  .scene-variable-group.is-extract > header :deep(svg), .scene-variable-group.is-extract > header :deep(svg:nth-of-type(2)), .scene-variable-group.is-extract > header strong { color: #ee940f; }
  .scene-variable-row { display: grid; min-height: 40px; padding: 0 9px; grid-template-columns: minmax(82px, .8fr) minmax(0, 1.35fr) auto; align-items: center; gap: 7px; border-bottom: 1px solid #edf0f5; }
  .scene-variable-row:last-child { border-bottom: 0; }
  .scene-variable-row:hover { background: #fbfcff; }
  .scene-variable-row code { min-width: 0; overflow: hidden; color: #34445a; font: 11px/24px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; text-overflow: ellipsis; white-space: nowrap; }
  .scene-variable-group.is-function .scene-variable-row { grid-template-columns: minmax(0, 1fr) auto; }
  .scene-variable-group.is-function .scene-variable-value { display: none; }
  .scene-variable-row code.selected { padding: 0 4px; border-radius: 3px; color: #2468f2; background: #edf3ff; }
  .scene-variable-value { display: inline-flex; min-width: 0; overflow: hidden; align-items: center; gap: 4px; color: #7f8da2; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
  .scene-variable-value:not(:has(.variable-eye-button)) { display: block; }
  .variable-eye-button { display: inline-grid; width: 20px; height: 20px; padding: 0; border: 0; flex: none; place-items: center; color: #8794a7; background: transparent; cursor: pointer; }
  .variable-eye-button :deep(svg) { font-size: 15px; }
  .scene-variable-actions { display: inline-flex; align-items: center; gap: 6px; }
  .scene-variable-actions button { padding: 2px 0; border: 0; color: #2468f2; background: transparent; font-size: 10px; font-weight: 600; cursor: pointer; }
  .scene-variable-actions button:hover { color: #164fc3; }
  .scene-variable-empty { min-height: 148px; }
  .recent-run-summary { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 12px; padding: 15px 17px 8px; color: #445166; font-size: 12px; }
  .recent-run-summary strong { font-weight: 500; }
  .run-context-panel time { display: block; padding: 0 17px 10px; color: #7c899b; font-size: 11px; }
  .view-run-result { margin: 0 17px 15px; font-size: 12px; }
  .execution-rule-panel p { padding: 14px 18px 18px; font-size: 12px; line-height: 1.7; }

  @media (max-width: 1260px) {
    .scene-workspace-layout { grid-template-columns: minmax(0, 1fr) 360px; }
    .basic-fields { grid-template-columns: minmax(190px, 1fr) minmax(130px, .6fr) minmax(260px, 1.2fr); }
  }
  @media (max-width: 1040px) {
    .scene-workspace-layout { grid-template-columns: 1fr; }
    .scene-context-column { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
  @media (max-width: 760px) {
    .scene-basic-strip { grid-template-columns: 1fr; }
    .basic-fields { grid-template-columns: 1fr; }
    .basic-fields :deep(.n-form-item) { grid-template-columns: 82px minmax(0, 1fr); }
    .scene-save-state { justify-content: flex-start; }
    .flow-header-actions-host { width: 100%; min-width: 0; }
    .add-row { width: 100%; justify-content: flex-start; }
    .step-header-meta { display: none; }
    .main-step-summary, .branch-step-summary { align-items: flex-start; flex-direction: column; gap: 3px; }
    .main-step-summary .step-name, .branch-step-summary .step-name { width: 100%; min-width: 0; flex: none; }
    .step-workspace { grid-template-columns: 1fr; }
    .editor-panel { border-right: 0; border-bottom: 1px solid #dfe5ee; }
  }
</style>
<style scoped src="./scenario-studio.css"></style>
