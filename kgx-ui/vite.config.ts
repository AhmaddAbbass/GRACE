// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// You can override this with an .env file later (VITE_API_BASE)
const API = process.env.VITE_API_BASE ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      // KG catalogue and misc
      '/kgs': API,
      '/summaries': API,
      '/healthz': API,

      // RAG endpoints (we’ll call /hi/... from the UI)
      '/hi': API,            // covers /hi/retrieve, /hi/answer, /hi/history, etc.

      // Static JSONs served by backend under /data/<rag>/...
      '/data': API,

      // If your backend also exposes top-level routes, keep these:
      '/retrieve': API,
      '/answer': API,
      '/history': API,
    }
  }
})
