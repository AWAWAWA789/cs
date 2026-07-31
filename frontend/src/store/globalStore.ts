/**
 * 全局状态管理 —— Zustand store
 *
 * 职责：
 * 1. 全局共享标的选择（subIndex）、周期（period）、平台（platform）、
 *    单品ID（itemGoodId）和图表指标（chartKey），切换页面不丢失。
 * 2. 提供 URL 同步辅助函数，支持分享链接与刷新保持。
 * 3. 持久化到 localStorage，浏览器重启后恢复上次选择。
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

/** 默认标的与周期，meta 加载后会校验是否可用。 */
export const DEFAULT_SUB_INDEX = "手套";
export const DEFAULT_PERIOD = "1day";

/** 单品图表可选指标 key（对应 CSQAQ /info/chart 的 11 种指标）。 */
export type ChartKey =
  | "sell_price"
  | "buy_price"
  | "short_lease_price"
  | "long_lease_price"
  | "lease_annual"
  | "long_lease_annual"
  | "sell_num"
  | "buy_num"
  | "lease_num"
  | "turnover_number"
  | "transfer_price";

/** 平台枚举：1-BUFF / 2-悠悠有品 / 3-Steam / 4-C5GAME。 */
export type Platform = 1 | 2 | 3 | 4;

export interface GlobalState {
  /** 子指数标的名称（如"手套"）。 */
  subIndex: string;
  /** K 线周期：1hour / 4hour / 1day / 7day。 */
  period: string;
  /** 当前查看的单品 good_id（单品详情页使用），null 表示未选中。 */
  itemGoodId: string | null;
  /** 单品图表平台：1-BUFF / 2-悠悠有品 / 3-Steam / 4-C5GAME。 */
  platform: Platform;
  /** 单品图表指标 key。 */
  chartKey: ChartKey;
  /** 单品图表周期（天）：7/15/30/90/180/365/1095。 */
  chartPeriod: number;

  setSubIndex: (subIndex: string) => void;
  setPeriod: (period: string) => void;
  setItemGoodId: (itemGoodId: string | null) => void;
  setPlatform: (platform: Platform) => void;
  setChartKey: (chartKey: ChartKey) => void;
  setChartPeriod: (chartPeriod: number) => void;

  /** 从 URL search params 读取并覆盖当前状态（刷新时调用）。 */
  hydrateFromUrl: (search: string) => void;
  /** 将当前状态序列化为 URL search params 字符串。 */
  serializeToUrl: () => string;
}

/**
 * 解析 URL query string 为状态片段。
 * 仅识别 sub / period / item / platform / ckey / cperiod 六个 key。
 */
function parseUrl(search: string): Partial<GlobalState> {
  const params = new URLSearchParams(search);
  const patch: Partial<GlobalState> = {};
  const sub = params.get("sub");
  const period = params.get("period");
  const item = params.get("item");
  const platform = params.get("platform");
  const ckey = params.get("ckey");
  const cperiod = params.get("cperiod");

  if (sub) patch.subIndex = sub;
  if (period) patch.period = period;
  if (item) patch.itemGoodId = item;
  if (platform) {
    const n = Number(platform);
    if (n >= 1 && n <= 4) patch.platform = n as Platform;
  }
  if (ckey) patch.chartKey = ckey as ChartKey;
  if (cperiod) {
    const n = Number(cperiod);
    if (Number.isFinite(n) && n > 0) patch.chartPeriod = n;
  }
  return patch;
}

export const useGlobalStore = create<GlobalState>()(
  persist(
    (set, get) => ({
      subIndex: DEFAULT_SUB_INDEX,
      period: DEFAULT_PERIOD,
      itemGoodId: null,
      platform: 1,
      chartKey: "sell_price",
      chartPeriod: 30,

      setSubIndex: (subIndex) => set({ subIndex }),
      setPeriod: (period) => set({ period }),
      setItemGoodId: (itemGoodId) => set({ itemGoodId }),
      setPlatform: (platform) => set({ platform }),
      setChartKey: (chartKey) => set({ chartKey }),
      setChartPeriod: (chartPeriod) => set({ chartPeriod }),

      hydrateFromUrl: (search) => {
        const patch = parseUrl(search);
        if (Object.keys(patch).length > 0) set(patch);
      },

      serializeToUrl: () => {
        const { subIndex, period, itemGoodId, platform, chartKey, chartPeriod } = get();
        const params = new URLSearchParams();
        params.set("sub", subIndex);
        params.set("period", period);
        if (itemGoodId) params.set("item", itemGoodId);
        params.set("platform", String(platform));
        params.set("ckey", chartKey);
        params.set("cperiod", String(chartPeriod));
        return params.toString();
      },
    }),
    {
      name: "csqaq-global-storage",
      // 仅持久化数据字段，不持久化方法
      partialize: (state) => ({
        subIndex: state.subIndex,
        period: state.period,
        itemGoodId: state.itemGoodId,
        platform: state.platform,
        chartKey: state.chartKey,
        chartPeriod: state.chartPeriod,
      }),
    },
  ),
);
