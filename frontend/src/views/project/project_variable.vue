<template>
  <div class="project-variable-page">
    <header class="page-head">
      <div>
        <h2>项目参数</h2>
        <p>为项目维护可复用的变量，场景和执行套件中使用 ${变量名} 引用。</p>
      </div>
      <n-button type="primary" :disabled="!selectedProject" @click="addVariable">
        ＋ 添加项目参数
      </n-button>
    </header>

    <n-card :bordered="true" class="variable-card">
      <div class="toolbar">
        <span class="toolbar-label">所属项目</span>
        <n-select
          v-model:value="selectedProject"
          :options="projectOptions"
          filterable
          clearable
          placeholder="请选择项目"
          class="project-select"
          @update:value="loadVariables"
        />
        <span v-if="selectedProject" class="toolbar-tip">保存后即可在场景、执行套件中引用</span>
      </div>

      <div v-if="selectedProject && variables.length" class="variable-list">
        <div class="variable-header"><span>变量名</span><span>变量值</span><span>操作</span></div>
        <div v-for="(variable, index) in variables" :key="variable.id || `new-${index}`" class="variable-row">
          <n-input v-model:value="variable.name" placeholder="如：tenant_id" maxlength="64" />
          <n-input v-model:value="variable.value" placeholder="请输入变量值" />
          <n-space :size="10">
            <n-button text type="primary" :loading="savingIndex === index" @click="saveVariable(variable, index)">保存</n-button>
            <n-button text type="error" :disabled="savingIndex === index" @click="removeVariable(variable, index)">删除</n-button>
          </n-space>
        </div>
      </div>
      <n-empty v-else-if="selectedProject" description="暂未配置项目参数" />
      <n-empty v-else description="请先选择项目" />
    </n-card>
  </div>
</template>

<script lang="ts" setup>
import { asList } from '@/utils/list';

  import { computed, onMounted, ref } from 'vue';
  import { NButton, NCard, NEmpty, NInput, NSpace, NSelect, useDialog, useMessage } from 'naive-ui';
  import { ProjectAPI, ProjectVariableAPI } from '@/api/project/http';

  type ProjectVariableRow = { id?: number; project: number; name: string; value: string };
  const message = useMessage();
  const dialog = useDialog();
  const projectApi = new ProjectAPI();
  const variableApi = new ProjectVariableAPI();
  const projects = ref<any[]>([]);
  const selectedProject = ref<number | null>(null);
  const variables = ref<ProjectVariableRow[]>([]);
  const savingIndex = ref<number | null>(null);

  
  const projectOptions = computed(() => projects.value.map((project) => ({ value: project.id, label: project.name })));

  async function loadProjects() {
    projects.value = asList(await projectApi.getDataList({ pageSize: 1000 }));
    if (!selectedProject.value && projects.value.length) selectedProject.value = projects.value[0].id;
    await loadVariables(selectedProject.value);
  }

  async function loadVariables(projectId = selectedProject.value) {
    if (!projectId) {
      variables.value = [];
      return;
    }
    selectedProject.value = projectId;
    variables.value = asList(await variableApi.getDataList({ project: projectId }))
      .map((item: any) => ({ id: item.id, project: projectId, name: item.name || '', value: item.value || '' }));
  }

  function addVariable() {
    if (!selectedProject.value) return;
    variables.value.push({ project: selectedProject.value, name: '', value: '' });
  }

  async function saveVariable(variable: ProjectVariableRow, index: number) {
    const name = variable.name.trim();
    if (!name) return message.warning('请输入变量名');
    const duplicate = variables.value.some((item, itemIndex) => itemIndex !== index && item.name.trim() === name);
    if (duplicate) return message.warning('当前项目下变量名不能重复');
    savingIndex.value = index;
    try {
      const payload = { project: selectedProject.value as number, name, value: variable.value || '' };
      const saved: any = variable.id
        ? await variableApi.update(variable.id, payload)
        : await variableApi.createData(payload);
      variable.id = saved?.id || variable.id;
      variable.name = name;
      message.success('项目参数已保存');
    } catch (error: any) {
      message.error(error?.message || '项目参数保存失败');
    } finally {
      savingIndex.value = null;
    }
  }

  function removeVariable(variable: ProjectVariableRow, index: number) {
    if (!variable.id) {
      variables.value.splice(index, 1);
      return;
    }
    dialog.warning({
      title: '删除项目参数',
      content: `确定删除变量「${variable.name}」吗？`,
      positiveText: '删除',
      negativeText: '取消',
      onPositiveClick: async () => {
        try {
          await variableApi.DeleteDataByID(variable.id);
          variables.value.splice(index, 1);
          message.success('项目参数已删除');
        } catch (error: any) {
          message.error(error?.message || '项目参数删除失败');
        }
      },
    });
  }

  onMounted(loadProjects);
</script>

<style scoped lang="less">
  .project-variable-page { max-width: 1120px; padding: 20px 28px 32px; }
  .page-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin-bottom: 20px; }
  .page-head h2 { margin: 0; color: #111827; font-size: 20px; font-weight: 650; }
  .page-head p { margin: 7px 0 0; color: #6b7280; font-size: 13px; }
  .variable-card { border-radius: 10px; }
  .toolbar { display: flex; align-items: center; gap: 12px; padding-bottom: 18px; border-bottom: 1px solid #f0f2f5; }
  .toolbar-label { flex: none; color: #374151; font-size: 13px; font-weight: 600; }
  .project-select { width: 280px; }
  .toolbar-tip { color: #6b7280; font-size: 12px; }
  .variable-list { margin-top: 18px; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }
  .variable-header, .variable-row { display: grid; grid-template-columns: minmax(180px, .8fr) minmax(260px, 1.5fr) 110px; gap: 12px; align-items: center; padding: 10px 14px; }
  .variable-header { color: #6b7280; background: #f8fafc; font-size: 12px; font-weight: 600; }
  .variable-row { min-height: 56px; border-top: 1px solid #eef0f3; }
  @media (max-width: 700px) {
    .project-variable-page { padding: 14px; }
    .page-head, .toolbar { align-items: flex-start; flex-direction: column; }
    .project-select { width: 100%; }
    .variable-header { display: none; }
    .variable-row { grid-template-columns: 1fr; gap: 8px; }
  }
</style>
