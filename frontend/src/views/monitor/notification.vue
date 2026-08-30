<template>
  <n-result v-if="projectsLoaded && !canMaintain" class="access-denied" status="403" title="无访问权限" description="仅系统管理员或项目负责人可以配置监控告警通知。" />
  <section v-else class="monitor-notification">
    <header><div><h2>告警通知</h2><p>复用「系统管理 → 通知管理」中的飞书或企业微信渠道；异常与恢复只在状态变化时投递。</p></div></header>
    <n-tabs type="line">
      <n-tab-pane name="rules" tab="通知规则">
        <div class="toolbar"><n-button type="primary" @click="openRule()">新增通知规则</n-button></div>
        <n-data-table :columns="ruleColumns" :data="rules" :loading="loading" />
      </n-tab-pane>
      <n-tab-pane name="deliveries" tab="投递记录">
        <div class="toolbar"><n-button @click="load">刷新</n-button></div>
        <n-data-table :columns="deliveryColumns" :data="deliveries" :loading="loading" :pagination="{ pageSize: 10 }" />
      </n-tab-pane>
    </n-tabs>

    <n-modal v-model:show="visible" preset="card" :title="form.id ? '编辑通知规则' : '新增通知规则'" class="platform-form-modal">
      <n-form label-placement="top">
        <n-form-item label="已有通知渠道"><n-select v-model:value="form.channel" :options="channelOptions" placeholder="请先在通知管理中创建渠道" /></n-form-item>
        <n-form-item label="监控对象类型">
          <n-radio-group v-model:value="objectType"><n-radio value="target">监控主机</n-radio><n-radio value="service">服务监控</n-radio></n-radio-group>
        </n-form-item>
        <n-form-item v-if="objectType === 'target'" label="监控主机"><n-select v-model:value="targetId" :options="targetOptions" /></n-form-item>
        <n-form-item v-else label="监控服务">
          <n-select v-model:value="serviceIds" multiple :options="serviceOptions" placeholder="请选择一个或多个服务" @update:value="normalizeServiceSelection" />
        </n-form-item>
        <n-alert v-if="objectType === 'service' && serviceIds.includes(ALL_SERVICES)" type="info" :show-icon="true" class="scope-tip">全部服务为动态范围：当前通知渠道所关联项目中的现有服务及后续新增服务都会自动纳入。</n-alert>
        <n-form-item label="触发事件"><n-select v-model:value="form.event" :options="eventOptions" /></n-form-item>
        <n-switch v-model:value="form.enabled" /> 启用规则
      </n-form>
      <template #footer><n-space justify="end"><n-button @click="visible = false">取消</n-button><n-button type="primary" @click="save">保存</n-button></n-space></template>
    </n-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, watch } from 'vue';
import { NButton, NPopconfirm, NTag, useMessage } from 'naive-ui';
import { MonitorAPI, type MonitorNotificationDelivery, type MonitorNotificationRule, type MonitorTarget, type ServiceMonitor } from '@/api/monitor/http';
import { NotificationChannelAPI } from '@/api/suite/http';
import { useUserStore } from '@/store/modules/user';
import { ProjectAPI } from '@/api/project/http';

const ALL_SERVICES = -1;
const message = useMessage();
const userStore = useUserStore();
const isAdmin = computed(() => Boolean((userStore.info as any)?.is_admin));
const currentUserId = computed(() => Number((userStore.info as any)?.user || (userStore.info as any)?.id || 0));
const loading = ref(false);
const projectsLoaded = ref(false);
const visible = ref(false);
const rules = ref<MonitorNotificationRule[]>([]);
const deliveries = ref<MonitorNotificationDelivery[]>([]);
const targets = ref<MonitorTarget[]>([]);
const services = ref<ServiceMonitor[]>([]);
const channels = ref<any[]>([]);
const projects = ref<any[]>([]);
const objectType = ref<'target' | 'service'>('target');
const targetId = ref<number | null>(null);
const serviceIds = ref<number[]>([]);
const channelApi = new NotificationChannelAPI();
const projectApi = new ProjectAPI();
const managedProjects = computed(() => isAdmin.value ? projects.value : projects.value.filter((item) => Number(item.pm) === currentUserId.value));
const managedProjectIds = computed(() => new Set(managedProjects.value.map((item) => Number(item.id))));
const canMaintain = computed(() => isAdmin.value || managedProjects.value.length > 0);

const blank = (): MonitorNotificationRule => ({ channel: null, target: null, services: [], all_services: false, event: 'alert', enabled: true });
const form = reactive<MonitorNotificationRule>(blank());
const asList = <T,>(data: any): T[] => Array.isArray(data) ? data : data?.list || data?.results || data?.data || [];
const channelOptions = computed(() => channels.value.map((item) => ({ label: `${item.name}（${item.platform === 'lark' ? '飞书' : '企业微信'}）`, value: item.id })));
const targetOptions = computed(() => targets.value.map((item) => ({ label: `${item.name} · ${item.project_name || '平台级'}`, value: item.id })));
const serviceOptions = computed(() => [
  { label: '全部服务', value: ALL_SERVICES },
  ...services.value.map((item) => ({ label: `${item.name} · ${item.project_name || '平台级'}`, value: item.id })),
]);
const eventOptions = [{ label: '仅异常告警', value: 'alert' }, { label: '仅恢复通知', value: 'recovered' }, { label: '异常和恢复', value: 'all' }];
const eventName = (value: string) => value === 'alert' ? '异常告警' : value === 'recovered' ? '恢复通知' : '异常和恢复';

watch(objectType, () => { targetId.value = null; serviceIds.value = []; });

const normalizeServiceSelection = (values: number[]) => {
  if (!values.includes(ALL_SERVICES)) return;
  serviceIds.value = values[values.length - 1] === ALL_SERVICES ? [ALL_SERVICES] : values.filter((value) => value !== ALL_SERVICES);
};

const load = async () => {
  if (!canMaintain.value) return;
  loading.value = true;
  try {
    const [ruleData, deliveryData, targetData, serviceData, channelData] = await Promise.all([
      MonitorAPI.notificationRules(), MonitorAPI.notificationDeliveries(), MonitorAPI.targetList(), MonitorAPI.serviceList(), channelApi.getDataList({}),
    ]);
    rules.value = asList(ruleData);
    deliveries.value = asList(deliveryData);
    targets.value = asList<MonitorTarget>(targetData).filter((item) => item.project != null && managedProjectIds.value.has(Number(item.project)));
    services.value = asList<ServiceMonitor>(serviceData).filter((item) => item.project != null && managedProjectIds.value.has(Number(item.project)));
    channels.value = asList<any>(channelData).filter((item) => isAdmin.value || (Array.isArray(item.projects) && item.projects.length > 0 && item.projects.every((projectId: number) => managedProjectIds.value.has(Number(projectId)))));
  } catch (error: any) {
    message.error(error?.message || '加载告警通知失败');
  } finally {
    loading.value = false;
  }
};

const loadProjects = async () => {
  try {
    projects.value = asList(await projectApi.getDataList({ page: 1, pageSize: 1000 }));
  } catch (error: any) {
    projects.value = [];
    message.error(error?.message || '项目列表加载失败');
  } finally {
    projectsLoaded.value = true;
  }
};

const openRule = (row?: MonitorNotificationRule) => {
  Object.assign(form, blank(), row || {});
  objectType.value = row?.target ? 'target' : 'service';
  targetId.value = row?.target || null;
  serviceIds.value = row?.all_services ? [ALL_SERVICES] : [...(row?.services || [])];
  visible.value = true;
};

const save = async () => {
  if (!form.channel) return message.warning('请选择通知渠道');
  if (objectType.value === 'target' && !targetId.value) return message.warning('请选择监控主机');
  if (objectType.value === 'service' && !serviceIds.value.length) return message.warning('请选择一个或多个监控服务');
  const allServices = objectType.value === 'service' && serviceIds.value.includes(ALL_SERVICES);
  const data: MonitorNotificationRule = {
    ...form,
    target: objectType.value === 'target' ? targetId.value : null,
    services: objectType.value === 'service' && !allServices ? serviceIds.value : [],
    all_services: allServices,
  };
  try {
    if (form.id) await MonitorAPI.updateNotificationRule(form.id, data);
    else await MonitorAPI.createNotificationRule(data);
    visible.value = false;
    message.success('通知规则已保存');
    await load();
  } catch (error: any) {
    message.error(error?.message || '保存失败');
  }
};

const remove = async (row: MonitorNotificationRule) => {
  try {
    await MonitorAPI.deleteNotificationRule(row.id!);
    rules.value = rules.value.filter((item) => item.id !== row.id);
    message.success('已删除');
  } catch (error: any) {
    message.error(error?.message || '删除失败');
  }
};

const ruleColumns: any[] = [
  { title: '通知渠道', key: 'channel_name' },
  { title: '监控对象', key: 'object', render: (row: MonitorNotificationRule) => row.target_name || (row.all_services ? '全部服务' : row.service_names?.join('、')) || '-' },
  { title: '事件', key: 'event', render: (row: MonitorNotificationRule) => eventName(row.event) },
  { title: '状态', key: 'enabled', render: (row: MonitorNotificationRule) => h(NTag, { type: row.enabled ? 'success' : 'default' }, { default: () => row.enabled ? '启用' : '停用' }) },
  { title: '操作', key: 'actions', width: 160, render: (row: MonitorNotificationRule) => h('div', { style: 'display:flex;align-items:center;gap:14px;white-space:nowrap;' }, [h(NButton, { text: true, type: 'primary', onClick: () => openRule(row) }, { default: () => '编辑' }), h(NPopconfirm, { onPositiveClick: () => remove(row) }, { trigger: () => h(NButton, { text: true, type: 'error' }, { default: () => '删除' }), default: () => '确认删除该通知规则？' })]) },
];
const deliveryColumns: any[] = [
  { title: '对象', key: 'object', render: (row: MonitorNotificationDelivery) => row.target_name || row.service_name || '-' },
  { title: '渠道', key: 'channel_name' },
  { title: '事件', key: 'event', render: (row: MonitorNotificationDelivery) => eventName(row.event) },
  { title: '状态', key: 'status', render: (row: MonitorNotificationDelivery) => h(NTag, { type: row.status === 'sent' ? 'success' : 'error' }, { default: () => row.status === 'sent' ? '已发送' : '发送失败' }) },
  { title: 'HTTP', key: 'response_code' }, { title: '响应摘要', key: 'response_summary', ellipsis: true }, { title: '时间', key: 'created_at' },
];

onMounted(async () => { await loadProjects(); await load(); });
</script>

<style scoped lang="less">
.access-denied { display: flex; min-height: calc(100vh - 150px); flex-direction: column; justify-content: center; padding: 24px; box-sizing: border-box; }
.monitor-notification { padding: 24px 28px; }
.monitor-notification header { margin-bottom: 20px; }
.monitor-notification h2 { margin: 0; color: #1e293b; }
.monitor-notification p { margin: 8px 0 0; color: #7b8ba3; }
.toolbar { display: flex; justify-content: flex-end; margin-bottom: 14px; }
.scope-tip { margin: -4px 0 18px; }
</style>
