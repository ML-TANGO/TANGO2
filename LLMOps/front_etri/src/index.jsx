// Polyfill
import 'react-app-polyfill/ie11';
import 'react-app-polyfill/stable';

import elementClosest from 'element-closest';
// React modules
import React from 'react';
import { createRoot } from 'react-dom/client';
import smoothscroll from 'smoothscroll-polyfill';

// Global style
import './styles/style.scss';

import { Buffer } from 'buffer';

import Root from './Root';
import * as serviceWorker from './serviceWorker';

import '@tango/ui-react/index.css';

window.Buffer = Buffer;

// Apply Polyfill modules
smoothscroll.polyfill();
elementClosest(window);

// React render
// ReactDOM.render(<Root />, document.getElementById('root'));
const root = createRoot(document.getElementById('root'));
root.render(<Root />);

// If you want your app to work offline and load faster, you can change
// unregister() to register() below. Note this comes with some pitfalls.
// Learn more about service workers: https://bit.ly/CRA-PWA
serviceWorker.unregister();
