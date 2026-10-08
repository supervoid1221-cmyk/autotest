<template>
  <section class="inspector-page">
    <header class="page-header">
      <div><h2>元素检查</h2><p>连接 Android 设备，查看页面结构并生成可验证的元素定位。</p></div>
      <n-space>
        <n-tag v-if="sessionId && inspectionMode === 'record'" type="error" :bordered="false">录制中 · {{ recordedSteps.length }} 步</n-tag>
        <n-button v-if="sessionId && inspectionMode === 'record' && recordedSteps.length" @click="undoRecordedStep">撤销上一步</n-button>
        <n-button v-if="sessionId" :loading="refreshing" @click="refresh">刷新页面</n-button>
        <n-button v-if="sessionId" :loading="refreshing" @click="deviceBack">设备返回</n-button>
        <n-button v-if="sessionId && inspectionMode === 'record'" type="primary" :loading="draftSaving" @click="finishRecording">结束录制并生成草稿</n-button>
        <n-button v-else-if="sessionId" type="error" ghost @click="closeSession">结束检查</n-button>
        <n-button v-else type="primary" :loading="starting" @click="start">{{ inspectionMode === 'record' ? '启动录制' : '启动检查' }}</n-button>
        <n-button @click="returnToElementManagement">返回元素管理</n-button>
      </n-space>
    </header>

    <div class="connection-bar">
      <n-select v-model:value="project" filterable :options="projectOptions" placeholder="选择项目" :disabled="!!sessionId" @update:value="onProjectChange" />
      <n-select v-model:value="application" filterable :options="applicationOptions" placeholder="选择应用" :disabled="!!sessionId" @update:value="onApplicationChange" />
      <n-select v-model:value="version" clearable :options="versionOptions" placeholder="已安装版本（可选）" :disabled="!!sessionId" />
      <n-select v-model:value="device" filterable :options="deviceOptions" placeholder="选择在线设备" :disabled="!!sessionId" />
      <n-checkbox v-model:checked="resetApp" :disabled="!!sessionId">重置应用数据</n-checkbox>
      <div class="inspection-mode-switch" :class="{ disabled: !!sessionId }">
        <button type="button" :class="{ active: inspectionMode === 'inspect' }" :disabled="!!sessionId" @click="inspectionMode = 'inspect'">仅检查</button>
        <button type="button" :class="{ active: inspectionMode === 'record' }" :disabled="!!sessionId" @click="inspectionMode = 'record'">检查并录制</button>
      </div>
    </div>

    <n-alert v-if="!sessionId" type="info" :show-icon="true">{{ inspectionMode === 'record' ? '平台执行的点击、输入、滑动和返回会自动记录，结束后生成停用状态的 App 用例草稿。' : '启动后设备将标记为“检查中”，此期间不会被 App 用例任务占用。' }}</n-alert>

    <div v-if="snapshot" class="workspace">
      <section class="device-panel panel-card">
        <div class="panel-title">
          <div><strong>{{ snapshot.package_name || '-' }}</strong><span>{{ snapshot.activity || '-' }}</span></div>
          <n-tag type="success" :bordered="false" class="inspection-status-tag">检查中</n-tag>
        </div>
        <div v-if="inspectionMode === 'record'" class="record-toolbar">
          <span>录制操作</span>
          <n-button size="small" :disabled="!selected" :loading="acting" @click="openInput">输入</n-button>
          <n-button size="small" :loading="acting" @click="recordSwipe('up')">上滑</n-button>
          <n-button size="small" :loading="acting" @click="recordSwipe('down')">下滑</n-button>
          <n-button size="small" :loading="acting" @click="recordSwipe('left')">左滑</n-button>
          <n-button size="small" :loading="acting" @click="recordSwipe('right')">右滑</n-button>
          <em>点击操作请先选中元素，再点击右侧“在设备上点击”</em>
        </div>
        <div class="screen-stage">
          <div ref="screenRef" class="screen-wrap" @click="selectFromScreen">
            <img ref="screenImageRef" :src="snapshot.screenshot" alt="设备截图" draggable="false" />
            <div v-if="selected" class="element-highlight" :style="highlightStyle">
              <span>{{ selected.label }}</span>
            </div>
          </div>
        </div>
        <div class="screen-meta">
          <span>分辨率 {{ snapshot.screen.width }} × {{ snapshot.screen.height }}</span>
          <span>更新 {{ formatTime(snapshot.updated_at) }}</span>
          <span>点击截图可选中元素</span>
        </div>
      </section>

      <section class="element-panel panel-card">
        <div class="element-search"><n-input v-model:value="keyword" clearable placeholder="搜索文本、Resource ID、类名" /></div>
        <div v-if="selected" class="selected-action-bar">
          <div><span>当前元素</span><strong>{{ selected.label }}</strong></div>
          <n-space size="small" :wrap="false">
            <n-button size="small" :loading="tapping" @click="tapSelected">{{ inspectionMode === 'record' ? '点击并记录' : '在设备上点击' }}</n-button>
            <n-button v-if="inspectionMode === 'record'" size="small" :loading="acting" @click="openInput">输入并记录</n-button>
            <n-button size="small" :disabled="!activeCandidate" @click="copyLocator">复制定位</n-button>
            <n-button size="small" :loading="validating" :disabled="!activeCandidate" @click="validateLocator">验证定位</n-button>
            <n-button size="small" type="primary" :disabled="!activeCandidate" @click="openSave">保存到元素库</n-button>
          </n-space>
        </div>
        <div class="element-content">
          <div class="tree-area">
            <div class="section-label">页面元素 <span>{{ filteredElements.length }}</span></div>
            <n-tree
              block-line virtual-scroll :data="treeData" key-field="key" label-field="label"
              :selected-keys="selectedKeys" :default-expand-all="true" @update:selected-keys="selectFromTree"
            />
          </div>
          <div class="detail-area">
            <template v-if="selected">
              <div class="section-label">元素属性</div>
              <div class="property-grid">
                <span>text</span><code>{{ selected.text || '-' }}</code>
                <span>resource-id</span><code>{{ selected.resource_id || '-' }}</code>
                <span>content-desc</span><code>{{ selected.content_desc || '-' }}</code>
                <span>class</span><code>{{ selected.class_name || '-' }}</code>
                <span>bounds</span><code>{{ boundsText(selected.bounds) }}</code>
                <span>可点击</span><code>{{ selected.clickable ? '是' : '否' }}</code>
              </div>

              <div class="section-label locator-title">定位候选</div>
              <div v-if="selected.candidates.length" class="candidate-list">
                <button
                  v-for="(candidate,index) in selected.candidates" :key="`${candidate.type}-${index}`"
                  type="button" class="candidate" :class="{ active: activeCandidateIndex === index }"
                  @click="chooseCandidate(index)"
                >
                  <span><b>{{ candidate.label }}</b><em :class="candidate.stability">{{ stabilityLabel[candidate.stability] }}</em></span>
                  <code>{{ candidate.value }}</code>
                </button>
              </div>
              <n-empty v-else description="当前元素没有可用定位属性" size="small" />

              <n-alert v-if="validation" class="validation" :type="validation.unique ? 'success' : validation.matched ? 'warning' : 'error'">
                {{ validation.unique ? '定位成功，唯一匹配 1 个元素' : `当前定位匹配 ${validation.matched} 个元素` }}
              </n-alert>
            </template>
            <n-empty v-else description="点击左侧截图或元素树选择元素" />
          </div>
        </div>
      </section>
    </div>

    <section v-if="sessionId && inspectionMode === 'record'" class="recorded-steps panel-card">
      <header><div><strong>已录制步骤</strong><span>结束录制后自动生成 App 用例草稿</span></div><b>{{ recordedSteps.length }}</b></header>
      <div v-if="recordedSteps.length" class="recorded-step-list">
        <div v-for="(step,index) in recordedSteps" :key="`${index}-${step.action}`"><span>{{ index + 1 }}</span><strong>{{ recordedActionLabel(step.action) }}</strong><em>{{ step.element_name || recordedStepDetail(step) }}</em></div>
      </div>
      <n-empty v-else size="small" description="请在上方执行点击、输入、滑动或返回操作" />
    </section>

    <n-empty v-else class="empty-workspace" description="选择项目、应用和设备后启动元素检查" />

    <n-modal v-model:show="saveVisible" preset="card" title="保存到元素库" class="platform-form-modal inspector-save-modal" :mask-closable="false">
      <n-form label-placement="top">
        <div class="form-grid">
          <n-form-item label="元素名称" required><n-input v-model:value="saveForm.name" placeholder="例如：登录按钮" /></n-form-item>
          <n-form-item label="页面名称"><n-input v-model:value="saveForm.page_name" placeholder="例如：登录页" /></n-form-item>
          <n-form-item label="定位方式"><n-select v-model:value="saveForm.locator_type" :options="locatorOptions" /></n-form-item>
          <n-form-item label="Activity"><n-input v-model:value="saveForm.activity" /></n-form-item>
        </div>
        <n-form-item label="定位表达式" required><n-input v-model:value="saveForm.locator_value" type="textarea" :autosize="{minRows:2,maxRows:4}" /></n-form-item>
        <n-form-item label="描述"><n-input v-model:value="saveForm.description" type="textarea" /></n-form-item>
      </n-form>
      <template #footer><n-space justify="end"><n-button @click="saveVisible=false">取消</n-button><n-button type="primary" :loading="saving" @click="saveElement">保存</n-button></n-space></template>
    </n-modal>

    <n-modal v-model:show="inputVisible" preset="dialog" title="输入并记录" positive-text="确定" negative-text="取消" :positive-button-props="{ loading: acting }" @positive-click="recordInput">
      <n-form label-placement="top"><n-form-item label="输入内容" required><n-input v-model:value="inputText" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" placeholder="请输入要发送到当前元素的内容" /></n-form-item></n-form>
    </n-modal>
  </section>
</template>

<script setup lang="ts">
import { asList } from '@/utils/list';

defineOptions({ name: 'case_app_inspector' });

import { computed, onActivated, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import { useMessage } from 'naive-ui';
import { useRouter } from 'vue-router';
import { ProjectAPI } from '@/api/project/http';
import {
  AppTestAPI, type AppApplication, type AppDevice, type AppInspectorCandidate,
  type AppInspectorElement, type AppInspectorSnapshot, type AppStep, type AppVersion,
} from '@/api/case_app/http';

const message = useMessage();
const router = useRouter();
const projectApi = new ProjectAPI();
const projects = ref<any[]>([]), applications = ref<AppApplication[]>([]), devices = ref<AppDevice[]>([]), versions = ref<AppVersion[]>([]);
const project = ref<number|null>(null), application = ref<number|null>(null), device = ref<number|null>(null), version = ref<number|null>(null);
const resetApp = ref(false), starting = ref(false), refreshing = ref(false), validating = ref(false), tapping = ref(false), saving = ref(false);
const inspectionMode = ref<'inspect'|'record'>('inspect'), acting = ref(false), draftSaving = ref(false), inputVisible = ref(false), inputText = ref('');
const recordedSteps = ref<Partial<AppStep>[]>([]);
const snapshot = ref<AppInspectorSnapshot|null>(null), sessionId = ref(''), keyword = ref(''), selectedId = ref(''), activeCandidateIndex = ref(0);
const validation = ref<{matched:number;unique:boolean}|null>(null), saveVisible = ref(false), screenRef = ref<HTMLElement|null>(null), screenImageRef = ref<HTMLImageElement|null>(null);
const saveForm = reactive({name:'',page_name:'',activity:'',locator_type:'id',locator_value:'',description:''});
const locatorOptions = [
  {label:'Accessibility ID',value:'accessibility id'}, {label:'Resource ID',value:'id'},
  {label:'UIAutomator',value:'-android uiautomator'}, {label:'XPath',value:'xpath'},
  {label:'坐标定位',value:'coordinate'},
  {label:'OCR 文字定位',value:'ocr_text'}, {label:'图像文字识别',value:'image_text'},
];
const stabilityLabel = {high:'稳定',medium:'一般',low:'较弱'};

const projectOptions = computed(() => projects.value.map(item=>({label:item.name,value:Number(item.id)})));
const applicationOptions = computed(() => applications.value.map(item=>({label:item.name,value:Number(item.id)})));
const versionOptions = computed(() => versions.value.map(item=>({label:`${item.version_name}${item.version_code ? ` · ${item.version_code}` : ''}`,value:Number(item.id)})));
const deviceOptions = computed(() => devices.value.filter(item=>item.enabled && item.state==='online').map(item=>({label:`${item.name} · 在线`,value:Number(item.id)})));
const selected = computed(() => snapshot.value?.elements.find(item=>item.node_id===selectedId.value) || null);
const selectedKeys = computed(() => selectedId.value ? [selectedId.value] : []);
const activeCandidate = computed<AppInspectorCandidate|null>(() => selected.value?.candidates[activeCandidateIndex.value] || null);
const filteredElements = computed(() => {
  const value=keyword.value.trim().toLowerCase();
  if(!value)return snapshot.value?.elements||[];
  const matched=new Set<string>();
  const all=snapshot.value?.elements||[];
  const byId=new Map(all.map(item=>[item.node_id,item]));
  all.forEach(item=>{if([item.label,item.text,item.resource_id,item.content_desc,item.class_name].some(field=>field.toLowerCase().includes(value))){let current:AppInspectorElement|undefined=item;while(current){matched.add(current.node_id);current=current.parent_id?byId.get(current.parent_id):undefined;}}});
  return all.filter(item=>matched.has(item.node_id));
});
const treeData = computed(() => {
  const nodes=new Map<string,any>();
  filteredElements.value.forEach(item=>nodes.set(item.node_id,{key:item.node_id,label:`${item.label}  ·  ${shortClass(item.class_name)}`,children:[]}));
  const roots:any[]=[];
  filteredElements.value.forEach(item=>{const node=nodes.get(item.node_id);const parent=item.parent_id?nodes.get(item.parent_id):null;if(parent)parent.children.push(node);else roots.push(node);});
  return roots;
});
const highlightStyle = computed(() => {
  const b=selected.value?.bounds||[0,0,0,0],w=snapshot.value?.screen.width||1,h=snapshot.value?.screen.height||1;
  return {left:`${b[0]/w*100}%`,top:`${b[1]/h*100}%`,width:`${Math.max(0,b[2]-b[0])/w*100}%`,height:`${Math.max(0,b[3]-b[1])/h*100}%`};
});

function shortClass(value:string){return value.split('.').pop()||value;}
function boundsText(bounds:number[]){return `[${bounds[0]},${bounds[1]}][${bounds[2]},${bounds[3]}]`;}
function formatTime(value:string){return value?new Date(value).toLocaleTimeString():'-';}
const recordingStorageKey = (id:string) => `app-inspector-recording:${id}`;
function persistRecording(){if(!sessionId.value)return;sessionStorage.setItem(recordingStorageKey(sessionId.value),JSON.stringify({mode:inspectionMode.value,steps:recordedSteps.value}));}
function restoreRecording(id:string){try{const saved=JSON.parse(sessionStorage.getItem(recordingStorageKey(id))||'null');if(saved?.mode==='record'){inspectionMode.value='record';recordedSteps.value=Array.isArray(saved.steps)?saved.steps:[];}}catch{recordedSteps.value=[];}}
function clearRecording(id:string){sessionStorage.removeItem(recordingStorageKey(id));recordedSteps.value=[];}
function appendRecorded(data:AppInspectorSnapshot){if(inspectionMode.value==='record'&&data.recorded_step){recordedSteps.value.push(data.recorded_step);persistRecording();}}
function undoRecordedStep(){recordedSteps.value.pop();persistRecording();}
function recordedActionLabel(action?:string){return ({click:'点击',input:'输入',swipe:'滑动',back:'返回'} as Record<string,string>)[String(action||'')]||String(action||'-');}
function recordedStepDetail(step:Partial<AppStep>){if(step.action==='input')return String(step.value||'');if(step.action==='swipe')return '屏幕手势';return '设备操作';}
function selectedPayload(){if(!selected.value||!activeCandidate.value)return null;return {element_name:selected.value.text||selected.value.content_desc||selected.value.resource_id.split('/').pop()||shortClass(selected.value.class_name)||'页面元素',page_name:'',activity:snapshot.value?.activity||'',locator_type:activeCandidate.value.type,locator_value:activeCandidate.value.value,fallback_locator:selected.value.candidates.filter((_,index)=>index!==activeCandidateIndex.value),element_class:selected.value.class_name,snapshot:selected.value.attributes};}
async function onProjectChange(){application.value=null;device.value=null;version.value=null;applications.value=[];devices.value=[];if(!project.value)return;const[a,d]=await Promise.all([AppTestAPI.applications({project:project.value,pageSize:1000}),AppTestAPI.devices({project:project.value,pageSize:1000})]);applications.value=asList(a);devices.value=asList(d);}
async function onApplicationChange(){version.value=null;versions.value=application.value?asList(await AppTestAPI.versions(application.value)):[];}
async function start(){if(!project.value||!application.value||!device.value)return message.warning('请选择项目、应用和执行设备');starting.value=true;try{const data=await AppTestAPI.startInspector({project:project.value,application:application.value,device:device.value,version:version.value,reset_app:resetApp.value});sessionId.value=data.id;recordedSteps.value=[];applySnapshot(data);persistRecording();message.success(inspectionMode.value==='record'?'检查并录制已启动':'元素检查已启动');}catch(e:any){message.error(e?.message||'元素检查启动失败');}finally{starting.value=false;}}
function applySnapshot(data:AppInspectorSnapshot){snapshot.value=data;if(selectedId.value&&!data.elements.some(item=>item.node_id===selectedId.value))selectedId.value='';validation.value=null;}
async function restoreCurrentSession(){try{const result=await AppTestAPI.currentInspector();if(!result.active||!result.session){if(result.message)message.warning(result.message);return;}const data=result.session;project.value=Number(data.project);application.value=Number(data.application);device.value=Number(data.device);version.value=data.version?Number(data.version):null;sessionId.value=data.id;restoreRecording(data.id);applySnapshot(data);const[a,d,v]=await Promise.all([AppTestAPI.applications({project:project.value,pageSize:1000}),AppTestAPI.devices({project:project.value,pageSize:1000}),AppTestAPI.versions(application.value)]);applications.value=asList(a);devices.value=asList(d);versions.value=asList(v);}catch(e:any){message.error(e?.message||'检查会话恢复失败');}}
async function refresh(){if(!sessionId.value)return;refreshing.value=true;try{applySnapshot(await AppTestAPI.refreshInspector(sessionId.value));}catch(e:any){message.error(e?.message||'页面刷新失败');}finally{refreshing.value=false;}}
async function deviceBack(){if(!sessionId.value)return;refreshing.value=true;try{const data=await AppTestAPI.backInspector(sessionId.value,inspectionMode.value==='record');appendRecorded(data);applySnapshot(data);}catch(e:any){message.error(e?.message||'设备返回操作失败');}finally{refreshing.value=false;}}
async function returnToElementManagement(){const id=sessionId.value;sessionId.value='';snapshot.value=null;selectedId.value='';if(id){clearRecording(id);try{await AppTestAPI.closeInspector(id);}catch{/* 页面返回不受已失效的 Appium 会话影响 */}}router.push({name:'case_app_element'});}
async function closeSession(){const id=sessionId.value;if(!id)return;sessionId.value='';snapshot.value=null;selectedId.value='';clearRecording(id);try{await AppTestAPI.closeInspector(id);message.success('元素检查已结束');}catch(e:any){message.error(e?.message||'会话释放失败');}}
function selectFromTree(keys:Array<string|number>){selectedId.value=String(keys[0]||'');activeCandidateIndex.value=0;validation.value=null;}
function selectFromScreen(event:MouseEvent){if(!snapshot.value||!screenImageRef.value)return;const rect=screenImageRef.value.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)return;const x=(event.clientX-rect.left)/rect.width*snapshot.value.screen.width,y=(event.clientY-rect.top)/rect.height*snapshot.value.screen.height;const area=(item:AppInspectorElement)=>(item.bounds[2]-item.bounds[0])*(item.bounds[3]-item.bounds[1]);const hits=snapshot.value.elements.filter(item=>{const b=item.bounds;return item.displayed&&x>=b[0]&&x<=b[2]&&y>=b[1]&&y<=b[3]&&b[2]>b[0]&&b[3]>b[1];}).sort((a,b)=>Number(b.clickable)-Number(a.clickable)||area(a)-area(b)||b.depth-a.depth);if(hits[0])selectFromTree([hits[0].node_id]);}
function chooseCandidate(index:number){activeCandidateIndex.value=index;validation.value=null;}
async function copyLocator(){if(!activeCandidate.value)return;const value=activeCandidate.value.value;if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(value);}else{const input=document.createElement('textarea');input.value=value;input.style.position='fixed';input.style.opacity='0';document.body.appendChild(input);input.select();document.execCommand('copy');input.remove();}message.success('定位表达式已复制');}
async function validateLocator(){if(!sessionId.value||!activeCandidate.value)return;validating.value=true;try{validation.value=await AppTestAPI.validateInspector(sessionId.value,activeCandidate.value.type,activeCandidate.value.value);}catch(e:any){message.error(e?.message||'定位验证失败');}finally{validating.value=false;}}
async function tapSelected(){if(!sessionId.value||!selected.value)return;const b=selected.value.bounds,payload=selectedPayload();tapping.value=true;try{const data=await AppTestAPI.tapInspector(sessionId.value,{x:Math.round((b[0]+b[2])/2),y:Math.round((b[1]+b[3])/2),record:inspectionMode.value==='record',...(payload||{})});appendRecorded(data);applySnapshot(data);selectedId.value='';}catch(e:any){message.error(e?.message||'设备点击失败');}finally{tapping.value=false;}}
function openInput(){if(!selected.value||!activeCandidate.value)return message.warning('请先选择一个可定位元素');inputText.value='';inputVisible.value=true;}
async function recordInput(){if(!sessionId.value)return false;if(!inputText.value){message.warning('请输入内容');return false;}const payload=selectedPayload();if(!payload){message.warning('当前元素没有可用定位');return false;}acting.value=true;try{const data=await AppTestAPI.inputInspector(sessionId.value,{...payload,text:inputText.value,clear:true});appendRecorded(data);applySnapshot(data);inputVisible.value=false;selectedId.value='';return true;}catch(e:any){message.error(e?.message||'输入操作失败');return false;}finally{acting.value=false;}}
async function recordSwipe(direction:'up'|'down'|'left'|'right'){if(!sessionId.value||!snapshot.value)return;const w=snapshot.value.screen.width,h=snapshot.value.screen.height;const points={up:[.5,.75,.5,.25],down:[.5,.25,.5,.75],left:[.8,.5,.2,.5],right:[.2,.5,.8,.5]}[direction];acting.value=true;try{const data=await AppTestAPI.swipeInspector(sessionId.value,{start_x:Math.round(w*points[0]),start_y:Math.round(h*points[1]),end_x:Math.round(w*points[2]),end_y:Math.round(h*points[3]),duration:500});appendRecorded(data);applySnapshot(data);selectedId.value='';}catch(e:any){message.error(e?.message||'滑动操作失败');}finally{acting.value=false;}}
async function finishRecording(){if(!sessionId.value)return;if(!recordedSteps.value.length)return message.warning('请至少录制一个操作步骤');const id=sessionId.value;draftSaving.value=true;try{const draft=await AppTestAPI.finishInspectorRecording(id,{steps:recordedSteps.value});clearRecording(id);sessionId.value='';snapshot.value=null;selectedId.value='';message.success('App 用例草稿已生成');router.push({name:'case_app_case_edit',params:{id:draft.id}});}catch(e:any){message.error(e?.message||'用例草稿生成失败');}finally{draftSaving.value=false;}}
function openSave(){if(!selected.value||!activeCandidate.value)return;Object.assign(saveForm,{name:selected.value.text||selected.value.content_desc||selected.value.resource_id.split('/').pop()||'',page_name:'',activity:snapshot.value?.activity||'',locator_type:activeCandidate.value.type,locator_value:activeCandidate.value.value,description:''});saveVisible.value=true;}
async function saveElement(){if(!sessionId.value||!selected.value||!saveForm.name.trim()||!saveForm.locator_value.trim())return message.warning('请填写元素名称和定位表达式');saving.value=true;try{await AppTestAPI.saveInspectorElement(sessionId.value,{...saveForm,element_class:selected.value.class_name,snapshot:selected.value.attributes,fallback_locator:selected.value.candidates.filter((_,index)=>index!==activeCandidateIndex.value)});saveVisible.value=false;message.success('元素已保存到元素库');}catch(e:any){message.error(e?.message||'元素保存失败');}finally{saving.value=false;}}
async function releaseSilently(){const id=sessionId.value;if(!id)return;sessionId.value='';try{await AppTestAPI.closeInspector(id);}catch{/* 后端超时机制会继续释放 */}}

onMounted(async()=>{projects.value=asList(await projectApi.getDataList({pageSize:1000}));await restoreCurrentSession();});
onActivated(()=>{if(sessionId.value)void refresh();});
onBeforeUnmount(()=>{void releaseSilently();});
</script>

<style scoped lang="less">
.inspector-page{padding:24px 28px;min-width:0}.page-header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:18px}.page-header h2{margin:0;color:#1e293b}.page-header p{margin:8px 0 0;color:#7b8ba3}.connection-bar{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr)) auto;align-items:center;gap:12px;margin-bottom:16px}.workspace{display:grid;grid-template-columns:minmax(420px,1.12fr) minmax(420px,.88fr);gap:16px;margin-top:16px;min-height:680px}.panel-card{min-width:0;border:1px solid #e3e9f2;border-radius:12px;background:#fff;overflow:hidden}.panel-title{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:16px 18px;border-bottom:1px solid #edf1f6}.panel-title div{min-width:0;display:flex;flex-direction:column;gap:4px}.panel-title strong,.panel-title span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.panel-title span{font-size:12px;color:#7b8ba3}.screen-stage{display:flex;align-items:center;justify-content:center;min-height:570px;padding:20px;background:#eef2f7}.screen-wrap{position:relative;display:inline-block;max-width:100%;line-height:0;cursor:crosshair;box-shadow:0 10px 30px rgba(30,41,59,.18)}.screen-wrap img{display:block;max-width:100%;max-height:650px;object-fit:contain;user-select:none}.element-highlight{position:absolute;border:2px solid #3366ff;background:rgba(51,102,255,.16);pointer-events:none;box-sizing:border-box}.element-highlight span{position:absolute;left:-2px;bottom:100%;max-width:220px;padding:3px 6px;background:#3366ff;color:#fff;font-size:11px;line-height:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.screen-meta{display:flex;justify-content:space-between;gap:12px;padding:12px 16px;color:#7b8ba3;font-size:12px}.element-panel{display:flex;flex-direction:column}.element-search{padding:14px 16px;border-bottom:1px solid #edf1f6}.element-content{display:grid;grid-template-rows:minmax(250px,.9fr) minmax(360px,1.1fr);height:100%;min-height:0}.tree-area,.detail-area{min-height:0;padding:14px 16px;overflow:auto}.tree-area{border-bottom:1px solid #edf1f6}.section-label{margin-bottom:10px;color:#27364d;font-weight:600}.section-label span{margin-left:5px;color:#8b98aa;font-weight:400}.property-grid{display:grid;grid-template-columns:100px minmax(0,1fr);border:1px solid #e7ebf1;border-radius:8px;overflow:hidden}.property-grid>span,.property-grid>code{padding:8px 10px;border-bottom:1px solid #edf1f6}.property-grid>*:nth-last-child(-n+2){border-bottom:0}.property-grid>span{color:#718096;background:#f8fafc}.property-grid>code{overflow:hidden;color:#27364d;text-overflow:ellipsis;white-space:nowrap}.locator-title{margin-top:18px}.candidate-list{display:flex;flex-direction:column;gap:8px}.candidate{width:100%;padding:10px 12px;border:1px solid #e1e7ef;border-radius:8px;background:#fff;text-align:left;cursor:pointer}.candidate:hover,.candidate.active{border-color:#5b6df8;background:#f4f6ff}.candidate span{display:flex;align-items:center;justify-content:space-between;gap:8px}.candidate em{padding:1px 6px;border-radius:10px;font-size:11px;font-style:normal}.candidate em.high{color:#12805c;background:#e8f8f1}.candidate em.medium{color:#b66b00;background:#fff5df}.candidate em.low{color:#cf3f4f;background:#fff0f2}.candidate code{display:block;margin-top:5px;color:#607089;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.validation{margin-top:12px}.detail-actions{margin-top:14px}.empty-workspace{min-height:520px;margin-top:16px;border:1px dashed #d8e0ea;border-radius:12px;background:#fff}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 16px}
@media(max-width:1100px){.connection-bar{grid-template-columns:repeat(2,minmax(0,1fr))}.workspace{grid-template-columns:1fr}.screen-stage{min-height:480px}.element-content{height:700px}}
@media(max-width:640px){.inspector-page{padding:16px}.page-header{display:block}.page-header .n-space{margin-top:14px}.connection-bar{grid-template-columns:1fr}.workspace{grid-template-columns:1fr;min-height:0}.screen-stage{min-height:360px;padding:12px}.screen-wrap img{max-height:520px}.screen-meta{flex-direction:column}.element-content{height:auto;grid-template-rows:330px auto}.detail-area{max-height:none}.form-grid{grid-template-columns:1fr}}
.connection-bar{grid-template-columns:repeat(4,minmax(150px,1fr)) auto auto}.record-toolbar{display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid #e5eaf1;background:#f8fafc}.record-toolbar>span{margin-right:4px;color:#344054;font-size:12px;font-weight:650}.record-toolbar>em{min-width:0;margin-left:auto;overflow:hidden;color:#8a96a8;font-size:11px;font-style:normal;text-overflow:ellipsis;white-space:nowrap}.recorded-steps{margin-top:16px}.recorded-steps>header{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid #edf1f6}.recorded-steps>header>div{display:flex;gap:12px;align-items:baseline}.recorded-steps>header strong{color:#26344a}.recorded-steps>header span{color:#8a96a8;font-size:12px}.recorded-steps>header b{display:grid;width:28px;height:24px;border-radius:5px;color:#1769e8;background:#eaf2ff;place-items:center;font-size:12px}.recorded-step-list{display:flex;gap:8px;padding:12px 16px;overflow-x:auto}.recorded-step-list>div{display:grid;grid-template-columns:24px auto;gap:2px 8px;min-width:150px;padding:9px 11px;border:1px solid #e3e9f2;border-radius:7px;background:#fbfcfe}.recorded-step-list>div>span{grid-row:1/3;display:grid;width:24px;height:24px;border-radius:50%;color:#fff;background:#3979de;place-items:center;font-size:11px}.recorded-step-list strong{color:#344054;font-size:12px}.recorded-step-list em{max-width:170px;overflow:hidden;color:#8a96a8;font-size:11px;font-style:normal;text-overflow:ellipsis;white-space:nowrap}.recorded-steps>.n-empty{padding:22px}@media(max-width:1100px){.connection-bar{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){.connection-bar{grid-template-columns:1fr}.record-toolbar{align-items:stretch;flex-wrap:wrap}.record-toolbar>em{width:100%;margin-left:0;white-space:normal}}
.inspection-mode-switch{display:grid;grid-template-columns:auto auto;overflow:hidden;height:34px;border:1px solid #d8dee8;border-radius:6px;background:#f7f9fc}.inspection-mode-switch button{min-width:72px;padding:0 12px;border:0;border-right:1px solid #e1e6ee;color:#59677a;background:transparent;cursor:pointer;font-size:12px;transition:color .16s,background .16s,box-shadow .16s}.inspection-mode-switch button:last-child{min-width:96px;border-right:0}.inspection-mode-switch button:hover:not(:disabled){color:#246fd1;background:#eef5ff}.inspection-mode-switch button.active{position:relative;color:#fff;background:#4f6bed;box-shadow:0 1px 3px rgba(50,82,190,.24);font-weight:600}.inspection-mode-switch.disabled{opacity:.58}.inspection-mode-switch button:disabled{cursor:not-allowed}
.selected-action-bar{position:sticky;z-index:3;top:-14px;display:flex;gap:12px;align-items:center;justify-content:space-between;margin:-14px -16px 14px;padding:11px 14px;border-bottom:1px solid #dfe6ef;background:rgba(255,255,255,.96);box-shadow:0 4px 12px rgba(31,52,82,.06);backdrop-filter:blur(8px)}.selected-action-bar>div{display:grid;min-width:100px}.selected-action-bar>div span{color:#8a96a8;font-size:10px}.selected-action-bar>div strong{max-width:180px;overflow:hidden;color:#26344a;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.selected-action-bar :deep(.n-space){overflow-x:auto;padding-bottom:1px}.selected-action-bar :deep(.n-button){flex:none}@media(max-width:640px){.selected-action-bar{align-items:stretch;flex-direction:column}.selected-action-bar>div strong{max-width:100%}}
.element-panel>.selected-action-bar{position:relative;top:auto;flex:none;margin:0;padding:10px 14px;box-shadow:none}.element-panel>.element-content{height:auto;flex:1}
.inspection-status-tag{display:inline-flex;align-items:center;justify-content:center;height:32px;padding:0 10px;line-height:1}.inspection-status-tag :deep(.n-tag__content){display:flex;align-items:center;justify-content:center;height:100%;line-height:1}
</style>
