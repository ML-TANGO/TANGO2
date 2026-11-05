// Templates
import ModalTemplate from '@src/components/templates/ModalTemplate';

// Organisms
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
import ModalFooter from '@src/components/organisms/modal/ModalFooter';

// CSS Module
import classNames from 'classnames/bind';
import style from './ServingDeleteModalContent.module.scss';
const cx = classNames.bind(style);

function ServingDeleteModalContent({ type, modalData, onDelete }) {
  const { submit, cancel, modalTitle, modalContents } = modalData;

  const newSubmit = {
    text: submit.text,
    func: async () => {
      submit.func();
    },
  };
  return (
    <div>
      <ModalTemplate
        headerRender={<ModalHeader title={modalTitle} />}
        footerRender={
          <ModalFooter
            submit={newSubmit}
            cancel={cancel}
            type={type}
            modalData={modalData}
            isValidate={true}
            leftButtonType={'red'}
          />
        }
        customStyle={{
          component: {
            width: '600px',
          },
          position: {
            top: '300px',
          },
        }}
      >
        <p className={cx('description')}>{modalContents}</p>
      </ModalTemplate>
    </div>
  );
}
export default ServingDeleteModalContent;
