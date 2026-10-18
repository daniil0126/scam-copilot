import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  root: 'src',
  publicDir: resolve(import.meta.dirname, 'public'),
  base: './',
  plugins: [
    react(),
    babel({ presets: [reactCompilerPreset()] }),
    tailwindcss(),
  ],
  build: {
    outDir: resolve(import.meta.dirname, 'dist'),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        index: resolve(import.meta.dirname, 'src/index.html'),
        service_worker: resolve(import.meta.dirname, 'src/service_worker.ts'),
      },
      output: {
        entryFileNames: (chunk) =>
          chunk.name === 'service_worker' ? 'service_worker.js' : 'assets/[name]-[hash].js',
      },
    },
  },
})
