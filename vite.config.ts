import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 5173,
    hmr: {
      overlay: false,
    },
    proxy: {
      '/slots': 'http://localhost:8000',
      '/slot-stats': 'http://localhost:8000',
      '/analysis-status': 'http://localhost:8000',
      '/start-analysis': 'http://localhost:8000',
      '/stop-analysis': 'http://localhost:8000',
      '/reset-slots': 'http://localhost:8000',
      '/upload-parking-video': 'http://localhost:8000',
    }
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
