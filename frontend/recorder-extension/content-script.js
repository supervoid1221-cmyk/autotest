window.addEventListener('message', (messageEvent) => {
  if (messageEvent.source !== window) return;
  const payload = messageEvent.data;
  if (payload?.source !== 'autotest-ui-recorder' || payload?.type !== 'event' || !payload.event) return;
  chrome.runtime.sendMessage({ type: 'AUTOTEST_RECORDER_APPEND', event: payload.event }).catch(() => {});
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== 'AUTOTEST_READ_PLATFORM_TOKEN') return false;
  try {
    const stored = JSON.parse(localStorage.getItem('ACCESS-TOKEN') || 'null');
    const valid = stored && stored.value && (stored.expire === null || Number(stored.expire) >= Date.now());
    sendResponse({ token: valid ? String(stored.value) : '' });
  } catch (_) {
    sendResponse({ token: '' });
  }
  return false;
});
