import { reactive } from 'vue';
import logoImage from '@/assets/images/logo.png';
import loginImage from '@/assets/images/account-logo.png';
import { SystemConfigurationAPI } from '@/api/system/configuration';

export const websiteConfig = reactive({
  title: '自动化测试平台',
  enTitle: 'TEST PLATFORM',
  logo: logoImage,
  platformIcon: '',
  platformLogoLight: '',
  platformLogoDark: '',
  logoNeedsContrastPlate: false,
  faviconUrl: '',
  loginImage: loginImage,
  loginDesc: 'Naive Ui Admin中后台前端/设计解决方案',
});

export function syncBrandingTheme(isDark: boolean) {
  const lightLogo = websiteConfig.platformLogoLight;
  const darkLogo = websiteConfig.platformLogoDark;
  const selectedLogo = isDark ? darkLogo || lightLogo : lightLogo || darkLogo;
  websiteConfig.logo = selectedLogo || logoImage;
  websiteConfig.platformIcon = selectedLogo || '';
  websiteConfig.logoNeedsContrastPlate = Boolean(isDark && !darkLogo && lightLogo);

  const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]') || document.createElement('link');
  favicon.rel = 'icon';
  favicon.href = selectedLogo || websiteConfig.faviconUrl || '/favicon.png';
  if (!favicon.parentNode) document.head.appendChild(favicon);
}

export async function initializeBranding() {
  try {
    const branding = await SystemConfigurationAPI.branding();
    websiteConfig.platformLogoLight = branding.platform_logo_light_url || '';
    websiteConfig.platformLogoDark = branding.platform_logo_dark_url || '';
    websiteConfig.faviconUrl = branding.favicon_url || '';
    syncBrandingTheme(document.documentElement.dataset.theme === 'dark');
  } catch {
    // 配置服务暂不可用时继续使用打包内置图标，不影响平台登录和使用。
  }
}
