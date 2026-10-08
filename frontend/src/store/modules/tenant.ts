import { defineStore } from 'pinia';
import { store } from '@/store';
import { getTenants, TenantInfo } from '@/api/account/http';
import { CURRENT_TENANT } from '@/store/mutation-types';
import { storage } from '@/utils/Storage';

interface TenantState {
  tenants: TenantInfo[];
  currentTenantId: string;
  loaded: boolean;
  loading: boolean;
}

export const useTenantStore = defineStore({
  id: 'app-tenant',
  state: (): TenantState => ({
    tenants: [],
    currentTenantId: String(storage.get(CURRENT_TENANT, '') || ''),
    loaded: false,
    loading: false,
  }),
  getters: {
    currentTenant(state): TenantInfo | undefined {
      return state.tenants.find((tenant) => tenant.id === state.currentTenantId);
    },
    tenantOptions(state) {
      return state.tenants.map((tenant) => ({
        label: tenant.name,
        value: tenant.id,
      }));
    },
  },
  actions: {
    async loadTenants(force = false, includeInactive = false) {
      if (this.loading || (this.loaded && !force)) return;
      this.loading = true;
      try {
        const response: any = await getTenants(
          includeInactive ? { include_inactive: true } : undefined
        );
        this.tenants = Array.isArray(response) ? response : response?.list || [];
        const selectedIsValid = this.tenants.some(
          (tenant) => tenant.id === this.currentTenantId
        );
        if (!selectedIsValid) {
          this.setCurrentTenant(this.tenants[0]?.id || '');
        }
        this.loaded = true;
      } finally {
        this.loading = false;
      }
    },
    setCurrentTenant(tenantId: string) {
      this.currentTenantId = tenantId;
      if (tenantId) storage.set(CURRENT_TENANT, tenantId, null);
      else storage.remove(CURRENT_TENANT);
    },
    reset() {
      this.tenants = [];
      this.currentTenantId = '';
      this.loaded = false;
      storage.remove(CURRENT_TENANT);
    },
  },
});

export function useTenant() {
  return useTenantStore(store);
}
