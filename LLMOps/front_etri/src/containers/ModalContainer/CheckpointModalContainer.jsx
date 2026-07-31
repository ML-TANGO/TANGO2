import { PureComponent } from 'react';

import { connect } from 'react-redux';

// Action
import { closeModal } from '@src/store/modules/modal';
// Components
import CheckpointModal from '@src/components/Modal/CheckpointModal';

class CheckpointModalContainer extends PureComponent {
  // submit 버튼 클릭 이벤트
  onSubmit = () => {
    const { type } = this.props;
    this.props.closeModal(type);
  };

  render() {
    const { props, onSubmit } = this;
    return <CheckpointModal {...props} onSubmit={onSubmit} />;
  }
}

export default connect(null, { closeModal })(CheckpointModalContainer);
