<template>
  <div class="user-detail">
    <!-- 面包屑 -->
    <n-breadcrumb class="crumb">
      <n-breadcrumb-item @click="back">系统管理</n-breadcrumb-item>
      <n-breadcrumb-item @click="back">用户管理</n-breadcrumb-item>
      <n-breadcrumb-item>{{ dataID ? '用户详情' : '新增用户' }}</n-breadcrumb-item>
    </n-breadcrumb>

    <!-- 头部 -->
    <div class="head">
      <div class="id">
        <div class="avatar">{{ avatarText }}</div>
        <div>
          <h1>{{ form.username || (dataID ? '加载中…' : '新增用户') }}</h1>
          <div class="sub" v-if="dataID && detail.id">
            ID {{ detail.id }} · 创建于 {{ fmt(detail.date_joined) }} · 最近登录 {{ fmt(detail.last_login) }}
          </div>
          <div class="sub" v-else-if="!dataID">填写下方信息以创建新用户</div>
        </div>
      </div>
      <div class="actions">
        <n-button @click="back">返回</n-button>
        <n-button type="primary" @click="submit">{{ dataID ? '保存修改' : '创建用户' }}</n-button>
      </div>
    </div>

    <n-form ref="formRef" :model="form" :rules="rules" label-placement="left" label-width="90">
      <div class="cols">
        <!-- 左列 -->
        <div class="col">
          <n-card class="card">
            <template #header><span class="ttl">基本资料</span></template>
            <n-form-item label="用户名" path="username">
              <n-input v-model:value="form.username" :disabled="!!dataID" placeholder="请输入用户名" />
            </n-form-item>
            <n-form-item label="登录密码" :path="dataID ? '' : 'password'">
              <n-input v-model:value="form.password" type="password" show-password-on="click"
                :placeholder="dataID ? '留空则不修改密码' : '至少 6 位'" />
            </n-form-item>
            <n-form-item v-if="isAdmin" label="账号状态">
              <n-switch v-model:value="form.is_active">
                <template #checked>启用</template>
                <template #unchecked>禁用</template>
              </n-switch>
              <span class="switch-tip">{{ form.is_active ? '启用' : '禁用' }}</span>
            </n-form-item>
            <n-form-item v-if="isAdmin" label="平台管理员">
              <n-switch v-model:value="form.is_staff">
                <template #checked>是</template>
                <template #unchecked>否</template>
              </n-switch>
              <span class="switch-tip">{{ form.is_staff ? '是' : '否' }}</span>
            </n-form-item>
            <n-form-item label="所属项目">
              <div v-if="isAllProjects" class="tags">
                <n-tag size="small" type="primary" :bordered="false">All</n-tag>
              </div>
              <div v-else-if="projectList.length" class="tags">
                <n-tag v-for="name in projectList" :key="name" size="small" type="primary" :bordered="false">{{ name }}</n-tag>
              </div>
              <span v-else class="muted">暂无关联项目</span>
            </n-form-item>
            <p class="tip">用户名创建后不可修改；密码留空表示保持原密码。账号状态为「禁用」时该用户将无法登录。</p>
          </n-card>

          <n-card v-if="dataID" class="card">
            <template #header>
              <span class="ttl">操作记录 <span class="muted-sm">最近 5 条</span></span>
            </template>
            <n-empty description="暂无操作记录" size="small" />
          </n-card>
        </div>

        <!-- 右列（仅编辑态） -->
        <div class="col" v-if="dataID">
          <n-card class="card">
            <template #header><span class="ttl">账号概览</span></template>
            <div class="meta">
              <div class="row"><span class="k">用户 ID</span><span class="v">{{ detail.id }}</span></div>
              <div class="divider"></div>
              <div class="row"><span class="k">创建时间</span><span class="v">{{ fmt(detail.date_joined) }}</span></div>
              <div class="row"><span class="k">最近登录</span><span class="v">{{ fmt(detail.last_login) }}</span></div>
              <div class="row"><span class="k">登录次数</span><span class="v">—</span></div>
              <div class="divider"></div>
              <div class="row">
                <span class="k">账号状态</span>
                <span class="v">
                  <n-tag size="small" :type="form.is_active ? 'success' : 'default'" :bordered="false">{{ form.is_active ? '启用' : '禁用' }}</n-tag>
                </span>
              </div>
              <div class="row">
                <span class="k">管理员</span>
                <span class="v">
                  <n-tag size="small" :type="form.is_staff ? 'warning' : 'default'" :bordered="false">{{ form.is_staff ? '是' : '否' }}</n-tag>
                </span>
              </div>
            </div>
          </n-card>

          <n-card class="card">
            <template #header><span class="ttl">安全</span></template>
            <div class="meta">
              <div class="row"><span class="k">两步验证</span><span class="v"><n-tag size="small" type="default" :bordered="false">未开启</n-tag></span></div>
              <div class="row"><span class="k">上次改密</span><span class="v">—</span></div>
            </div>
            <n-button dashed block class="full-btn" @click="logoutAll">强制退出全部会话</n-button>
          </n-card>

          <div class="danger-zone">
            <div class="t">危险操作</div>
            <div class="d">删除用户后，其创建的套件、场景等数据将一并移除且不可恢复。</div>
            <n-button block type="error" @click="removeUser">删除用户</n-button>
          </div>
        </div>
      </div>
    </n-form>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useDialog, useMessage } from 'naive-ui';
import { UserManageAPI } from '@/api/account/http';
import { useUserStore } from '@/store/modules/user';

const route = useRoute();
const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const api = new UserManageAPI();
const formRef = ref();
const dataID = Number(route.params.id || 0);
const userStore = useUserStore();
const isAdmin = computed(() => Boolean((userStore.info as any)?.is_admin));

const form = reactive<any>({ username: '', password: '', is_active: true, is_staff: false });
const detail = reactive<any>({ id: '', date_joined: '', last_login: '', projects: '' });
const rules = {
  username: { required: true, message: '请输入用户名', trigger: 'blur' },
  password: { required: true, min: 6, message: '密码至少 6 位', trigger: 'blur' },
};

const avatarText = computed(() =>
  form.username ? form.username.charAt(0).toUpperCase() : dataID ? 'U' : '+'
);
function fmt(dt: string) {
  return dt ? dt.split('.')[0].replace('T', ' ') : '—';
}

const isAllProjects = computed(() => detail.projects === 'ALL' || form.is_staff);
const projectList = computed(() =>
  Array.isArray(detail.projects) ? detail.projects.map((p: any) => p.name) : []
);

onMounted(async () => {
  if (dataID) {
    if (!isAdmin.value) {
      message.error('仅管理员可以编辑用户');
      back();
      return;
    }
    try {
      const d: any = await api.getDataByID(dataID);
      Object.assign(form, d);
      Object.assign(detail, { id: d.id, date_joined: d.date_joined, last_login: d.last_login, projects: d.projects });
    } catch (e) {
      message.error('加载用户失败');
      back();
    }
  }
});

function back() {
  router.push({ name: 'system_user' });
}

function submit() {
  formRef.value?.validate(async (errors: any) => {
    if (errors) return;
    const data: any = { ...form };
    if (!data.password) delete data.password;
    try {
      if (dataID) await api.updateData(dataID, data);
      else await api.createData(data);
      message.success('保存成功');
      back();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    }
  });
}

function logoutAll() {
  message.info('后端暂未提供「强制退出会话」接口');
}

function removeUser() {
  dialog.warning({
    title: '确认删除',
    content: `确认删除用户「${form.username}」？该操作不可恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.deleteData(dataID);
        message.success('删除成功');
        back();
      } catch (e: any) {
        message.error(e?.response?.data?.detail || '删除失败');
      }
    },
  });
}
</script>

<style scoped>
.user-detail { max-width: 1080px; margin: 0 auto; padding: 4px 0; }
.crumb { font-size: 13px; margin-bottom: 14px; }
.crumb :deep(.n-breadcrumb-item__link) { cursor: pointer; }

.head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.head .id { display: flex; align-items: center; gap: 14px; }
.avatar {
  width: 56px; height: 56px; border-radius: 14px;
  background: linear-gradient(135deg, #536dfe, #7c8cff); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; font-weight: 700;
}
.head h1 { font-size: 20px; font-weight: 750; margin: 0; }
.head .sub { font-size: 12px; color: #8793a5; margin-top: 3px; }
.actions { display: flex; gap: 10px; }

.cols { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr); gap: 16px; align-items: start; }
.col { min-width: 0; }
.card { margin-bottom: 16px; }
.card :deep(.n-card-header) { padding: 14px 20px; border-bottom: 1px solid #edf1f6; }
.card :deep(.n-card__content) { padding: 18px 20px; }
.ttl { font-size: 15px; font-weight: 650; color: #263549; }
.muted-sm { font-weight: 400; font-size: 12px; color: #8793a5; }

.tags { display: flex; flex-wrap: wrap; gap: 8px; }
.muted { color: #8793a5; font-size: 14px; }
.switch-tip { margin-left: 12px; font-size: 13px; color: #263549; }
.tip { font-size: 12px; color: #8793a5; margin-top: 12px; line-height: 1.6; }

.meta { display: grid; gap: 14px; }
.meta .row { display: flex; justify-content: space-between; font-size: 13px; }
.meta .row .k { color: #8793a5; }
.meta .row .v { color: #263549; font-weight: 600; }
.divider { height: 1px; background: #edf1f6; margin: 4px 0; }
.full-btn { margin-top: 14px; }

.danger-zone { border: 1px solid #ffeaed; background: #ffeaed; border-radius: 12px; padding: 14px 16px; }
.danger-zone .t { font-size: 13px; font-weight: 700; color: #e5484d; margin-bottom: 6px; }
.danger-zone .d { font-size: 12px; color: #a23a3e; margin-bottom: 10px; line-height: 1.5; }

@media (max-width: 900px) { .cols { grid-template-columns: 1fr; } }
</style>
