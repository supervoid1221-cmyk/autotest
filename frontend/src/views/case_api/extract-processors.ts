export type ExtractProcessor = {
  type: string;
  [key: string]: unknown;
};

export type ExtractRule = {
  name: string;
  mode: 'jsonpath' | 're';
  source: 'json' | 'text' | 'headers';
  expression: string;
  index: number;
  processors: ExtractProcessor[];
  autoVariableName?: string;
};

export const extractProcessorOptions = [
  { label: '去除首尾空格', value: 'trim' },
  { label: '添加字符串前缀', value: 'prefix' },
  { label: '添加字符串后缀', value: 'suffix' },
  { label: '字符串替换', value: 'replace' },
  { label: '正则提取', value: 'regex' },
  { label: '分割并取指定位置', value: 'split' },
  { label: 'JSON 字符串解析', value: 'json_parse' },
  { label: '类型转换', value: 'cast' },
  { label: 'Base64 编码', value: 'base64_encode' },
  { label: 'Base64 解码', value: 'base64_decode' },
  { label: 'URL 编码', value: 'url_encode' },
  { label: 'URL 解码', value: 'url_decode' },
  { label: '日期时间转时间戳', value: 'datetime_to_timestamp' },
  { label: '时间戳转日期时间', value: 'timestamp_to_datetime' },
  { label: '数组取值', value: 'array_item' },
  { label: '对象字段选取', value: 'object_pick' },
  { label: '对象字段重命名', value: 'object_rename' },
  { label: '空值默认值', value: 'default' },
];

export function defaultProcessor(type: string): ExtractProcessor {
  const defaults: Record<string, ExtractProcessor> = {
    trim: { type: 'trim' },
    prefix: { type: 'prefix', value: '' },
    suffix: { type: 'suffix', value: '' },
    replace: { type: 'replace', search: '', replacement: '', count: -1 },
    regex: { type: 'regex', pattern: '', group: 0 },
    split: { type: 'split', separator: '', index: 0 },
    json_parse: { type: 'json_parse' },
    cast: { type: 'cast', target: 'string' },
    base64_encode: { type: 'base64_encode' },
    base64_decode: { type: 'base64_decode' },
    url_encode: { type: 'url_encode' },
    url_decode: { type: 'url_decode' },
    datetime_to_timestamp: { type: 'datetime_to_timestamp', format: '', unit: 'seconds', timezone: 'Asia/Shanghai' },
    timestamp_to_datetime: { type: 'timestamp_to_datetime', format: '%Y-%m-%d %H:%M:%S', unit: 'auto', timezone: 'Asia/Shanghai' },
    array_item: { type: 'array_item', position: 'first', index: 0 },
    object_pick: { type: 'object_pick', keys: '' },
    object_rename: { type: 'object_rename', mapping: '' },
    default: { type: 'default', value: '' },
  };
  return { ...(defaults[type] || { type }) };
}

export const defaultExtractRule = (): ExtractRule => ({
  name: '', mode: 'jsonpath', source: 'json', expression: '', index: 0, processors: [],
});

export function extractRuleFromConfig(
  name: string,
  value: unknown,
  normalizeExpression: (value: unknown) => string,
  inferVariableName: (value: unknown) => string,
): ExtractRule | null {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const config = value as Record<string, unknown>;
    const expression = normalizeExpression(config.expression);
    const inferredName = inferVariableName(expression);
    return {
      name,
      mode: config.mode === 're' ? 're' : 'jsonpath',
      source: String(config.source || (config.mode === 're' ? 'text' : 'json')) as ExtractRule['source'],
      expression,
      index: Number(config.index ?? 0),
      processors: Array.isArray(config.processors) ? JSON.parse(JSON.stringify(config.processors)) : [],
      autoVariableName: name === inferredName ? inferredName : undefined,
    };
  }
  if (!Array.isArray(value)) return null;
  if (value[0] === 're') {
    return {
      name, mode: 're', source: (value[1] || 'text') as ExtractRule['source'],
      expression: String(value[2] || ''), index: Number(value[3] ?? 0), processors: [],
    };
  }
  const expression = normalizeExpression(value[1]);
  const inferredName = inferVariableName(expression);
  return {
    name, mode: 'jsonpath', source: (value[0] || 'json') as ExtractRule['source'],
    expression, index: Number(value[2] ?? 0), processors: [],
    autoVariableName: name === inferredName ? inferredName : undefined,
  };
}

export function extractRuleToConfig(rule: ExtractRule, normalizeExpression: (value: unknown) => string) {
  return {
    mode: rule.mode,
    source: rule.source,
    expression: rule.mode === 'jsonpath' ? normalizeExpression(rule.expression) : rule.expression,
    index: Number(rule.index || 0),
    processors: JSON.parse(JSON.stringify(rule.processors || [])),
  };
}
