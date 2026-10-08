<template>
  <div class="element-editor-page">
    <header class="page-header">
      <div>
        <div class="breadcrumb"><span>App 测试</span><i>/</i><span>元素管理</span><i>/</i><strong>{{ dataId ? '编辑元素' : '新增元素' }}</strong></div>
        <h1>{{ dataId ? '编辑元素' : '新增元素' }}</h1>
        <p>维护元素归属与 Appium 定位配置</p>
      </div>
      <n-space><n-button @click="goBack">返回</n-button><n-button type="primary" :loading="saving" @click="submit">保存元素</n-button></n-space>
    </header>

    <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
      <section class="editor-card basic-card">
        <div class="card-heading"><h2>基本信息</h2><span>定义元素名称、应用与页面归属</span></div>
        <div class="basic-grid">
          <n-form-item label="元素名称" path="name"><n-input v-model:value="form.name" maxlength="96" placeholder="例如：登录按钮" /></n-form-item>
          <n-form-item label="所属项目" path="project"><n-select v-model:value="form.project" filterable :options="projectOptions" placeholder="请选择项目" @update:value="projectChanged" /></n-form-item>
          <n-form-item label="所属应用"><n-select v-model:value="form.application" clearable filterable :disabled="!form.project" :options="applicationOptions" placeholder="项目通用元素" @update:value="applicationChanged" /></n-form-item>
          <n-form-item label="所属模块"><n-select v-model:value="form.module" clearable filterable :disabled="!form.project" :options="moduleOptions" placeholder="未分组" /></n-form-item>
          <n-form-item label="页面名称"><n-input v-model:value="form.page_name" maxlength="128" placeholder="例如：登录页" /></n-form-item>
          <n-form-item label="Activity"><n-input v-model:value="form.activity" maxlength="255" placeholder="例如：.com.demo.LoginActivity" /></n-form-item>
          <n-form-item label="元素类型"><n-input v-model:value="form.element_class" maxlength="255" placeholder="例如：android.widget.Button" /></n-form-item>
        </div>
      </section>

      <div class="content-grid">
        <section class="editor-card locator-card">
          <div class="card-heading"><h2>定位配置</h2><span>配置元素的主定位表达式</span></div>
          <div class="locator-body">
            <div class="locator-method-row">
              <n-form-item label="定位方式" path="locator_type" :show-feedback="false"><n-select v-model:value="form.locator_type" :options="locatorOptions" /></n-form-item>
              <div class="method-summary"><span class="method-badge">{{ currentLocator?.short }}</span><span>{{ currentLocator?.description }}</span></div>
            </div>
            <n-form-item label="定位表达式" path="locator_value" class="expression-field">
              <div class="expression-panel">
                <div class="expression-toolbar"><div><span class="status-dot"></span><span>{{ currentLocator?.label }} 表达式</span></div><n-space size="small"><n-button size="small" @click="formatExpression">格式化</n-button><n-button size="small" type="primary" ghost @click="validateExpression">验证表达式</n-button></n-space></div>
                <div class="code-input"><span class="line-number">1</span><n-input v-model:value="form.locator_value" type="textarea" :autosize="{ minRows: 5, maxRows: 9 }" :placeholder="currentLocator?.placeholder" /></div>
                <div class="expression-help"><span class="help-icon">i</span><span>{{ currentLocator?.tip }}</span></div>
              </div>
            </n-form-item>
            <n-form-item label="描述"><n-input v-model:value="form.description" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" maxlength="300" show-count placeholder="记录元素用途或定位注意事项（选填）" /></n-form-item>
          </div>
        </section>
        <aside class="side-column">
          <section class="editor-card strategy-card">
            <div class="card-heading"><h2>支持的定位方式</h2></div>
            <div class="strategy-list">
              <button v-for="item in locatorOptions" :key="item.value" type="button" :class="['strategy-item', { active: form.locator_type === item.value }]" @click="form.locator_type = item.value">
                <span class="strategy-code">{{ item.short }}</span><span><strong>{{ item.label }}</strong><small>{{ item.description }}</small></span><i v-if="form.locator_type === item.value">当前</i>
              </button>
            </div>
          </section>
          <div class="locator-advice">建议优先使用 Accessibility ID 或 Resource ID；XPath 层级越深，页面变化后越容易失效。</div>
        </aside>
      </div>
    </n-form>
  </div>
</template>

<script setup lang="ts">
import { asList } from '@/utils/list';

import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useMessage } from 'naive-ui';
import { ModuleAPI, ProjectAPI } from '@/api/project/http';
import type { Module } from '@/api/project/models';
import { AppTestAPI, type AppApplication, type AppElement } from '@/api/case_app/http';

const route = useRoute();
const router = useRouter();
const message = useMessage();
const dataId = Number(route.params.id) || 0;
const projectApi = new ProjectAPI();
const moduleApi = new ModuleAPI();
const formRef = ref<any>();
const saving = ref(false);
const projects = ref<any[]>([]);
const applications = ref<AppApplication[]>([]);
// 模块是项目级共享数据，与接口管理、UI 元素管理同源。
const modules = ref<Module[]>([]);
const form = reactive<AppElement>({ project: null, application: null, module: null, name: '', page_name: '', activity: '', locator_type: 'id', locator_value: '', fallback_locator: [], element_class: '', snapshot: {}, description: '' });

const locatorOptions = [
  { label: 'Accessibility ID', value: 'accessibility id', short: 'A11Y', description: '使用 content-desc 语义定位', placeholder: 'login_button', tip: '填写元素 content-desc，通常稳定且执行速度快。' },
  { label: 'Resource ID', value: 'id', short: 'ID', description: '使用 Android resource-id', placeholder: 'com.demo:id/login', tip: '可填写完整 resource-id，例如 com.demo:id/login。' },
  { label: '文本', value: 'text', short: 'TXT', description: '按元素可见文本定位', placeholder: '登录', tip: '文案变化或多语言环境下可能失效。' },
  { label: 'UIAutomator', value: '-android uiautomator', short: 'UIA', description: '使用 Android UIAutomator 表达式', placeholder: 'new UiSelector().text("登录")', tip: '适合组合属性、滚动和原生 Android 复杂定位。' },
  { label: 'XPath', value: 'xpath', short: '/', description: '使用 XML 节点路径', placeholder: '//android.widget.Button[@text="登录"]', tip: '避免使用过深的绝对路径，优先使用属性组合。' },
  { label: '坐标', value: 'coordinate', short: 'XY', description: '使用屏幕绝对坐标', placeholder: '540,1200', tip: '坐标仅建议用于暂无稳定元素树的场景，不同分辨率可能失效。' },
  { label: 'OCR 文字', value: 'ocr_text', short: 'OCR', description: '从设备截图精确识别文字', placeholder: '登录', tip: '只需填写页面可见文字，系统会识别文字区域并操作中心点。' },
  { label: '图像文字', value: 'image_text', short: 'IMG', description: '从画面中模糊识别文字', placeholder: '立即购买', tip: '只需填写目标文字，适合 Canvas、图片或元素树不可见的内容。' },
];
const currentLocator = computed(() => locatorOptions.find((item) => item.value === form.locator_type));
const projectOptions = computed(() => projects.value.map((item) => ({ label: item.name, value: Number(item.id) })));
const applicationOptions = computed(() => applications.value.filter((item) => item.project === form.project).map((item) => ({ label: item.name, value: Number(item.id) })));
const moduleOptions = computed(() => modules.value.filter((item) => item.project === form.project).map((item) => ({ label: item.name, value: Number(item.id) })));
const rules = { project: { required: true, type: 'number', message: '请选择项目', trigger: 'change' }, name: { required: true, message: '请输入元素名称', trigger: 'blur' }, locator_type: { required: true, message: '请选择定位方式', trigger: 'change' }, locator_value: { required: true, message: '请输入定位表达式', trigger: 'blur' } };
function projectChanged() { if (!applicationOptions.value.some((item) => item.value === form.application)) form.application = null; if (!moduleOptions.value.some((item) => item.value === form.module)) form.module = null; }
function applicationChanged() { /* 模块按项目共享，切换应用不影响可选模块。 */ }
function formatExpression() { form.locator_value = String(form.locator_value || '').trim(); }
function validateExpression() {
  const value = String(form.locator_value || '').trim();
  if (!value) return message.warning('请先填写定位表达式');
  if (form.locator_type === 'coordinate' && !/^\d+\s*,\s*\d+$/.test(value)) return message.error('坐标格式应为 x,y');
  if (form.locator_type === 'xpath' && !/^(\/\/|\.|\/)/.test(value)) return message.error('XPath 表达式格式不正确');
  message.success('表达式格式校验通过');
}
function goBack() { router.push({ name: 'case_app_element' }); }
async function load() {
  const [projectResult, appResult, moduleResult] = await Promise.all([projectApi.getDataList({ pageSize: 1000 }), AppTestAPI.applications({ pageSize: 1000 }), moduleApi.getDataList({ pageSize: 1000 })]);
  projects.value = asList(projectResult); applications.value = asList(appResult); modules.value = asList(moduleResult);
  if (dataId) Object.assign(form, await AppTestAPI.element(dataId));
  else { form.project = Number(route.query.project) || null; form.application = Number(route.query.application) || null; form.module = Number(route.query.module) || null; }
}
async function submit() {
  try {
    await formRef.value?.validate(); saving.value = true;
    await AppTestAPI.saveElement({ ...form, name: form.name.trim(), locator_value: form.locator_value.trim() });
    message.success('元素保存成功'); goBack();
  } catch (error: any) { if (error?.message) message.error(error.message || '保存失败，请检查配置'); }
  finally { saving.value = false; }
}
onMounted(load);
</script>

<style scoped lang="less">
.element-editor-page{min-height:100%;padding:20px 28px 36px;background:#f6f8fb;color:#172033}.page-header{display:flex;align-items:flex-end;justify-content:space-between;max-width:1440px;margin:0 auto 18px}.breadcrumb{display:flex;gap:9px;align-items:center;margin-bottom:13px;color:#7b8798;font-size:13px}.breadcrumb i{color:#aab3c0;font-style:normal}.breadcrumb strong{color:#344054}.page-header h1{margin:0;font-size:27px;font-weight:700;letter-spacing:-.4px}.page-header p{margin:7px 0 0;color:#758297;font-size:13px}.page-header :deep(.n-button){min-width:108px;height:40px}.editor-card{overflow:hidden;border:1px solid #dce3ed;border-radius:9px;background:#fff}.basic-card{max-width:1440px;margin:0 auto 14px}.card-heading{display:flex;gap:16px;align-items:baseline;min-height:58px;padding:17px 20px;box-sizing:border-box;border-bottom:1px solid #edf1f5}.card-heading h2{margin:0;color:#202b3d;font-size:17px;font-weight:650}.card-heading span{color:#8a96a8;font-size:12px}.basic-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 20px;padding:18px 20px 4px}.content-grid{display:grid;grid-template-columns:minmax(0,2.2fr) minmax(310px,.8fr);gap:14px;max-width:1440px;margin:0 auto}.locator-body{padding:20px 22px 24px}.locator-method-row{display:grid;grid-template-columns:minmax(240px,360px) minmax(0,1fr);gap:18px;align-items:end;padding-bottom:20px;border-bottom:1px solid #edf1f5}.locator-method-row :deep(.n-form-item){margin-bottom:0}.method-summary{display:flex;gap:10px;align-items:center;min-height:34px;color:#7b8798;font-size:12px}.method-badge{padding:4px 9px;border:1px solid #ccdafd;border-radius:5px;background:#f2f6ff;color:#2f64e8;font-family:ui-monospace,monospace;font-weight:650}.expression-field{margin-top:18px}.expression-panel{width:100%;overflow:hidden;border:1px solid #dce3ed;border-radius:7px}.expression-toolbar{display:flex;align-items:center;justify-content:space-between;min-height:45px;padding:0 12px;background:#f8fafc;color:#5b687b;font-size:12px}.expression-toolbar>div{display:flex;gap:8px;align-items:center}.status-dot{width:7px;height:7px;border-radius:50%;background:#17a66b}.code-input{display:grid;grid-template-columns:52px 1fr;overflow:hidden;border-top:1px solid #2e3746;background:#202733}.line-number{padding-top:13px;border-right:1px solid #364052;color:#8290a5;font-family:ui-monospace,monospace;text-align:center}.code-input :deep(.n-input){--n-border:none!important;--n-border-hover:none!important;--n-border-focus:none!important;--n-box-shadow-focus:none!important;--n-color:#202733!important;--n-color-hover:#202733!important;--n-color-focus:#202733!important;--n-text-color:#dce7f7!important;--n-caret-color:#7da2ff!important;border-radius:0}.expression-help{display:flex;gap:8px;padding:10px 12px;color:#7b8798;background:#f8fafc;font-size:12px;line-height:1.5}.help-icon{display:grid;flex:none;width:17px;height:17px;border-radius:50%;color:#fff;background:#8290a5;place-items:center;font-size:11px}.side-column{display:grid;align-content:start;gap:12px}.strategy-list{padding:9px}.strategy-item{display:grid;grid-template-columns:40px minmax(0,1fr) auto;gap:10px;align-items:center;width:100%;padding:10px;border:1px solid transparent;border-radius:6px;color:#344054;text-align:left;background:#fff;cursor:pointer}.strategy-item:hover{background:#f8faff}.strategy-item.active{border-color:#bfd4fa;background:#f4f8ff}.strategy-code{display:grid;width:36px;height:30px;border-radius:5px;color:#2563d9;background:#eaf2ff;place-items:center;font:650 11px ui-monospace,monospace}.strategy-item>span:nth-child(2){display:grid;gap:2px}.strategy-item strong{font-size:13px}.strategy-item small{color:#8793a5;font-size:11px}.strategy-item i{color:#2475ef;font-size:11px;font-style:normal}.locator-advice{padding:13px 15px;border:1px solid #d8e5f8;border-radius:7px;color:#61718a;background:#f6f9fe;font-size:12px;line-height:1.65}@media(max-width:900px){.page-header{align-items:flex-start;gap:16px;flex-direction:column}.basic-grid,.content-grid{grid-template-columns:1fr}.locator-method-row{grid-template-columns:1fr}.element-editor-page{padding:16px}}
</style>
