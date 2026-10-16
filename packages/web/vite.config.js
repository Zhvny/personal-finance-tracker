import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'
import fs from 'fs'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      disable: true,
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'icon/apple-touch-icon.png'],
      manifest: {
        name: 'Alpha',
        short_name: 'Alpha',
        description: 'Alpha Advanced Personal Finance & Quant Terminal',
        theme_color: '#0d0f1a',
        background_color: '#0d0f1a',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        icons: [
          {
            src: '/icon/android-chrome-192x192.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: '/icon/android-chrome-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable'
          }
        ]
      }
    })
  ],
  resolve: {
    dedupe: ['react', 'react-dom'],
  },
  server: {
    host: '0.0.0.0',
    port: 45678,
    strictPort: true,
    /*
    https: {
      key: fs.readFileSync(path.resolve(__dirname, 'certs/server.key')),
      cert: fs.readFileSync(path.resolve(__dirname, 'certs/server.crt')),
    },
    */
    hmr: {
      clientPort: 45678,
      protocol: 'ws',
    },
    historyApiFallback: true,
    proxy: {
      '/api': {
        // Dev-local default. In Docker, run vite with
        // API_TARGET=http://gateway:8444 (compose service DNS);
        // 127.0.0.1 only reaches the vite container's own loopback.
        target: process.env.API_TARGET || 'http://127.0.0.1:8444',
        changeOrigin: true,
        secure: false,
      }
    },
    watch: {
      ignored: ['**/data/**', '**/cache.db**']
    }
  },
  publicDir: 'public',
  test: {
    globals: true,
    environment: 'jsdom',
    css: true,
    include: [
      'tests/**/*.test.{js,jsx}',
      'tests/audit/**/*.test.{js,jsx}',
    ],
    testTimeout: 15000,
    setupFiles: [],
  },
})
