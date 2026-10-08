import { NModal } from 'naive-ui';

export const basicProps = {
  ...NModal.props,
  // 确认按钮文字
  subBtuText: {
    type: String,
    default: '确认',
  },
  showIcon: {
    type: Boolean,
    default: false,
  },
  width: {
    type: [Number, String],
    default: 'min(1100px, calc(100vw - 48px))',
  },
  title: {
    type: String,
    default: '',
  },
  maskClosable: {
    type: Boolean,
    default: false,
  },
  preset: {
    type: String,
    default: 'dialog',
  },
};
