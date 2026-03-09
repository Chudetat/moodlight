"use client";

import { useDashboardStore } from "@/store/dashboard-store";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

export function Header() {
  const now = new Date();
  const dateStr = `${MONTHS[now.getMonth()]} ${now.getDate()} - ${DAYS[now.getDay()]}`;
  const setSidebarOpen = useDashboardStore((s) => s.setSidebarOpen);
  const sidebarOpen = useDashboardStore((s) => s.sidebarOpen);

  return (
    <header className="flex h-14 items-center border-b border-border px-4 lg:px-6">
      <Button
        variant="ghost"
        size="sm"
        className="mr-2 lg:hidden"
        onClick={() => setSidebarOpen(!sidebarOpen)}
      >
        <Menu className="h-5 w-5" />
      </Button>
      <h1 className="text-lg font-semibold">
        {dateStr}
      </h1>
    </header>
  );
}
