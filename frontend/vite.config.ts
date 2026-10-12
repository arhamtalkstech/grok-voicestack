import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backend = process.env.VOICESTACK_BACKEND ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: backend, ws: true, changeOrigin: true },
      '/webhooks': { target: backend, changeOrigin: true },
      '/healthz': { target: backend },
    },
  },
  build: { chunkSizeWarningLimit: 900 },
})
