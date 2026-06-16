import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

const path = require('path');

function I18nHotReload() {
  return {
    name: 'i18n-hot-reload',
    handleHotUpdate({ file, server }) {
      if (file.endsWith('.json')) {
        server.ws.send({
          type: 'custom',
          event: 'locales-update',
        });
      }
    },
  };
}

// Serves /api/model-config?model_id=xxx → returns config.json from the local
// checkpoint directory so the browser can build the architecture graph directly.
function ModelConfigPlugin() {
  return {
    name: 'model-config-api',
    configureServer(server) {
      const fs = require('fs');

      const MODEL_PATHS = {
        'llama-single': '/home/etri/Downloads/Llama-3.1-8B-Instruct',
      };
      const DEFAULT_DIR = '/home/etri/Downloads/Llama-3.1-8B-Instruct';

      server.middlewares.use('/api/model-config', (req, res) => {
        const url     = new URL(req.url, 'http://localhost');
        const mId     = url.searchParams.get('model_id') ?? '';
        const dir     = MODEL_PATHS[mId] ?? DEFAULT_DIR;
        const cfgPath = path.join(dir, 'config.json');

        try {
          const data = fs.readFileSync(cfgPath, 'utf-8');
          res.setHeader('Content-Type', 'application/json; charset=utf-8');
          res.statusCode = 200;
          res.end(data);
        } catch (e) {
          res.setHeader('Content-Type', 'application/json; charset=utf-8');
          res.statusCode = 404;
          res.end(JSON.stringify({ error: e.message }));
        }
      });
    },
  };
}

// https://vitejs.dev/config/
const config = ({ mode }) => {
  // process.env = { ...process.env, ...loadEnv(mode, process.cwd()) };
  const envDir = path.resolve(__dirname, '.');
  const env = loadEnv(mode, envDir, '');
  const isLocal = env.VITE_REACT_APP_API_HOST === 'local';

  return defineConfig({
    resolve: {
      alias: {
        '@src': path.resolve(__dirname, './src'),
        '@images': path.resolve(__dirname, './src/static/images'),
        '@tango': path.resolve(__dirname, './xlib'),
      },
    },
    envDir: './',
    plugins: [react(), I18nHotReload(), ModelConfigPlugin()],
    build: {
      outDir: 'build',
    },
    server: {
      host: true,
      usePolling: true,
      ...(isLocal && {
        proxy: {
          '/api': {
            // target: 'http://115.71.28.100/api',
            target: 'http://115.71.28.72/api',
            changeOrigin: true,
            rewrite: (path) => path.replace(/^\/api/, ''),
          },
        },
      }),
    },
    preview: {
      open: true,
    },
    css: {
      preprocessorOptions: {
        scss: {
          api: 'modern',
          silenceDeprecations: [
            'legacy-js-api', // JS 레거시 API 경고
            'import', // @import 경고
          ],
        },
        sass: {
          api: 'modern',
          silenceDeprecations: ['legacy-js-api', 'import'],
        },
      },
    },
  });
};

export default config;
