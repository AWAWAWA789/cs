import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { MetaResponse } from "../types/api";
import { Select } from "./ui/Select";
import { Button } from "./ui/Button";
import { useGlobalStore, DEFAULT_SUB_INDEX, DEFAULT_PERIOD } from "../store/globalStore";

/** Selector 组件的 props —— subIndex/period 从全局 store 读取，仅保留页面级回调。 */
interface SelectorProps {
  onRefresh?: () => void;
  loading?: boolean;
  refreshLabel?: string;
}

const FALLBACK_SUB_INDICES = [DEFAULT_SUB_INDEX];
const FALLBACK_PERIODS = [DEFAULT_PERIOD, "4hour", "1hour", "7day"];

const PERIOD_LABELS: Record<string, string> = {
  "1day": "日线",
  "4hour": "4小时",
  "1hour": "1小时",
  "7day": "周线",
};

/**
 * Meta 数据 Hook：加载后端支持的标的与周期列表。
 * 使用全局 signal 支持取消（meta 通常只加载一次，无需取消）。
 */
export function useMeta() {
  const [meta, setMeta] = useState<MetaResponse | null>(null);

  useEffect(() => {
    api.scenario.meta().then(setMeta).catch(() => {
      // Use defaults on error
    });
  }, []);

  return meta;
}

/**
 * 标的与周期选择器。
 *
 * 改造点：
 * 1. subIndex/period 从全局 Zustand store 读取，切换页面不丢失选择。
 * 2. meta 加载后校验当前值是否在选项列表中，不在则自动切换到第一项（修复 B4）。
 * 3. 去除 props 传入的 subIndex/period/onSubIndexChange/onPeriodChange。
 */
export function SubIndexSelector({
  onRefresh,
  loading,
  refreshLabel = "刷新数据",
}: SelectorProps) {
  const meta = useMeta();
  const subIndex = useGlobalStore((s) => s.subIndex);
  const period = useGlobalStore((s) => s.period);
  const setSubIndex = useGlobalStore((s) => s.setSubIndex);
  const setPeriod = useGlobalStore((s) => s.setPeriod);

  const subIndices = meta?.available_sub_indices?.length ? meta.available_sub_indices : FALLBACK_SUB_INDICES;
  const periods = meta?.supported_periods?.length ? meta.supported_periods : FALLBACK_PERIODS;

  // 修复 B4：校验当前 subIndex 是否在列表中，不在则自动选第一项
  useEffect(() => {
    if (subIndices.length > 0 && !subIndices.includes(subIndex)) {
      setSubIndex(subIndices[0]);
    }
  }, [subIndices, subIndex, setSubIndex]);

  // 校验当前 period 是否在列表中，不在则自动选第一项
  useEffect(() => {
    if (periods.length > 0 && !periods.includes(period)) {
      setPeriod(periods[0]);
    }
  }, [periods, period, setPeriod]);

  return (
    <div className="flex flex-wrap items-end gap-3">
      <Select
        label="标的"
        value={subIndex}
        onChange={(e) => setSubIndex(e.target.value)}
      >
        {subIndices.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </Select>
      <Select
        label="周期"
        value={period}
        onChange={(e) => setPeriod(e.target.value)}
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
