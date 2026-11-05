import { Component } from 'react';
let listener;
const EnterSubmitHOC = (param) => (WrappedComponent) => {
  return class extends Component {
    componentDidMount() {
      listener = (e) => {
        if (
          (e.key === 'Enter' || e.key === 'NumpadEnter') &&
          param.onSubmitEvent
        ) {
          param.onSubmitEvent();
        }
      };
      document.addEventListener('keydown', listener);
    }

    componentWillUnmount() {
      document.removeEventListener('keydown', listener);
    }

    render() {
      return <WrappedComponent {...this.props} />;
    }
  };
};

export default EnterSubmitHOC;
