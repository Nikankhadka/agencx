import type { ReactNode } from "react";

export interface TableColumn<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
}

export interface TableProps<T> {
  columns: TableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  error?: string;
  emptyState: ReactNode;
  /**
   * When set, each row becomes a pointer target invoking this on click. For
   * keyboard access, render a real focusable control (e.g. a Link) inside one
   * of the columns as well - this handler is a convenience, not the only path.
   */
  onRowClick?: (row: T) => void;
  /**
   * Responsive card variant: a real table on md+ and one stacked card per row
   * below md, so a 4-5 column table never squeezes or overflows on a phone.
   * A column with an empty header renders full-width (action columns).
   */
  card?: boolean;
}

function skeletonBlocks(count: number, lines: number): ReactNode {
  return Array.from({ length: count }).map((_, index) => (
    <div key={index} className="flex flex-col gap-2">
      {Array.from({ length: lines }).map((_, line) => (
        <div key={line} className="h-4 w-full animate-pulse rounded bg-surface-sunken" />
      ))}
    </div>
  ));
}

/**
 * docs/design/frontend.md section 6: sticky header, row hover; loading
 * (skeleton rows), empty (EmptyState inside), error. Collapses to horizontal
 * scroll within the card at 768px (frontend.md section 8) via the wrapping
 * overflow-x-auto - never the page itself. With `card`, drops to stacked
 * cards below md instead of horizontal-scrolling.
 */
export function Table<T>({
  columns,
  rows,
  rowKey,
  loading,
  error,
  emptyState,
  onRowClick,
  card = false,
}: TableProps<T>) {
  if (error) {
    return (
      <div className="rounded-lg border border-border bg-surface p-6 text-body-sm text-danger">
        {error}
      </div>
    );
  }

  const rowClass = `border-t border-border hover:bg-surface-sunken ${
    onRowClick ? "cursor-pointer" : ""
  }`;

  return (
    <>
      {/* md+: real table */}
      <div className={`${card ? "hidden md:block" : ""} overflow-x-auto rounded-lg border border-border bg-surface`}>
        <table className="w-full text-body-sm">
          <thead className="sticky top-0 bg-surface-sunken">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className="whitespace-nowrap px-4 py-2 text-left font-medium text-text-secondary"
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 3 }).map((_, index) => (
                <tr key={index} className="border-t border-border">
                  <td colSpan={columns.length} className="px-4 py-3">
                    <div className="h-4 w-full animate-pulse rounded bg-surface-sunken" />
                  </td>
                </tr>
              ))
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length}>{emptyState}</td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr
                  key={rowKey(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={rowClass}
                >
                  {columns.map((column) => (
                    <td key={column.key} className="whitespace-nowrap px-4 py-3 text-text">
                      {column.render(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* below md: stacked cards (only when the card variant is on) */}
      {card ? (
        <ul className="flex flex-col gap-3 md:hidden">
          {loading ? (
            skeletonBlocks(3, 2)
          ) : rows.length === 0 ? (
            <li className="rounded-card border border-border bg-surface p-4">{emptyState}</li>
          ) : (
            rows.map((row) => (
              <li
                key={rowKey(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={`rounded-card border border-border bg-surface p-4 shadow-card ${
                  onRowClick ? "cursor-pointer" : ""
                }`}
              >
                {columns.map((column) =>
                  column.header ? (
                    <div
                      key={column.key}
                      className="flex items-start justify-between gap-4 py-1.5"
                    >
                      <span className="shrink-0 text-footnote text-text-tertiary">
                        {column.header}
                      </span>
                      <span className="min-w-0 text-right text-body-sm text-text">
                        {column.render(row)}
                      </span>
                    </div>
                  ) : (
                    <div key={column.key} className="mt-2">
                      {column.render(row)}
                    </div>
                  ),
                )}
              </li>
            ))
          )}
        </ul>
      ) : null}
    </>
  );
}
