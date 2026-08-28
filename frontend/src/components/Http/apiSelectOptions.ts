export const RespAttrOptions = ['headers', 'cookies', 'json'].map((item) => ({
  value: item,
  label: item,
}));

export const AssertOptions = [
  { value: 'equals', label: '相等' },
  { value: 'not_equals', label: '不等于' },
  { value: 'greater_than', label: '大于' },
  { value: 'less_than', label: '小于' },
  { value: 'contains', label: '包含' },
];
