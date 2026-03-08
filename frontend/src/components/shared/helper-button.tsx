"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { useChartExplain } from "@/lib/hooks/use-api";
import type { ChartType } from "@/lib/types";

interface HelperButtonProps {
  chartType: ChartType;
  dataSummary: string;
}

export function HelperButton({ chartType, dataSummary }: HelperButtonProps) {
  const [explanation, setExplanation] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mutation = useChartExplain();

  const handleClick = () => {
    if (explanation) {
      setExplanation(null);
      setError(null);
      return;
    }
    setError(null);
    mutation.mutate(
      { chart_type: chartType, data_summary: dataSummary },
      {
        onSuccess: (data) => setExplanation(data.explanation),
        onError: (err) =>
          setError((err as Error).message || "Failed to generate explanation"),
      }
    );
  };

  return (
    <div>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleClick}
        disabled={mutation.isPending}
        className="text-xs"
      >
        {mutation.isPending ? (
          <>
            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            Analyzing...
          </>
        ) : explanation ? (
          "Hide insight"
        ) : (
          "Explain this chart"
        )}
      </Button>
      {explanation && (
        <div className="mt-2 rounded-md bg-muted p-3 text-sm whitespace-pre-wrap">
          {explanation}
        </div>
      )}
      {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
    </div>
  );
}
