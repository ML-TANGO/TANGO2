// i18n

// Components
import { InputText } from '@tango/ui-react';

import { useTranslation } from 'react-i18next';

import ModalFrame from '@src/components/Modal/ModalFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from './DeploymentApiCodeModalContent.module.scss';

const cx = classNames.bind(style);

/**
 * 배포 API 코드 생성 모달 컨텐츠 컴포넌트
 * @param {Object} props - 배포 API 코드 모달 폼 데이터
 * @param {'CREATE_DEPLOYMENT_API'} props.type - 모달 타입
 * @param {{
 *    cancel: {
 *      func: () => {} | undefined,
 *      text: string | undefined
 *    },
 *    submit: {
 *      func: () => {} | undefined,
 *      text: string | undefined,
 *    },
 * }} props.modalData - 모달 Footer의 cancel, submit 버튼 관련 값(버튼에 보여줄 텍스트, 클릭 이벤트) 및 node id 값
 * @param {string} props.title 모달 타이틀
 * @param {boolean} props.isValidate - 활성화된 커스텀 훅의 인풋 값이 유효하면 true 하나라도 유효하지 않으면 false
 * @param {Function} props.onSubmit - Submit 버튼 클릭 이벤트
 * @returns {JSX.Element}
 */
function DeploymentApiCodeModalContent({
  type,
  title,
  modalData,
  onSubmit,
  isValidate,
  apiFileNameState,
  apiFileNameHandler,
  deploymentInputValueRender,
  deploymentOutputTypeRender,
  deploymentParserRender,
  deployFooterMessage,
}) {
  const { t } = useTranslation();
  const { submit, cancel, ...rest } = modalData;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };

  return (
    <ModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={type}
      validate={isValidate}
      isResize={true}
      isMinimize={true}
      title={title}
      headerTitle={title}
      footerMessage={deployFooterMessage}
      customStyle={{ width: '664px' }}
    >
      <div className={cx('form')}>
        <div className={cx('modal-content')}>
          <div className={cx('row', 'margin-bottom-32')}>
            <label className={cx('input-label')}>
              {t('apiFileName.label')}
            </label>
            <InputText
              size='medium'
              value={apiFileNameState.value}
              onChange={apiFileNameHandler}
              placeholder={t('apiFileName.placeholder')}
              autoFocus
              disableLeftIcon
              disableClearBtn
              customStyle={{
                border: '1px solid #dbdbdb',
                padding: '11px 12px',
                fontWeight: 500,
              }}
            />
          </div>
          <div className={cx('row', 'margin-bottom-34')}>
            <label className={cx('input-label')}>
              {t('serviceTestInputForm.label')}
            </label>
            {deploymentInputValueRender()}
          </div>
          {deploymentOutputTypeRender()}
        </div>
      </div>
    </ModalFrame>
    // <ModalTemplate
    //   headerRender={<ModalHeader title={title} />}
    //   footerRender={
    //     <ModalFooter
    //       submit={newSubmit}
    //       cancel={cancel}
    //       type={type}
    //       isValidate={isValidate}
    //       deployFooterMessage={deployFooterMessage}
    //     />
    //   }
    // >
    //   <div className={cx('modal-content')}>
    //     <div className={cx('row', 'margin-bottom-48')}>
    //       <label className={cx('input-label')}>{t('apiFileName.label')}</label>
    //       <InputText
    //         size='medium'
    //         value={apiFileNameState.value}
    //         onChange={apiFileNameHandler}
    //         placeholder={t('apiFileName.placeholder')}
    //         autoFocus
    //         disableLeftIcon
    //         disableClearBtn
    //       />
    //     </div>
    //     <div className={cx('row', 'margin-bottom-48')}>
    //       <label className={cx('input-label')}>
    //         {t('serviceTestInputForm.label')}
    //       </label>
    //       {deploymentInputValueRender()}
    //     </div>
    //     {deploymentOutputTypeRender()}
    //     {/* {deploymentParserRender()} */}
    //   </div>
    // </ModalTemplate>
  );
}

export default DeploymentApiCodeModalContent;
