import { type ReactNode } from "react";

type BadgeVariant = "default" | "bull" | "bear" | "neutral" | "info";

interface SkeletonProps {
  /** Number of rows to render. Each row is a bar with slight spacing. */
  rows?: number;
  /** Height of each row in px. Defaults to 14 (≈ text-sm line height). */
  rowHeight?: number;
  /** Width CSS for each row — accepts any CSS width. Defaults to ``100%``. */
  width?: string | number;
  /** Extra classes for the outer container. */
  className?: string;
}

/**
 * Lightweight content placeholder used during initial load.
 *
 * Replaces the old "spinner on a blank page" pattern with a greyed-out
 * skeleton of the expected content shape. The perceived load time drops
 * because the layout is already in place when real data arrives — no
 * layout shift, no empty flash.
 */
export function Skeleton({ rows = 3, rowHeight = 14, width = "100%", className = "" }: SkeletonProps) {
  const bars = Array.from({ length: rows });
  return (
    <div className={`flex flex-col gap-2.5 ${className}`} role="status" aria-busy="true">
      {bars.map((_, i) => (
        <div
          key={i}
          className="animate-pulse rounded bg-slate-200/70"
          style={{
            height: rowHeight,
            width: i === rows - 1 && rows > 1 ? "60%" : width,
          }}
        />
      ))}
    </div>
  );
}

interface SkeletonChartProps {
  /** Chart height in px. */
  height?: number;
  /** Extra classes for the outer container. */
  className?: string;
}

/** Skeleton shaped like a chart area (one tall rectangle + axis ticks). */
export function SkeletonChart({ height = 320, className = "" }: SkeletonChartProps) {
  return (
    <div
      className={`flex items-end gap-1.5 rounded-lg border border-slate-100 bg-slate-50/60 p-4 ${className}`}
      style={{ height }}
      role="status"
      aria-busy="true"
    >
      {Array.from({ length: 14 }).map((_, i) => (
        <div
          key={i}
          className="animate-pulse rounded-t bg-slate-200/70"
          style={{ flex: 1, height: `${40 + ((i * 37) % 55)}%` }}
        />
      ))}
    </div>
  );
}

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-slate-100 text-slate-700",
  bull: "bg-green-50 text-green-700 ring-1 ring-green-200",
  bear: "bg-red-50 text-red-700 ring-1 ring-red-200",
  neutral: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  info: "bg-blue-50 text-blue-700 ring-1 ring-blue-200",
};

export function Badge({ variant = "default", children, className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
}

interface RefreshBadgeProps {
  /** Whether a background refresh is in progress (``useAsync.isStale``). */
  isStale: boolean;
  /** Optional label override. Defaults to ``更新中``. */
  label?: string;
  className?: string;
}

/**
 * Small "updating" indicator shown while a background refresh is running.
 *
 * The app keeps stale data visible during a refresh (stale-while-revalidate);
 * without this badge the user has no feedback that newer data is on the way,
 * so a demo viewer may mistake a stale chart for a frozen one.
 */
export function RefreshBadge({ isStale, label = "更新中", className = "" }: RefreshBadgeProps) {
  if (!isStale) return null;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-600 ring-1 ring-blue-200 ${className}`}
      role="status"
    >
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
      {label}
    </span>
  );
}

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function Spinner({ size = "md", className = "" }: SpinnerProps) {
  const sizeClass = { sm: "h-4 w-4", md: "h-8 w-8", lg: "h-12 w-12" }[size];
  return (
    <div className={`flex items-center justify-center ${className}`}>
      <svg className={`${sizeClass} animate-spin text-brand-500`} viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    </div>
  );
}

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {icon && <div className="mb-3 text-ink-muted">{icon}</div>}
      <p className="text-sm font-medium text-ink-secondary">{title}</p>
      {description && <p className="mt-1 text-xs text-ink-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <svg className="mb-3 h-10 w-10 text-bear" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
      </svg>
      <p className="text-sm font-medium text-bear">加载失败</p>
      <p className="mt-1 max-w-md text-xs text-ink-muted">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          重试
        </button>
      )}
    </div>
  );
}
