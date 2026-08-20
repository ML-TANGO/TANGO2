import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

import { inspectorServer } from '@react-dev-inspector/vite-plugin';

// ESM 환경 대응을 위한 고유 경로 설정
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

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

function ModelConfigPlugin() {
  return {
    name: 'model-config-api',
    configureServer(server) {
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

function SdsDatasetPlugin(datasetPath) {
  return {
    name: 'sds-dataset',
    configureServer(server) {
      const mime = {
        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.gif': 'image/gif', '.webp': 'image/webp',
        '.csv': 'text/csv', '.json': 'application/json', '.txt': 'text/plain',
      };

      server.middlewares.use('/sds-dataset', (req, res) => {
        const filePath = path.join(datasetPath, req.url.split('?')[0]);
        const ext = path.extname(filePath).toLowerCase();
        try {
          const data = fs.readFileSync(filePath);
          res.setHeader('Content-Type', mime[ext] ?? 'application/octet-stream');
          res.statusCode = 200;
          res.end(data);
        } catch (e) {
          res.statusCode = 404;
          res.end('Not found');
        }
      });
    },
  };
}

const config = ({ mode }) => {
  const envDir = path.resolve(__dirname, '.');
  const env = loadEnv(mode, envDir, '');
  
  if (env.REACT_EDITOR) {
    process.env.REACT_EDITOR = env.REACT_EDITOR;
  }
  console.log('[DEBUG] env.REACT_EDITOR:', env.REACT_EDITOR);
  console.log('[DEBUG] process.env.REACT_EDITOR:', process.env.REACT_EDITOR);

  const isLocal = env.VITE_REACT_APP_API_HOST === 'local';
  const sdsDatasetPath = path.resolve(__dirname, env.VITE_SDS_DATASET_PATH ?? '../../Field_Test/SDS/dataset/20260227/');

  return defineConfig({
    resolve: {
      alias: {
        '@src': path.resolve(__dirname, './src'),
        '@images': path.resolve(__dirname, './src/static/images'),
        '@tango': path.resolve(__dirname, './xlib'),
      },
    },
    envDir: './',
    plugins: [
      react(),
      inspectorServer(),
      I18nHotReload(),
      ModelConfigPlugin(),
      SdsDatasetPlugin(sdsDatasetPath)
    ].filter(Boolean), // null 값 제거 시팅
    build: {
      outDir: 'build',
    },
    server: {
      host: true,
      usePolling: true,
      ...(isLocal && {
        proxy: {
          '/api': {
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
          silenceDeprecations: ['legacy-js-api', 'import'],
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