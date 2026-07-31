import { Component } from 'react';

// Components
import Loading from '@src/components/atoms/loading/Loading';

const withSplitting = (getComponent) => {
  return (isPage) => {
    class WithSplitting extends Component {
      _isMounted = false;

      componentDidMount() {
        this._isMounted = true;
        this.importComponent();
      }

      componentWillUnmount() {
        this._isMounted = false;
      }

      constructor(props) {
        super(props);
        this.state = {
          Splitted: null,
        };
      }

      importComponent = () => {
        if (!this._isMounted) return;
        getComponent().then(({ default: Splitted }) => {
          this.setState({
            Splitted,
          });
        });
      };

      render() {
        const { Splitted } = this.state;
        if (!Splitted) {
          return isPage ? (
            <div
              style={{
                width: '100%',
                display: 'flex',
                justifyContent: 'center',
              }}
            >
              <Loading />
            </div>
          ) : null;
        }
        return <Splitted {...this.props} />;
      }
    }
    return WithSplitting;
  };
};

export default withSplitting;
