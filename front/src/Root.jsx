import { Provider } from 'react-redux';
import { PersistGate } from 'redux-persist/integration/react';
import configureStore from '@src/store';
import { BrowserRouter } from 'react-router-dom';

// Components
import App from './App';

// i18n
import './i18n';

const { store, persistor } = configureStore;

function Root() {
  return (
    <Provider store={store}>
      <PersistGate loading={null} persistor={persistor}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </PersistGate>
    </Provider>
  );
}

export default Root;
