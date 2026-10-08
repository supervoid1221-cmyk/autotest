export function checkStatus(status: number, msg: string): void {
  const $message = window['$message'];
  switch (status) {
    case 400:
      $message.error(msg || '请求参数有误，请检查填写内容');
      break;
    // 401: 未登录
    // 未登录则跳转登录页面，并携带当前页面的路径
    // 在登录成功后返回当前页面，这一步需要在登录页操作。
    case 401:
      $message.warning(msg || '登录已过期，请重新登录激活');
      break;
    case 403:
      $message.error('用户得到授权，但是访问是被禁止的。!');
      break;
    // 404请求不存在
    case 404:
      $message.error('网络请求错误，未找到该资源!');
      break;
    case 405:
      $message.error('网络请求错误，请求方法未允许!');
      break;
    case 408:
      $message.error('网络请求超时');
      break;
    // 409: 冲突。租户存储配额不足、套件停用、设备占用等都走这个码，
    // 后端会把具体原因放在 detail 里，优先展示它而不是一句笼统的冲突提示。
    case 409:
      $message.error(msg || '当前操作存在冲突，请刷新页面后重试');
      break;
    case 500:
      $message.error('服务器错误,请联系管理员!');
      break;
    case 501:
      $message.error('网络未实现');
      break;
    case 502:
      $message.error('网络错误');
      break;
    case 503:
      $message.error('服务不可用，服务器暂时过载或维护!');
      break;
    case 504:
      $message.error('网络超时');
      break;
    case 505:
      $message.error('http版本不支持该请求!');
      break;
    default:
      // 兜底：取不到后端文案时也要给一句可读的提示，否则会弹出一个空白 toast。
      $message.error(msg || '请求失败，请稍后重试');
  }
}
