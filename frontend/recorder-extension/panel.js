let recording=false,paused=false,apiEntries=[],uiEvents=[],pollTimer=null,pullingEvents=false;
const recorderVersion='3.6.0';
const $=id=>document.getElementById(id),settingsKey='autotest-recorder-settings-v2';
const injection=`(()=>{
  const recorderVersion='${recorderVersion}';
  if(window.__autotestUiRecorderInstalled===recorderVersion)return true;
  window.__autotestUiRecorderInstalled=recorderVersion;
  window.__autotestUiRecorderEvents=window.__autotestUiRecorderEvents||[];
  const persistedQueueKey='__autotestUiRecorderPersistedEventsV1';
  const clean=v=>String(v||'').replace(/\\s+/g,' ').trim().slice(0,512);
  const esc=v=>window.CSS&&CSS.escape?CSS.escape(v):String(v).replace(/[^a-zA-Z0-9_-]/g,'\\\\$&');
  const visible=e=>{if(!e)return false;const s=getComputedStyle(e),b=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&b.width>0&&b.height>0};
  const nearbyLabelsFor=e=>{
    const control=e.getBoundingClientRect();
    if(!control.width||!control.height)return'';
    const candidates=[...document.querySelectorAll('label,[data-slot="form-label"],.form-label,dt,strong,b,span,p,div')]
      .map(item=>{
        if(item===e||item.contains(e)||e.contains(item)||!visible(item))return null;
        const text=clean(item.innerText||item.textContent),box=item.getBoundingClientRect();
        if(!text||text.length>80||box.width>Math.max(control.width*1.8,520))return null;
        const vertical=control.top-box.bottom;
        const horizontalGap=Math.max(0,Math.max(box.left,control.left)-Math.min(box.right,control.right));
        const overlapsHorizontally=box.right>=control.left-24&&box.left<=control.right+24;
        if(vertical>130||vertical<-42||(!overlapsHorizontally&&horizontalGap>140))return null;
        const belowPenalty=vertical<0?34:0;
        const distance=Math.abs(vertical)+(horizontalGap*.45)+belowPenalty;
        return{text,distance,vertical,horizontalGap};
      })
      .filter(Boolean)
      .sort((a,b)=>a.distance-b.distance||a.text.length-b.text.length);
    return candidates.slice(0,6);
  };
  const nearbyLabelFor=e=>nearbyLabelsFor(e)[0]?.text||'';
  const labelFor=e=>{
    if(!e)return'';
    if(e.labels&&e.labels[0])return clean(e.labels[0].innerText||e.labels[0].textContent);
    const wrapped=e.closest('label');if(wrapped)return clean(wrapped.innerText||wrapped.textContent);
    if(e.id){const linked=document.querySelector('label[for="'+esc(e.id)+'"]');if(linked)return clean(linked.innerText||linked.textContent)}
    const labelledBy=e.getAttribute('aria-labelledby');
    if(labelledBy){const linked=document.getElementById(labelledBy.split(/\\s+/)[0]);if(linked)return clean(linked.innerText||linked.textContent)}
    const nearby=nearbyLabelFor(e);if(nearby)return nearby;
    let current=e.parentElement;
    for(let depth=0;current&&depth<4;depth+=1,current=current.parentElement){
      const labels=[...current.querySelectorAll(':scope > label,:scope > .form-label,:scope > [data-slot="form-label"],:scope > dt,:scope > strong')]
        .filter(item=>item!==e&&visible(item));
      if(labels.length===1){const text=clean(labels[0].innerText||labels[0].textContent);if(text&&text.length<=80)return text}
      let previous=current.previousElementSibling;
      while(previous){const text=clean(previous.innerText||previous.textContent);if(visible(previous)&&text&&text.length<=80)return text;previous=previous.previousElementSibling}
    }
    return'';
  };
  const roleFor=e=>{const r=e.getAttribute('role');if(r)return r;const t=e.tagName.toLowerCase();if(t==='button')return'button';if(t==='a'&&e.href)return'link';if(t==='select')return'combobox';if(t==='textarea')return'textbox';if(t==='input'){const type=String(e.type||'').toLowerCase();if(['button','submit','reset','image'].includes(type))return'button';return['checkbox','radio'].includes(type)?type:'textbox'}if(t==='option')return'option';return''};
  const cssFor=e=>{
    if(e.id)return'#'+esc(e.id);
    const test=e.getAttribute('data-testid');if(test)return'[data-testid="'+String(test).replace(/"/g,'\\\\"')+'"]';
    if(e.name)return e.tagName.toLowerCase()+'[name="'+String(e.name).replace(/"/g,'\\\\"')+'"]';
    const parts=[];let current=e;
    for(let depth=0;current&&current.nodeType===1&&depth<5;depth+=1,current=current.parentElement){
      if(current.id){parts.unshift('#'+esc(current.id));break}
      let part=current.tagName.toLowerCase();
      const type=current.getAttribute('type');if(type)part+='[type="'+String(type).replace(/"/g,'\\\\"')+'"]';
      const siblings=current.parentElement?[...current.parentElement.children].filter(item=>item.tagName===current.tagName):[];
      if(siblings.length>1)part+=':nth-of-type('+(siblings.indexOf(current)+1)+')';
      parts.unshift(part);
    }
    return parts.join(' > ');
  };
  const normalizeElement=raw=>{
    const e0=raw&&raw.nodeType===3?raw.parentElement:raw;if(!e0||!e0.tagName)return{};
    const selector='button,a,input,textarea,select,[role="button"],[role="link"],[role="checkbox"],[role="combobox"],[role="option"],[role="menuitem"],[data-radix-collection-item],[data-slot="select-item"],[contenteditable="true"]';
    return e0.closest(selector)||e0;
  };
  const describe=raw=>{
    const e=normalizeElement(raw);if(!e||!e.tagName)return{};
    const tag=e.tagName.toLowerCase(),type=String(e.type||'').toLowerCase(),role=roleFor(e);
    const actionable=['button','a'].includes(tag)||['button','link','menuitem','option','tab'].includes(role)||['button','submit','reset','image'].includes(type);
    const text=clean(e.innerText||e.textContent),value=['button','submit','reset'].includes(type)?clean(e.value):'';
    return{tag,type,role,id:e.id||'',name:e.getAttribute('name')||'',testId:e.getAttribute('data-testid')||'',ariaLabel:e.getAttribute('aria-label')||'',title:e.getAttribute('title')||'',placeholder:e.getAttribute('placeholder')||'',label:actionable?'':labelFor(e),nearbyLabels:nearbyLabelsFor(e),text,value,css:cssFor(e)};
  };
  const persist=event=>{
    try{
      const stored=JSON.parse(localStorage.getItem(persistedQueueKey)||'[]');
      const events=Array.isArray(stored)?stored:[];
      events.push(event);
      localStorage.setItem(persistedQueueKey,JSON.stringify(events.slice(-500)));
    }catch(_){}
  };
  const emit=(action,element,extra={})=>{
    const timestamp=Date.now();
    const described=describe(element);
    const actionable=action==='click'&&(['button','a'].includes(described.tag)||['button','link','menuitem','option','tab'].includes(described.role)||['button','submit','reset','image'].includes(described.type));
    const target=actionable?[described.text,described.value,described.ariaLabel,described.title,described.name,described.id].find(Boolean)||'':undefined;
    const event={eventId:timestamp+'-'+Math.random().toString(36).slice(2),action,timestamp,url:location.href,tabKey:window.name||'tab-1',recorderVersion,element:described,...(target?{target}:{}),...extra};
    window.__autotestUiRecorderEvents.push(event);
    persist(event);
    window.postMessage({source:'autotest-ui-recorder',type:'event',event},'*');
    return event;
  };
  let lastPointerElement=null,lastPointerAt=0,lastSubmitAt=0;
  document.addEventListener('pointerdown',e=>{
    if(e.button!==0)return;
    lastPointerElement=normalizeElement(e.target);lastPointerAt=Date.now();
    emit('click',lastPointerElement);
  },true);
  document.addEventListener('click',e=>{
    const element=normalizeElement(e.target);
    if(element===lastPointerElement&&Date.now()-lastPointerAt<1000)return;
    emit('click',element);
  },true);
  document.addEventListener('submit',e=>{
    const now=Date.now();
    if(now-lastSubmitAt<1000)return;
    lastSubmitAt=now;
    const submitter=e.submitter||e.target.querySelector?.('button[type="submit"],input[type="submit"],button:not([type])')||e.target;
    emit('click',submitter,{trigger:'submit'});
  },true);
  document.addEventListener('input',e=>{const el=e.target,value=el.type==='password'?'\${password}':el.value;emit(el.type==='file'?'upload':'input',el,{value})},true);
  document.addEventListener('change',e=>{const el=e.target;if(el.tagName==='SELECT')emit('select',el,{value:el.value,text:clean(el.selectedOptions?.[0]?.textContent)});else if(['checkbox','radio'].includes(el.type))emit('check',el,{checked:el.checked})},true);
  return true;
})()`;
const mode=()=>$('mode').value;
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const evaluate=expression=>new Promise(resolve=>chrome.devtools.inspectedWindow.eval(expression,(_result,error)=>resolve(!error)));
const evaluateResult=expression=>new Promise(resolve=>chrome.devtools.inspectedWindow.eval(expression,(result,error)=>resolve(error?null:result)));
const installCapture=()=>evaluate(injection);
function appendUiEvents(events){
  if(!Array.isArray(events)||!events.length)return false;
  const known=new Set(uiEvents.map(item=>item?.eventId).filter(Boolean));
  const identity=item=>{const e=item?.element||{};return e.css||e.testId||e.id||e.name||[e.tag,e.type,e.role,e.text,e.value,e.ariaLabel].join('|')};
  let changed=false;
  events.forEach(item=>{
    const eventId=item?.eventId;
    if(eventId&&known.has(eventId))return;
    const timestamp=Number(item?.timestamp||0);
    const sameInteractionIndex=uiEvents.findLastIndex(existing=>
      existing?.action===item?.action&&
      Math.abs(Number(existing?.timestamp||0)-timestamp)<=80&&
      identity(existing)===identity(item)&&
      String(existing?.value??'')===String(item?.value??'')
    );
    if(sameInteractionIndex>=0){
      const existing=uiEvents[sameInteractionIndex];
      if(item?.recorderVersion===recorderVersion&&existing?.recorderVersion!==recorderVersion){uiEvents[sameInteractionIndex]=item;changed=true}
      if(eventId)known.add(eventId);
      return;
    }
    const sameActionIndex=uiEvents.findLastIndex(existing=>
      existing?.action===item?.action&&
      Math.abs(Number(existing?.timestamp||0)-timestamp)<=80
    );
    if(item?.recorderVersion===recorderVersion&&sameActionIndex>=0&&uiEvents[sameActionIndex]?.recorderVersion!==recorderVersion){
      uiEvents[sameActionIndex]=item;
      changed=true;
      if(eventId)known.add(eventId);
      return;
    }
    if(item?.recorderVersion!==recorderVersion&&sameActionIndex>=0&&uiEvents[sameActionIndex]?.recorderVersion===recorderVersion){
      if(eventId)known.add(eventId);
      return;
    }
    if(eventId)known.add(eventId);
    const previous=uiEvents[uiEvents.length-1];
    const duplicateSubmit=item?.action==='click'&&item?.trigger==='submit'&&previous?.action==='click'&&identity(item)===identity(previous)&&Math.abs(Number(item.timestamp||0)-Number(previous.timestamp||0))<1500;
    if(duplicateSubmit)uiEvents[uiEvents.length-1]=item;else uiEvents.push(item);
    changed=true;
  });
  return changed;
}
const recorderMessage=message=>new Promise(resolve=>chrome.runtime.sendMessage({...message,tabId:chrome.devtools.inspectedWindow.tabId},response=>resolve(chrome.runtime.lastError?null:response)));
async function pullBridgeEvents(){
  const response=await recorderMessage({type:'AUTOTEST_RECORDER_DRAIN'});
  const events=Array.isArray(response?.events)?response.events:[];
  const current=events.filter(item=>item?.recorderVersion===recorderVersion);
  return appendUiEvents(current.length?current:events);
}
async function clearBridgeEvents(){await recorderMessage({type:'AUTOTEST_RECORDER_CLEAR'})}
async function pullEvents(){
  if(!recording||paused||mode()!=='ui'||pullingEvents)return false;
  pullingEvents=true;
  try{
    if(!await installCapture())return false;
    let changed=await pullBridgeEvents();
    const result=await evaluateResult(`(()=>{const key='__autotestUiRecorderPersistedEventsV1',q=window.__autotestUiRecorderEvents||[];let persisted=[];try{persisted=JSON.parse(localStorage.getItem(key)||'[]');localStorage.removeItem(key)}catch(_){}return q.splice(0,q.length).concat(Array.isArray(persisted)?persisted:[])})()`);
    if(Array.isArray(result)&&result.length){
      const current=result.filter(item=>item?.recorderVersion==='${recorderVersion}');
      changed=appendUiEvents(current.length?current:result)||changed;
    }
    if(changed)render();
    return true;
  }finally{
    pullingEvents=false;
  }
}
async function recordNavigation(url){if(!recording||paused||mode()!=='ui'||!url)return;await pullBridgeEvents();const previous=uiEvents[uiEvents.length-1];if(!previous||previous.action!=='navigate'||previous.url!==url)uiEvents.push({eventId:'navigate-'+Date.now()+'-'+url,action:'navigate',url,value:url,timestamp:Date.now(),tabKey:'tab-1'});await installCapture();render()}
chrome.devtools.network.onNavigated.addListener(recordNavigation);
chrome.devtools.network.onRequestFinished.addListener(request=>{if(!recording||paused||mode()!=='api')return;request.getContent(body=>{const data=request.request||{},response=request.response||{};apiEntries.push({_id:`${Date.now()}-${apiEntries.length}`,request:{method:data.method,url:data.url,headers:data.headers||[],postData:data.postData||{}},response:{status:response.status,content:{text:body||''}},time:request.time||0});render()})});
const currentItems=()=>mode()==='ui'?uiEvents:apiEntries;
function selected(){const items=currentItems();return[...document.querySelectorAll('input[data-index]:checked')].map(item=>items[Number(item.dataset.index)]).filter(Boolean)}
function recordedTarget(item){
  const e=item?.element||{};
  if(item?.action==='navigate')return item.url||item.value||'页面地址';
  const tag=String(e.tag||'').toLowerCase(),role=String(e.role||'').toLowerCase(),type=String(e.type||'').toLowerCase();
  const ownControl=item?.action==='click'&&(['button','a'].includes(tag)||['button','link','menuitem','option','tab'].includes(role)||['button','submit','reset','image'].includes(type));
  const values=ownControl
    ?[e.text,e.value,e.ariaLabel,e.title,item.target,e.name,e.id]
    :[e.label,e.ariaLabel,e.placeholder,e.text,e.value,e.name,e.id];
  return values.find(value=>String(value||'').trim())||item.url||'页面元素';
}
function render(){const items=currentItems();$('count').textContent=`${items.length} 条`;$('table-head').innerHTML=mode()==='ui'?'<tr><th>保留</th><th>#</th><th>操作</th><th>元素 / 地址</th><th>操作值</th></tr>':'<tr><th>保留</th><th>方法</th><th>请求</th><th>状态</th><th>耗时</th></tr>';if(!items.length){$('rows').innerHTML='<tr><td colspan="5" class="empty">点击“开始录制”后操作业务页面。</td></tr>';return}$('rows').innerHTML=items.map((item,index)=>{if(mode()==='api'){const r=item.request||{},s=item.response||{};return`<tr><td><input type="checkbox" data-index="${index}" checked></td><td class="method ${escapeHtml(r.method)}">${escapeHtml(r.method)}</td><td class="url" title="${escapeHtml(r.url)}">${escapeHtml(r.url)}</td><td>${escapeHtml(s.status||'-')}</td><td>${Math.round(item.time||0)} ms</td></tr>`}const e=item.element||{},target=recordedTarget(item),labels={navigate:'打开页面',click:'点击',input:'输入文本',select:'选择下拉项',check:'勾选',upload:'上传文件'},value=e.type==='password'?'已转为 ${password}':(item.value||'');return`<tr><td><input type="checkbox" data-index="${index}" checked></td><td>${index+1}</td><td><span class="action-tag">${escapeHtml(labels[item.action]||item.action)}</span></td><td class="url" title="${escapeHtml(target)}">${escapeHtml(target)}</td><td class="url">${escapeHtml(value)}</td></tr>`}).join('')}
function download(name,content){const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([content],{type:'application/json'}));link.download=name;link.click();URL.revokeObjectURL(link.href)}
const normalizeToken=value=>String(value||'').trim().replace(/^(Token|Bearer)\s+/i,'').trim();
const getPlatformToken=platform=>new Promise(resolve=>chrome.runtime.sendMessage({type:'AUTOTEST_RECORDER_GET_PLATFORM_TOKEN',platform},response=>resolve(chrome.runtime.lastError?'':normalizeToken(response?.token))));
async function resolveToken(platform){
  const discovered=await getPlatformToken(platform);
  const token=discovered||normalizeToken($('token').value);
  if(!token)throw Error('未获取到登录凭证。请先在该平台地址登录，或填写登录 Token。');
  $('token').value=token;
  return token;
}
async function authHeaders(platform){return{'Content-Type':'application/json','Authorization':`Token ${await resolveToken(platform)}`}}
async function previewCode(){if(mode()!=='ui'||!uiEvents.length||!$('platform').value)return;try{const platform=$('platform').value;const response=await fetch(platform.replace(/\/$/,'')+'/api/case_ui/playwright-case/preview-recording/',{method:'POST',headers:await authHeaders(platform),body:JSON.stringify({events:selected()})}),data=await response.json();if(response.ok)$('code-preview').textContent=(data.result||data).code||''}catch(_){}}
$('start').onclick=async()=>{recording=true;paused=false;$('start').disabled=true;$('pause').disabled=false;$('stop').disabled=false;$('mode').disabled=true;if(mode()==='ui'){await clearBridgeEvents();if(!await installCapture()){recording=false;$('start').disabled=false;$('pause').disabled=true;$('stop').disabled=true;$('mode').disabled=false;alert('录制脚本未能注入当前页面，请刷新业务页面并重新开始录制。');return}chrome.devtools.inspectedWindow.eval('location.href',url=>recordNavigation(url));pollTimer=setInterval(pullEvents,150)}};
$('pause').onclick=()=>{paused=!paused;$('pause').textContent=paused?'继续':'暂停'};
$('stop').onclick=async()=>{if(mode()==='ui')await pullEvents();recording=false;paused=false;clearInterval(pollTimer);pollTimer=null;$('start').disabled=false;$('pause').disabled=true;$('pause').textContent='暂停';$('stop').disabled=true;$('mode').disabled=false;await previewCode()};
$('clear').onclick=()=>{apiEntries=[];uiEvents=[];clearBridgeEvents();chrome.devtools.inspectedWindow.eval(`(()=>{window.__autotestUiRecorderEvents=[];try{localStorage.removeItem('__autotestUiRecorderPersistedEventsV1')}catch(_){}return true})()`);$('code-preview').textContent='停止录制后可生成代码预览。';render()};
$('mode').onchange=()=>{updateMode();render()};
$('copy').onclick=async()=>{try{await navigator.clipboard.writeText(JSON.stringify(mode()==='ui'?{events:selected()}:{records:selected()},null,2));alert('已复制录制数据。')}catch(_){alert('复制失败，请使用下载。')}};
$('download').onclick=()=>download(mode()==='ui'?'ui-recording.json':'api-recording.har',JSON.stringify(mode()==='ui'?{events:selected()}:{log:{version:'1.2',creator:{name:'Automation Test Platform Recorder',version:'2.0'},entries:selected()}},null,2));
function updateMode(){const ui=mode()==='ui';$('module-field').classList.toggle('hidden',ui);$('conflict-field').classList.toggle('hidden',ui);$('case-name-field').classList.toggle('hidden',!ui);$('environment-field').classList.toggle('hidden',!ui);$('code-section').classList.toggle('hidden',!ui);$('push').textContent=ui?'生成智能 UI 用例':'推送已选接口';$('recording-tip').textContent=ui?'UI 模式会记录当前 DevTools 所属页面的点击、输入、下拉和勾选操作。':'接口模式会记录当前页面完成的网络请求。'}
async function saveSettings(){const ids=['platform','token','project','module','conflict','caseName','environment','mode'],settings=Object.fromEntries(ids.map(id=>[id,$(id).value]));await chrome.storage.local.set({[settingsKey]:settings});return settings}
async function loadSettings(){const value=(await chrome.storage.local.get(settingsKey))[settingsKey]||{};['platform','token','project','module','conflict','caseName','environment','mode'].forEach(id=>{if(value[id]!==undefined)$(id).value=value[id]});updateMode();render()}
$('push').onclick=async()=>{const settings=await saveSettings();if(!settings.platform||!settings.project)return alert('请填写平台地址和项目 ID。');if(!selected().length)return alert('没有可推送的录制内容。');try{const headers=await authHeaders(settings.platform);if(mode()==='ui'){const response=await fetch(settings.platform.replace(/\/$/,'')+'/api/case_ui/playwright-case/import-recording/',{method:'POST',headers,body:JSON.stringify({project:Number(settings.project),name:settings.caseName,environment_name:settings.environment,events:selected()})}),data=await response.json();if(!response.ok)throw Error(data.detail||data.message||JSON.stringify(data.result||data));const result=data.result||data;$('code-preview').textContent=result.code||'';alert(`已生成智能 UI 用例：${result.name||settings.caseName}`)}else{if(!settings.module)return alert('接口录制需填写模块 ID。');const base=settings.platform.replace(/\/$/,'')+'/api/case_api/recording/',parsed=await fetch(base+'parse/',{method:'POST',headers,body:JSON.stringify({records:selected()})}),parsedJson=await parsed.json();if(!parsed.ok)throw Error(parsedJson.detail||'解析失败');const response=await fetch(base+'import_records/',{method:'POST',headers,body:JSON.stringify({project:Number(settings.project),module:Number(settings.module),conflict_mode:settings.conflict,records:(parsedJson.result||parsedJson).records||[]})}),data=await response.json();if(!response.ok)throw Error(data.detail||data.message||JSON.stringify(data.result||data));alert('已推送至平台。')}}catch(error){alert(`推送失败：${error.message}`)}};
loadSettings();
