/** Formatting utility functions for numbers, dates, and percentages. */

/**
 * Format a number as a percentage string.
 * @param value A fraction (0.15 => "15.00%")
 * @param digits Number of decimal places
 */
export function formatPercent(value: number, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return `${(value * 100).toFixed(digits)}%`;
}

/**
 * Format a raw number with thousands separators.
 * @param value The number to format
 * @param digits Number of decimal places
 */
export function formatNumber(value: number, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/**
 * Format a price value (compact for large numbers).
 * @param value Price value
 */
export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  if (Math.abs(value) >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  }
  return value.toFixed(4);
}

/**
 * Format an ISO date string to a readable Chinese date.
 * @param iso ISO 8601 string
 */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "--";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Format an ISO date string to a short date (YYYY-MM-DD).
 */
export function formatDateShort(iso: string | null | undefined): string {
  if (!iso) return "--";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

/**
 * Format file size in bytes to a human-readable string.
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

/**
 * Format milliseconds to a human-readable duration.
 */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const mins = Math.floor(ms / 60_000);
  const secs = Math.floor((ms % 60_000) / 1000);
  return `${mins}m${secs}s`;
}

/**
 * Get a color class for a direction label.
 */
export function directionColor(label: string): string {
  switch (label) {
    case "bullish":
      return "text-bull";
    case "bearish":
      return "text-bear";
    default:
      return "text-neutral";
  }
}

/**
 * Get a Chinese label for a direction.
 */
export function directionLabel(label: string): string {
  switch (label) {
    case "bullish":
      return "看涨";
    case "bearish":
      return "看跌";
    default:
      return "中性";
  }
}

/**
 * Get a Chinese label for an exit reason.
 */
export function exitReasonLabel(reason: string): string {
  const map: Record<string, string> = {
    stop_loss: "止损",
    take_profit: "止盈",
    signal_exit: "信号退出",
    end_of_data: "数据结束",
    trailing_stop: "追踪止损",
  };
  return map[reason] || reason;
}
