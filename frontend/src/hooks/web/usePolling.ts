import { onBeforeUnmount } from 'vue';

/** 统一定时器启停与销毁；刷新条件、频率和请求处理由页面决定。 */
export function usePolling() {
  let timer: number | undefined;
  let disposed = false;
  const stop = () => {
    if (timer !== undefined) window.clearInterval(timer);
    timer = undefined;
  };
  const start = (refresh: () => unknown, interval: number) => {
    stop();
    if (!disposed) timer = window.setInterval(refresh, interval);
  };
  onBeforeUnmount(() => { disposed = true; stop(); });
  return { start, stop };
}
