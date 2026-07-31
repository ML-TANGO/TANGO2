import { PureComponent } from 'react';

import { connect } from 'react-redux';

// Action
import { closeModal } from '@src/store/modules/modal';
// Components
import JsonViewModal from '@src/components/Modal/JsonViewModal';

class JsonViewModalContainer extends PureComponent {
  // submit 버튼 클릭 이벤트
  onSubmit = () => {
    const { type } = this.props;
    this.props.closeModal(type);
  };

  render() {
    const { props, onSubmit } = this;
    return <JsonViewModal {...props} onSubmit={onSubmit} />;
  }
}

export default connect(null, { closeModal })(JsonViewModalContainer);
