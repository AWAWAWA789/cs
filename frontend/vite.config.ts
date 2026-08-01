import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ["echarts", "echarts-for-react"],
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/scenario": "http://localhost:8000",
      "/backtest": "http://localhost:8000",
      "/ensemble": "http://localhost:8000",
      "/trend-scan": "http://localhost:8000",
      "/reports": "http://localhost:8000",
      "/data": "http://localhost:8000",
      "/monitoring": "http://localhost:8000",
      "/item": "http://localhost:8000",
      "/rank": "http://localhost:8000",
      "/monitor": "http://localhost:8000",
      "/volume": "http://localhost:8000",
      "/accumulation": "http://localhost:8000",
    },
  },
});
