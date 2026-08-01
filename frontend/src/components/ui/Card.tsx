import { type ReactNode } from "react";

interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}

export function Card({ title, subtitle, actions, children, className = "", bodyClassName = "" }: CardProps) {
  return (
    <div
      className={`rounded-xl border border-surface-border bg-surface-card shadow-card transition-shadow duration-200 hover:shadow-card-hover ${className}`}
    >
      {(title || actions) && (
        <div className="flex items-center justify-between border-b border-surface-border px-5 py-3">
          <div>
            {title && <h3 className="text-sm font-semibold text-ink-primary">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-muted">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={`p-5 ${bodyClassName}`}>{children}</div>
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  color?: "default" | "bull" | "bear" | "neutral";
}

export function StatCard({ label, value, hint, color = "default" }: StatCardProps) {
  const colorClass = {
    default: "text-ink-primary",
    bull: "text-bull",
    bear: "text-bear",
    neutral: "text-neutral",
  }[color];

  return (
    <div className="animate-fade-in rounded-xl border border-surface-border bg-surface-card p-4 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover">
      <p className="text-xs font-medium text-ink-muted">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${colorClass}`}>{value}</p>
      {hint && <p className="mt-0.5 text-xs text-ink-secondary">{hint}</p>}
    </div>
  );
}
