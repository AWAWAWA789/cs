import { useState } from "react";
import { Card, StatCard } from "../components/ui/Card";
import { Badge, Spinner, EmptyState, ErrorState } from "../components/ui/misc";
import { SubIndexSelector } from "../components/Selector";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { formatBytes, formatDate, formatNumber } from "../lib/format";

/** 数据刷新后的内联提示消息。 */
interface RefreshMessage {
  type: "success" | "error";
  text: string;
}

export default function DataPage() {
  const [subIndex, setSubIndex] = useState("手套");
  const [period, setPeriod] = useState("1day");

  // 缓存状态：通过 useAsync 管理，数据刷新成功后调用 refetch 重新加载
  const cache = useAsync(() => api.data.cacheStatus(), []);
  const { refetch } = cache;

  // 数据刷新的独立 loading 与提示消息状态
  const [refreshLoading, setRefreshLoading] = useState(false);
  const [message, setMessage] = useState<RefreshMessage | null>(null);

  const handleRefresh = async () => {
    setRefreshLoading(true);
    setMessage(null);
    try {
      const res = await api.data.refresh(subIndex, period);
      if (res.success) {
        setMessage({
          type: "success",
          text: res.message || `数据刷新成功，共获取 ${res.bar_count} 根K线`,
        });
        // 刷新成功后自动重新加载缓存状态
        refetch();
      } else {
        setMessage({
          type: "error",
          text: res.message || "数据刷新失败，请稍后重试",
        });
      }
    } catch (err) {
      setMessage({
        type: "error",
        text: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setRefreshLoading(false);
    }
  };

  const totalFiles = cache.data?.total_files ?? 0;
  const totalSize = cache.data?.total_size_bytes ?? 0;
  const totalBars = (cache.data?.files ?? []).reduce(
    (sum, f) => sum + (f.bar_count ?? 0),
    0,
  );

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h1 className="text-2xl font-bold text-ink-primary">数据管理</h1>
        <p className="mt-1 text-sm text-ink-muted">
          查看本地数据缓存状态，并按标的与周期触发数据刷新
        </p>
      </div>

      {/* 标的与周期选择器 + 刷新按钮 */}
      <SubIndexSelector
        subIndex={subIndex}
        period={period}
        onSubIndexChange={setSubIndex}
        onPeriodChange={setPeriod}
        onRefresh={handleRefresh}
        loading={refreshLoading}
        refreshLabel="刷新数据"
      />

      {/* 刷新结果提示 */}
      {message && (
        <div
          className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm ${
            message.type === "success"
              ? "border-bull/30 bg-bull/5 text-bull"
              : "border-bear/30 bg-bear/5 text-bear"
          }`}
        >
          <span className="mt-0.5 shrink-0">
            {message.type === "success" ? (
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v2m0 4h.01M5.07 19h13.86c1.54 0 2.5-1.67 1.73-3L13.73 4a2 2 0 00-3.46 0L3.34 16c-.77 1.33.19 3 1.73 3z"
                />
              </svg>
            )}
          </span>
          <div className="flex-1">
            <p className="font-medium">
              {message.type === "success" ? "刷新成功" : "刷新失败"}
            </p>
            <p className="mt-0.5 text-xs opacity-80">{message.text}</p>
          </div>
          <button
            type="button"
            onClick={() => setMessage(null)}
            className="shrink-0 opacity-50 transition-opacity hover:opacity-100"
            aria-label="关闭提示"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* 缓存概览指标 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">缓存概览</h2>
        {cache.loading ? (
          <Spinner className="py-10" />
        ) : cache.error ? (
          <ErrorState message={cache.error} onRetry={refetch} />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard
              label="缓存文件数"
              value={formatNumber(totalFiles, 0)}
              hint="本地缓存文件总数"
            />
            <StatCard
              label="缓存总大小"
              value={formatBytes(totalSize)}
              hint="所有缓存文件占用空间"
            />
            <StatCard
              label="K线总数"
              value={formatNumber(totalBars, 0)}
              hint="缓存中K线数据总量"
            />
          </div>
        )}
      </section>

      {/* 缓存文件列表 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-ink-secondary">缓存文件列表</h2>
        <Card
          title="缓存文件"
          subtitle={cache.data ? `目录：${cache.data.cache_dir}` : undefined}
          actions={
            cache.data ? (
              <Badge variant="info">共 {cache.data.files.length} 个文件</Badge>
            ) : undefined
          }
          bodyClassName="p-0"
        >
          {cache.loading ? (
            <Spinner className="py-10" />
          ) : cache.error ? (
            <ErrorState message={cache.error} onRetry={refetch} />
          ) : !cache.data || cache.data.files.length === 0 ? (
            <EmptyState
              title="暂无缓存文件"
              description="本地数据缓存为空，请选择标的与周期后点击「刷新数据」。"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-border bg-surface-hover text-left text-xs text-ink-muted">
                    <th className="px-5 py-3 font-medium">文件名</th>
                    <th className="px-5 py-3 text-right font-medium">文件大小</th>
                    <th className="px-5 py-3 text-right font-medium">K线数量</th>
                    <th className="px-5 py-3 text-right font-medium">修改时间</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {cache.data.files.map((file, idx) => (
                    <tr
                      key={`${file.filename}-${idx}`}
                      className="transition-colors hover:bg-surface-hover"
                    >
                      <td className="px-5 py-3 font-medium text-ink-primary">
                        {file.filename}
                      </td>
                      <td className="px-5 py-3 text-right text-ink-secondary">
                        {formatBytes(file.size_bytes)}
                      </td>
                      <td className="px-5 py-3 text-right text-ink-secondary">
                        {file.bar_count !== null ? formatNumber(file.bar_count, 0) : "--"}
                      </td>
                      <td className="px-5 py-3 text-right text-ink-secondary">
                        {formatDate(file.modified_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}
