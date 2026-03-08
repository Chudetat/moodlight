"use client";

import { useUserPreferences } from "@/lib/hooks/use-api";
import { useQueryClient } from "@tanstack/react-query";
import { Label } from "@/components/ui/label";

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-center justify-between gap-2 text-xs">
      <span>{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-5 w-9 rounded-full transition-colors ${
          checked ? "bg-primary" : "bg-muted"
        }`}
      >
        <span
          className={`absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
            checked ? "translate-x-4" : ""
          }`}
        />
      </button>
    </label>
  );
}

export function EmailPreferences() {
  const { data } = useUserPreferences();
  const queryClient = useQueryClient();

  async function updatePref(key: string, value: boolean) {
    await fetch("/api/proxy/api/user/preferences", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [key]: value }),
    });
    queryClient.invalidateQueries({ queryKey: ["user-preferences"] });
  }

  if (!data) return null;

  return (
    <div className="space-y-2">
      <Label className="text-xs text-muted-foreground">
        Email Preferences
      </Label>
      <div className="space-y-2">
        <Toggle
          label="Daily Brief"
          checked={data.digest_daily}
          onChange={(v) => updatePref("digest_daily", v)}
        />
        <Toggle
          label="Weekly Digest"
          checked={data.digest_weekly}
          onChange={(v) => updatePref("digest_weekly", v)}
        />
        <Toggle
          label="Alert Emails"
          checked={data.alert_emails}
          onChange={(v) => updatePref("alert_emails", v)}
        />
      </div>
    </div>
  );
}
