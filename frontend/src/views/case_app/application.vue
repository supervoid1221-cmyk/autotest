<template>
  <section class="app-page">
    <header class="page-header"><div><h2>应用管理</h2><p>维护 Android 应用、包名和可执行安装包版本。</p></div><n-button type="primary" @click="openForm()">新增应用</n-button></header>
    <div class="filters"><n-input v-model:value="filters.name" clearable placeholder="应用名称" /><n-select v-model:value="filters.project" clearable :options="projectOptions" placeholder="全部项目" /><n-button @click="load">查询</n-button></div>
    <n-data-table :loading="loading" :columns="columns" :data="rows" :row-key="(row) => row.id" />

    <n-modal v-model:show="showForm" preset="card" :title="form.id ? '编辑应用' : '新增应用'" class="platform-form-modal app-modal">
      <n-form label-placement="top"><div class="form-grid">
        <n-form-item label="所属项目" required><n-select v-model:value="form.project" :options="projectOptions" /></n-form-item>
        <n-form-item label="应用名称" required><n-input v-model:value="form.name" /></n-form-item>
        <n-form-item label="Package Name" required><n-input v-model:value="form.package_name" placeholder="com.example.app" /></n-form-item>
        <n-form-item label="Main Activity"><n-input v-model:value="form.main_activity" placeholder=".MainActivity" /></n-form-item>
      </div><n-space><n-switch v-model:value="form.auto_install" />自动安装<n-switch v-model:value="form.replace_install" />覆盖安装<n-switch v-model:value="form.clear_data" />执行前清理数据<n-switch v-model:value="form.enabled" />启用</n-space><n-form-item label="描述" class="description"><n-input v-model:value="form.description" type="textarea" /></n-form-item></n-form>
      <template #footer><n-space justify="end"><n-button @click="showForm=false">取消</n-button><n-button type="primary" :loading="saving" @click="save">保存</n-button></n-space></template>
    </n-modal>

    <n-modal v-model:show="showVersions" preset="card" title="应用版本" class="platform-form-modal app-modal">
      <div class="version-upload"><n-input v-model:value="versionName" placeholder="版本名称，如 1.2.0" /><n-input v-model:value="versionCode" placeholder="版本号（可选）" /><input ref="fileInput" type="file" accept=".apk" /><n-button type="primary" :loading="uploading" @click="upload">上传 APK</n-button></div>
      <n-data-table :columns="versionColumns" :data="versions" :row-key="(row) => row.id" />
    </n-modal>
  </section>
</template>

<script setup lang="ts">
import { asList } from '@/utils/list';

import { computed, h, onMounted, reactive, ref } from 'vue';
import { NButton, NSpace, NTag, useDialog, useMessage } from 'naive-ui';
import { ProjectAPI } from '@/api/project/http';
import { AppTestAPI, type AppApplication, type AppVersion } from '@/api/case_app/http';

const message=useMessage(), dialog=useDialog(), projectApi=new ProjectAPI();
const rows=ref<AppApplication[]>([]), projects=ref<any[]>([]), loading=ref(false), saving=ref(false), showForm=ref(false), showVersions=ref(false), uploading=ref(false), currentApp=ref<AppApplication>();
const filters=reactive({name:'',project:null as number|null});
const emptyForm=():AppApplication=>({project:null,name:'',platform:'android',package_name:'',main_activity:'',startup_options:{},auto_install:false,replace_install:true,clear_data:false,enabled:true,description:''});
const form=reactive<AppApplication>(emptyForm()); const versions=ref<AppVersion[]>([]), versionName=ref(''), versionCode=ref(''), fileInput=ref<HTMLInputElement>();

const projectOptions=computed(()=>projects.value.map(p=>({label:p.name,value:Number(p.id)})));
const columns:any[]=[
  {title:'应用名称',key:'name'},{title:'所属项目',key:'project_name'},{title:'平台',key:'platform',width:90,render:()=> 'Android'},
  {title:'Package Name',key:'package_name'},{title:'Main Activity',key:'main_activity',render:(r:any)=>r.main_activity||'-'},
  {title:'版本数',key:'version_count',width:80},{title:'状态',key:'enabled',width:90,render:(r:any)=>h(NTag,{type:r.enabled?'success':'default',bordered:false},{default:()=>r.enabled?'启用':'停用'})},
  {title:'操作',key:'action',width:220,render:(r:any)=>h(NSpace,{size:14,wrap:false},{default:()=>[
    h(NButton,{text:true,type:'primary',onClick:()=>openVersions(r)},{default:()=> '版本'}),h(NButton,{text:true,type:'primary',onClick:()=>openForm(r)},{default:()=> '编辑'}),h(NButton,{text:true,type:'error',onClick:()=>remove(r)},{default:()=> '删除'})]})}
];
const versionColumns:any[]=[{title:'版本名称',key:'version_name'},{title:'版本号',key:'version_code',render:(r:any)=>r.version_code||'-'},{title:'文件',key:'original_name'},{title:'大小',key:'file_size',render:(r:any)=>`${(r.file_size/1024/1024).toFixed(2)} MB`},{title:'操作',key:'action',width:80,render:(r:any)=>h(NButton,{text:true,type:'error',onClick:()=>removeVersion(r)},{default:()=> '删除'})}];
async function load(){loading.value=true;try{rows.value=asList(await AppTestAPI.applications({name:filters.name||undefined,project:filters.project||undefined,pageSize:1000}));}catch(e:any){message.error(e?.message||'应用加载失败');}finally{loading.value=false;}}
function openForm(row?:AppApplication){Object.assign(form,emptyForm(),row||{});showForm.value=true;}
async function save(){if(!form.project||!form.name.trim()||!form.package_name.trim())return message.warning('请填写所属项目、应用名称和 Package Name');saving.value=true;try{await AppTestAPI.saveApplication({...form});message.success('保存成功');showForm.value=false;await load();}catch(e:any){message.error(e?.message||'保存失败');}finally{saving.value=false;}}
function remove(row:AppApplication){dialog.warning({title:'删除应用',content:`确定删除「${row.name}」吗？`,positiveText:'删除',negativeText:'取消',onPositiveClick:async()=>{await AppTestAPI.deleteApplication(Number(row.id));await load();}});}
async function openVersions(row:AppApplication){currentApp.value=row;versions.value=asList(await AppTestAPI.versions(Number(row.id)));versionName.value='';versionCode.value='';showVersions.value=true;}
async function upload(){const file=fileInput.value?.files?.[0];if(!currentApp.value?.id||!versionName.value.trim()||!file)return message.warning('请填写版本名称并选择 APK');uploading.value=true;try{await AppTestAPI.uploadVersion(currentApp.value.id,versionName.value.trim(),versionCode.value.trim(),file);message.success('上传成功');await openVersions(currentApp.value);await load();}catch(e:any){message.error(e?.message||'上传失败');}finally{uploading.value=false;}}
function removeVersion(row:AppVersion){dialog.warning({title:'删除版本',content:`确定删除版本「${row.version_name}」吗？`,positiveText:'删除',negativeText:'取消',onPositiveClick:async()=>{await AppTestAPI.deleteVersion(row.id);if(currentApp.value)await openVersions(currentApp.value);await load();}});}
onMounted(async()=>{projects.value=asList(await projectApi.getDataList({pageSize:1000}));await load();});
</script>

<style scoped lang="less">
.app-page{padding:24px 28px}.page-header{display:flex;justify-content:space-between;gap:16px}.page-header h2{margin:0;color:#1e293b}.page-header p{margin:8px 0 22px;color:#7b8ba3}.filters{display:grid;grid-template-columns:240px 220px max-content;gap:12px;margin-bottom:16px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 16px}.description{margin-top:16px}.version-upload{display:grid;grid-template-columns:1fr 1fr 1.4fr max-content;gap:10px;margin-bottom:16px}@media(max-width:640px){.app-page{padding:16px}.page-header{flex-direction:column}.filters,.form-grid,.version-upload{grid-template-columns:1fr}}
</style>
