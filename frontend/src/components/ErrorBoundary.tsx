import { Component, type ReactNode, type ErrorInfo } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("React Error Boundary caught:", error, info);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen items-center justify-center bg-slate-50 p-8">
          <div className="max-w-lg rounded-xl border border-red-200 bg-white p-6 shadow-lg">
            <h2 className="text-lg font-bold text-red-600">应用渲染出错</h2>
            <p className="mt-2 text-sm text-slate-600">
              {this.state.error?.message ?? "未知错误"}
            </p>
            <pre className="mt-3 max-h-48 overflow-auto rounded-lg bg-slate-100 p-3 text-xs text-slate-700">
              {this.state.error?.stack ?? ""}
            </pre>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              刷新页面
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
