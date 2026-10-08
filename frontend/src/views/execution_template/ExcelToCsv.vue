<template>
  <section class="csv-tool">
    <header><h3>Excel 转 CSV</h3><p>上传 Excel，选择工作表后下载 CSV。文件仅在当前浏览器中处理。</p></header>
    <label class="file-picker">
      <strong>{{ loading ? '正在读取文件…' : '选择 Excel 文件' }}</strong>
      <span>支持 .xlsx、.xls，最大 20 MB</span>
      <input type="file" accept=".xlsx,.xls" :disabled="loading" @change="readFile" />
    </label>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <template v-if="workbook">
      <p class="file-name">{{ fileName }}</p>
      <div class="options">
        <label for="csv-sheet">工作表</label>
        <n-select id="csv-sheet" v-model:value="sheetName" :options="sheetOptions" aria-label="选择工作表" />
        <n-checkbox v-model:checked="withBom">兼容 Excel 中文（UTF-8 BOM）</n-checkbox>
      </div>
      <p class="hint">每个 CSV 对应一个工作表。导出单元格显示值，不保留样式；公式使用文件中已保存的计算结果，请先在 Excel 中计算并保存。</p>
      <div class="actions">
        <n-button type="primary" :disabled="!csv" @click="download">下载 CSV</n-button>
        <n-button @click="clear">清空</n-button>
        <span v-if="!csv">当前工作表为空</span>
      </div>
      <label class="preview-label">CSV 预览（最多 5,000 字符，下载包含完整内容）</label>
      <n-input :value="csv.slice(0, 5000)" type="textarea" readonly :autosize="{ minRows: 10, maxRows: 16 }" aria-label="CSV 预览" />
    </template>
  </section>
</template>

<script setup lang="ts">
  import { computed, ref, shallowRef } from 'vue';
  import type { WorkBook } from 'xlsx';

  const workbook = shallowRef<WorkBook | null>(null);
  const converter = shallowRef<typeof import('xlsx') | null>(null);
  const fileName = ref('');
  const sheetName = ref('');
  const loading = ref(false);
  const error = ref('');
  const withBom = ref(true);
  const sheetOptions = computed(() => (workbook.value?.SheetNames || []).map((name) => ({ label: name, value: name })));
  const csv = computed(() => {
    const sheet = workbook.value?.Sheets[sheetName.value];
    if (!sheet || !converter.value) return '';
    return converter.value.utils.sheet_to_csv(sheet, { FS: ',', RS: '\r\n', blankrows: true });
  });

  function clear() {
    workbook.value = null;
    fileName.value = '';
    sheetName.value = '';
    error.value = '';
  }

  async function readFile(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    clear();
    if (!/\.(xlsx|xls)$/i.test(file.name)) { error.value = '请选择 .xlsx 或 .xls 文件'; return; }
    if (file.size > 20 * 1024 * 1024) { error.value = '文件超过 20 MB，请拆分后重试'; return; }
    loading.value = true;
    try {
      const xlsx = await import('xlsx');
      const bytes = new Uint8Array(await file.arrayBuffer());
      // Reject renamed text files: supported Excel formats are ZIP or OLE containers.
      const zip = bytes[0] === 0x50 && bytes[1] === 0x4b;
      const ole = [0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1].every((b, i) => bytes[i] === b);
      if (!zip && !ole) throw new Error('invalid workbook');
      const parsed = xlsx.read(bytes, { type: 'array', cellFormula: false });
      if (!parsed.SheetNames.length) throw new Error('no sheets');
      converter.value = xlsx;
      workbook.value = parsed;
      fileName.value = file.name;
      sheetName.value = parsed.SheetNames[0];
    } catch {
      error.value = '无法读取 Excel，请确认文件未损坏、未加密，并另存为 .xlsx 或 .xls 后重试';
    } finally {
      loading.value = false;
    }
  }

  function download() {
    if (!csv.value) return;
    const blob = new Blob([withBom.value ? '\uFEFF' : '', csv.value], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${fileName.value.replace(/\.(xlsx|xls)$/i, '')}-${sheetName.value}`.replace(/[\\/:*?"<>|]/g, '_') + '.csv';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
</script>

<style scoped lang="less">
  header { padding-bottom: 20px; border-bottom: 1px solid #e7ebf1; }
  h3 { margin: 0; color: #1d293b; font-size: 20px; }
  header p, .hint { color: #7b899d; font-size: 13px; line-height: 1.7; }
  .file-picker { display: flex; flex-direction: column; gap: 10px; margin-top: 22px; padding: 24px; border: 1px dashed #acbde6; border-radius: 8px; background: #f7f9ff; }
  .file-picker span, .actions span { color: #7b899d; font-size: 12px; }
  .file-picker input { max-width: 100%; }
  .file-name { overflow-wrap: anywhere; font-weight: 600; }
  .options { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .options .n-select { width: 240px; max-width: 100%; }
  .actions { display: flex; align-items: center; gap: 12px; margin: 18px 0; }
  .preview-label { display: block; margin-bottom: 10px; color: #536176; font-size: 13px; }
  .error { color: #d03050; }
  :deep(textarea) { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
</style>
