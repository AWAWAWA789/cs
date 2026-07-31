import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Spinner, EmptyState, ErrorState } from "../components/ui/misc";
import { api, isApiError } from "../lib/api";
import { useGlobalStore } from "../store/globalStore";
import type { SearchSuggestItem, SearchSuggestResponse } from "../types/csqaq";

/** 搜索防抖延迟（毫秒）。 */
const DEBOUNCE_MS = 600;

/**
 * 判断是否为请求被取消（AbortError）。
 * 取消请求不作为错误展示，仅用于打断过期的搜索。
 */
function isAbortError(err: unknown): boolean {
  if (err instanceof DOMException) return err.name === "AbortError";
  return (err as { name?: string } | null)?.name === "AbortError";
}

/** 搜索页面状态机：idle=未搜索 / loading=搜索中 / success=搜索完成 / error=搜索失败。 */
type SearchStatus = "idle" | "loading" | "success" | "error";

/**
 * 饰品搜索页 —— CSQAQ 量化平台的饰品名称联想搜索入口。
 *
 * - 顶部全宽大号搜索框，输入即触发联想搜索（300ms 防抖）
 * - 使用 AbortController 取消上一个未完成请求，避免竞态
 * - 结果以卡片列表展示，点击后写入全局 itemGoodId 并跳转至 /item/:good_id
 * - 覆盖未搜索、加载中、无结果、出错四种状态
 */
export default function SearchPage() {
  const [text, setText] = useState("");
  const [results, setResults] = useState<SearchSuggestItem[]>([]);
  const [status, setStatus] = useState<SearchStatus>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  /** 当前未完成请求的控制器，用于在发起新搜索或卸载时取消旧请求。 */
  const abortRef = useRef<AbortController | null>(null);

  const navigate = useNavigate();
  const setItemGoodId = useGlobalStore((s) => s.setItemGoodId);

  /**
   * 执行一次搜索请求。
   * - 取消上一个未完成请求，避免结果错乱
   * - 通过 controller 身份校验丢弃已被取代的过期响应
   * 该函数仅依赖稳定的 ref 与 setState，闭包不会过期。
   */
  function runSearch(query: string) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setStatus("loading");
    setErrorMsg("");

    api.item
      .search(query, controller.signal)
      .then((raw) => {
        // 若已被更新的请求取代，丢弃本次结果
        if (controller.signal.aborted || abortRef.current !== controller) return;
        const res = raw as SearchSuggestResponse;
        setResults(Array.isArray(res.data) ? res.data : []);
        setStatus("success");
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || abortRef.current !== controller) return;
        if (isAbortError(err)) return;
        setStatus("error");
        setErrorMsg(
          isApiError(err)
            ? err.detail
            : err instanceof Error
              ? err.message
              : String(err),
        );
      });
  }

  // 输入防抖：text 变化后延迟 300ms 触发搜索；输入过程中持续显示 loading
  useEffect(() => {
    const trimmed = text.trim();
    if (!trimmed) {
      // 清空输入：取消请求并回到初始态
      abortRef.current?.abort();
      abortRef.current = null;
      setResults([]);
      setErrorMsg("");
      setStatus("idle");
      return;
    }
    setStatus("loading");
    const timer = window.setTimeout(() => runSearch(trimmed), DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
    // runSearch 仅依赖稳定的 ref/setState，无需列入依赖
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  // 组件卸载时取消未完成请求，避免 setState 作用于已卸载组件
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const handleSelect = (item: SearchSuggestItem) => {
    setItemGoodId(item.good_id);
    navigate(`/item/${item.good_id}`);
  };

  const handleClear = () => {
    setText("");
  };

  const handleRetry = () => {
    const trimmed = text.trim();
    if (trimmed) runSearch(trimmed);
  };

  const trimmedText = text.trim();

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h1 className="text-2xl font-bold text-ink-primary">饰品搜索</h1>
        <p className="mt-1 text-sm text-ink-muted">
          通过名称联想搜索 CS:GO 饰品，点击结果查看多平台价格与历史走势
        </p>
      </div>

      {/* 大号搜索框 */}
      <div className="relative">
        <span className="pointer-events-none absolute inset-y-0 left-4 flex items-center text-ink-muted">
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" />
          </svg>
        </span>
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="搜索饰品名称，如「蝴蝶刀」「渐变」「崭新出厂」"
          autoFocus
          className="w-full rounded-xl border border-surface-border bg-surface-card py-4 pl-12 pr-12 text-base text-ink-primary shadow-card outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30"
        />
        {text && (
          <span className="absolute inset-y-0 right-2 flex items-center">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClear}
              aria-label="清除搜索内容"
              className="px-2"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </Button>
          </span>
        )}
      </div>

      {/* 搜索结果区域 */}
      {status === "idle" ? (
        <EmptyState
          title="输入饰品名称开始搜索"
          description="支持中文名称、系列与磨损度联想，例如「蝴蝶刀 | 渐变」「手套」「崭新出厂」。"
          icon={
            <svg className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" />
            </svg>
          }
        />
      ) : status === "loading" ? (
        <div className="flex flex-col items-center justify-center py-16">
          <Spinner size="lg" />
          <p className="mt-3 text-sm text-ink-muted">正在搜索「{trimmedText}」...</p>
        </div>
      ) : status === "error" ? (
        <ErrorState message={errorMsg || "搜索请求失败，请稍后重试"} onRetry={handleRetry} />
      ) : results.length === 0 ? (
        <EmptyState
          title="无搜索结果"
          description={`没有找到与「${trimmedText}」相关的饰品，请尝试更换关键词或减少筛选条件。`}
          icon={
            <svg className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.5M12 18h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          }
          action={
            <Button variant="secondary" size="md" onClick={handleClear}>
              清除搜索
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-ink-muted">共 {results.length} 条结果</p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {results.map((item) => (
              <div
                key={item.good_id}
                role="button"
                tabIndex={0}
                onClick={() => handleSelect(item)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    handleSelect(item);
                  }
                }}
                className="cursor-pointer rounded-xl outline-none transition focus-visible:ring-2 focus-visible:ring-brand-500"
              >
                <Card className="transition-shadow hover:shadow-card-hover">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-3">
                      <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z"
                          />
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 6h.008v.008H6V6z" />
                        </svg>
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-ink-primary">{item.name}</p>
                        <p className="mt-0.5 text-xs text-ink-muted">good_id: {item.good_id}</p>
                      </div>
                    </div>
                    <svg
                      className="h-5 w-5 flex-shrink-0 text-ink-muted"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                    </svg>
                  </div>
                </Card>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
