import { type SelectHTMLAttributes, type ReactNode } from "react";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  children: ReactNode;
}

export function Select({ label, children, className = "", ...rest }: SelectProps) {
  return (
    <label className="flex flex-col gap-1">
      {label && <span className="text-xs font-medium text-ink-secondary">{label}</span>}
      <select
        className={`rounded-lg border border-surface-border bg-surface-card px-3 py-2 text-sm text-ink-primary focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 ${className}`}
        {...rest}
      >
        {children}
      </select>
    </label>
  );
}

interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export function TextInput({ label, className = "", ...rest }: TextInputProps) {
  return (
    <label className="flex flex-col gap-1">
      {label && <span className="text-xs font-medium text-ink-secondary">{label}</span>}
      <input
        className={`rounded-lg border border-surface-border bg-surface-card px-3 py-2 text-sm text-ink-primary focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 ${className}`}
        {...rest}
      />
    </label>
  );
}
