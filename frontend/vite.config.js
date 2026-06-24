import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Vite auto-exposes any VITE_-prefixed env var via import.meta.env. In
// particular VITE_ASSET_BASE_URL (consumed in SCALE_UI.deepfield.assetBase)
// overrides the default `/deepfield` asset base so production CDN builds can
// point Deep Field tile streaming at an external host. No config change needed
// here — documented for discoverability.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
