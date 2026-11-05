import { Component } from 'react';
import ReactGA from 'react-ga';

const TrackingHOC = (WrappedComponent) => {
  const token = import.meta.env.VITE_REACT_APP_ANALYTICS_TOKEN;
  const isToken = token !== 'false';
  class InnerComponent extends Component {
    componentDidMount() {
      if (!isToken) return;
      ReactGA.initialize(token, {
        debug: false,
      });
      this.trackingPage();
    }

    componentDidUpdate() {
      if (isToken) this.trackingPage();
    }

    trackingPage = () => {
      if (isToken)
        ReactGA.pageview(window.location.pathname + window.location.search);
    };

    trackingEvent = (param) => {
      if (!param || !isToken) return;
      ReactGA.event(param);
    };

    render() {
      const { trackingEvent } = this;
      return <WrappedComponent {...this.props} trackingEvent={trackingEvent} />;
    }
  }
  return InnerComponent;
};

export default TrackingHOC;
