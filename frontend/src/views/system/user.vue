<template>
  <n-card :bordered="false" class="proCard">
    <BasicTable title="用户管理" :columns="columns" :request="loadData" :row-key="row => row.id" ref="actionRef" :actionColumn="actionColumn" :scroll-x="980">
      <template #toolbar><n-button type="primary" @click="add">新增用户</n-button></template>
    </BasicTable>
  </n-card>
</template>
<script setup lang="ts">
import { computed, h, reactive, ref } from 'vue';
import { NButton, NInput, useDialog, useMessage } from 'naive-ui';
import { BasicTable } from '@/components/Table';
import { useRouter } from 'vue-router';
import { UserManageAPI } from '@/api/account/http';
import { useUserStore } from '@/store/modules/user';
const api = new UserManageAPI(); const router = useRouter(); const dialog = useDialog(); const message = useMessage(); const actionRef = ref(); const userStore = useUserStore();
const isAdmin = computed(() => Boolean((userStore.info as any)?.is_admin));
const currentUserId = computed(() => Number((userStore.info as any)?.user));
const columns = [
  { title: '用户名', key: 'username' },
  { title: '状态', key: 'is_active', render: (row) => row.is_active ? '启用' : '禁用' },
  { title: '管理员', key: 'is_staff', render: (row) => row.is_staff ? '是' : '否' },
  { title: '创建时间', key: 'date_joined', render: (row) => (row.date_joined || '').split('.')[0].replace('T', ' ') },
];
const loadData = (params) => api.getDataList(params);
const actionColumn = reactive({ width: 250, title: '操作', key: 'action', fixed: 'right', render: (row) => {
  const children: any[] = [];
  if (isAdmin.value || row.id === currentUserId.value) children.push(h(NButton, { text: true, type: 'warning', onClick: () => resetPassword(row) }, { default: () => '重置密码' }));
  if (isAdmin.value) {
    children.push(h(NButton, { text: true, type: 'primary', onClick: () => router.push({ name: 'system_user_edit', params: { id: row.id } }) }, { default: () => '编辑' }));
    children.push(h(NButton, { text: true, type: 'error', onClick: () => remove(row) }, { default: () => '删除' }));
  }
  return h('div', { style: 'display:flex;gap:12px' }, children);
} });
function add() { router.push({ name: 'system_user_edit', params: { id: 0 } }); }
function remove(row) { dialog.warning({ title: '确认删除', content: `确认删除用户「${row.username}」？`, positiveText: '删除', negativeText: '取消', onPositiveClick: async () => { await api.deleteData(row.id); await actionRef.value?.removeRowByKey(row.id); message.success('删除成功'); } }); }

function resetPassword(row: any) {
  // 用闭包 reactive 承载输入与错误；不在 dialog content 里传 ref（ref 在该场景下不可靠）
  const state = reactive({ password: '', err: '' });
  dialog.warning({
    title: `重置「${row.username}」的密码`,
    showIcon: false,
    style: 'width: 460px',
    content: () => h('div', { style: 'padding:4px 0 0' }, [
      h('label', { style: 'display:block;font-size:13px;color:#263549;margin-bottom:8px;font-weight:500' }, '新密码'),
      h(NInput, {
        type: 'password',
        showPasswordOn: 'click',
        placeholder: '请输入新密码（至少 6 位）',
        autofocus: true,
        clearable: true,
        value: state.password,
        status: state.err ? 'error' : undefined,
        'onUpdate:value': (v: string) => { state.password = v; if (state.err) state.err = ''; },
      }),
      h('p', { style: 'font-size:12px;color:#8793a5;margin:8px 0 0;line-height:1.5' },
        '至少 6 位，重置后该用户将以新密码登录。'),
      state.err
        ? h('div', { style: 'margin-top:6px;font-size:12px;color:#e5484d;line-height:1.5' }, state.err)
        : null,
    ]),
    positiveText: '重置密码',
    negativeText: '取消',
    onPositiveClick: async () => {
      if (!state.password || state.password.length < 6) {
        state.err = '密码至少 6 位';
        return false;
      }
      try {
        await api.resetPassword(row.id, state.password);
        message.success(`已重置「${row.username}」的密码`);
        return true;
      } catch (e: any) {
        const detail = e?.response?.data;
        const msg = (detail && (detail.password?.[0] || detail.password || detail.detail)) || '重置失败，请稍后重试';
        state.err = msg;
        return false;
      }
    },
  });
}
</script>
