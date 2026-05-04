import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  css: {
    preprocessorOptions: {
      less: {
        additionalData: `@import "@/styles/variables.less";`,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 1600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (
            id.includes('/node_modules/echarts/') ||
            id.includes('\\node_modules\\echarts\\') ||
            id.includes('/node_modules/zrender/') ||
            id.includes('\\node_modules\\zrender\\') ||
            id.includes('/node_modules/vue-echarts/') ||
            id.includes('\\node_modules\\vue-echarts\\')
          ) {
            return 'charts'
          }
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
})
