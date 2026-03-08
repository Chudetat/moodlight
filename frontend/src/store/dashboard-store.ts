import { create } from "zustand";

interface DashboardState {
  // Search
  searchQuery: string;
  setSearchQuery: (q: string) => void;

  // Brand focus
  focusedBrand: string | null;
  setFocusedBrand: (brand: string | null) => void;

  // Compare mode
  compareMode: boolean;
  compareBrands: string[];
  setCompareMode: (on: boolean) => void;
  setCompareBrands: (brands: string[]) => void;

  // Time range
  days: number;
  setDays: (d: number) => void;

  // Sidebar
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  searchQuery: "",
  setSearchQuery: (q) => set({ searchQuery: q }),

  focusedBrand: null,
  setFocusedBrand: (brand) => set({ focusedBrand: brand }),

  compareMode: false,
  compareBrands: ["", "", ""],
  setCompareMode: (on) => set({ compareMode: on }),
  setCompareBrands: (brands) => set({ compareBrands: brands }),

  days: 7,
  setDays: (d) => set({ days: d }),

  sidebarOpen: true,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}));
