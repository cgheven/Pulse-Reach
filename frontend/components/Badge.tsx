import { cx, priorityClass, salesPriorityClass, statusClass } from "@/lib/utils";

export function PriorityBadge({ value }: { value?: string }) {
  return <span className={cx("badge", priorityClass(value))}>{value || "—"}</span>;
}

export function SalesPriorityBadge({ value }: { value?: string }) {
  return <span className={cx("badge", salesPriorityClass(value))}>{value || "—"}</span>;
}

export function StatusBadge({ value }: { value?: string }) {
  return <span className={cx("badge", statusClass(value))}>{(value || "new").replaceAll("_", " ")}</span>;
}
