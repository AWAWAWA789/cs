import { Link } from "react-router-dom";
import { Button } from "../components/ui/Button";

/**
 * 404 页面 —— 替换原先兜底路由直接渲染 Dashboard 的行为。
 */
export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center space-y-6 text-center">
      <div>
        <p className="text-7xl font-bold text-brand-600">404</p>
        <h1 className="mt-4 text-2xl font-bold text-ink-primary">页面不存在</h1>
        <p className="mt-2 text-sm text-ink-muted">
          您访问的页面可能已被移除或地址输入有误。
        </p>
      </div>
      <Link to="/">
        <Button variant="primary" size="md">
          返回首页
        </Button>
      </Link>
    </div>
  );
}
