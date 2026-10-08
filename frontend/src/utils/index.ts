import { h, unref } from 'vue';
import type { App, Plugin, Component } from 'vue';
import { NBadge, NIcon, NTag } from 'naive-ui';
import { PageEnum } from '@/enums/pageEnum';
import { isObject } from './is/index';
import { cloneDeep } from 'lodash-es';
/**
 * render 图标
 * */
export function renderIcon(icon) {
  // 菜单图标统一使用 Phosphor 线性（regular）风格，与「左侧菜单优化原型」保持一致。
  // 实心（fill）在 18px 下视觉过重、显大，与 13.5px 文字不协调。
  return () => h(NIcon, null, { default: () => h(icon, { weight: 'regular' }) });
}
/**
 * font 图标(Font class)
 * */
export function renderFontClassIcon(icon: string, iconName = 'iconfont') {
  return () => h('span', { class: [iconName, icon] });
}
/**
 * font 图标(Unicode)
 * */
export function renderUnicodeIcon(icon: string, iconName = 'iconfont') {
  return () => h('span', { class: [iconName], innerHTML: icon });
}
/**
 * font svg 图标
 * */
export function renderfontsvg(icon) {
  return () =>
    h(NIcon, null, {
      default: () =>
        h('svg', { class: `icon`, 'aria-hidden': 'true' }, h('use', { 'xlink:href': `#${icon}` })),
    });
}

/**
 * render new Tag
 * */
const newTagColors = { color: '#f90', textColor: '#fff', borderColor: '#f90' };
export function renderNew(type = 'warning', text = 'New', color: object = newTagColors) {
  return () =>
    h(
      NTag as any,
      {
        type,
        round: true,
        size: 'small',
        color,
      },
      { default: () => text }
    );
}

/**
 * 一级菜单分组顺序（对应路由 meta.group）
 * 未声明 group、或 group 不在该列表中的菜单项，统一归入"其他"排在最后。
 */
export const MENU_GROUP_ORDER: string[] = ['工作区', '测试资产', '执行与报告', '系统'];

/**
 * 递归组装菜单格式
 */
export function generatorMenu(routerMap: Array<any>) {
  return filterRouter(routerMap).map((item) => {
    const isRoot = isRootRouter(item);
    const info = isRoot
      ? item.children.find((child) => !Boolean(child?.meta?.hidden))
      : item;
    const currentMenu: Recordable = {
      ...info,
      ...info.meta,
      label: info.meta?.title,
      key: info.name,
      icon: isRoot ? item.meta?.icon : info.meta?.icon,
      // 分组信息挂在顶层 meta 上；isRoot 提升时 info 是子项，需要回退到 item.meta
      group: item.meta?.group || info.meta?.group,
    };
    // meta.badge：在菜单项右侧显示数字徽标（如待处理告警数）
    if (info.meta?.badge) {
      currentMenu.extra = () =>
        h(
          NBadge as any,
          {
            value: info.meta.badge,
            type: info.meta.badgeType || 'error',
            max: 99,
            'show-zero': false,
          },
          null
        );
    }
    // 是否有子菜单，并递归处理
    if (info.children && info.children.length > 0) {
      // Recursion
      currentMenu.children = generatorMenu(info.children);
    }
    return currentMenu;
  });
}

/**
 * 按 meta.group 把一级菜单包装成 NMenu 的分组节点（带分组标题）。
 * 分组内按 meta.sort 升序排列；没有任何分组声明时原样返回，保证 mixMenu 等既有用法不受影响。
 */
export function generatorMenuGroup(routerMap: Array<any>) {
  const items = generatorMenu(routerMap);
  const grouped = new Map<string, any[]>();
  const rest: any[] = [];
  items.forEach((item) => {
    const name: string = item.group || '';
    if (name && MENU_GROUP_ORDER.includes(name)) {
      if (!grouped.has(name)) grouped.set(name, []);
      (grouped.get(name) as any[]).push(item);
    } else {
      rest.push(item);
    }
  });
  const result: any[] = [];
  MENU_GROUP_ORDER.forEach((name) => {
    const list = grouped.get(name);
    if (!list || !list.length) return;
    list.sort((a, b) => (a.sort ?? 0) - (b.sort ?? 0));
    result.push({
      type: 'group',
      key: `__group_${name}`,
      // NMenu 的分组节点读 title；同时给 label，兼容不同版本取值差异
      title: name,
      label: name,
      children: list,
    });
  });
  return result.concat(rest);
}

/**
 * 混合菜单
 * */
export function generatorMenuMix(routerMap: Array<any>, routerName: string, location: string) {
  const cloneRouterMap = cloneDeep(routerMap);
  const newRouter = filterRouter(cloneRouterMap);
  if (location === 'header') {
    const firstRouter: any[] = [];
    newRouter.forEach((item) => {
      const isRoot = isRootRouter(item);
      const info = isRoot
        ? item.children.find((child) => !Boolean(child?.meta?.hidden))
        : item;
      info.children = undefined;
      const currentMenu = {
        ...info,
        ...info.meta,
        label: info.meta?.title,
        key: info.name,
      };
      firstRouter.push(currentMenu);
    });
    return firstRouter;
  } else {
    return getChildrenRouter(newRouter.filter((item) => item.name === routerName));
  }
}

/**
 * 递归组装子菜单
 * */
export function getChildrenRouter(routerMap: Array<any>) {
  return filterRouter(routerMap).map((item) => {
    const isRoot = isRootRouter(item);
    const info = isRoot
      ? item.children.find((child) => !Boolean(child?.meta?.hidden))
      : item;
    const currentMenu = {
      ...info,
      ...info.meta,
      label: info.meta?.title,
      key: info.name,
    };
    // 是否有子菜单，并递归处理
    if (info.children && info.children.length > 0) {
      // Recursion
      currentMenu.children = getChildrenRouter(info.children);
    }
    return currentMenu;
  });
}

/**
 * 判断根路由 Router
 * */
export function isRootRouter(item) {
  return (
    item.meta?.alwaysShow != true &&
    item?.children?.filter((item) => !Boolean(item?.meta?.hidden))?.length === 1
  );
}

/**
 * 排除Router
 * */
export function filterRouter(routerMap: Array<any>) {
  return routerMap.filter((item) => {
    return (
      (item.meta?.hidden || false) != true &&
      !['/:path(.*)*', '/', PageEnum.REDIRECT, PageEnum.BASE_LOGIN].includes(item.path)
    );
  });
}

export const withInstall = <T extends Component>(component: T, alias?: string) => {
  const comp = component as any;
  comp.install = (app: App) => {
    app.component(comp.name || comp.displayName, component);
    if (alias) {
      app.config.globalProperties[alias] = component;
    }
  };
  return component as T & Plugin;
};

/**
 *  找到对应的节点
 * */
export function getTreeItem(data: any[], key?: string | number): any {
  for (const item of data) {
    if (item.key === key) return item;
    if (item.children?.length) {
      const matched = getTreeItem(item.children, key);
      if (matched) return matched;
    }
  }
  return null;
}

// dynamic use hook props
export function getDynamicProps<T extends {}, U>(props: T): Partial<U> {
  const ret: Recordable = {};

  Object.keys(props).map((key) => {
    ret[key] = unref((props as Recordable)[key]);
  });

  return ret as Partial<U>;
}

export function deepMerge<T = any>(src: any = {}, target: any = {}): T {
  let key: string;
  for (key in target) {
    src[key] = isObject(src[key]) ? deepMerge(src[key], target[key]) : (src[key] = target[key]);
  }
  return src;
}

/**
 * Sums the passed percentage to the R, G or B of a HEX color
 * @param {string} color The color to change
 * @param {number} amount The amount to change the color by
 * @returns {string} The processed part of the color
 */
function addLight(color: string, amount: number) {
  const cc = parseInt(color, 16) + amount;
  const c = cc > 255 ? 255 : cc;
  return c.toString(16).length > 1 ? c.toString(16) : `0${c.toString(16)}`;
}

/**
 * Lightens a 6 char HEX color according to the passed percentage
 * @param {string} color The color to change
 * @param {number} amount The amount to change the color by
 * @returns {string} The processed color represented as HEX
 */
export function lighten(color: string, amount: number) {
  color = color.indexOf('#') >= 0 ? color.substring(1, color.length) : color;
  amount = Math.trunc((255 * amount) / 100);
  return `#${addLight(color.substring(0, 2), amount)}${addLight(
    color.substring(2, 4),
    amount
  )}${addLight(color.substring(4, 6), amount)}`;
}

/**
 * 判断是否 url
 * */
export function isUrl(url: string) {
  return /^(http|https):\/\//g.test(url);
}
