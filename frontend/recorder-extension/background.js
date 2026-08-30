const queueKey = (tabId) => `autotest-recorder-events-${tabId}`;
const pending = new Map();

function serialized(tabId, task) {
  const previous = pending.get(tabId) || Promise.resolve();
  const current = previous.catch(() => {}).then(task);
  const settled = current.finally(() => {
    if (pending.get(tabId) === settled) pending.delete(tabId);
  });
  pending.set(tabId, settled);
  return settled;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === 'AUTOTEST_RECORDER_GET_PLATFORM_TOKEN') {
    (async () => {
      try {
        const origin = new URL(String(message.platform || '')).origin;
        const tabs = await chrome.tabs.query({ url: `${origin}/*` });
        for (const tab of tabs) {
          if (!Number.isInteger(tab.id)) continue;
          try {
            const response = await chrome.tabs.sendMessage(tab.id, { type: 'AUTOTEST_READ_PLATFORM_TOKEN' });
            if (response?.token) return { token: response.token };
          } catch (_) {}
        }
      } catch (_) {}
      return { token: '' };
    })().then(sendResponse, () => sendResponse({ token: '' }));
    return true;
  }

  const senderTabId = sender.tab?.id;
  const tabId = Number(senderTabId ?? message?.tabId);
  if (!Number.isInteger(tabId)) return false;

  if (message?.type === 'AUTOTEST_RECORDER_APPEND' && message.event) {
    serialized(tabId, async () => {
      const key = queueKey(tabId);
      const stored = await chrome.storage.session.get(key);
      const events = Array.isArray(stored[key]) ? stored[key] : [];
      events.push(message.event);
      await chrome.storage.session.set({ [key]: events.slice(-2000) });
    }).then(() => sendResponse({ ok: true }), () => sendResponse({ ok: false }));
    return true;
  }

  if (message?.type === 'AUTOTEST_RECORDER_DRAIN') {
    serialized(tabId, async () => {
      const key = queueKey(tabId);
      const stored = await chrome.storage.session.get(key);
      const events = Array.isArray(stored[key]) ? stored[key] : [];
      await chrome.storage.session.remove(key);
      return events;
    }).then((events) => sendResponse({ events }), () => sendResponse({ events: [] }));
    return true;
  }

  if (message?.type === 'AUTOTEST_RECORDER_CLEAR') {
    serialized(tabId, () => chrome.storage.session.remove(queueKey(tabId)))
      .then(() => sendResponse({ ok: true }), () => sendResponse({ ok: false }));
    return true;
  }

  return false;
});

chrome.tabs?.onRemoved?.addListener((tabId) => {
  chrome.storage.session.remove(queueKey(tabId));
});
