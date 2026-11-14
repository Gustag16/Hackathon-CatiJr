import fs from 'node:fs'
import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    {
      name: 'local-media-fallback',
      configureServer(server) {
        server.middlewares.use('/media', (req, res, next) => {
          const cleanUrl = (req.url || '').split('?')[0]
          const candidates = [
            path.resolve(import.meta.dirname, '../backend/media', `.${cleanUrl}`),
            path.resolve(import.meta.dirname, '../media', `.${cleanUrl}`),
          ]
          for (const filePath of candidates) {
            if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
              const ext = path.extname(filePath).toLowerCase()
              const mime =
                ext === '.png'
                  ? 'image/png'
                  : ext === '.webp'
                    ? 'image/webp'
                    : 'image/jpeg'
              res.setHeader('Content-Type', mime)
              fs.createReadStream(filePath).pipe(res)
              return
            }
          }
          next()
        })
      },
    },
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        headers: {
          Origin: 'http://localhost:8000',
          Referer: 'http://localhost:8000/',
        },
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
        headers: {
          Origin: 'http://localhost:8000',
        },
      },
      '/media': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
