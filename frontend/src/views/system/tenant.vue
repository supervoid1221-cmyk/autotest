<template>
  <section class="tenant-page">
    <header class="page-header">
      <div><p class="eyebrow">系统管理</p><h2>租户管理</h2><p class="description">维护租户空间、成员和租户内角色，并切换当前数据范围。</p></div>
      <div class="header-actions"><n-button :loading="tenantStore.loading" @click="reload">刷新</n-button><n-button v-if="isPlatformAdmin" type="primary" @click="openCreate">新增租户</n-button></div>
    </header>

    <div class="summary-grid">
      <article class="summary-card"><span>可访问租户</span><strong>{{ tenantStore.tenants.length }}</strong><small>根据当前账号成员关系统计</small></article>
      <article class="summary-card current-summary"><span>当前租户</span><strong>{{ tenantStore.currentTenant?.name || '未选择' }}</strong><small>{{ tenantStore.currentTenant?.slug || '请选择租户' }}</small></article>
      <article class="summary-card"><span>我的角色</span><strong>{{ tenantStore.currentTenant?.role_name || '-' }}</strong><small>权限以服务端成员关系为准</small></article>
    </div>

    <div class="tenant-panel">
      <div class="panel-heading"><div><h3>租户列表</h3><p>切换后，项目和用户数据将按新租户重新加载。</p></div><span class="security-note">租户隔离已启用</span></div>
      <n-spin :show="tenantStore.loading">
        <div v-if="tenantStore.tenants.length" class="tenant-list">
          <article v-for="tenant in tenantStore.tenants" :key="tenant.id" class="tenant-item" :class="{ active: tenant.id === tenantStore.currentTenantId, 'platform-view': isPlatformAdmin }">
            <div class="tenant-mark">{{ tenant.name.slice(0, 1).toUpperCase() }}</div>
            <div class="tenant-info"><div class="tenant-title"><strong>{{ tenant.name }}</strong><span v-if="tenant.id === tenantStore.currentTenantId" class="current-tag">当前</span><span class="status-tag" :class="tenant.status">{{ tenant.status === 'active' ? '正常' : '已停用' }}</span></div><span class="tenant-code">{{ tenant.slug }}</span></div>
            <dl class="tenant-meta"><div v-if="!isPlatformAdmin"><dt>我的角色</dt><dd>{{ tenant.role_name || '-' }}</dd></div><div><dt>成员 / 项目</dt><dd>{{ tenant.member_count }} / {{ tenant.project_count || 0 }}</dd></div><div><dt>普通 / 性能并发</dt><dd>{{ tenant.max_regular_concurrent_executions }} / {{ tenant.max_performance_concurrent_executions }}</dd></div><div><dt>存储</dt><dd>{{ formatBytes(tenant.storage_used_bytes) }} / {{ formatBytes(tenant.storage_quota_bytes) }}</dd></div></dl>
            <div class="row-actions">
              <n-button v-if="canManage(tenant)" text @click="openMembers(tenant)">成员</n-button><n-button v-if="canManage(tenant)" text @click="openEdit(tenant)">编辑</n-button><n-button v-if="isPlatformAdmin && tenant.slug !== 'default'" text type="error" @click="removeTenant(tenant)">删除</n-button>
              <n-button :type="tenant.id === tenantStore.currentTenantId ? 'default' : 'primary'" size="small" :disabled="tenant.id === tenantStore.currentTenantId || tenant.status !== 'active'" @click="selectTenant(tenant.id)">{{ tenant.id === tenantStore.currentTenantId ? '正在使用' : '切换' }}</n-button>
            </div>
          </article>
        </div><n-empty v-else class="empty-state" description="当前账号没有可访问的租户" />
      </n-spin>
    </div>

    <n-modal v-model:show="showTenantModal" preset="card" class="tenant-modal" :title="editingTenant ? '编辑租户' : '新增租户'" :bordered="false">
      <n-form ref="tenantFormRef" :model="tenantForm" :rules="tenantRules" label-placement="top">
        <n-form-item label="租户名称" path="name"><n-input v-model:value="tenantForm.name" maxlength="64" placeholder="例如：质量保障中心" /></n-form-item>
        <n-form-item label="租户编码" path="slug"><n-input v-model:value="tenantForm.slug" :disabled="editingTenant?.slug === 'default'" maxlength="64" placeholder="例如：qa-center" /></n-form-item>
        <n-form-item label="状态" path="status"><n-radio-group v-model:value="tenantForm.status" :disabled="editingTenant?.slug === 'default'"><n-radio value="active">正常</n-radio><n-radio value="suspended">停用</n-radio></n-radio-group></n-form-item>
        <template v-if="isPlatformAdmin">
          <n-form-item label="普通任务最大并发数" path="maxRegularConcurrentExecutions"><n-input-number v-model:value="tenantForm.maxRegularConcurrentExecutions" :min="1" :max="999" /></n-form-item>
          <n-form-item label="性能任务最大并发数" path="maxPerformanceConcurrentExecutions"><n-input-number v-model:value="tenantForm.maxPerformanceConcurrentExecutions" :min="1" :max="32" /></n-form-item>
          <n-form-item label="存储配额（GB）" path="storageQuotaGb"><n-input-number v-model:value="tenantForm.storageQuotaGb" :min="1" :max="1048576" /></n-form-item>
        </template>
      </n-form>
      <template #footer><div class="modal-actions"><n-button @click="showTenantModal=false">取消</n-button><n-button type="primary" :loading="savingTenant" @click="saveTenant">保存</n-button></div></template>
    </n-modal>

    <n-drawer v-model:show="showMembers" :width="640" placement="right"><n-drawer-content :title="`${managedTenant?.name || ''} · 成员管理`" closable>
      <div class="add-member"><n-select v-model:value="newMember.user" filterable remote clearable :loading="loadingCandidates" :options="userOptions" placeholder="输入用户名检索并选择" @search="searchCandidates" /><n-select v-model:value="newMember.role" :options="roleOptions" /><n-button type="primary" :loading="addingMember" @click="addMember">添加</n-button></div>
      <n-spin :show="loadingMembers"><div v-if="members.length" class="member-list">
        <div v-for="member in members" :key="member.id" class="member-item"><div class="member-avatar">{{ member.username.slice(0,1).toUpperCase() }}</div><div class="member-name"><strong>{{ member.username }}</strong><small>{{ memberStatusText(member) }}{{ isSelfMember(member) ? ' · 当前账号' : '' }}</small></div><n-select :value="member.role" :options="roleOptionsFor(member)" size="small" @update:value="value => updateMember(member, { role: value })" /><n-switch :value="member.status === 'active'" :disabled="cannotToggleStatus(member)" size="small" @update:value="value => updateMember(member, { status: value ? 'active' : 'disabled' })" /><n-button text type="error" :disabled="removingMember || cannotRemove(member)" @click="removeMember(member)">删除</n-button></div>
      </div><n-empty v-else description="暂无租户成员" /></n-spin>
    </n-drawer-content></n-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useDialog, useMessage, type FormInst, type FormRules } from 'naive-ui';
import { TenantAPI, type TenantInfo, type TenantMember, type TenantUserCandidate } from '@/api/account/http';
import { useTenantStore } from '@/store/modules/tenant';
import { useUserStore } from '@/store/modules/user';
import { TABS_ROUTES } from '@/store/mutation-types';
import { storage } from '@/utils/Storage';

const tenantStore=useTenantStore(); const userStore=useUserStore(); const message=useMessage(); const dialog=useDialog();
const isPlatformAdmin=computed(()=>Boolean((userStore.info as any)?.is_admin));
const showTenantModal=ref(false); const savingTenant=ref(false); const editingTenant=ref<TenantInfo|null>(null); const tenantFormRef=ref<FormInst|null>(null);
const tenantForm=reactive({name:'',slug:'',status:'active' as 'active'|'suspended',maxRegularConcurrentExecutions:2,maxPerformanceConcurrentExecutions:1,storageQuotaGb:10});
const tenantRules:FormRules={name:{required:true,message:'请输入租户名称',trigger:['input','blur']},slug:[{required:true,message:'请输入租户编码',trigger:['input','blur']},{pattern:/^[a-z0-9]+(?:-[a-z0-9]+)*$/,message:'只能使用小写字母、数字和中划线',trigger:['input','blur']}]};
const showMembers=ref(false); const managedTenant=ref<TenantInfo|null>(null); const members=ref<TenantMember[]>([]); const loadingMembers=ref(false); const addingMember=ref(false); const removingMember=ref(false); const loadingCandidates=ref(false); const userOptions=ref<Array<{label:string;value:number;disabled:boolean}>>([]); const newMember=reactive<{user:number|null;role:TenantMember['role']}>({user:null,role:'member'}); let candidateRequest=0;
const roleOptions=[{label:'租户所有者',value:'owner'},{label:'租户管理员',value:'admin'},{label:'成员',value:'member'},{label:'只读成员',value:'viewer'}];
function canManage(tenant:TenantInfo){return isPlatformAdmin.value||['owner','admin','platform_admin'].includes(tenant.role)}
/* 与后端 account/views.py 的 member_detail 规则保持一致，避免点了必然失败的按钮：
   ① 当前操作账号不能被移除、不能被停用；② 租户必须保留至少一名正常状态的所有者或管理员
   （成员里只有一名 owner/admin 时，该成员不能移除/停用，也不能降级为普通成员）。
   注意用的是 member.user（User 主键）而不是 member.id（成员关系主键）——后端按 User 比对。 */
const currentUserId=computed(()=>Number((userStore.info as any)?.user)||0);
const activeManagerIds=computed(()=>members.value.filter(item=>item.status==='active'&&['owner','admin'].includes(item.role)).map(item=>item.id));
function isSelfMember(member:TenantMember){return currentUserId.value>0&&member.user===currentUserId.value}
function memberStatusText(member:TenantMember){const tenantStatus=member.status==='active'?'租户内已启用':'租户内已停用';return member.is_active?tenantStatus:`${tenantStatus} · 平台账号已禁用`}
function isSoleManager(member:TenantMember){return activeManagerIds.value.length===1&&activeManagerIds.value[0]===member.id}
function cannotRemove(member:TenantMember){return isSelfMember(member)||isSoleManager(member)}
function cannotToggleStatus(member:TenantMember){return member.status==='active'&&(isSelfMember(member)||isSoleManager(member))}
function roleOptionsFor(member:TenantMember){return isSoleManager(member)?roleOptions.map(item=>({...item,disabled:item.value!=='owner'&&item.value!=='admin'})):roleOptions}
async function reload(){try{await tenantStore.loadTenants(true,isPlatformAdmin.value)}catch(error:any){message.error(error?.message||'租户列表加载失败')}}
function selectTenant(id:string){tenantStore.setCurrentTenant(id);storage.remove(TABS_ROUTES);location.reload()}
function formatBytes(value:number){const bytes=Math.max(0,Number(value)||0);if(bytes<1024)return `${bytes} B`;if(bytes<1024**2)return `${(bytes/1024).toFixed(1)} KB`;if(bytes<1024**3)return `${(bytes/1024**2).toFixed(1)} MB`;return `${(bytes/1024**3).toFixed(1)} GB`}
function openCreate(){editingTenant.value=null;Object.assign(tenantForm,{name:'',slug:'',status:'active',maxRegularConcurrentExecutions:2,maxPerformanceConcurrentExecutions:1,storageQuotaGb:10});showTenantModal.value=true}
function openEdit(tenant:TenantInfo){editingTenant.value=tenant;Object.assign(tenantForm,{name:tenant.name,slug:tenant.slug,status:tenant.status,maxRegularConcurrentExecutions:tenant.max_regular_concurrent_executions||2,maxPerformanceConcurrentExecutions:tenant.max_performance_concurrent_executions||1,storageQuotaGb:Math.max(1,Math.round((tenant.storage_quota_bytes||0)/1024**3))});showTenantModal.value=true}
async function saveTenant(){try{await tenantFormRef.value?.validate();savingTenant.value=true;const payload:any={name:tenantForm.name,slug:tenantForm.slug,status:tenantForm.status};if(isPlatformAdmin.value){payload.max_regular_concurrent_executions=tenantForm.maxRegularConcurrentExecutions;payload.max_performance_concurrent_executions=tenantForm.maxPerformanceConcurrentExecutions;payload.storage_quota_bytes=tenantForm.storageQuotaGb*1024**3}if(editingTenant.value)await TenantAPI.update(editingTenant.value.id,payload);else await TenantAPI.create(payload);showTenantModal.value=false;message.success(editingTenant.value?'租户已更新':'租户已创建');await reload()}catch(error:any){if(Array.isArray(error))return;message.error(error?.message||'保存失败')}finally{savingTenant.value=false}}
function removeTenant(tenant:TenantInfo){dialog.warning({title:'删除租户',content:`确认删除「${tenant.name}」？租户下存在项目时将会拒绝删除。`,positiveText:'删除',negativeText:'取消',onPositiveClick:async()=>{try{await TenantAPI.remove(tenant.id);message.success('租户已删除');await reload()}catch(error:any){message.error(error?.message||'删除失败')}}})}
async function openMembers(tenant:TenantInfo){managedTenant.value=tenant;newMember.user=null;showMembers.value=true;await Promise.all([loadMembers(),searchCandidates('')])}
async function loadMembers(){if(!managedTenant.value)return;loadingMembers.value=true;try{members.value=await TenantAPI.members(managedTenant.value.id)}catch(error:any){message.error(error?.message||'成员加载失败')}finally{loadingMembers.value=false}}
async function searchCandidates(search=''){if(!managedTenant.value)return;const request=++candidateRequest;loadingCandidates.value=true;try{const users:TenantUserCandidate[]=await TenantAPI.memberCandidates(managedTenant.value.id,search);if(request===candidateRequest)userOptions.value=users.map(user=>({label:user.is_member?`${user.username}（已加入）`:user.username,value:user.id,disabled:user.is_member}))}catch(error:any){if(request===candidateRequest)message.error(error?.message||'用户检索失败')}finally{if(request===candidateRequest)loadingCandidates.value=false}}
async function addMember(){if(!managedTenant.value||!newMember.user)return message.warning('请选择用户');addingMember.value=true;try{await TenantAPI.addMember(managedTenant.value.id,{user:newMember.user,role:newMember.role});newMember.user=null;message.success('成员已添加');await Promise.all([loadMembers(),searchCandidates(''),reload()])}catch(error:any){message.error(error?.message||'添加失败')}finally{addingMember.value=false}}
async function updateMember(member:TenantMember,data:Partial<Pick<TenantMember,'role'|'status'>>){if(!managedTenant.value)return;try{await TenantAPI.updateMember(managedTenant.value.id,member.user,data);message.success('成员信息已更新');await loadMembers()}catch(error:any){message.error(error?.message||'更新失败');await loadMembers()}}
async function removeMember(member:TenantMember){if(!managedTenant.value||removingMember.value)return;removingMember.value=true;try{await TenantAPI.removeMember(managedTenant.value.id,member.user);message.success('成员已移除');await loadMembers();await reload()}catch(error:any){message.error(error?.message||'移除失败')}finally{removingMember.value=false}}
onMounted(reload);
</script>

<style scoped lang="less">
.tenant-page{max-width:1440px;margin:0 auto;padding:22px 28px 40px;color:#263449}.page-header{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:20px}.eyebrow{margin:0 0 7px;color:#77859a;font-size:11px;font-weight:700;letter-spacing:.13em}.page-header h2{margin:0;color:#172033;font-size:27px;font-weight:750;letter-spacing:-.035em}.description{margin:8px 0 0;color:#7b889b;font-size:13px}.header-actions,.modal-actions{display:flex;justify-content:flex-end;gap:8px}.summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:18px}.summary-card{display:flex;min-height:120px;box-sizing:border-box;flex-direction:column;padding:20px 22px;border:1px solid #e1e7ef;border-radius:10px;background:#fff}.summary-card span{color:#768499;font-size:12px}.summary-card strong{margin-top:13px;overflow:hidden;color:#263449;font-size:24px;font-weight:700;line-height:1.1;text-overflow:ellipsis;white-space:nowrap}.summary-card small{margin-top:9px;color:#98a2b2;font-size:11px}.current-summary{border-color:#cbd9ef;background:#f8faff}.current-summary strong{color:#315fae}.tenant-panel{overflow:hidden;border:1px solid #dfe6ee;border-radius:11px;background:#fff}.panel-heading{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:19px 22px;border-bottom:1px solid #e9edf2}.panel-heading h3{margin:0;color:#28364b;font-size:16px}.panel-heading p{margin:6px 0 0;color:#8793a5;font-size:12px}.security-note{padding:5px 9px;border-radius:5px;color:#41745a;background:#edf7f1;font-size:11px;font-weight:600}.tenant-list{display:grid;padding:0 22px}.tenant-item{display:grid;grid-template-columns:42px minmax(180px,1fr) minmax(300px,.8fr) minmax(280px,auto);align-items:center;gap:16px;min-height:92px;border-bottom:1px solid #edf0f4}.tenant-item:last-child{border-bottom:0}.tenant-item.active{background:linear-gradient(90deg,rgba(65,105,170,.055),transparent 70%)}.tenant-mark{display:grid;width:38px;height:38px;place-items:center;border-radius:9px;color:#53637a;background:#edf1f6;font-size:14px;font-weight:700}.tenant-item.active .tenant-mark{color:#365f9e;background:#e8eff9}.tenant-info{min-width:0}.tenant-title,.row-actions{display:flex;align-items:center;gap:8px}.tenant-title strong{overflow:hidden;color:#2b394e;font-size:14px;text-overflow:ellipsis;white-space:nowrap}.tenant-code{display:block;margin-top:6px;color:#8e99aa;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px}.current-tag,.status-tag{padding:3px 6px;border-radius:4px;font-size:10px;font-weight:600}.current-tag{color:#3866ad;background:#eaf1fb}.status-tag{color:#47745b;background:#eef7f1}.status-tag.suspended{color:#9a5e5e;background:#f8eded}.tenant-meta{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:0}.tenant-meta dt{color:#929dad;font-size:10px}.tenant-meta dd{margin:5px 0 0;color:#445268;font-size:12px;font-weight:600;white-space:nowrap}.empty-state{padding:70px 20px}.tenant-modal{width:min(520px,calc(100vw - 32px))}.add-member{display:grid;grid-template-columns:minmax(0,1fr) 150px 72px;gap:8px}.member-hint{margin:8px 0 18px;color:#8a96a8;font-size:12px}.member-list{border-top:1px solid #e8edf3}.member-item{display:grid;grid-template-columns:36px minmax(110px,1fr) 150px 80px 42px;align-items:center;gap:12px;min-height:68px;border-bottom:1px solid #e8edf3}.member-avatar{display:grid;width:32px;height:32px;place-items:center;border-radius:8px;color:#49617f;background:#edf2f7;font-weight:700}.member-name{display:grid;gap:3px;min-width:0}.member-name strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.member-name small{overflow:hidden;color:#929daf;font-size:10px;text-overflow:ellipsis;white-space:nowrap}
.member-list { margin-top: 18px; }
@media(min-width:1051px) {
  .tenant-item { grid-template-columns:42px minmax(180px,.75fr) minmax(400px,1.35fr) minmax(250px,auto); }
  .tenant-meta { grid-template-columns:repeat(4,minmax(0,1fr)); }
  .tenant-item.platform-view { grid-template-columns:42px minmax(180px,.8fr) minmax(400px,1.2fr) minmax(250px,auto); }
  .tenant-item.platform-view .tenant-meta { grid-template-columns:repeat(3,minmax(0,1fr)); }
}
/* 深色适配。全局 dark-theme.less 用 [class$='-page']、*-panel、*-card 等通用选择器配合
   !important 已经收口了页面画布、标题和卡片表面，本页的 .tenant-page / .page-header h2 /
   .summary-card / .tenant-panel / .panel-heading h3 都在覆盖范围内，重复声明会被 !important
   压掉（此前这里就有 5 条这样的死规则）。下面只补通用层够不到的部分：状态徽标、元信息文字，
   以及需要抢回主权的「当前租户」强调卡。 */
html[data-theme='dark'] .eyebrow,
html[data-theme='dark'] .description,
html[data-theme='dark'] .summary-card span,
html[data-theme='dark'] .summary-card small,
html[data-theme='dark'] .panel-heading p,
html[data-theme='dark'] .tenant-code,
html[data-theme='dark'] .tenant-meta dt,
html[data-theme='dark'] .member-name small { color: var(--tp-text-muted); }
html[data-theme='dark'] .summary-card strong,
html[data-theme='dark'] .tenant-title strong,
html[data-theme='dark'] .member-name strong { color: var(--tp-text); }
html[data-theme='dark'] .tenant-meta dd { color: var(--tp-text-secondary); }
/* 行分隔线比面板描边更浅，深色下对应 --tp-border-soft。 */
html[data-theme='dark'] .panel-heading,
html[data-theme='dark'] .tenant-item,
html[data-theme='dark'] .member-list,
html[data-theme='dark'] .member-item { border-color: var(--tp-border-soft); }
html[data-theme='dark'] .tenant-item.active { background: linear-gradient(90deg, rgba(108, 178, 240, 0.07), transparent 70%); }
html[data-theme='dark'] .tenant-mark,
html[data-theme='dark'] .member-avatar { color: #9aa6b8; background: var(--tp-surface-raised); }
/* 选中态的方块要比普通态更亮，否则和旁边的灰底方块分不出层次。这条必须写全
   .tenant-item.active .tenant-mark：浅色那条选择器更长（3 类 + 1 属性），只写 .tenant-mark
   压不住它，选中项会一直留着浅蓝色块。 */
html[data-theme='dark'] .tenant-item.active .tenant-mark { color: #9cb9e7; background: rgba(108, 178, 240, 0.16); }
/* 徽标在浅色下是「淡底深字」，深色下必须反转为「透明底亮字」，否则会留下浅绿 / 浅蓝的实心块，
   在深色页面上非常刺眼。色值沿用项目深色语义色 --sc-ok / --sc-info / --sc-bad。 */
html[data-theme='dark'] .security-note,
html[data-theme='dark'] .status-tag { color: #4cc38a; background: rgba(76, 195, 138, 0.12); }
html[data-theme='dark'] .current-tag { color: #6cb2f0; background: rgba(108, 178, 240, 0.14); }
html[data-theme='dark'] .status-tag.suspended { color: #f08a94; background: rgba(240, 138, 148, 0.13); }
/* 放在 .summary-card strong 之后：两者特异性相同（0,2,1），靠源序决定「当前租户」的蓝色数值。
   这里用 !important 是因为全局 *-card 表面规则带 !important，同为 !important 时比特异性。 */
html[data-theme='dark'] .current-summary { border-color: #33465e !important; background: #1e2530 !important; }
html[data-theme='dark'] .current-summary strong { color: #9cb9e7; }
@media(max-width:1050px){.tenant-item{grid-template-columns:42px minmax(0,1fr) auto}.tenant-meta{display:none}}@media(max-width:760px){.summary-grid{grid-template-columns:1fr}.tenant-page{padding:18px}.tenant-item{grid-template-columns:38px minmax(0,1fr);padding:14px 0}.row-actions{grid-column:2;flex-wrap:wrap}.panel-heading{align-items:flex-start;flex-direction:column}.add-member{grid-template-columns:1fr}.member-item{grid-template-columns:36px minmax(0,1fr) 42px}.member-item>.n-select,.member-item>.n-switch{grid-column:2}}
</style>
