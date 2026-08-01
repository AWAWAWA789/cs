import { useState } from "react";
import { Card } from "../components/ui/Card";
import { Badge, Spinner, EmptyState, ErrorState } from "../components/ui/misc";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { formatBytes, formatDate } from "../lib/format";
import type { ReportGetResponse } from "../types/api";

export default function ReportsPage() {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  // 报告文件列表（仅在挂载时加载一次）
  const list = useAsync((signal) => api.reports.list(signal), []);

  // 当前选中报告的 JSON 内容，未选中时返回 null
  const content = useAsync<ReportGetResponse | null>(
    (signal) =>
      selectedFile
        ? api.reports.get(selectedFile, signal)
        : Promise.resolve<ReportGetResponse | null>(null),
    [selectedFile],
  );

  const reports = list.data?.reports ?? [];
  const selectedReport = reports.find((r) => r.filename === selectedFile) ?? null;
  const jsonText = content.data?.content
    ? JSON.stringify(content.data.content, null, 2)
    : "";

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h1 className="text-2xl font-bold text-ink-primary">报告查看</h1>
        <p className="mt-1 text-sm text-ink-muted">
          浏览已生成的扫描报告文件，查看详细的 JSON 内容
        </p>
      </div>

      {/* 双栏布局：左侧文件列表 + 右侧内容 */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* 左侧：报告列表 */}
        <Card
          title="报告列表"
          className="lg:col-span-1"
          actions={
            list.data ? <Badge variant="info">共 {reports.length} 份</Badge> : undefined
          }
        >
          {list.loading ? (
            <Spinner className="py-10" />
          ) : list.error ? (
            <ErrorState message={list.error} onRetry={list.refetch} />
          ) : reports.length === 0 ? (
            <EmptyState title="暂无报告" description="尚未生成任何报告文件。" />
          ) : (
            <ul className="space-y-1">
              {reports.map((file) => {
                const active = file.filename === selectedFile;
                return (
                  <li key={file.filename}>
                    <button
                      type="button"
                      onClick={() => setSelectedFile(file.filename)}
                      className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                        active
                          ? "border-brand-500 bg-brand-50"
                          : "border-transparent hover:bg-surface-hover"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`truncate text-sm font-medium ${
                            active ? "text-brand-700" : "text-ink-primary"
                          }`}
                          title={file.filename}
                        >
                          {file.filename}
                        </span>
                        {active && <Badge variant="info">已选</Badge>}
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-xs text-ink-muted">
                        <span>{formatBytes(file.size_bytes)}</span>
                        <span>·</span>
                        <span>{formatDate(file.modified_at)}</span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        {/* 右侧：报告内容 */}
        <Card
          title="报告内容"
          className="lg:col-span-2"
          actions={
            selectedReport ? (
              <Badge variant="default">{selectedReport.filename}</Badge>
            ) : undefined
          }
        >
          {!selectedFile ? (
            <EmptyState
              title="请选择报告"
              description="从左侧列表中选择一份报告以查看其 JSON 内容。"
            />
          ) : content.loading ? (
            <Spinner className="py-10" />
          ) : content.error ? (
            <ErrorState message={content.error} onRetry={content.refetch} />
          ) : !content.data || !content.data.content ? (
            <EmptyState title="内容为空" description="该报告文件没有可显示的内容。" />
          ) : (
            <pre className="max-h-[640px] overflow-auto rounded-lg bg-surface-base p-4 font-mono text-xs leading-relaxed text-ink-primary">
              {jsonText}
            </pre>
          )}
        </Card>
      </div>
    </div>
  );
}
