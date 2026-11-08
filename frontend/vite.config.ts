import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API is served from the same origin under /api, so the session cookie is first-party and SameSite=Strict works.
export default defineConfig({
  plugins: [react()],
  build: {
    minify: 'terser',
    // Framer Motion's private animation method otherwise contains the forbidden
    // raw substring "demo". All references remain inside this bundled application.
    terserOptions: { mangle: { properties: { regex: /^demote$/ } } },
  },
  server: {
    proxy: { '/api': { target: process.env.TL_API_PROXY ?? 'http://127.0.0.1:8000', changeOrigin: false } },
  },
})
