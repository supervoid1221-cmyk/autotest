const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function load(relative, globals = {}) {
  const source = fs.readFileSync(path.join(__dirname, '..', relative), 'utf8');
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  });
  const context = { exports: {}, ...globals };
  vm.runInNewContext(outputText, context);
  return context.exports;
}
const { asList } = load('src/utils/list.ts');
const list = [{ id: 1 }];
assert.equal(asList(list), list);
for (const key of ['list', 'results', 'data']) assert.equal(asList({ [key]: list }), list);
assert.equal(asList({ list, results: [{ id: 2 }] }), list);
assert.equal(asList({ list: {}, results: list }), list);
for (const input of [null, undefined, false, 'bad', { data: {} }])
  assert.equal(asList(input).length, 0);
assert.equal(asList({ list: [], results: list }).length, 0);

const time = load('src/utils/time.ts');
assert.equal(time.formatDateTime(new Date(2026, 8, 19, 7, 8, 9)), '2026-09-19 07:08:09');
assert.equal(time.formatDateTime(null), '-');
assert.equal(time.formatDurationMilliseconds(999), '999 ms');
assert.equal(time.formatDurationMilliseconds(null), '-');
assert.equal(time.formatDurationMilliseconds(3723000), '1小时2分3秒');
assert.equal(time.formatDurationSeconds(125), '2分5秒');
assert.equal(time.formatDurationSeconds(undefined), '-');
assert.equal(
  time.formatElapsedDuration('2026-09-19T00:00:00Z', '2026-09-19T00:01:05Z', {
    showMilliseconds: false,
  }),
  '1分5秒'
);

const report = load('src/utils/report.ts', {
  require: (id) => (id === './time' ? time : {}),
});
assert.equal(report.formatDuration(1500), '1秒');
assert.equal(report.formatDuration(-1), '0 ms');
assert.equal(report.formatDuration(undefined), '-');
assert.equal(
  report.formatDuration(undefined, {
    started_at: '2026-09-10T00:00:00Z',
    finished_at: '2026-09-10T00:00:02Z',
  }),
  '2秒'
);
assert.equal(report.stepStatus({ passed: false }).label, '失败');
assert.equal(report.stepStatus({ status: 'skipped' }).label, '已跳过');
const request = { params: {}, json: { a: 1 } };
assert.deepEqual(JSON.parse(report.formatRequest(request)), { json: { a: 1 } });
assert.deepEqual(request.params, {});

const status = load('src/utils/executionStatus.ts');
assert.equal(status.isAppActive('installing'), true);
assert.equal(status.isPerformanceActive('installing'), false);
assert.equal(status.isPerformanceActive('stopped'), false);
assert.equal(status.performanceStatusLabels.queued, '等待执行');
assert.equal(status.appStatusLabels.queued[0], '等待设备');

let dispose;
let nextId = 0;
const timers = new Map();
const { usePolling } = load('src/hooks/web/usePolling.ts', {
  require: () => ({
    onBeforeUnmount: (callback) => {
      dispose = callback;
    },
  }),
  window: {
    setInterval: (callback, interval) => {
      const id = ++nextId;
      timers.set(id, { callback, interval });
      return id;
    },
    clearInterval: (id) => timers.delete(id),
  },
});
const poller = usePolling();
poller.start(() => {}, 3000);
poller.start(() => {}, 5000);
assert.equal(timers.size, 1);
assert.equal([...timers.values()][0].interval, 5000);
poller.stop();
assert.equal(timers.size, 0);
poller.start(() => {}, 3000);
dispose();
assert.equal(timers.size, 0);
poller.start(() => {}, 3000);
assert.equal(timers.size, 0, '页面卸载后的异步回调不能重新启动轮询');
console.log('Shared list, report, execution status and polling checks passed.');

// 错误文案提取。用例里的形状全部照抄后端实测产物，不是设想：
// 视图里抛 ValidationError({"detail": "..."}) 出来是字符串；
// 序列化器字段错误是数组；serializers.ValidationError 在 validate() 里抛会被
// as_serializer_error 包成 {"字段": [文案]}。
const isModule = load('src/utils/is/index.ts');
const { extractErrorMessage } = load('src/utils/http/axios/helper.ts', {
  require: (id) => (id === '@/utils/is' ? isModule : {}),
});

const quotaDetail = '当前租户存储配额不足（已使用 0 字节，配额 1 字节）。';
assert.equal(extractErrorMessage({ detail: quotaDetail }), quotaDetail, '409 配额文案必须原样取出');
assert.equal(extractErrorMessage({ detail: '不能移除当前操作账号。' }), '不能移除当前操作账号。');
assert.equal(
  extractErrorMessage({ status: '不能停用当前操作账号。' }),
  '不能停用当前操作账号。',
  '非 detail 字段也要能取到'
);
assert.equal(
  extractErrorMessage({ message: ['密码和确认密码不一致'] }),
  '密码和确认密码不一致',
  '数组要摊平成字符串'
);
assert.equal(
  extractErrorMessage({ name: ['This field is required.'], project: ['This field is required.'] }),
  'This field is required.',
  '序列化器字段错误取第一条'
);
assert.equal(
  extractErrorMessage({ connected: false, message: '节点离线', status: 'offline' }),
  '节点离线'
);
assert.equal(extractErrorMessage({ detail: '  超限  ' }), '超限', '两侧空白要去掉');
for (const empty of [{}, { detail: '' }, { detail: [] }, null, undefined, 0, false]) {
  assert.equal(
    extractErrorMessage(empty),
    '',
    `取不到文案时必须返回空串：${JSON.stringify(empty)}`
  );
}
console.log('Error message extraction checks passed.');
