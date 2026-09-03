<template>
  <n-result
    v-if="projectsLoaded && !canMaintain"
    class="access-denied"
    status="403"
    title="无访问权限"
    description="仅系统管理员或项目负责人可以维护服务器配置。"
  />
  <section v-else class="server-page">
    <header class="server-page__header">
      <div><h2>服务器连接</h2><p>系统管理员可维护全部连接，项目负责人可维护所负责项目的 SSH 服务器连接。</p></div>
      <div class="server-page__actions"><n-select v-model:value="selectedProject" clearable class="project-filter" :options="projectOptions" placeholder="全部项目" @update:value="load" /><n-button type="primary" @click="openEditor()">新增服务器</n-button></div>
    </header>
    <n-card :bordered="false" class="server-card">
      <n-data-table striped :columns="columns" :data="records" :loading="loading" :row-key="row => row.id" />
    </n-card>

    <n-modal v-model:show="editorVisible" preset="card" :title="editing?.id ? '编辑服务器连接' : '新增服务器连接'" class="platform-form-modal server-editor" :mask-closable="false">
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
        <n-grid :cols="2" :x-gap="16">
          <n-gi><n-form-item label="所属项目" path="project"><n-select v-model:value="form.project" :options="formProjectOptions" placeholder="请选择所属项目" /></n-form-item></n-gi>
          <n-gi><n-form-item label="连接名称" path="name"><n-input v-model:value="form.name" placeholder="例如：生产应用服务器" /></n-form-item></n-gi>
          <n-gi><n-form-item label="服务器地址" path="host"><n-input v-model:value="form.host" placeholder="IP 或域名" /></n-form-item></n-gi>
          <n-gi><n-form-item label="SSH 端口" path="port"><n-input-number v-model:value="form.port" :min="1" :max="65535" class="full-width" /></n-form-item></n-gi>
          <n-gi><n-form-item label="登录账号" path="username"><n-input v-model:value="form.username" placeholder="例如：deployer" :input-props="{ autocomplete: 'off', name: 'server-ssh-login-account', 'data-1p-ignore': 'true' }" /></n-form-item></n-gi>
        </n-grid>
        <n-form-item label="认证方式"><n-radio-group v-model:value="form.auth_type" @update:value="resetEditorScroll"><n-space><n-radio value="private_key">私钥认证</n-radio><n-radio value="password">密码认证</n-radio></n-space></n-radio-group></n-form-item>
        <template v-if="form.auth_type === 'private_key'">
          <n-form-item label="私钥文件路径" path="private_key_path"><n-input v-model:value="form.private_key_path" placeholder="平台服务端可访问的绝对路径" /></n-form-item>
          <n-form-item :label="editing?.private_key_passphrase_configured ? '私钥口令（留空保持原值）' : '私钥口令（可选）'"><n-input v-model:value="form.private_key_passphrase" type="password" show-password-on="click" :input-props="{ autocomplete: 'new-password', name: 'server-private-key-passphrase', 'data-1p-ignore': 'true' }" /></n-form-item>
        </template>
        <n-form-item v-else :label="editing?.password_configured ? '登录密码（留空保持原值）' : '登录密码'" path="password"><n-input v-model:value="form.password" type="password" show-password-on="click" :input-props="{ autocomplete: 'new-password', name: 'server-ssh-login-password', 'data-1p-ignore': 'true' }" /></n-form-item>
        <n-space align="center" class="server-options"><n-switch v-model:value="form.strict_host_key" />校验 SSH 主机指纹<n-switch v-model:value="form.enabled" />启用连接</n-space>
        <n-form-item label="备注"><n-input v-model:value="form.description" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="填写用途、部署说明等" /></n-form-item>
      </n-form>
      <template #footer><n-space justify="end"><n-button :loading="testing" @click="testCurrentConnection">测试连接</n-button><n-button @click="editorVisible = false">取消</n-button><n-button type="primary" :loading="saving" @click="save">保存</n-button></n-space></template>
    </n-modal>
  </section>
</template>

<script setup lang="ts">
  import { computed, h, nextTick, onMounted, reactive, ref } from 'vue';
  import { NButton, NPopconfirm, NSpace, NTag, useMessage, type FormInst, type FormRules } from 'naive-ui';
  import { ServerConnectionAPI, type ServerConnection } from '@/api/system/server';
  import { ProjectAPI } from '@/api/project/http';
  import { useUserStore } from '@/store/modules/user';

  const message = useMessage();
  const userStore = useUserStore();
  const projectApi = new ProjectAPI();
  const isAdmin = computed(() => Boolean((userStore.info as any)?.is_admin));
  const currentUserId = computed(() => Number((userStore.info as any)?.user || (userStore.info as any)?.id || 0));
  const loading = ref(false); const saving = ref(false); const testing = ref(false); const editorVisible = ref(false); const projectsLoaded = ref(false);
  const records = ref<ServerConnection[]>([]); const projects = ref<any[]>([]); const selectedProject = ref<number | null>(null); const editing = ref<ServerConnection>(); const formRef = ref<FormInst>();
  const emptyForm = (): ServerConnection => ({ project: selectedProject.value, name: '', host: '', port: 22, username: '', auth_type: 'private_key', private_key_path: '', private_key_passphrase: '', password: '', strict_host_key: true, enabled: true, description: '' });
  const form = reactive<ServerConnection>(emptyForm());
  const managedProjects = computed(() => isAdmin.value ? projects.value : projects.value.filter((item) => Number(item.pm) === currentUserId.value));
  const canMaintain = computed(() => isAdmin.value || managedProjects.value.length > 0);
  const projectOptions = computed(() => managedProjects.value.map((item) => ({ label: item.name, value: Number(item.id) })));
  const formProjectOptions = computed(() => selectedProject.value == null ? projectOptions.value : projectOptions.value.filter((item) => item.value === selectedProject.value));
  const rules: FormRules = {
    project: { required: true, type: 'number', message: '请选择所属项目', trigger: ['blur', 'change'] }, name: { required: true, message: '请输入连接名称', trigger: ['blur', 'input'] }, host: { required: true, message: '请输入服务器地址', trigger: ['blur', 'input'] }, username: { required: true, message: '请输入登录账号', trigger: ['blur', 'input'] },
    private_key_path: { validator: () => form.auth_type !== 'private_key' || !!form.private_key_path?.trim(), message: '请填写私钥文件路径', trigger: ['blur', 'input'] },
    password: { validator: () => form.auth_type !== 'password' || !!form.password || !!editing.value?.password_configured, message: '请填写登录密码', trigger: ['blur', 'input'] },
  };
  const formatTime = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-';
  const asList = <T,>(payload: unknown): T[] => { if (Array.isArray(payload)) return payload as T[]; const response = payload as { list?: T[]; results?: T[]; data?: T[] } | null; return response?.list || response?.results || response?.data || []; };
  const load = async () => { if (!canMaintain.value) return; loading.value = true; try { records.value = asList(await ServerConnectionAPI.list(selectedProject.value)); } catch (error: any) { message.error(error?.message || '获取服务器连接失败'); } finally { loading.value = false; } };
  const loadProjects = async () => { try { projects.value = asList(await projectApi.getDataList({ page: 1, pageSize: 1000 })); } catch (error: any) { projects.value = []; message.error(error?.message || '项目列表加载失败'); } finally { projectsLoaded.value = true; } };
  const resetEditorScroll = async () => {
    await nextTick();
    document.querySelector('.server-editor .n-card__content')?.scrollTo({ top: 0 });
  };
  const openEditor = (row?: ServerConnection) => { editing.value = row; Object.assign(form, emptyForm(), row ? { ...row, project: row.project == null ? null : Number(row.project), password: '', private_key_passphrase: '' } : {}); editorVisible.value = true; void resetEditorScroll(); };
  const testCurrentConnection = async () => {
    try {
      await formRef.value?.validate();
      testing.value = true;
      const data = await ServerConnectionAPI.testDraft({ ...form, id: editing.value?.id });
      message.success(`连接成功，耗时 ${data.elapsed_ms} ms`);
    } catch (error: any) {
      if (error?.errors) return;
      message.error(error?.detail || error?.message || '连接失败');
    } finally { testing.value = false; }
  };
  const save = async () => { try { await formRef.value?.validate(); saving.value = true; const payload = { ...form }; if (editing.value?.id) await ServerConnectionAPI.update(editing.value.id, payload); else await ServerConnectionAPI.create(payload); message.success('服务器连接已保存'); editorVisible.value = false; await load(); } catch (error: any) { if (error?.errors) return; message.error(error?.message || '保存失败'); } finally { saving.value = false; } };
  const test = async (row: ServerConnection) => { try { const data = await ServerConnectionAPI.test(row.id!); message.success(`连接成功，耗时 ${data.elapsed_ms} ms`); await load(); } catch (error: any) { message.error(error?.detail || error?.message || '连接失败'); await load(); } };
  const remove = async (row: ServerConnection) => { try { await ServerConnectionAPI.remove(row.id!); records.value = records.value.filter((item) => item.id !== row.id); message.success('服务器连接已删除'); } catch (error: any) { message.error(error?.message || '删除失败'); } };
  const columns: any[] = [
    { title: '连接名称', key: 'name', minWidth: 160 }, { title: '所属项目', key: 'project_name', minWidth: 130, render: (row: ServerConnection) => row.project_name || '-' }, { title: '服务器', key: 'host', minWidth: 190, render: (row: ServerConnection) => `${row.username}@${row.host}:${row.port}` },
    { title: '认证方式', key: 'auth_type', render: (row: ServerConnection) => row.auth_type === 'private_key' ? '私钥认证' : '密码认证' },
    { title: '状态', key: 'enabled', render: (row: ServerConnection) => h(NTag, { type: row.enabled ? 'success' : 'default', size: 'small' }, { default: () => row.enabled ? '启用' : '停用' }) },
    { title: '最近测试', key: 'last_test_status', minWidth: 210, render: (row: ServerConnection) => row.last_test_status == null ? '-' : h(NTag, { type: row.last_test_status ? 'success' : 'error', size: 'small' }, { default: () => `${row.last_test_status ? '成功' : '失败'} · ${formatTime(row.last_tested_at)}` }) },
    { title: '创建人', key: 'created_by_name', width: 110, render: (row: ServerConnection) => row.created_by_name || '-' },
    { title: '操作', key: 'actions', width: 230, fixed: 'right', render: (row: ServerConnection) => h(NSpace, { size: 14, wrap: false, align: 'center' }, { default: () => [h(NButton, { text: true, type: 'info', onClick: () => test(row) }, { default: () => '测试连接' }), h(NButton, { text: true, type: 'primary', onClick: () => openEditor(row) }, { default: () => '编辑' }), h(NPopconfirm, { onPositiveClick: () => remove(row) }, { trigger: () => h(NButton, { text: true, type: 'error' }, { default: () => '删除' }), default: () => `确认删除「${row.name}」？` })] }) },
  ];
  onMounted(async () => { await loadProjects(); await load(); });
</script>

<style scoped lang="less">
  .access-denied { display: flex; min-height: calc(100vh - 150px); flex-direction: column; justify-content: center; padding: 24px; box-sizing: border-box; }
  .server-page { padding: 24px 28px; }.server-page__header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:18px; }.server-page__header h2 { margin:0; color:#1e293b; }.server-page__header p { margin:8px 0 0; color:#7a8ba5; }.server-page__actions { display:flex; align-items:center; gap:12px; }.project-filter { width:200px; }.server-card { border-radius:14px; }.full-width { width:100%; }.server-options { margin:0 0 20px; color:#52637c; }.server-options :deep(.n-switch) { margin-left:8px; }
</style>
