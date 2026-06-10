// i18n
import { useTranslation } from 'react-i18next';

// Templates
import ModalTemplate from '@src/components/templates/ModalTemplate';

// Organisms
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
import ModalFooter from '@src/components/organisms/modal/ModalFooter';

// Atoms
import Loading from '@src/components/atoms/loading/Loading';

// CSS Module
import classNames from 'classnames/bind';
import style from './GitHubFormModalContent.module.scss';
const cx = classNames.bind(style);

/**
 * 데이터셋 GitHub Clone 모달의 컨텐츠 컴포넌트
 * @returns
 */
function GitHubFormModalContent({
  type,
  modalData,
  renderUrlInputForm,
  renderAccessInputForm,
  isValidate,
  onSubmit,
  loading,
}) {
  const { t } = useTranslation();

  // 모달 제목
  const title = t('github.title.label');

  const { submit, cancel } = modalData;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };

  return (
    <ModalTemplate
      headerRender={<ModalHeader title={title} />}
      footerRender={
        <ModalFooter
          submit={newSubmit}
          cancel={cancel}
          type={type}
          isValidate={isValidate}
        />
      }
    >
      <div className={cx('modal-content')}>
        {/* URL 입력 창 */}
        {renderUrlInputForm()}
        {/* Access 설정 */}
        {renderAccessInputForm()}
        {/* 로딩 */}
        {loading && (
          <Loading
            customStyle={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
            }}
          />
        )}
      </div>
    </ModalTemplate>
  );
}

export default GitHubFormModalContent;
