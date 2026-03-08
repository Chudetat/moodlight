"use client";

import { useState } from "react";
import { useAlertPreferences, useUpdateAlertPreferences } from "@/lib/hooks/use-api";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { ALERT_TYPE_CATEGORIES } from "@/lib/constants";

export function AlertSettings() {
  const update = useUpdateAlertPreferences();
  const { data: prefsData } = useAlertPreferences();
  const prefs = prefsData?.preferences ?? {};

  const sensValues = Object.values(prefs).map((p) => p.sensitivity || "medium");
  const currentSens =
    sensValues.length > 0
      ? ["low", "medium", "high"].reduce((a, b) =>
          sensValues.filter((v) => v === a).length >=
          sensValues.filter((v) => v === b).length
            ? a
            : b
        )
      : "medium";
  const sensIndex = ["low", "medium", "high"].indexOf(currentSens);
  const [sensitivity, setSensitivity] = useState(sensIndex >= 0 ? sensIndex : 1);
  const labels = ["Low", "Medium", "High"];
  const values = ["low", "medium", "high"];

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase text-muted-foreground">
        Alert Settings
      </p>
      <div className="space-y-1">
        <Label className="text-xs text-muted-foreground">Sensitivity</Label>
        <Slider
          min={0}
          max={2}
          step={1}
          value={[sensitivity]}
          onValueChange={(val) => {
            const v = Array.isArray(val) ? val[0] : val;
            setSensitivity(v);
            update.mutate({ sensitivity: values[v] });
          }}
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          {labels.map((l) => (
            <span key={l}>{l}</span>
          ))}
        </div>
      </div>

      <div className="space-y-1">
        <Label className="text-xs text-muted-foreground">
          Alert types to receive:
        </Label>
        {Object.entries(ALERT_TYPE_CATEGORIES).map(([category, types]) => (
          <div key={category} className="space-y-0.5">
            <div className="text-xs font-medium capitalize">{category}</div>
            {types.map((alertType) => {
              const enabled = prefs[alertType]?.enabled ?? true;
              return (
                <div
                  key={alertType}
                  className="flex items-center justify-between pl-2"
                >
                  <span className="text-[11px]">
                    {alertType
                      .replace(/_/g, " ")
                      .replace(/\b\w/g, (c) => c.toUpperCase())}
                  </span>
                  <Switch
                    checked={enabled}
                    onCheckedChange={(checked) => {
                      update.mutate({
                        alert_type: alertType,
                        enabled: checked,
                      });
                    }}
                    className="scale-75"
                  />
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
