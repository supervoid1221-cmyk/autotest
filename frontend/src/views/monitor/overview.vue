<template>
  <section class="monitor-overview">
    <header class="dashboard-header">
      <div><h2>监控台</h2><p>主机资源、业务服务与告警状态实时概览</p></div>
      <div class="header-actions">
        <n-select v-model:value="selectedProject" class="project-select" :options="projectOptions" placeholder="全部项目" @update:value="load" />
        <span class="updated-at"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v5l3 2"/></svg>{{ updatedLabel }}</span>
        <n-button type="primary" class="refresh-button" :loading="loading" @click="load"><template #icon><svg viewBox="0 0 24 24"><path d="M20 11a8 8 0 1 0-2.34 5.66"/><path d="M20 5v6h-6"/></svg></template>刷新数据</n-button>
      </div>
    </header>

    <div class="summary-grid">
      <article v-for="item in summaries" :key="item.label" class="summary-card">
        <span class="summary-icon" :class="item.tone">
          <svg v-if="item.icon === 'host'" viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="6" rx="2"/><rect x="4" y="14" width="16" height="6" rx="2"/><path d="M8 7h.01M8 17h.01"/></svg>
          <svg v-else-if="item.icon === 'service'" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.4 2.5 3.6 5.5 3.6 9s-1.2 6.5-3.6 9c-2.4-2.5-3.6-5.5-3.6-9S9.6 5.5 12 3Z"/></svg>
          <svg v-else-if="item.icon === 'alert'" viewBox="0 0 24 24"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/></svg>
          <svg v-else viewBox="0 0 24 24"><path d="M12 3 5 6v5c0 4.7 2.8 8.2 7 10 4.2-1.8 7-5.3 7-10V6l-7-3Z"/><path d="m9 12 2 2 4-4"/></svg>
        </span>
        <div class="summary-copy"><span>{{ item.label }}</span><strong :class="item.tone">{{ item.value }}</strong></div>
      </article>
    </div>

    <n-alert v-for="item in overview.errors" :key="item.target_id" type="warning" class="monitor-error" :show-icon="true">{{ item.target_name }}：{{ item.message }}</n-alert>

    <div v-if="primaryHost" class="overview-main-grid">
      <article class="panel host-panel">
        <header class="panel-header host-heading">
          <div><h3>{{ primaryHost.target.name }}</h3><p>{{ primaryHost.target.instance_label }} · {{ primaryHost.target.job || primaryHost.target.project_name || 'node' }}</p></div>
          <span class="online-state" :class="{ offline: !primaryHost.current.up }"><i />{{ primaryHost.current.up ? '在线' : '离线' }}</span>
        </header>
        <div class="host-content" @click="openDetail(primaryHost.target)">
          <div class="resource-rings">
            <div v-for="metric in hostMetrics" :key="metric.key" class="ring-row">
              <div class="metric-ring" :style="{ '--value': `${metric.raw || 0}%`, '--tone': metric.color }"><span /></div>
              <div><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong></div>
            </div>
          </div>
          <div class="trend-panel">
            <div class="trend-heading"><strong>24 小时资源使用率</strong><div class="chart-legend"><span v-for="metric in hostMetrics" :key="metric.key"><i :style="{ background: metric.color }" />{{ metric.shortLabel }}</span></div></div>
            <div v-if="hasSeries" class="trend-chart">
              <svg viewBox="0 0 720 230" preserveAspectRatio="none" role="img" aria-label="24小时资源使用率趋势图">
                <g class="grid-lines"><line v-for="line in chartGrid" :key="line.value" x1="48" :y1="line.y" x2="704" :y2="line.y" /><text v-for="line in chartGrid" :key="`label-${line.value}`" x="0" :y="line.y + 4">{{ line.value }}%</text></g>
                <polyline class="line cpu" :points="chartLines.cpu" /><polyline class="line memory" :points="chartLines.memory" /><polyline class="line disk" :points="chartLines.disk" />
              </svg>
              <div class="chart-times"><span v-for="time in chartTimes" :key="time">{{ time }}</span></div>
            </div>
            <n-empty v-else size="small" description="暂无24小时趋势数据" class="chart-empty" />
          </div>
        </div>
      </article>

      <article class="panel alert-panel">
        <header class="panel-header alert-heading"><h3>当前告警</h3><button type="button" @click="goAlerts">查看全部</button></header>
        <div class="alert-content">
          <div v-if="primaryActiveAlert" class="active-alert" :class="activeSeverity(primaryActiveAlert)">
            <div class="active-alert-title"><span class="alert-bell"><svg viewBox="0 0 24 24"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/></svg></span><strong>{{ alertTitle(primaryActiveAlert) }}</strong><span v-if="deliveryLabel" class="delivery-badge">{{ deliveryLabel }}</span></div>
            <div class="active-alert-values"><strong>{{ alertValue(primaryActiveAlert) }}</strong><span v-if="!('service_name' in primaryActiveAlert)">阈值&nbsp; {{ thresholdValue(primaryActiveAlert) }}</span><span>持续&nbsp; {{ activeDuration(activeStartedAt(primaryActiveAlert)) }}</span></div>
          </div>
          <div v-else class="alert-empty"><span><svg viewBox="0 0 24 24"><path d="m8 12 2.6 2.6L16.5 9"/><circle cx="12" cy="12" r="9"/></svg></span><div><strong>当前运行正常</strong><p>暂无活动告警</p></div></div>
          <div class="recovered-heading"><strong>已恢复事件</strong><span>（最近 {{ recoveredAlerts.length }} 条）</span></div>
          <div v-if="recoveredAlerts.length" class="recovered-list">
            <div v-for="event in recoveredAlerts" :key="recoveryKey(event)" class="recovered-item"><span class="recovered-check"><svg viewBox="0 0 24 24"><path d="m8 12 2.6 2.6L16.5 9"/><circle cx="12" cy="12" r="9"/></svg></span><strong>{{ alertTitle(event) }}</strong><b>已恢复</b><time>{{ recoveredAgo(event.recovered_at) }}</time></div>
          </div>
          <n-empty v-else size="small" description="暂无已恢复事件" class="recovered-empty" />
          <button class="all-alerts-link" type="button" @click="goAlerts">查看全部告警事件</button>
        </div>
      </article>
    </div>

    <section v-if="overview.services.length" class="service-section"><div class="section-title"><h3>服务监控</h3><span>HTTP / TCP 连通性与响应耗时</span></div><n-grid :cols="2" :x-gap="16" :y-gap="16"><n-gi v-for="item in overview.services" :key="item.service.id"><n-card class="service-card" :bordered="false"><template #header><div class="target-title"><div><strong>{{ item.service.name }}</strong><small>{{ item.service.monitor_type.toUpperCase() }} · {{ item.service.project_name || '平台级' }}</small></div><n-tag :type="item.up ? 'success' : 'error'">{{ item.up ? '在线' : '异常' }}</n-tag></div></template><div class="service-detail"><span>{{ item.service.address }}<template v-if="item.service.monitor_type === 'tcp'">:{{ item.service.port }}</template></span><b>{{ item.response_time_ms == null ? '-' : `${item.response_time_ms} ms` }}</b><n-tag v-if="item.status_code" size="small" :type="item.up ? 'success' : 'error'">HTTP {{ item.status_code }}</n-tag></div><template #footer><span :class="item.up ? 'target-footer' : 'service-error'">{{ item.up ? '检测正常' : item.message || '检测失败' }}</span></template></n-card></n-gi></n-grid></section>

    <n-empty v-if="!loading && !overview.targets.length && !overview.services.length && !overview.errors.length" description="暂无监控目标或服务，请先在「监控配置」中完成配置" class="empty" />
    <n-modal v-model:show="detailVisible" preset="card" title="服务器指标详情" class="platform-form-modal"><n-spin :show="detailLoading"><template v-if="detail"><div class="detail-name">{{ detail.target.name }} · {{ detail.target.instance_label }}</div><n-grid :cols="3" :x-gap="14"><n-gi v-for="metric in metricItems(detail.current)" :key="metric.label"><div class="detail-metric"><span>{{ metric.label }}</span><strong :class="metric.tone">{{ metric.value }}</strong></div></n-gi></n-grid><div class="series-list"><section v-for="key in ['cpu', 'memory', 'disk']" :key="key"><strong>{{ metricNames[key] }}趋势（近 1 小时）</strong><div class="series-points"><span v-for="point in (detail.series?.[key] || []).slice(-30)" :key="point.timestamp" :style="{ height: `${Math.max(3, Math.min(100, point.value))}%` }" /></div></section></div></template></n-spin></n-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useMessage } from 'naive-ui';
import { ProjectAPI } from '@/api/project/http';
import { useUserStore } from '@/store/modules/user';
import { MonitorAPI, type MonitorAlertEvent, type MonitorNotificationDelivery, type MonitorOverview, type MonitorServiceEvent, type MonitorServiceRecovery, type MonitorSnapshot, type MonitorTarget } from '@/api/monitor/http';

const router = useRouter();
const message = useMessage();
const projectApi = new ProjectAPI();
const userStore = useUserStore();
const loading = ref(false);
const detailLoading = ref(false);
const detailVisible = ref(false);
const detail = ref<(MonitorSnapshot & { target: MonitorTarget })>();
const hostDetail = ref<(MonitorSnapshot & { target: MonitorTarget })>();
const alerts = ref<MonitorAlertEvent[]>([]);
const deliveries = ref<MonitorNotificationDelivery[]>([]);
const projects = ref<any[]>([]);
const selectedProject = ref<number | null>(null);
const lastUpdated = ref<Date>();
const overview = ref<MonitorOverview>({ targets: [], services: [], service_alerts: [], service_recoveries: [], errors: [], summary: { total: 0, online: 0, services_total: 0, services_online: 0, alerts: 0 } });
const metricNames: Record<string, string> = { cpu: 'CPU 使用率', memory: '内存使用率', disk: '磁盘使用率' };
const chartColors: Record<string, string> = { cpu: '#18a36b', memory: '#f08b0b', disk: '#2574e8' };

const asList = <T,>(payload: unknown): T[] => { if (Array.isArray(payload)) return payload as T[]; const response = payload as { list?: T[]; results?: T[]; data?: T[] } | null; return response?.list || response?.results || response?.data || []; };
const percent = (value: number | null | undefined) => value == null ? '-' : `${value.toFixed(1)}%`;
const metricItems = (current: MonitorSnapshot['current']) => [{ label: 'CPU', value: percent(current.cpu), tone: current.cpu != null && current.cpu >= 90 ? 'danger' : '' }, { label: '内存', value: percent(current.memory), tone: current.memory != null && current.memory >= 95 ? 'danger' : '' }, { label: '磁盘最高', value: percent(current.disk), tone: current.disk != null && current.disk >= 90 ? 'danger' : '' }];
const primaryHost = computed(() => overview.value.targets[0]);
const currentMetrics = computed(() => hostDetail.value?.current || primaryHost.value?.current || { up: null, cpu: null, memory: null, disk: null });
const hostMetrics = computed(() => [{ key: 'cpu', label: 'CPU', shortLabel: 'CPU', raw: currentMetrics.value.cpu, value: percent(currentMetrics.value.cpu), color: chartColors.cpu }, { key: 'memory', label: '内存', shortLabel: '内存', raw: currentMetrics.value.memory, value: percent(currentMetrics.value.memory), color: chartColors.memory }, { key: 'disk', label: '磁盘', shortLabel: '磁盘', raw: currentMetrics.value.disk, value: percent(currentMetrics.value.disk), color: chartColors.disk }]);
const availability = computed(() => { const total = overview.value.summary.total + overview.value.summary.services_total; const online = overview.value.summary.online + overview.value.summary.services_online; return total ? `${((online / total) * 100).toFixed(2)}%` : '-'; });
const summaries = computed(() => [{ label: '主机健康', value: `${overview.value.summary.online} / ${overview.value.summary.total}`, tone: 'success', icon: 'host' }, { label: '服务在线', value: `${overview.value.summary.services_online} / ${overview.value.summary.services_total}`, tone: 'success', icon: 'service' }, { label: '活动告警', value: overview.value.summary.alerts, tone: overview.value.summary.alerts ? 'warning' : 'success', icon: 'alert' }, { label: '24h 可用性', value: availability.value, tone: 'primary', icon: 'availability' }]);
const projectOptions = computed(() => [{ label: '全部项目', value: null }, ...projects.value.map((item) => ({ label: item.name, value: Number(item.id) }))]);
const updatedLabel = computed(() => lastUpdated.value ? '刚刚更新' : '等待更新');
const targetIds = computed(() => new Set(overview.value.targets.map((item) => item.target.id)));
const visibleAlerts = computed(() => alerts.value.filter((item) => targetIds.value.has(item.target)));
const activeAlerts = computed(() => visibleAlerts.value.filter((item) => item.status === 'active'));
type DashboardAlert = MonitorAlertEvent | MonitorServiceEvent;
type DashboardRecovery = MonitorAlertEvent | MonitorServiceRecovery;
const primaryActiveAlert = computed<DashboardAlert | undefined>(() => activeAlerts.value[0] || overview.value.service_alerts[0]);
const recoveredAlerts = computed<DashboardRecovery[]>(() => [
  ...visibleAlerts.value.filter((item) => item.status === 'recovered'),
  ...(overview.value.service_recoveries || []),
].sort((left, right) => new Date(right.recovered_at || 0).getTime() - new Date(left.recovered_at || 0).getTime()).slice(0, 3));
const deliveryLabel = computed(() => { const current = primaryActiveAlert.value; if (!current) return ''; const delivery = deliveries.value.find((item) => item.event === 'alert' && item.status === 'sent' && ('target_name' in current ? item.target_name === current.target_name : item.service_name === current.service_name)); return delivery ? `${delivery.channel_name || '通知'} 已发送` : ''; });

const seriesFor = (key: string) => hostDetail.value?.series?.[key] || [];
const hasSeries = computed(() => ['cpu', 'memory', 'disk'].some((key) => seriesFor(key).length > 1));
const chartGrid = [100, 75, 50, 25, 0].map((value) => ({ value, y: 12 + ((100 - value) / 100) * 178 }));
const linePoints = (key: string) => { const series = seriesFor(key); if (!series.length) return ''; return series.map((point, index) => { const x = 48 + (index / Math.max(1, series.length - 1)) * 656; const y = 12 + ((100 - Math.max(0, Math.min(100, point.value))) / 100) * 178; return `${x.toFixed(1)},${y.toFixed(1)}`; }).join(' '); };
const chartLines = computed(() => ({ cpu: linePoints('cpu'), memory: linePoints('memory'), disk: linePoints('disk') }));
const chartTimes = computed(() => { const source = seriesFor('cpu').length ? seriesFor('cpu') : seriesFor('memory').length ? seriesFor('memory') : seriesFor('disk'); if (!source.length) return []; return [0, .25, .5, .75, 1].map((ratio) => { const point = source[Math.min(source.length - 1, Math.round((source.length - 1) * ratio))]; return new Date(point.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }); }); });
const alertTitle = (event: DashboardAlert) => 'service_name' in event ? `${event.service_name} 服务异常` : event.alert_key === 'cpu' ? 'CPU 使用率预警' : event.alert_key === 'memory' ? '内存使用率预警' : event.alert_key === 'disk' ? '磁盘使用率预警' : event.alert_key === 'host_down' ? '主机离线告警' : event.message;
const alertValue = (event: DashboardAlert) => 'service_name' in event ? '服务不可用' : event.metric_value == null ? '-' : `${Number(event.metric_value).toFixed(1)}%`;
const thresholdValue = (event: DashboardAlert) => 'service_name' in event ? '-' : event.threshold == null ? '-' : `${Number(event.threshold).toFixed(0)}%`;
const activeStartedAt = (event: DashboardAlert) => 'service_name' in event ? event.occurred_at : event.started_at;
const activeSeverity = (event: DashboardAlert) => 'service_name' in event ? 'critical' : event.severity;
const recoveryKey = (event: DashboardRecovery) => `${'service_name' in event ? 'service' : 'target'}-${event.id}`;
const activeDuration = (startedAt: string) => { const minutes = Math.max(1, Math.round((Date.now() - new Date(startedAt).getTime()) / 60000)); if (minutes < 60) return `${minutes} 分钟`; const hours = Math.floor(minutes / 60); return `${hours} 小时 ${minutes % 60} 分钟`; };
const recoveredAgo = (recoveredAt?: string) => { if (!recoveredAt) return '-'; const minutes = Math.max(1, Math.round((Date.now() - new Date(recoveredAt).getTime()) / 60000)); if (minutes < 60) return `${minutes} 分钟前`; if (minutes < 1440) return `${Math.floor(minutes / 60)} 小时前`; return `${Math.floor(minutes / 1440)} 天前`; };
const loadProjects = async () => { try { projects.value = asList(await projectApi.getDataList({ page: 1, pageSize: 1000 })); } catch { projects.value = []; } };
const loadHostSeries = async () => { if (!primaryHost.value?.target.id) { hostDetail.value = undefined; return; } try { hostDetail.value = await MonitorAPI.targetMetrics(primaryHost.value.target.id, 86400); } catch { hostDetail.value = { ...primaryHost.value }; } };
const load = async () => { loading.value = true; try { const deliveryRequest = (userStore.info as any)?.is_admin ? MonitorAPI.notificationDeliveries() : Promise.resolve([]); const [overviewResult, alertsResult, deliveriesResult] = await Promise.allSettled([MonitorAPI.overview(selectedProject.value), MonitorAPI.alerts(), deliveryRequest]); if (overviewResult.status === 'rejected') throw overviewResult.reason; overview.value = overviewResult.value; alerts.value = alertsResult.status === 'fulfilled' ? asList(alertsResult.value) : []; deliveries.value = deliveriesResult.status === 'fulfilled' ? asList(deliveriesResult.value) : []; await loadHostSeries(); lastUpdated.value = new Date(); } catch (error: any) { message.error(error?.message || '获取监控数据失败'); } finally { loading.value = false; } };
const openDetail = async (target: MonitorTarget) => { detailVisible.value = true; detailLoading.value = true; try { detail.value = await MonitorAPI.targetMetrics(target.id!); } catch (error: any) { message.error(error?.message || '获取指标详情失败'); } finally { detailLoading.value = false; } };
const goAlerts = () => router.push({ name: 'monitor_alerts' });
let timer: number | undefined;
onMounted(() => { void loadProjects(); void load(); timer = window.setInterval(load, 30000); });
onBeforeUnmount(() => timer && window.clearInterval(timer));
</script>

<style scoped lang="less">
.monitor-overview{padding:24px 28px 36px;background:#f4f7fb;min-height:100%}.dashboard-header{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:24px}.dashboard-header h2{margin:0;color:#18243a;font-size:30px;line-height:1.2;font-weight:700;letter-spacing:-1px}.dashboard-header p{margin:9px 0 0;color:#8290a5;font-size:14px}.header-actions{display:flex;align-items:center;gap:16px}.project-select{width:180px}.updated-at{display:flex;align-items:center;gap:8px;padding:0 18px;border-left:1px solid #dde5ef;color:#55657c;font-size:14px;white-space:nowrap}.updated-at svg,.refresh-button svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round;stroke-width:1.8}.refresh-button{height:40px;padding:0 20px;border-radius:8px}.summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-bottom:18px}.summary-card{display:flex;align-items:center;min-height:126px;padding:22px 28px;border:1px solid #dfe6ef;border-radius:12px;background:#fff}.summary-icon{display:grid;place-items:center;width:72px;height:72px;margin-right:22px;border-radius:50%;background:#eaf8f2;color:#18a36b}.summary-icon.warning{background:#fff5e7;color:#f08b0b}.summary-icon.primary{background:#edf4ff;color:#2574e8}.summary-icon svg{width:38px;height:38px;fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round;stroke-width:1.8}.summary-copy span{display:block;color:#2f3a4d;font-size:16px}.summary-copy strong{display:block;margin-top:9px;color:#18a36b;font-size:30px;line-height:1;font-weight:650;font-variant-numeric:tabular-nums}.summary-copy strong.warning{color:#f08b0b}.summary-copy strong.primary{color:#2574e8}.monitor-error{margin-bottom:14px}.overview-main-grid{display:grid;grid-template-columns:minmax(0,1.28fr) minmax(420px,1fr);gap:18px;margin-bottom:26px}.panel{overflow:hidden;border:1px solid #dfe6ef;border-radius:12px;background:#fff}.panel-header{display:flex;align-items:center;justify-content:space-between;min-height:78px;padding:0 24px;border-bottom:1px solid #e6ebf2}.panel-header h3{margin:0;color:#18243a;font-size:20px;font-weight:650}.host-heading p{margin:5px 0 0;color:#65748a;font-size:14px}.online-state{display:flex;align-items:center;gap:8px;color:#18a36b;font-size:14px;font-weight:600}.online-state i{width:8px;height:8px;border-radius:50%;background:currentColor}.online-state.offline{color:#e34d59}.host-content{display:grid;grid-template-columns:220px minmax(0,1fr);min-height:335px;cursor:pointer}.resource-rings{display:flex;flex-direction:column;justify-content:center;gap:20px;padding:22px;border-right:1px solid #e6ebf2}.ring-row{display:flex;align-items:center;gap:16px}.metric-ring{position:relative;width:58px;height:58px;flex:0 0 58px;border-radius:50%;background:conic-gradient(var(--tone) var(--value),#e7ebf0 0)}.metric-ring:after{position:absolute;inset:7px;border-radius:50%;background:#fff;content:""}.ring-row span{color:#344258;font-size:14px}.ring-row strong{display:block;margin-top:3px;color:#17233a;font-size:20px;font-weight:650;font-variant-numeric:tabular-nums}.trend-panel{min-width:0;padding:24px 24px 16px}.trend-heading{display:flex;align-items:center;justify-content:space-between;gap:20px}.trend-heading>strong{color:#273449;font-size:15px}.chart-legend{display:flex;align-items:center;gap:18px;color:#68778d;font-size:13px}.chart-legend span{display:flex;align-items:center;gap:6px}.chart-legend i{width:7px;height:7px;border-radius:50%}.trend-chart{height:248px;margin-top:18px}.trend-chart svg{display:block;width:100%;height:215px;overflow:visible}.grid-lines line{stroke:#e6ebf2;stroke-dasharray:5 5;stroke-width:1}.grid-lines text{fill:#8a97aa;font-size:12px}.line{fill:none;stroke-linecap:round;stroke-linejoin:round;stroke-width:2.5;vector-effect:non-scaling-stroke}.line.cpu{stroke:#18a36b}.line.memory{stroke:#f08b0b}.line.disk{stroke:#2574e8}.chart-times{display:flex;justify-content:space-between;padding-left:48px;color:#8290a5;font-size:12px}.chart-empty{margin-top:76px}.alert-heading button,.all-alerts-link{border:0;background:transparent;color:#2574e8;cursor:pointer;font-size:14px}.alert-content{padding:16px 20px 14px}.active-alert{padding:18px 20px;border:1px solid #f4c76f;border-radius:10px;background:#fffaf1}.active-alert.critical{border-color:#f1aeb4;background:#fff7f8}.active-alert-title{display:flex;align-items:center;gap:10px;color:#263349}.alert-bell{display:flex;color:#f08b0b}.alert-bell svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round;stroke-width:2}.active-alert-title strong{font-size:16px}.delivery-badge{margin-left:auto;padding:6px 10px;border:1px solid #f2d9a8;border-radius:7px;background:#fff8e9;color:#d97806;font-size:13px}.active-alert-values{display:flex;align-items:baseline;gap:32px;margin-top:14px;padding-left:30px;color:#4f5d72;font-size:14px}.active-alert-values strong{color:#f08b0b;font-size:25px;font-variant-numeric:tabular-nums}.alert-empty{display:flex;align-items:center;min-height:102px;padding:0 20px;border:1px solid #cdebdc;border-radius:10px;background:#f5fcf8}.alert-empty>span{display:flex;margin-right:14px;color:#18a36b}.alert-empty svg,.recovered-check svg{width:26px;height:26px;fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round;stroke-width:2}.alert-empty strong{color:#263349}.alert-empty p{margin:4px 0 0;color:#718098}.recovered-heading{display:flex;align-items:baseline;margin:18px 0 10px;color:#223047}.recovered-heading span{color:#8a97a9;font-size:13px}.recovered-list{overflow:hidden;border:1px solid #e2e8f0;border-radius:9px}.recovered-item{display:grid;grid-template-columns:24px minmax(0,1fr) 70px 90px;align-items:center;min-height:44px;padding:0 14px;border-bottom:1px solid #e7ecf2;gap:8px}.recovered-item:last-child{border-bottom:0}.recovered-check{display:flex;color:#18a36b}.recovered-check svg{width:20px;height:20px}.recovered-item strong{overflow:hidden;color:#344158;font-size:14px;font-weight:500;white-space:nowrap;text-overflow:ellipsis}.recovered-item b{color:#18a36b;font-size:13px;font-weight:500}.recovered-item time{color:#8290a5;font-size:13px;text-align:right}.recovered-empty{height:116px}.all-alerts-link{display:block;margin:12px auto 0}.target-title{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.target-title small{display:block;margin-top:5px;color:#8c99aa}.target-footer{color:#718098;font-size:12px}.service-section{margin-top:28px}.section-title{display:flex;align-items:baseline;gap:10px;margin-bottom:14px}.section-title h3{margin:0;color:#29394f;font-size:17px}.section-title span{color:#8a98aa;font-size:13px}.service-card{border:1px solid #e4eaf2;border-radius:14px;transition:.2s}.service-card:hover{border-color:#719fff;box-shadow:0 8px 24px rgba(57,102,180,.09)}.service-detail{display:flex;align-items:center;gap:14px;min-height:28px}.service-detail span{flex:1;overflow:hidden;color:#718098;white-space:nowrap;text-overflow:ellipsis}.service-detail b{color:#33455d}.service-error{color:#df4d56;font-size:12px}.empty{margin-top:80px}.detail-name{margin-bottom:18px;color:#56667d}.detail-metric{padding:16px;border-radius:10px;background:#f7f9fc}.detail-metric span{display:block;color:#8290a5;font-size:13px}.detail-metric strong{display:block;margin-top:7px;color:#27364d;font-size:22px}.success{color:#0f9c67!important}.danger{color:#e5484d!important}.series-list{display:grid;gap:18px;margin-top:22px}.series-list section{height:128px;padding:14px;border:1px solid #e6ebf2;border-radius:10px}.series-list strong{color:#46556d;font-size:13px}.series-points{display:flex;align-items:end;height:76px;gap:3px;margin-top:8px}.series-points span{flex:1;min-width:2px;border-radius:2px 2px 0 0;background:#5b6af0}@media(max-width:1280px){.summary-card{padding:20px}.summary-icon{width:60px;height:60px;margin-right:16px}.summary-icon svg{width:30px;height:30px}.overview-main-grid{grid-template-columns:1fr}.alert-panel{min-height:360px}}@media(max-width:900px){.monitor-overview{padding:18px}.dashboard-header{flex-direction:column}.header-actions{width:100%;flex-wrap:wrap}.summary-grid{grid-template-columns:repeat(2,1fr)}.host-content{grid-template-columns:1fr}.resource-rings{display:grid;grid-template-columns:repeat(3,1fr);border-right:0;border-bottom:1px solid #e6ebf2}.project-select{flex:1}.overview-main-grid{display:block}.alert-panel{margin-top:16px}:deep(.service-section .n-grid){grid-template-columns:1fr!important}}@media(max-width:560px){.summary-grid{grid-template-columns:1fr}.resource-rings{grid-template-columns:1fr}.header-actions{align-items:stretch}.updated-at{border-left:0;padding:0}.refresh-button{width:100%}}
</style>
