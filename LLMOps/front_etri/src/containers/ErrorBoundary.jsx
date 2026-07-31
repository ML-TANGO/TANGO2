import React from 'react';

import ErrorPage from '@src/pages/ErrorPage';

class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null, errorInfo: null };

  componentDidCatch(error, info) {
    console.error('[ERROR MESSAGE] ', error);
    console.error('[ERROR STACK] ', info);
    // Display fallback UI
    this.setState({ hasError: true, error: error, errorInfo: info });
    // You can also log the error to an error reporting service
  }

  render() {
    if (this.state.hasError) {
      // You can render any custom fallback UI
      return <ErrorPage />;
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
