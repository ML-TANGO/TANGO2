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
