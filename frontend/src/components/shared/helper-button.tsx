"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Search, X, Loader2 } from "lucide-react";
import { useChartExplain } from "@/lib/hooks/use-api";
import type { ChartType } from "@/lib/types";

interface HelperButtonProps {
  chartType: ChartType;
  dataSummary: string;
}

export function HelperButton({ chartType, dataSummary }: HelperButtonProps) {
  const [open, setOpen] = useState(false);
  const { mutate, data, isPending, reset } = useChartExplain();

  function handleClick() {
    if (open) {
      setOpen(false);
      reset();
      return;
    }
    setOpen(true);
    mutate({ chart_type: chartType, data_summary: dataSummary });
  }

  return (
    <div>
      <Button
        variant="ghost"
        size="icon-xs"
        onClick={handleClick}
        title="Explain this chart"
      >
        {open ? (
          <X className="h-3.5 w-3.5" />
        ) : (
          <Search className="h-3.5 w-3.5" />
        )}
      </Button>

      {open && (
        <div className="mt-2 rounded-lg border border-border bg-accent/50 p-4 text-sm leading-relaxed">
          {isPending ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyzing...
            </div>
          ) : data?.explanation ? (
            <p className="whitespace-pre-wrap">{data.explanation}</p>
          ) : (
            <p className="text-muted-foreground">
              Unable to generate insight.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
