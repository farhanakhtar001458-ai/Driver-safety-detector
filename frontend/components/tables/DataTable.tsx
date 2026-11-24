"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, Inbox } from "lucide-react";
import { cn } from "@/lib/format";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => React.ReactNode;
  className?: string;
  align?: "left" | "right" | "center";
}

export function DataTable<T extends { id?: number }>({
  columns,
  rows,
  loading,
  emptyTitle = "Nothing here yet",
  emptyDescription,
  onRowClick,
  rowKey,
  minWidth = 720,
}: {
  columns: Column<T>[];
  rows: T[];
  loading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  onRowClick?: (row: T) => void;
  rowKey?: (row: T) => string | number;
  minWidth?: number;
}) {
  const isEmpty = !loading && rows.length === 0;
  return (
    <div className="overflow-x-auto">
      <table className="w-full" style={{ minWidth }}>
        <thead className="border-b border-ink-100 dark:border-white/5">
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={cn("table-th", column.className, column.align === "right" && "text-right")}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-100 dark:divide-white/5">
          {loading &&
            Array.from({ length: 5 }).map((_, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td key={column.key} className="table-td">
                    <div className="skeleton h-3.5 w-full max-w-[140px]" />
                  </td>
                ))}
              </tr>
            ))}
          {isEmpty && (
            <tr>
              <td colSpan={columns.length}>
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-ink-100 text-ink-400 dark:bg-white/5">
                    <Inbox className="h-4 w-4" />
                  </span>
                  <p className="text-xs font-semibold text-ink-700 dark:text-ink-200">{emptyTitle}</p>
                  {emptyDescription && <p className="mt-1 text-[11px] text-ink-400">{emptyDescription}</p>}
                </div>
              </td>
            </tr>
          )}
          {!loading &&
            rows.map((row, index) => {
              const key = rowKey ? rowKey(row) : row.id ?? index;
              return (
                <tr
                  key={key}
                  onClick={() => onRowClick?.(row)}
                  className={cn(
                    "transition hover:bg-ink-50/80 dark:hover:bg-white/[0.04]",
                    onRowClick && "cursor-pointer",
                  )}
                >
                  {columns.map((column) => (
                    <td key={column.key} className={cn("table-td", column.className, column.align === "right" && "text-right")}>
                      {column.render ? column.render(row) : String((row as Record<string, unknown>)[column.key] ?? "—")}
                    </td>
                  ))}
                </tr>
              );
            })}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({
  page,
  pages,
  total,
  onPage,
  pageSize,
}: {
  page: number;
  pages: number;
  total: number;
  onPage: (page: number) => void;
  pageSize?: number;
}) {
  const [jump, setJump] = useState("");
  if (total === 0) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink-100 px-4 py-3 dark:border-white/5">
      <p className="text-xs text-ink-500 dark:text-ink-400">
        Showing <span className="font-semibold text-ink-800 dark:text-ink-100">{Math.min(total, (page - 1) * (pageSize ?? 20) + 1)}–{Math.min(total, page * (pageSize ?? 20))}</span> of{" "}
        <span className="font-semibold text-ink-800 dark:text-ink-100">{total}</span>
      </p>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          className="flex h-7 w-7 items-center justify-center rounded-lg border border-ink-200 text-ink-500 transition hover:bg-ink-50 disabled:opacity-40 dark:border-white/10 dark:text-ink-300 dark:hover:bg-white/5"
          aria-label="Previous page"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>
        <span className="px-2 text-xs font-medium text-ink-600 dark:text-ink-300">
          {page} / {Math.max(1, pages)}
        </span>
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= pages}
          className="flex h-7 w-7 items-center justify-center rounded-lg border border-ink-200 text-ink-500 transition hover:bg-ink-50 disabled:opacity-40 dark:border-white/10 dark:text-ink-300 dark:hover:bg-white/5"
          aria-label="Next page"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
        {pages > 5 && (
          <input
            value={jump}
            onChange={(event) => setJump(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                const target = Number(jump);
                if (target >= 1 && target <= pages) onPage(target);
                setJump("");
              }
            }}
            placeholder="Page"
            className="ml-2 h-7 w-14 rounded-lg border border-ink-200 px-2 text-[11px] outline-none focus:border-brand-500 dark:border-white/10 dark:bg-white/5"
          />
        )}
      </div>
    </div>
  );
}
