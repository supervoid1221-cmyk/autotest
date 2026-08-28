<template>
  <main class="incident-preview-page">
    <header class="preview-header">
      <div class="brand-mark">AT</div>
      <div class="header-copy">
        <span>自动化测试平台</span>
        <strong>服务监控中心</strong>
      </div>
      <nav class="preview-nav" aria-label="监控预览导航">
        <span>监控台</span>
        <span>服务器</span>
        <span class="active">告警中心</span>
        <span>通知投递</span>
      </nav>
      <span class="preview-label">原型预览</span>
    </header>

    <section class="page-shell">
      <div class="breadcrumb">监控台 <i>/</i> 告警中心 <i>/</i> 告警详情</div>

      <div class="title-row">
        <div class="title-main">
          <span class="severity-mark"><PhWarningCircle weight="fill" /></span>
          <div>
            <div class="eyebrow">INCIDENT · {{ incidentId }}</div>
            <h1>支付服务健康检查失败</h1>
            <p>生产环境的支付服务连续 3 次探测失败，系统已触发高级告警。</p>
          </div>
        </div>
        <div class="title-actions">
          <button class="secondary-action" type="button" @click="silenced = !silenced">
            <PhBellSlash />{{ silenced ? '取消静默' : '静默 30 分钟' }}
          </button>
          <button
            class="primary-action"
            type="button"
            :disabled="acknowledged"
            @click="acknowledged = true"
          >
            <PhCheckCircle />{{ acknowledged ? '已确认告警' : '确认告警' }}
          </button>
        </div>
      </div>

      <section class="status-strip">
        <div class="status-cell critical">
          <span>当前状态</span>
          <strong><i></i>告警中</strong>
        </div>
        <div class="status-cell">
          <span>首次触发</span>
          <strong>2026-08-23 18:20:14</strong>
        </div>
        <div class="status-cell">
          <span>持续时间</span>
          <strong class="tabular">18 分 42 秒</strong>
        </div>
        <div class="status-cell">
          <span>最近检查</span>
          <strong>12 秒前</strong>
        </div>
        <div class="status-cell">
          <span>通知状态</span>
          <strong class="success-text">已投递 2 / 2</strong>
        </div>
      </section>

      <div class="content-grid">
        <div class="main-column">
          <section class="panel service-panel">
            <div class="panel-heading">
              <div>
                <span class="section-kicker">服务对象</span>
                <h2>prod-payment-01 · payment-api</h2>
              </div>
              <span class="environment-chip">PROD</span>
            </div>
            <div class="service-grid">
              <dl><dt>服务器地址</dt><dd>10.24.18.32</dd></dl>
              <dl><dt>服务类型</dt><dd>systemd · payment-api.service</dd></dl>
              <dl><dt>所属项目</dt><dd>支付服务</dd></dl>
              <dl><dt>检查策略</dt><dd>HTTP + 进程存活</dd></dl>
            </div>
            <div class="endpoint-row">
              <span class="method">GET</span>
              <code>https://api.example.com/health</code>
              <span>每 30 秒检查</span>
            </div>
          </section>

          <section class="panel metric-panel">
            <div class="panel-heading compact">
              <div><span class="section-kicker">异常指标</span><h2>响应时间与可用性</h2></div>
              <div class="range-tabs"
                ><button class="active">1 小时</button><button>6 小时</button
                ><button>24 小时</button></div
              >
            </div>
            <div class="metric-summary">
              <div
                ><span>当前响应</span><strong class="danger-text tabular">5,024 ms</strong
                ><small>阈值 2,000 ms</small></div
              >
              <div
                ><span>近 1 小时可用率</span><strong class="tabular">96.72%</strong
                ><small>目标 ≥ 99.90%</small></div
              >
              <div
                ><span>连续失败</span><strong class="tabular">3 次</strong
                ><small>触发阈值 3 次</small></div
              >
            </div>
            <div class="chart-wrap" aria-label="响应时间趋势示意图">
              <div class="chart-grid-line" v-for="line in 4" :key="line"></div>
              <div class="threshold"><span>阈值 2,000 ms</span></div>
              <svg class="trend-chart" viewBox="0 0 900 230" preserveAspectRatio="none" role="img">
                <defs>
                  <linearGradient id="incidentArea" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stop-color="#ef655f" stop-opacity=".24" />
                    <stop offset="1" stop-color="#ef655f" stop-opacity="0" />
                  </linearGradient>
                </defs>
                <path
                  class="area"
                  d="M0,184 C70,176 92,181 138,171 C190,160 211,172 260,154 C312,136 340,160 392,146 C450,131 473,142 520,115 C564,90 604,130 651,82 C695,37 731,67 770,45 C808,24 852,44 900,19 L900,230 L0,230 Z"
                />
                <path
                  class="line"
                  d="M0,184 C70,176 92,181 138,171 C190,160 211,172 260,154 C312,136 340,160 392,146 C450,131 473,142 520,115 C564,90 604,130 651,82 C695,37 731,67 770,45 C808,24 852,44 900,19"
                />
                <circle cx="900" cy="19" r="7" />
              </svg>
              <div class="chart-axis"
                ><span>17:20</span><span>17:35</span><span>17:50</span><span>18:05</span
                ><span>18:20</span></div
              >
            </div>
          </section>

          <section class="panel evidence-panel">
            <div class="panel-heading compact">
              <div><span class="section-kicker">检查证据</span><h2>最近一次探测结果</h2></div>
              <span class="result-badge">FAILED</span>
            </div>
            <div class="evidence-meta"
              ><span>HTTP 状态码 <b>503</b></span
              ><span>DNS <b>12 ms</b></span
              ><span>连接 <b>84 ms</b></span
              ><span>总耗时 <b>5,024 ms</b></span></div
            >
            <pre><code>{
  "status": "unhealthy",
  "message": "upstream database connection timeout",
  "service": "payment-api",
  "trace_id": "7dc9e1a0c12f4e58"
}</code></pre>
          </section>
        </div>

        <aside class="side-column">
          <section class="panel timeline-panel">
            <div class="panel-heading compact"
              ><div><span class="section-kicker">事件时间线</span><h2>处理进展</h2></div></div
            >
            <ol class="timeline">
              <li class="danger"
                ><i></i><time>18:20:14</time><strong>告警触发</strong
                ><p>连续 3 次健康检查失败。</p></li
              >
              <li
                ><i></i><time>18:20:15</time><strong>创建事件</strong
                ><p>事件编号 INC-98231。</p></li
              >
              <li class="success"
                ><i></i><time>18:20:17</time><strong>通知投递完成</strong
                ><p>飞书与企业微信均已送达。</p></li
              >
              <li :class="{ success: acknowledged }"
                ><i></i><time>{{ acknowledged ? '刚刚' : '待处理' }}</time
                ><strong>{{ acknowledged ? '告警已确认' : '等待人工确认' }}</strong
                ><p>{{
                  acknowledged ? '由当前用户确认并开始处理。' : '确认后将记录处理人和时间。'
                }}</p></li
              >
            </ol>
          </section>

          <section class="panel delivery-panel">
            <div class="panel-heading compact"
              ><div><span class="section-kicker">通知投递</span><h2>最近投递记录</h2></div
              ><button>查看全部</button></div
            >
            <div class="delivery-item"
              ><span class="channel-icon feishu">飞</span
              ><div><strong>飞书 · 运维告警群</strong><small>18:20:16 · 342 ms</small></div
              ><em>成功</em></div
            >
            <div class="delivery-item"
              ><span class="channel-icon wecom">企</span
              ><div><strong>企业微信 · 生产值班群</strong><small>18:20:17 · 518 ms</small></div
              ><em>成功</em></div
            >
          </section>

          <section class="panel owner-panel">
            <div class="panel-heading compact"
              ><div><span class="section-kicker">责任信息</span><h2>处理与升级</h2></div></div
            >
            <dl
              ><dt>负责人</dt><dd><span class="avatar">陈</span>陈嘉明</dd></dl
            >
            <dl><dt>值班组</dt><dd>支付平台 SRE</dd></dl>
            <dl><dt>升级策略</dt><dd>10 分钟未确认 → 电话通知</dd></dl>
          </section>
        </aside>
      </div>
    </section>
  </main>
</template>

<script lang="ts" setup>
  import { computed, ref } from 'vue';
  import { useRoute } from 'vue-router';
  import { PhBellSlash, PhCheckCircle, PhWarningCircle } from '@phosphor-icons/vue';

  const route = useRoute();
  const incidentId = computed(() => String(route.params.id || '98231'));
  const acknowledged = ref(false);
  const silenced = ref(false);
</script>

<style scoped>
  .incident-preview-page {
    min-height: 100dvh;
    color: #172033;
    background: radial-gradient(circle at 8% 0%, rgba(72, 99, 238, 0.08), transparent 28rem),
      #f5f7fb;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei',
      sans-serif;
  }
  .preview-header {
    height: 66px;
    padding: 0 34px;
    display: flex;
    align-items: center;
    gap: 12px;
    background: rgba(255, 255, 255, 0.96);
    border-bottom: 1px solid #e7ebf2;
  }
  .brand-mark {
    width: 38px;
    height: 38px;
    display: grid;
    place-items: center;
    border-radius: 11px;
    color: #fff;
    background: #4f63eb;
    font: 800 13px/1 ui-monospace, monospace;
    box-shadow: 0 8px 22px rgba(79, 99, 235, 0.2);
  }
  .header-copy {
    display: flex;
    flex-direction: column;
    line-height: 1.25;
    min-width: 160px;
  }
  .header-copy span {
    color: #8b96a9;
    font-size: 11px;
  }
  .header-copy strong {
    font-size: 15px;
  }
  .preview-nav {
    height: 100%;
    margin-left: 34px;
    display: flex;
    align-items: center;
    gap: 32px;
    color: #6f7c91;
    font-size: 14px;
  }
  .preview-nav span {
    height: 100%;
    display: flex;
    align-items: center;
    position: relative;
  }
  .preview-nav .active {
    color: #4056df;
    font-weight: 650;
  }
  .preview-nav .active::after {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 2px;
    background: #4f63eb;
  }
  .preview-label {
    margin-left: auto;
    padding: 5px 9px;
    color: #68758b;
    background: #f1f3f8;
    border: 1px solid #e1e6ef;
    border-radius: 6px;
    font-size: 12px;
  }
  .page-shell {
    width: min(1460px, calc(100% - 48px));
    margin: 0 auto;
    padding: 25px 0 44px;
  }
  .breadcrumb {
    color: #8c98aa;
    font-size: 13px;
    margin-bottom: 22px;
  }
  .breadcrumb i {
    margin: 0 9px;
    color: #c2c9d4;
    font-style: normal;
  }
  .title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 30px;
    margin-bottom: 25px;
  }
  .title-main {
    display: flex;
    align-items: flex-start;
    gap: 15px;
  }
  .severity-mark {
    width: 48px;
    height: 48px;
    display: grid;
    place-items: center;
    flex: 0 0 auto;
    border-radius: 14px;
    color: #db443f;
    background: #fff0ef;
    font-size: 28px;
  }
  .eyebrow {
    margin-bottom: 4px;
    color: #e0524d;
    font: 700 11px/1.4 ui-monospace, monospace;
    letter-spacing: 0.08em;
  }
  h1 {
    margin: 0;
    font-size: 30px;
    line-height: 1.2;
    letter-spacing: -0.025em;
  }
  .title-main p {
    margin: 8px 0 0;
    color: #758196;
    font-size: 14px;
  }
  .title-actions {
    display: flex;
    gap: 10px;
  }
  .title-actions button {
    min-height: 40px;
    padding: 0 15px;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    border-radius: 8px;
    font-weight: 650;
    cursor: pointer;
    transition: 0.2s ease;
  }
  .title-actions button svg {
    font-size: 18px;
  }
  .secondary-action {
    color: #435067;
    background: #fff;
    border: 1px solid #d9dee8;
  }
  .primary-action {
    color: #fff;
    background: #4f63eb;
    border: 1px solid #4f63eb;
  }
  .title-actions button:hover {
    transform: translateY(-1px);
  }
  .title-actions button:disabled {
    cursor: default;
    opacity: 0.62;
    transform: none;
  }
  .status-strip {
    display: grid;
    grid-template-columns: 1.05fr repeat(4, 1fr);
    margin-bottom: 18px;
    overflow: hidden;
    background: #fff;
    border: 1px solid #e0e5ee;
    border-radius: 12px;
  }
  .status-cell {
    min-height: 82px;
    padding: 18px 22px;
    display: flex;
    flex-direction: column;
    gap: 7px;
    border-left: 1px solid #edf0f5;
  }
  .status-cell:first-child {
    border-left: 0;
  }
  .status-cell > span {
    color: #8a95a7;
    font-size: 12px;
  }
  .status-cell strong {
    font-size: 15px;
    font-weight: 650;
  }
  .status-cell.critical strong {
    color: #d84540;
  }
  .status-cell.critical i {
    width: 8px;
    height: 8px;
    display: inline-block;
    margin-right: 8px;
    border-radius: 50%;
    background: #e24e48;
    box-shadow: 0 0 0 5px #fff0ef;
  }
  .tabular {
    font-variant-numeric: tabular-nums;
  }
  .success-text {
    color: #1b9564;
  }
  .content-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.75fr) minmax(330px, 0.75fr);
    gap: 18px;
  }
  .main-column,
  .side-column {
    display: flex;
    flex-direction: column;
    gap: 18px;
    min-width: 0;
  }
  .panel {
    background: #fff;
    border: 1px solid #e0e5ee;
    border-radius: 12px;
    overflow: hidden;
  }
  .panel-heading {
    min-height: 77px;
    padding: 17px 22px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    border-bottom: 1px solid #edf0f5;
  }
  .panel-heading.compact {
    min-height: 66px;
  }
  .section-kicker {
    display: block;
    margin-bottom: 4px;
    color: #8b96a8;
    font-size: 11px;
  }
  .panel-heading h2 {
    margin: 0;
    font-size: 17px;
    line-height: 1.35;
    letter-spacing: -0.01em;
  }
  .environment-chip,
  .result-badge {
    padding: 5px 8px;
    border-radius: 5px;
    font: 700 11px/1 ui-monospace, monospace;
    letter-spacing: 0.06em;
  }
  .environment-chip {
    color: #4f63eb;
    background: #eef0ff;
  }
  .result-badge {
    color: #d84540;
    background: #fff0ef;
  }
  .service-grid {
    padding: 20px 22px;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 22px;
  }
  dl {
    margin: 0;
  }
  dt {
    margin-bottom: 7px;
    color: #929caf;
    font-size: 12px;
  }
  dd {
    margin: 0;
    color: #283449;
    font-size: 14px;
    font-weight: 600;
  }
  .endpoint-row {
    margin: 0 22px 21px;
    padding: 12px 14px;
    display: flex;
    align-items: center;
    gap: 12px;
    color: #778398;
    background: #f8f9fc;
    border: 1px solid #e8ebf2;
    border-radius: 8px;
    font-size: 12px;
  }
  .endpoint-row .method {
    padding: 4px 7px;
    color: #2674d9;
    background: #eaf3ff;
    border-radius: 4px;
    font: 700 11px/1 ui-monospace, monospace;
  }
  .endpoint-row code {
    min-width: 0;
    overflow: hidden;
    color: #3e4a5f;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .endpoint-row > span:last-child {
    margin-left: auto;
  }
  .range-tabs {
    padding: 3px;
    display: flex;
    background: #f2f4f8;
    border-radius: 7px;
  }
  .range-tabs button {
    padding: 6px 9px;
    color: #8490a3;
    background: transparent;
    border: 0;
    border-radius: 5px;
    font-size: 11px;
    cursor: pointer;
  }
  .range-tabs button.active {
    color: #34425a;
    background: #fff;
    box-shadow: 0 1px 3px rgba(42, 56, 83, 0.1);
  }
  .metric-summary {
    padding: 18px 22px 8px;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
  }
  .metric-summary > div {
    padding: 0 16px;
    display: flex;
    flex-direction: column;
    gap: 5px;
    border-left: 1px solid #edf0f5;
  }
  .metric-summary > div:first-child {
    padding-left: 0;
    border-left: 0;
  }
  .metric-summary span,
  .metric-summary small {
    color: #8a95a7;
    font-size: 11px;
  }
  .metric-summary strong {
    font-size: 23px;
    letter-spacing: -0.03em;
  }
  .danger-text {
    color: #dc4742;
  }
  .chart-wrap {
    height: 260px;
    margin: 8px 22px 22px;
    position: relative;
    overflow: hidden;
    background: linear-gradient(180deg, #fbfcfe, #fff);
    border: 1px solid #edf0f5;
    border-radius: 8px;
  }
  .chart-grid-line {
    position: relative;
    height: 20%;
    border-bottom: 1px dashed #e5e9f0;
  }
  .threshold {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 34%;
    border-top: 1px dashed #e2a8a5;
  }
  .threshold span {
    position: absolute;
    right: 8px;
    top: -18px;
    color: #c86b67;
    font-size: 10px;
  }
  .trend-chart {
    position: absolute;
    inset: 18px 14px 28px;
    width: calc(100% - 28px);
    height: calc(100% - 46px);
    overflow: visible;
  }
  .trend-chart .area {
    fill: url(#incidentArea);
  }
  .trend-chart .line {
    fill: none;
    stroke: #e45550;
    stroke-width: 3;
    vector-effect: non-scaling-stroke;
  }
  .trend-chart circle {
    fill: #fff;
    stroke: #e45550;
    stroke-width: 4;
    vector-effect: non-scaling-stroke;
  }
  .chart-axis {
    position: absolute;
    left: 14px;
    right: 14px;
    bottom: 7px;
    display: flex;
    justify-content: space-between;
    color: #9ba5b4;
    font-size: 10px;
  }
  .evidence-meta {
    padding: 16px 22px;
    display: flex;
    gap: 28px;
    color: #8792a5;
    font-size: 12px;
  }
  .evidence-meta b {
    margin-left: 5px;
    color: #354158;
  }
  pre {
    margin: 0 22px 22px;
    padding: 16px 18px;
    overflow: auto;
    color: #dce5f5;
    background: #202836;
    border-radius: 8px;
    font: 12px/1.7 ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .timeline {
    margin: 0;
    padding: 19px 22px 6px;
    list-style: none;
  }
  .timeline li {
    min-height: 83px;
    padding: 0 0 18px 27px;
    position: relative;
    border-left: 1px solid #e2e7ee;
  }
  .timeline li:last-child {
    border-left-color: transparent;
  }
  .timeline li > i {
    width: 11px;
    height: 11px;
    position: absolute;
    left: -6px;
    top: 2px;
    border: 3px solid #fff;
    border-radius: 50%;
    background: #8190a7;
    box-shadow: 0 0 0 1px #bdc6d3;
  }
  .timeline li.danger > i {
    background: #df4d48;
    box-shadow: 0 0 0 1px #df4d48;
  }
  .timeline li.success > i {
    background: #25a16f;
    box-shadow: 0 0 0 1px #25a16f;
  }
  .timeline time {
    display: block;
    margin-bottom: 4px;
    color: #9aa4b3;
    font: 11px/1.2 ui-monospace, monospace;
  }
  .timeline strong {
    font-size: 13px;
  }
  .timeline p {
    margin: 5px 0 0;
    color: #7e8a9e;
    font-size: 12px;
    line-height: 1.5;
  }
  .delivery-panel .panel-heading button {
    color: #4f63eb;
    background: none;
    border: 0;
    font-size: 12px;
    cursor: pointer;
  }
  .delivery-item {
    padding: 15px 22px;
    display: grid;
    grid-template-columns: 34px minmax(0, 1fr) auto;
    align-items: center;
    gap: 11px;
    border-top: 1px solid #f0f2f6;
  }
  .delivery-item:first-of-type {
    border-top: 0;
  }
  .channel-icon {
    width: 32px;
    height: 32px;
    display: grid;
    place-items: center;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 800;
  }
  .channel-icon.feishu {
    color: #286de0;
    background: #eaf2ff;
  }
  .channel-icon.wecom {
    color: #188c63;
    background: #e8f7f1;
  }
  .delivery-item div {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }
  .delivery-item strong {
    overflow: hidden;
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .delivery-item small {
    color: #9aa4b3;
    font-size: 10px;
  }
  .delivery-item em {
    color: #1e9869;
    font-size: 11px;
    font-style: normal;
  }
  .owner-panel {
    padding-bottom: 8px;
  }
  .owner-panel dl {
    padding: 11px 22px;
    display: grid;
    grid-template-columns: 72px 1fr;
    align-items: center;
  }
  .owner-panel dt {
    margin: 0;
  }
  .owner-panel dd {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
  }
  .avatar {
    width: 24px;
    height: 24px;
    display: grid;
    place-items: center;
    border-radius: 7px;
    color: #fff;
    background: #4f63eb;
    font-size: 10px;
  }
  @media (max-width: 1050px) {
    .preview-nav {
      display: none;
    }
    .content-grid {
      grid-template-columns: 1fr;
    }
    .side-column {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .timeline-panel {
      grid-row: span 2;
    }
  }
  @media (max-width: 760px) {
    .preview-header {
      padding: 0 18px;
    }
    .page-shell {
      width: min(100% - 28px, 1460px);
      padding-top: 18px;
    }
    .title-row {
      align-items: flex-start;
      flex-direction: column;
    }
    .title-actions {
      width: 100%;
    }
    .title-actions button {
      flex: 1;
      justify-content: center;
    }
    .status-strip {
      grid-template-columns: repeat(2, 1fr);
    }
    .status-cell:nth-child(odd) {
      border-left: 0;
    }
    .service-grid,
    .metric-summary {
      grid-template-columns: repeat(2, 1fr);
    }
    .side-column {
      display: flex;
    }
  }
</style>
