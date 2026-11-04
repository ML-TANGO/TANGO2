import { applyMiddleware, compose, createStore } from 'redux';
import { persistReducer, persistStore } from 'redux-persist';
import storageSession from 'redux-persist/lib/storage/session';
import thunkMiddleware from 'redux-thunk';

import customHistory from '../customHistory';
import modules from './modules';

const composeEnhancer =
  (import.meta.env.VITE_REACT_APP_ENVIRONMENT !== 'live' &&
    window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__) ||
  compose;

const persistConfig = {
  key: 'root',
  storage: storageSession,
  blacklist: [
    'modal',
    'confirm',
    'nav',
    'loading',
    'upload',
    'tab',
    'progressList',
    'prompt',
    'download',
    'breadCrumb',
    'headerOptions',
    'popup',
    'alarmNotice',
    'uploadLoading',
    'popupState',
    'llmPlayground',
    'llmprompt',
    'llmRag',
    'llmModel',
    // 파이프라인 캔버스 상태 = 진입 시 getPipelineDetail 로 항상 재조회되는 휘발성 슬라이스.
    // persist 하면 옛 탭의 stale shape(신규 task 버킷 누락)가 rehydrate 되어 undefined.length 크래시.
    'pipelineList',
  ],
};

const enhancerReducer = persistReducer(persistConfig, modules);

const store = createStore(
  enhancerReducer,
  composeEnhancer(
    applyMiddleware(
      thunkMiddleware.withExtraArgument({ history: customHistory }),
    ),
  ),
);

const persistor = persistStore(store);
const stores = { store, persistor };
export default stores;
