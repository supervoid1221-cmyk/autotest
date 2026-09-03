<template>
  <section class="monitor-alerts">
    <header>
      <div><h2>告警事件</h2><p>统一展示主机指标与 HTTP、TCP、Docker 服务的异常和恢复记录。</p></div>
      <n-button :loading="loading" @click="load">刷新</n-button>
    </header>
    <n-data-table striped :columns="columns" :data="records" :loading="loading" :pagination="{ pageSize: 15 }" />
  </section>
</template>

<script setup lang="ts">
import { h, onMounted, ref } from 'vue';
import { NTag } from 'naive-ui';
import { MonitorAPI, type MonitorAlertEvent, type MonitorServiceEvent } from '@/api/monitor/http';

type AlertRecord = {
  id: string;
  object_name: string;
  project_name?: string;
  message: string;
  severity: 'warning' | 'critical';
  status: 'active' | 'recovered';
  started_at: string;
  recovered_at?: string;
};

const records = ref<AlertRecord[]>([]);
const loading = ref(false);
const asList = <T,>(data: any): T[] => Array.isArray(data) ? data : data?.list || data?.results || data?.data || [];

const load = async () => {
  loading.value = true;
  try {
    const [hostData, serviceData] = await Promise.all([MonitorAPI.alerts(), MonitorAPI.serviceEvents()]);
    const hosts = asList<MonitorAlertEvent>(hostData).map((item) => ({
      id: `host-${item.id}`,
      object_name: item.target_name,
      project_name: item.project_name,
      message: item.message,
      severity: item.severity,
      status: item.status,
      started_at: item.started_at,
      recovered_at: item.recovered_at,
    }));
    const services: AlertRecord[] = [];
    const pending = new Map<number, AlertRecord>();
    asList<MonitorServiceEvent>(serviceData)
      .sort((a, b) => new Date(a.occurred_at).getTime() - new Date(b.occurred_at).getTime())
      .forEach((item) => {
        if (item.status === 'down') {
          const record: AlertRecord = {
            id: `service-${item.id}`,
            object_name: item.service_name,
            project_name: item.project_name,
            message: item.message || `${item.service_name}服务不可用`,
            severity: 'critical',
            status: 'active',
            started_at: item.occurred_at,
          };
          services.push(record);
          pending.set(item.service, record);
          return;
        }
        const active = pending.get(item.service);
        if (active) {
          active.status = 'recovered';
          active.recovered_at = item.occurred_at;
          pending.delete(item.service);
        }
      });
    records.value = [...hosts, ...services].sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime());
  } finally {
    loading.value = false;
  }
};

const time = (value?: string) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-';
const columns: any[] = [
  { title: '目标', key: 'object_name' },
  { title: '项目', key: 'project_name', render: (row: AlertRecord) => row.project_name || '平台级' },
  { title: '告警内容', key: 'message' },
  { title: '级别', key: 'severity', render: (row: AlertRecord) => h(NTag, { type: row.severity === 'critical' ? 'error' : 'warning' }, { default: () => row.severity === 'critical' ? '告警' : '预警' }) },
  { title: '状态', key: 'status', render: (row: AlertRecord) => h(NTag, { type: row.status === 'active' ? 'error' : 'success' }, { default: () => row.status === 'active' ? '告警中' : '已恢复' }) },
  { title: '开始时间', key: 'started_at', render: (row: AlertRecord) => time(row.started_at) },
  { title: '恢复时间', key: 'recovered_at', render: (row: AlertRecord) => time(row.recovered_at) },
];

onMounted(load);
</script>

<style scoped lang="less">
.monitor-alerts { padding: 24px 28px; }
.monitor-alerts header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 22px; }
.monitor-alerts h2 { margin: 0; color: #1e293b; }
.monitor-alerts p { margin: 8px 0 0; color: #7b8ba3; }
</style>
