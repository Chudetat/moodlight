"use client";

import { useMemo, useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from "@tanstack/react-table";
import { useCombinedData } from "@/lib/hooks/use-api";
import { normalizeEmpathyScore, timeAgo } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Download, ArrowUpDown } from "lucide-react";
import type { CombinedDataItem } from "@/lib/types";

interface TableRow {
  text: string;
  topic: string;
  source: string;
  country: string;
  empathy: number;
  engagement: number;
  created_at: string;
}

const columnHelper = createColumnHelper<TableRow>();

const columns = [
  columnHelper.accessor("text", {
    header: "Headline",
    cell: (info) => (
      <span className="line-clamp-2 max-w-xs text-xs">{info.getValue()}</span>
    ),
  }),
  columnHelper.accessor("topic", {
    header: "Topic",
    cell: (info) => (
      <span className="text-xs capitalize">{info.getValue()}</span>
    ),
  }),
  columnHelper.accessor("source", {
    header: "Source",
    cell: (info) => <span className="text-xs">{info.getValue()}</span>,
  }),
  columnHelper.accessor("country", {
    header: "Country",
    cell: (info) => <span className="text-xs">{info.getValue()}</span>,
  }),
  columnHelper.accessor("empathy", {
    header: "Empathy",
    cell: (info) => (
      <span className="text-xs font-medium tabular-nums">
        {info.getValue()}
      </span>
    ),
  }),
  columnHelper.accessor("engagement", {
    header: "Engagement",
    cell: (info) => (
      <span className="text-xs tabular-nums">
        {info.getValue().toLocaleString()}
      </span>
    ),
  }),
  columnHelper.accessor("created_at", {
    header: "Time",
    cell: (info) => (
      <span className="text-xs text-muted-foreground">
        {timeAgo(info.getValue())}
      </span>
    ),
  }),
];

export function WorldViewTable() {
  const { data, isLoading } = useCombinedData(7);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");

  const tableData = useMemo<TableRow[]>(() => {
    return (data?.data ?? []).map((d: CombinedDataItem) => ({
      text: d.text,
      topic: d.topic,
      source: d.source,
      country: d.country,
      empathy: normalizeEmpathyScore(d.empathy_score),
      engagement: d.engagement,
      created_at: d.created_at,
    }));
  }, [data]);

  const table = useReactTable({
    data: tableData,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  function exportCsv() {
    const headers = ["Headline", "Topic", "Source", "Country", "Empathy", "Engagement", "Time"];
    const rows = tableData.map((r) => [
      `"${r.text.replace(/"/g, '""')}"`,
      r.topic,
      r.source,
      r.country,
      r.empathy,
      r.engagement,
      r.created_at,
    ]);
    const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "world_view.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="h-96 animate-pulse rounded bg-muted" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          World View{" "}
          <span className="text-sm font-normal text-muted-foreground">
            ({tableData.length} items)
          </span>
        </h2>
        <Button variant="outline" size="xs" onClick={exportCsv}>
          <Download className="mr-1 h-3 w-3" />
          CSV
        </Button>
      </div>

      <Input
        value={globalFilter}
        onChange={(e) => setGlobalFilter(e.target.value)}
        placeholder="Search headlines, topics, sources..."
        className="mb-3 h-8 text-xs"
      />

      <div className="max-h-96 overflow-auto rounded-lg border border-border">
        <table className="w-full text-left">
          <thead className="sticky top-0 bg-card">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => (
                  <th
                    key={header.id}
                    className="cursor-pointer border-b border-border px-3 py-2 text-xs font-medium text-muted-foreground"
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      <ArrowUpDown className="h-3 w-3" />
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.slice(0, 200).map((row) => (
              <tr
                key={row.id}
                className="border-b border-border/50 hover:bg-muted/30"
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
