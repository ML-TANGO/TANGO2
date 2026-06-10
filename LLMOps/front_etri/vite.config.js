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
        '@jonathan': path.resolve(__dirname, './xlib'),
      },
    },
    envDir: './',
    plugins: [react(), I18nHotReload()],
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
