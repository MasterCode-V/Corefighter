import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Point the dev proxy at another backend (e.g. an SSH tunnel to the VPS)
// with:  CF_API_PROXY=http://127.0.0.1:8088 npm run dev
const target = process.env.CF_API_PROXY || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target, changeOrigin: true },
      '/health': { target, changeOrigin: true },
    },
  },
})
