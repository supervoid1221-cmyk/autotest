/** 登录后只返回本站的非登录页面，并展开旧版本产生的嵌套 redirect。 */
export function resolveLoginRedirect(value: unknown): string {
  let target = typeof value === 'string' ? value : '/';

  for (let depth = 0; depth < 10; depth += 1) {
    if (!target.startsWith('/') || target.startsWith('//')) return '/';

    try {
      const url = new URL(target, window.location.origin);
      if (url.origin !== window.location.origin) return '/';
      if (url.pathname !== '/login') return `${url.pathname}${url.search}${url.hash}`;
      target = url.searchParams.get('redirect') || '/';
    } catch {
      return '/';
    }
  }

  return '/';
}
