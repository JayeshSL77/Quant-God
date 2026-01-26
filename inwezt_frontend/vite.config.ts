import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    build: {
        outDir: '../static',
        emptyOutDir: true,
    },
    server: {
        port: 3000,
        proxy: {
            '/api': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
                xfwd: true,
                buffer: false,
            },
            '/health': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
                xfwd: true,
                buffer: false,
            }
        }
    }
})
