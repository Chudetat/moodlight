import { create } from "zustand";

interface DashboardState {
  // Brand focus
  focusedBrand: string | null;
  setFocusedBrand: (brand: string | null) => void;

  // Compare mode
  compareMode: boolean;
  compareBrands: [string, string] | null;
  setCompareMode: (on: boolean) => void;
  setCompareBrands: (brands: [string, string] | null) => void;

  // Time range
  days: number;
  setDays: (d: number) => void;

  // Sidebar
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  focusedBrand: null,
  setFocusedBrand: (brand) => set({ focusedBrand: brand }),

  compareMode: false,
  compareBrands: null,
  setCompareMode: (on) => set({ compareMode: on }),
  setCompareBrands: (brands) => set({ compareBrands: brands }),

  days: 7,
  setDays: (d) => set({ days: d }),

  sidebarOpen: true,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}));
