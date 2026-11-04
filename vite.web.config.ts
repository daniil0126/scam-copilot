import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'
import { defineConfig, type Plugin } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// The web copy of the side panel: the same React app, built for a browser tab and served by the backend under /app/.
// It carries no extension files (no manifest, no service worker, no content script).
const webPage = (): Plugin => ({
  name: 'scamcopilot-web-page',
  transformIndexHtml(html) {
    return html
      .replace('href="/favicon.svg"', 'href="./favicon.svg"')
      // The server answers /app/config.js with the access token, so no secret is built into the files.
      .replace('<script type="module"', '<script src="./config.js"></script>\n  <script type="module"')
  },
  generateBundle() {
    this.emitFile({ type: 'asset', fileName: 'favicon.svg', source: readFileSync(resolve(import.meta.dirname, 'public/favicon.svg')) })
  },
})

export default defineConfig({
  root: 'src',
  publicDir: false,
  base: './',
  define: { 'import.meta.env.VITE_API_URL': JSON.stringify('self') },
  plugins: [
    react(),
    babel({ presets: [reactCompilerPreset()] }),
    tailwindcss(),
    webPage(),
  ],
  build: {
    outDir: resolve(import.meta.dirname, 'dist-web'),
    emptyOutDir: true,
  },
})
