<template>
  <div class="project-detail-page">
    <div class="page-shell">
      <nav class="breadcrumb">项目管理 <span>/</span> 项目信息 <span>/</span> 项目详情</nav>

      <header class="page-header">
        <div class="project-heading">
          <div class="project-mark">
            <n-icon :component="PeopleOutline" />
          </div>
          <div>
            <h1>{{ formValue.name || (isNewProject ? '新建项目' : '项目详情') }}</h1>
            <p>{{ formValue.intro || '配置项目基础资料、团队成员与公共参数' }}</p>
            <div class="project-meta">
              <span>项目 ID：{{ projectId || '—' }}</span>
              <i></i>
              <span>{{ selectedMembers.length }} 位成员</span>
              <i></i>
              <span>{{ projectVariables.length }} 个项目参数</span>
            </div>
          </div>
        </div>
        <div class="header-actions">
          <n-button class="action-button" @click="goBack">
            <template #icon><n-icon :component="ArrowBackOutline" /></template>
            返回
          </n-button>
          <n-button class="action-button" :loading="saving" @click="saveProject(false)">
            <template #icon><n-icon :component="SaveOutline" /></template>
            保存配置
          </n-button>
          <n-button
            class="action-button primary-button"
            type="primary"
            :loading="saving"
            @click="saveProject(true)"
          >
            保存并返回
          </n-button>
        </div>
      </header>

      <n-form ref="formRef" :model="formValue" :rules="rules" :show-label="false">
        <main class="content-grid">
          <div class="configuration-column">
            <section class="detail-panel basic-panel">
              <div class="panel-heading">
                <div class="section-number">A</div>
                <div>
                  <h2>基本信息</h2>
                  <p>项目的名称与用途说明</p>
                </div>
              </div>
              <div class="basic-grid">
                <n-form-item path="name">
                  <div class="field-block">
                    <label>项目名称 <em>*</em></label>
                    <n-input
                      v-model:value="formValue.name"
                      placeholder="请输入项目名称"
                      maxlength="64"
                    />
                  </div>
                </n-form-item>
                <n-form-item path="intro">
                  <div class="field-block">
                    <label>项目简介</label>
                    <n-input
                      v-model:value="formValue.intro"
                      placeholder="描述项目用途、范围与目标"
                      maxlength="256"
                    />
                  </div>
                </n-form-item>
              </div>
            </section>

            <section class="detail-panel people-panel">
              <div class="panel-heading">
                <div class="section-number">B</div>
                <div>
                  <h2>人员配置</h2>
                  <p>设置负责人并维护项目成员</p>
                </div>
              </div>

              <div class="owner-row">
                <div class="field-title">项目负责人 <em>*</em></div>
                <n-select
                  v-model:value="formValue.pm"
                  :options="ownerOptions"
                  placeholder="请选择项目负责人"
                  filterable
                  :disabled="!isAdmin"
                />
                <span class="owner-tip">负责人可维护项目成员与配置</span>
              </div>

              <div class="member-title-row">
                <div>
                  <strong>项目成员</strong>
                  <span>已添加 {{ selectedMembers.length }} 人</span>
                </div>
              </div>
              <div v-if="selectedMembers.length" class="member-grid">
                <div v-for="member in selectedMembers" :key="member.value" class="member-chip">
                  <span class="member-avatar" :style="{ background: avatarColor(member.value) }">
                    {{ getInitial(member.label) }}
                  </span>
                  <div class="member-copy">
                    <strong>{{ member.label }}</strong>
                    <span>{{
                      Number(member.value) === Number(formValue.pm) ? '项目负责人' : '项目成员'
                    }}</span>
                  </div>
                  <button
                    v-if="canManageMembers && Number(member.value) !== Number(formValue.pm)"
                    class="remove-member"
                    type="button"
                    aria-label="移除成员"
                    @click="removeMember(member.value)"
                    >×</button
                  >
                </div>
              </div>
              <n-empty v-else class="compact-empty" size="small" description="暂未添加项目成员" />

              <n-select
                v-if="canManageMembers"
                v-model:value="memberToAdd"
                class="member-add-select"
                :options="availableMemberOptions"
                placeholder="＋ 添加项目成员"
                filterable
                clearable
                @update:value="addMember"
              />
            </section>

            <section class="detail-panel variable-panel">
              <div class="panel-heading variable-heading">
                <div class="heading-copy">
                  <div class="section-number">C</div>
                  <div>
                    <h2>项目参数</h2>
                    <p>集中维护项目公共变量，在场景和套件中复用</p>
                  </div>
                </div>
                <div class="reference-tip">引用格式 <code>${变量名}</code></div>
              </div>

              <div class="variable-table">
                <div class="variable-table-head">
                  <span>变量名</span>
                  <span>变量值</span>
                  <span>参数描述</span>
                  <span>操作</span>
                </div>
                <div v-if="projectVariables.length" class="variable-table-body">
                  <div
                    v-for="(variable, index) in projectVariables"
                    :key="variable.id || `new-${index}`"
                    class="variable-row"
                  >
                    <n-input
                      v-model:value="variable.name"
                      placeholder="如：tenant_id"
                      maxlength="64"
                    />
                    <n-input v-model:value="variable.value" placeholder="请输入参数值" />
                    <n-input
                      v-model:value="variable.description"
                      placeholder="说明参数用途"
                      maxlength="256"
                    />
                    <n-button text type="error" @click="removeVariable(index)">删除</n-button>
                  </div>
                </div>
                <n-empty
                  v-else
                  class="variable-empty"
                  size="small"
                  description="暂未配置项目参数"
                />
                <button class="add-variable-button" type="button" @click="addVariable"
                  >＋ 添加项目参数</button
                >
              </div>
            </section>
          </div>

          <aside class="overview-column">
            <section class="side-panel overview-panel">
              <div class="side-panel-title">
                <h2>项目概览</h2>
                <span>实时统计</span>
              </div>
              <div class="stat-grid">
                <div class="stat-item stat-blue">
                  <span class="stat-icon"><n-icon :component="PeopleOutline" /></span>
                  <div
                    ><strong>{{ selectedMembers.length }}</strong
                    ><span>项目成员</span></div
                  >
                </div>
                <div class="stat-item stat-green">
                  <span class="stat-icon"><n-icon :component="ServerOutline" /></span>
                  <div
                    ><strong>{{ projectStats.environmentCount }}</strong
                    ><span>执行环境</span></div
                  >
                </div>
                <div class="stat-item stat-violet">
                  <span class="stat-icon"><n-icon :component="CodeSlashOutline" /></span>
                  <div
                    ><strong>{{ projectStats.endpointCount }}</strong
                    ><span>接口数量</span></div
                  >
                </div>
                <div class="stat-item stat-orange">
                  <span class="stat-icon"><n-icon :component="GitBranchOutline" /></span>
                  <div
                    ><strong>{{ projectStats.scenarioCount }}</strong
                    ><span>场景数量</span></div
                  >
                </div>
              </div>
            </section>

            <section class="side-panel permission-panel">
              <div class="side-panel-title">
                <h2>成员与权限</h2>
                <span>{{ selectedMembers.length }} 人</span>
              </div>
              <div v-if="overviewMembers.length" class="permission-list">
                <div v-for="member in overviewMembers" :key="member.value" class="permission-item">
                  <span class="member-avatar" :style="{ background: avatarColor(member.value) }">
                    {{ getInitial(member.label) }}
                  </span>
                  <div>
                    <strong>{{ member.label }}</strong>
                    <span>{{ member.role }}</span>
                  </div>
                  <em :class="member.roleClass">{{ member.role }}</em>
                </div>
                <div v-if="selectedMembers.length > overviewMembers.length" class="permission-more">
                  还有 {{ selectedMembers.length - overviewMembers.length }} 位成员，在左侧「项目成员」中查看
                </div>
              </div>
              <n-empty v-else class="compact-empty" size="small" description="暂无成员" />
            </section>

            <section class="side-panel help-panel">
              <div class="help-title">
                <span><n-icon :component="InformationCircleOutline" /></span>
                <h2>参数使用说明</h2>
              </div>
              <ul>
                <li>参数名称用于变量引用，参数描述用于说明业务含义。</li>
                <li>在接口或场景中使用 <code>${变量名}</code> 引用项目参数。</li>
                <li>环境与步骤提取变量可覆盖同名项目参数。</li>
              </ul>
              <div class="priority-note">变量优先级：步骤提取 ＞ 环境参数 ＞ 项目参数</div>
            </section>
          </aside>
        </main>
      </n-form>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { asList } from '@/utils/list';

  import { computed, onMounted, reactive, ref } from 'vue';
  import { useMessage } from 'naive-ui';
  import { useRoute, useRouter } from 'vue-router';
  import {
    ArrowBackOutline,
    CodeSlashOutline,
    GitBranchOutline,
    InformationCircleOutline,
    PeopleOutline,
    SaveOutline,
    ServerOutline,
  } from '@vicons/ionicons5';
  import { get_user_list } from '@/api/account/http';
  import { ProjectAPI, ProjectVariableAPI } from '@/api/project/http';
  import type { Project, ProjectVariable } from '@/api/project/models';
  import { useUserStore } from '@/store/modules/user';

  type UserOption = { value: number; label: string };

  const route = useRoute();
  const router = useRouter();
  const message = useMessage();
  const api = new ProjectAPI();
  const variableApi = new ProjectVariableAPI();
  const userStore = useUserStore();
  const formRef = ref<any>(null);
  const projectId = ref(Number(route.params.id || 0));
  const saving = ref(false);
  const memberToAdd = ref<number | null>(null);
  const userOptions = ref<UserOption[]>([]);
  const projectVariables = ref<
    Array<Partial<ProjectVariable> & { name: string; value: string; description: string }>
  >([]);
  const projectStats = reactive({ environmentCount: 0, endpointCount: 0, scenarioCount: 0 });
  const formValue = reactive<{
    name: string;
    intro: string;
    pm: number | null;
    user_list: number[];
  }>({
    name: '',
    intro: '',
    pm: null,
    user_list: [],
  });

  const isNewProject = computed(() => !projectId.value);
  const currentUserId = computed(() =>
    Number((userStore.info as any)?.user || (userStore.info as any)?.id || 0)
  );
  const isAdmin = computed(() => Boolean((userStore.info as any)?.is_admin));
  const canManageMembers = computed(
    () => isAdmin.value || Number(formValue.pm) === currentUserId.value
  );
  const selectedMembers = computed(() => {
    const ids = new Set((formValue.user_list || []).map(Number));
    if (formValue.pm) ids.add(Number(formValue.pm));
    return userOptions.value.filter((item) => ids.has(Number(item.value)));
  });
  const ownerOptions = computed(() =>
    userOptions.value.map((item) => ({
      ...item,
      label: Number(item.value) === Number(formValue.pm) ? `${item.label}（负责人）` : item.label,
    }))
  );
  const availableMemberOptions = computed(() => {
    const selected = new Set(selectedMembers.value.map((item) => Number(item.value)));
    return userOptions.value.filter((item) => !selected.has(Number(item.value)));
  });
  const overviewMembers = computed(() =>
    selectedMembers.value.slice(0, 6).map((member) => {
      if (Number(member.value) === Number(formValue.pm)) {
        return { ...member, role: '项目负责人', roleClass: 'role-owner' };
      }
      if (Number(member.value) === currentUserId.value && isAdmin.value) {
        return { ...member, role: '管理员', roleClass: 'role-admin' };
      }
      return { ...member, role: '项目成员', roleClass: 'role-member' };
    })
  );

  const rules = {
    name: { required: true, message: '请输入项目名称', trigger: ['blur', 'input'] },
  };

  

  function getInitial(label: string) {
    return String(label || '?')
      .trim()
      .slice(0, 1)
      .toUpperCase();
  }

  function avatarColor(value: number) {
    const palette = ['#536dfe', '#11a683', '#7b61d9', '#e7922f', '#2679d8', '#c65a7c'];
    return palette[Math.abs(Number(value) || 0) % palette.length];
  }

  function addMember(value: number | null) {
    if (!value) return;
    if (!formValue.user_list.includes(Number(value))) formValue.user_list.push(Number(value));
    memberToAdd.value = null;
  }

  function removeMember(value: number) {
    formValue.user_list = formValue.user_list.filter((item) => Number(item) !== Number(value));
  }

  function addVariable() {
    projectVariables.value.push({ name: '', value: '', description: '' });
  }

  function removeVariable(index: number) {
    projectVariables.value.splice(index, 1);
  }

  function goBack() {
    router.push({ name: 'project_project' });
  }

  async function syncProjectVariables(id: number) {
    const rows = projectVariables.value
      .map((item) => ({ ...item, name: String(item.name || '').trim() }))
      .filter((item) => item.name || item.value || item.description);
    const names = new Set<string>();
    for (const row of rows) {
      if (!row.name) throw new Error('项目参数名不能为空');
      if (names.has(row.name)) throw new Error(`项目参数“${row.name}”重复`);
      names.add(row.name);
    }

    const existing = asList(await variableApi.getDataList({ project: id }));
    const keptIds = new Set<number>();
    for (const row of rows) {
      const payload: ProjectVariable = {
        project: id,
        name: row.name,
        value: String(row.value || ''),
        description: String(row.description || ''),
      };
      if (row.id) {
        keptIds.add(Number(row.id));
        await variableApi.update(Number(row.id), payload);
      } else {
        const created: any = await variableApi.createData(payload);
        if (created?.id) keptIds.add(Number(created.id));
      }
    }

    await Promise.all(
      existing
        .filter((item: any) => item.id && !keptIds.has(Number(item.id)))
        .map((item: any) => variableApi.DeleteDataByID(item.id))
    );
  }

  async function saveProject(returnAfterSave: boolean) {
    if (saving.value) return;
    try {
      await formRef.value?.validate();
      saving.value = true;
      const creatingProject = !projectId.value;
      const memberIds = new Set((formValue.user_list || []).map(Number));
      if (formValue.pm) memberIds.add(Number(formValue.pm));
      const payload: any = {
        name: formValue.name.trim(),
        intro: formValue.intro || '',
        pm: formValue.pm,
        user_list: Array.from(memberIds),
      };
      const saved: any = projectId.value
        ? await api.update(projectId.value, payload as Project)
        : await api.createData(payload as Project);
      projectId.value = Number(saved?.id || projectId.value);
      if (!projectId.value) throw new Error('项目保存成功，但未返回项目 ID');
      // 新建完成后将 /project/project/0 替换为真实项目地址，避免后续回到缓存列表时状态失效。
      if (creatingProject) {
        await router.replace({ name: 'project_project_edit', params: { id: projectId.value } });
      }
      await syncProjectVariables(projectId.value);
      message.success('项目配置已保存');
      if (returnAfterSave) goBack();
      else await loadProject();
    } catch (error: any) {
      message.error(error?.message || '保存失败，请检查填写内容');
    } finally {
      saving.value = false;
    }
  }

  async function loadProject() {
    if (!projectId.value) return;
    const data: any = await api.getDataByID(projectId.value);
    formValue.name = data?.name || '';
    formValue.intro = data?.intro || '';
    formValue.pm = data?.pm ? Number(data.pm) : null;
    formValue.user_list = asList(data?.user_list).map(Number).filter(Boolean);
    projectStats.environmentCount = Number(data?.environment_count || 0);
    projectStats.endpointCount = Number(data?.endpoint_count || 0);
    projectStats.scenarioCount = Number(data?.scenario_count || 0);
    projectVariables.value = asList(
      await variableApi.getDataList({ project: projectId.value })
    ).map((item: any) => ({
      id: item.id,
      project: projectId.value,
      name: item.name || '',
      value: item.value || '',
      description: item.description || '',
    }));
  }

  async function loadPage() {
    try {
      const users = await get_user_list();
      userOptions.value = asList(users)
        .map((item: any) => ({
          value: Number(item.user || item.id),
          label: item.username || item.name || `用户 ${item.user || item.id}`,
        }))
        .filter((item: UserOption) => item.value);
      await loadProject();
    } catch (error: any) {
      message.error(error?.message || '项目详情加载失败');
    }
  }

  onMounted(loadPage);
</script>

<style lang="less" scoped>
  .project-detail-page {
    min-height: 100%;
    padding: 18px 24px 32px;
    background: #f6f8fc;
    color: #182135;
  }

  .page-shell {
    width: 100%;
    max-width: 1640px;
    margin: 0 auto;
  }
  .breadcrumb {
    color: #8a96aa;
    font-size: 13px;
    font-weight: 600;
  }
  .breadcrumb span {
    margin: 0 9px;
    color: #c0c8d4;
  }

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    margin: 14px 0 18px;
  }
  .project-heading {
    display: flex;
    align-items: center;
    gap: 16px;
    min-width: 0;
  }
  .project-mark {
    display: grid;
    place-items: center;
    flex: 0 0 62px;
    width: 62px;
    height: 62px;
    border-radius: 14px;
    color: #fff;
    font-size: 30px;
    background: #536dfe;
    box-shadow: 0 10px 24px rgba(83, 109, 254, 0.2);
  }
  .project-heading h1 {
    margin: 0;
    color: #151e31;
    font-size: 28px;
    line-height: 1.2;
    font-weight: 750;
  }
  .project-heading p {
    margin: 5px 0;
    color: #77849a;
    font-size: 14px;
  }
  .project-meta {
    display: flex;
    align-items: center;
    gap: 9px;
    color: #9aa5b7;
    font-size: 12px;
  }
  .project-meta i {
    width: 3px;
    height: 3px;
    border-radius: 50%;
    background: #b5bfcd;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 0 0 auto;
  }
  .action-button {
    min-width: 112px;
    height: 40px;
    border-radius: 5px;
  }
  .primary-button {
    box-shadow: 0 8px 18px rgba(83, 109, 254, 0.18);
  }

  .content-grid {
    display: grid;
    grid-template-columns: minmax(0, 2.05fr) minmax(330px, 1fr);
    gap: 16px;
    align-items: start;
  }
  .configuration-column,
  .overview-column {
    display: flex;
    flex-direction: column;
    gap: 14px;
    min-width: 0;
  }
  .detail-panel,
  .side-panel {
    background: #fff;
    border: 1px solid #dfe6f0;
    border-radius: 6px;
  }
  .detail-panel {
    padding: 17px 18px 18px;
  }

  .panel-heading {
    display: flex;
    align-items: center;
    gap: 11px;
    margin-bottom: 16px;
  }
  .panel-heading h2,
  .side-panel h2 {
    margin: 0;
    color: #1a2436;
    font-size: 16px;
    line-height: 1.35;
    font-weight: 700;
  }
  .panel-heading p {
    margin: 2px 0 0;
    color: #919caf;
    font-size: 12px;
  }
  .section-number {
    display: grid;
    place-items: center;
    width: 27px;
    height: 27px;
    border-radius: 5px;
    color: #4f67ef;
    font-size: 13px;
    font-weight: 800;
    background: #eef1ff;
  }

  .basic-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
  }
  .field-block {
    width: 100%;
  }
  .field-block label,
  .field-title {
    display: block;
    margin-bottom: 7px;
    color: #4d5a70;
    font-size: 13px;
    font-weight: 650;
  }
  em {
    color: #e23f54;
    font-style: normal;
  }
  :deep(.n-form-item) {
    display: block;
    min-width: 0;
  }
  :deep(.n-form-item-blank) {
    display: block;
    width: 100%;
  }
  :deep(.n-input),
  :deep(.n-base-selection) {
    border-radius: 5px;
  }

  .owner-row {
    display: grid;
    grid-template-columns: 116px minmax(230px, 316px) 1fr;
    align-items: center;
    gap: 13px;
  }
  .owner-row .field-title {
    margin: 0;
  }
  .owner-tip {
    color: #9aa5b7;
    font-size: 12px;
  }
  .member-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 17px 0 10px;
  }
  .member-title-row strong {
    color: #4d5a70;
    font-size: 13px;
  }
  .member-title-row span {
    margin-left: 8px;
    color: #9aa5b7;
    font-size: 12px;
  }
  .member-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 9px;
  }
  .member-chip {
    position: relative;
    display: flex;
    align-items: center;
    gap: 9px;
    min-width: 0;
    padding: 10px;
    border: 1px solid #e2e7f0;
    border-radius: 5px;
    background: #fbfcfe;
  }
  .member-avatar {
    display: grid;
    place-items: center;
    flex: 0 0 34px;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    color: #fff;
    font-size: 13px;
    font-weight: 750;
  }
  .member-copy {
    min-width: 0;
  }
  .member-copy strong {
    display: block;
    overflow: hidden;
    color: #28344a;
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .member-copy span {
    color: #929caf;
    font-size: 11px;
  }
  .remove-member {
    position: absolute;
    top: 4px;
    right: 6px;
    border: 0;
    color: #b0bac8;
    background: transparent;
    cursor: pointer;
  }
  .member-add-select {
    margin-top: 10px;
  }
  :deep(.member-add-select .n-base-selection) {
    border: 1px dashed #8295ff;
    background: #f8f9ff;
  }
  :deep(.member-add-select .n-base-selection-label) {
    justify-content: center;
    color: #536dfe;
  }
  .compact-empty {
    padding: 4px 0;
  }

  .variable-heading {
    justify-content: space-between;
  }
  .heading-copy {
    display: flex;
    align-items: center;
    gap: 11px;
  }
  .reference-tip {
    color: #8d98aa;
    font-size: 12px;
  }
  code {
    padding: 2px 6px;
    border-radius: 4px;
    color: #4864ec;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    background: #eef2ff;
  }
  .variable-table {
    overflow: hidden;
    border: 1px solid #dfe6f0;
    border-radius: 5px;
  }
  .variable-table-head,
  .variable-row {
    display: grid;
    grid-template-columns: 0.72fr 1.25fr 1.1fr 60px;
    gap: 10px;
    align-items: center;
  }
  .variable-table-head {
    min-height: 38px;
    padding: 0 12px;
    color: #69768b;
    font-size: 12px;
    font-weight: 700;
    background: #f5f7fb;
    border-bottom: 1px solid #e4e9f1;
  }
  .variable-row {
    padding: 8px 12px;
    border-bottom: 1px solid #edf0f5;
  }
  .variable-row:last-child {
    border-bottom: 0;
  }
  .variable-empty {
    padding: 18px 0 12px;
  }
  .add-variable-button {
    width: 100%;
    height: 39px;
    border: 0;
    border-top: 1px dashed #cbd4e2;
    color: #536dfe;
    font-size: 13px;
    background: #fafbff;
    cursor: pointer;
  }
  .add-variable-button:hover {
    background: #f2f4ff;
  }

  .side-panel {
    overflow: hidden;
  }
  .side-panel-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 49px;
    padding: 0 16px;
    border-bottom: 1px solid #e5eaf1;
  }
  .side-panel-title span {
    color: #9aa5b7;
    font-size: 11px;
  }
  .stat-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .stat-item {
    display: flex;
    align-items: center;
    gap: 11px;
    min-height: 89px;
    padding: 14px 16px;
    border-right: 1px solid #e8ecf2;
    border-bottom: 1px solid #e8ecf2;
  }
  .stat-item:nth-child(2n) {
    border-right: 0;
  }
  .stat-item:nth-child(n + 3) {
    border-bottom: 0;
  }
  .stat-icon {
    display: grid;
    place-items: center;
    width: 39px;
    height: 39px;
    border-radius: 9px;
    font-size: 21px;
  }
  .stat-item strong {
    display: block;
    color: #172033;
    font-size: 22px;
    line-height: 1.1;
  }
  .stat-item div span {
    color: #8d99ab;
    font-size: 11px;
  }
  .stat-blue .stat-icon {
    color: #536dfe;
    background: #eef1ff;
  }
  .stat-green .stat-icon {
    color: #11a683;
    background: #eaf8f4;
  }
  .stat-violet .stat-icon {
    color: #7b61d9;
    background: #f1edff;
  }
  .stat-orange .stat-icon {
    color: #e7922f;
    background: #fff4e7;
  }

  .permission-list {
    padding: 5px 16px;
  }
  .permission-more {
    padding: 9px 0;
    border-top: 1px dashed #edf0f5;
    color: #9aa5b7;
    font-size: 10px;
  }
  .permission-item {
    display: grid;
    grid-template-columns: 34px minmax(0, 1fr) auto;
    align-items: center;
    gap: 10px;
    min-height: 55px;
    border-bottom: 1px solid #edf0f5;
  }
  .permission-item:last-child {
    border-bottom: 0;
  }
  .permission-item div {
    min-width: 0;
  }
  .permission-item strong {
    display: block;
    overflow: hidden;
    color: #2a3548;
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .permission-item div span {
    color: #9aa5b7;
    font-size: 10px;
  }
  .permission-item em {
    padding: 3px 7px;
    border-radius: 10px;
    font-size: 10px;
  }
  .role-owner {
    color: #536dfe !important;
    background: #eef1ff;
  }
  .role-admin {
    color: #a26c16 !important;
    background: #fff3d9;
  }
  .role-member {
    color: #698096 !important;
    background: #eef2f5;
  }

  .help-panel {
    padding: 16px;
  }
  .help-title {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .help-title > span {
    display: grid;
    place-items: center;
    width: 25px;
    height: 25px;
    border-radius: 6px;
    color: #536dfe;
    font-size: 17px;
    background: #eef1ff;
  }
  .help-panel ul {
    margin: 13px 0;
    padding-left: 19px;
    color: #78859a;
    font-size: 12px;
    line-height: 1.8;
  }
  .priority-note {
    padding: 9px 10px;
    border-left: 3px solid #536dfe;
    color: #5e6c82;
    font-size: 11px;
    background: #f5f7ff;
  }

  @media (max-width: 1180px) {
    .content-grid {
      grid-template-columns: 1fr;
    }
    .overview-column {
      display: grid;
      grid-template-columns: 1fr 1fr;
    }
    .help-panel {
      grid-column: 1 / -1;
    }
  }

  @media (max-width: 760px) {
    .project-detail-page {
      padding: 14px;
    }
    .page-header {
      align-items: flex-start;
      flex-direction: column;
    }
    .header-actions {
      width: 100%;
      flex-wrap: wrap;
    }
    .action-button {
      flex: 1;
    }
    .basic-grid,
    .member-grid,
    .overview-column {
      grid-template-columns: 1fr;
    }
    .owner-row {
      grid-template-columns: 1fr;
    }
    .variable-table {
      overflow-x: auto;
    }
    .variable-table-head,
    .variable-row {
      min-width: 720px;
    }
  }
</style>
