import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useGlobalStore } from "../store/globalStore";
import { Spinner } from "./ui/misc";
import type { SearchSuggestItem, SearchSuggestResponse } from "../types/csqaq";

/** 输入防抖延迟（毫秒）。 */
const DEBOUNCE_MS = 600;
/** 失焦后关闭下拉的延迟（毫秒），留出时间让下拉项的点击事件触发。 */
const BLUR_CLOSE_MS = 160;

/**
 * 判断是否为请求被取消（AbortError）。
 * 取消请求不作为错误展示，仅用于打断过期的搜索。
 */
function isAbortError(err: unknown): boolean {
  if (err instanceof DOMException) return err.name === "AbortError";
  return (err as { name?: string } | null)?.name === "AbortError";
}

interface ItemSearchBarProps {
  /** 附加到最外层容器的额外 className（可用于控制宽度等）。 */
  className?: string;
  /** 输入框 placeholder。 */
  placeholder?: string;
  /**
   * 选中饰品时的回调。若提供，则调用该回调而非导航至 /item/:good_id。
   * 用于在非详情页（如吸货分析页）复用搜索框来填充 good_id。
   */
  onSelect?: (item: SearchSuggestItem) => void;
}

/**
 * 全局饰品搜索框 —— 可置于导航栏顶部的紧凑型搜索输入。
 *
 * - 输入即触发联想搜索（300ms 防抖）
 * - 结果以下拉浮层展示，支持键盘上下选择 / Enter 确认 / Esc 关闭
 * - 选中后写入全局 itemGoodId 并导航至 /item/:good_id
 * - 失焦后延迟关闭下拉，保证下拉项点击可正常触发
 */
export function ItemSearchBar({
  className = "",
  placeholder = "搜索饰品...",
  onSelect,
}: ItemSearchBarProps) {
  const [text, setText] = useState("");
  const [results, setResults] = useState<SearchSuggestItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [open, setOpen] = useState(false);
  /** 键盘高亮的下拉项索引，-1 表示未高亮。 */
  const [activeIndex, setActiveIndex] = useState(-1);

  /** 当前未完成请求的控制器，用于取消旧请求。 */
  const abortRef = useRef<AbortController | null>(null);
  /** 失焦关闭下拉的定时器句柄，用于在点击下拉项前取消关闭。 */
  const blurTimerRef = useRef<number | null>(null);

  const navigate = useNavigate();
  const setItemGoodId = useGlobalStore((s) => s.setItemGoodId);

  // 输入防抖搜索：text 变化后延迟 300ms 触发联想
  useEffect(() => {
    const trimmed = text.trim();
    if (!trimmed) {
      abortRef.current?.abort();
      abortRef.current = null;
      setResults([]);
      setLoading(false);
      setHasError(false);
      setOpen(false);
      setActiveIndex(-1);
      return;
    }
    setLoading(true);
    setHasError(false);
    const timer = window.setTimeout(() => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      api.item
        .search(trimmed, controller.signal)
        .then((raw) => {
          // 若已被更新的请求取代，丢弃本次结果
          if (controller.signal.aborted || abortRef.current !== controller) return;
          const res = raw as SearchSuggestResponse;
          const list = Array.isArray(res.data) ? res.data : [];
          setResults(list);
          setLoading(false);
          setActiveIndex(list.length > 0 ? 0 : -1);
          setOpen(true);
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted || abortRef.current !== controller) return;
          if (isAbortError(err)) return;
          setResults([]);
          setLoading(false);
          setHasError(true);
          setActiveIndex(-1);
          // 出错时仍展开下拉，展示错误提示
          setOpen(true);
        });
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [text]);

  // 卸载时取消未完成请求并清理定时器
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (blurTimerRef.current) window.clearTimeout(blurTimerRef.current);
    };
  }, []);

  const showDropdown = open && text.trim().length > 0;

  const closeDropdown = () => {
    setOpen(false);
    setActiveIndex(-1);
  };

  const cancelPendingClose = () => {
    if (blurTimerRef.current) {
      window.clearTimeout(blurTimerRef.current);
      blurTimerRef.current = null;
    }
  };

  const handleFocus = () => {
    // 聚焦时撤销尚未执行的关闭操作，并在有内容时重新展开
    cancelPendingClose();
    if (text.trim() && (results.length > 0 || loading || hasError)) {
      setOpen(true);
    }
  };

  const handleBlur = () => {
    // 延迟关闭，使下拉项的 onClick 能在关闭前触发
    blurTimerRef.current = window.setTimeout(() => {
      closeDropdown();
      blurTimerRef.current = null;
    }, BLUR_CLOSE_MS);
  };

  const handleSelect = (item: SearchSuggestItem) => {
    cancelPendingClose();
    setItemGoodId(item.good_id);
    if (onSelect) {
      // 回调模式：仅通知父组件选中的饰品，不导航
      onSelect(item);
    } else {
      navigate(`/item/${item.good_id}`);
    }
    setText("");
    closeDropdown();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!text.trim()) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      if (results.length === 0) return;
      setActiveIndex((idx) => (idx + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      if (results.length === 0) return;
      setActiveIndex((idx) => (idx - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      if (open && activeIndex >= 0 && activeIndex < results.length) {
        e.preventDefault();
        handleSelect(results[activeIndex]);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      closeDropdown();
    }
  };

  return (
    <div className={`relative ${className}`}>
      {/* 搜索图标 */}
      <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-ink-muted">
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" />
        </svg>
      </span>
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        aria-label="搜索饰品"
        aria-expanded={showDropdown}
        aria-autocomplete="list"
        autoComplete="off"
        className="w-full rounded-lg border border-surface-border bg-surface-card py-2 pl-9 pr-3 text-sm text-ink-primary outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30"
      />

      {/* 下拉浮层 */}
      {showDropdown && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-lg border border-surface-border bg-surface-card shadow-card-hover">
          {hasError ? (
            <div className="px-4 py-3 text-sm text-bear">搜索失败，请重试</div>
          ) : loading ? (
            <div className="flex items-center gap-2 px-4 py-3 text-sm text-ink-muted">
              <Spinner size="sm" />
              <span>搜索中...</span>
            </div>
          ) : results.length === 0 ? (
            <div className="px-4 py-3 text-sm text-ink-muted">无搜索结果</div>
          ) : (
            <ul className="max-h-80 overflow-y-auto py-1" role="listbox">
              {results.map((item, idx) => (
                <li key={item.good_id} role="option" aria-selected={idx === activeIndex}>
                  <button
                    type="button"
                    onMouseEnter={() => setActiveIndex(idx)}
                    onClick={() => handleSelect(item)}
                    className={`flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm transition-colors ${
                      idx === activeIndex
                        ? "bg-brand-50 text-brand-700"
                        : "text-ink-primary hover:bg-surface-hover"
                    }`}
                  >
                    <span className="truncate">{item.name}</span>
                    <span className="shrink-0 text-xs text-ink-muted">#{item.good_id}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
