import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { MetaResponse } from "../types/api";
import { Select } from "./ui/Select";
import { Button } from "./ui/Button";

interface SelectorProps {
  subIndex: string;
  period: string;
  onSubIndexChange: (v: string) => void;
  onPeriodChange: (v: string) => void;
  onRefresh?: () => void;
  loading?: boolean;
  refreshLabel?: string;
}

const DEFAULT_SUB_INDICES = ["手套"];
const DEFAULT_PERIODS = ["1day", "4hour", "1hour", "7day"];

const PERIOD_LABELS: Record<string, string> = {
  "1day": "日线",
  "4hour": "4小时",
  "1hour": "1小时",
  "7day": "周线",
};

export function useMeta() {
  const [meta, setMeta] = useState<MetaResponse | null>(null);

  useEffect(() => {
    api.scenario.meta().then(setMeta).catch(() => {
      // Use defaults on error
    });
  }, []);

  return meta;
}

export function SubIndexSelector({
  subIndex,
  period,
  onSubIndexChange,
  onPeriodChange,
  onRefresh,
  loading,
  refreshLabel = "刷新数据",
}: SelectorProps) {
  const meta = useMeta();
  const subIndices = meta?.available_sub_indices?.length ? meta.available_sub_indices : DEFAULT_SUB_INDICES;
  const periods = meta?.supported_periods?.length ? meta.supported_periods : DEFAULT_PERIODS;

  return (
    <div className="flex flex-wrap items-end gap-3">
      <Select
        label="标的"
        value={subIndex}
        onChange={(e) => onSubIndexChange(e.target.value)}
      >
        {subIndices.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </Select>
      <Select
        label="周期"
        value={period}
        onChange={(e) => onPeriodChange(e.target.value)}
      >
        {periods.map((p) => (
          <option key={p} value={p}>{PERIOD_LABELS[p] ?? p}</option>
        ))}
      </Select>
      {onRefresh && (
        <Button variant="secondary" size="md" onClick={onRefresh} loading={loading}>
          {refreshLabel}
        </Button>
      )}
    </div>
  );
}

export { PERIOD_LABELS };
