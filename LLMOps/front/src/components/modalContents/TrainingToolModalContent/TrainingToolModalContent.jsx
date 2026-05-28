// i18n
import { useTranslation } from 'react-i18next';

// Templates
import ModalTemplate from '@src/components/templates/ModalTemplate';

// Organisms
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
import ModalFooter from '@src/components/organisms/modal/ModalFooter';

// Components
import { Selectbox, Checkbox } from '@jonathan/ui-react';

// Type
import { TRAINING_TOOL_TYPE } from '@src/types';

// CSS Module
import classNames from 'classnames/bind';
import style from './TrainingToolModalContent.module.scss';
const cx = classNames.bind(style);

/**
 * 학습 도구 모달 컨텐츠 컴포넌트
 * @param {Object} props - 학습 도구 모달 폼 데이터
 * @param {'EDIT_TRAINING_TOOL'} props.type - 모달 타입
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
function TrainingToolModalContent({
  type,
  title,
  modalData,
  onSubmit,
  isValidate,
  dockerState,
  dockerHandler,
  gpuSettingBoxRender,
  portForwardingInputRender,
  checkOption,
  checkOptionHandler,
  visualStatus,
}) {
  const { t } = useTranslation();
  const { submit, cancel, toolType, toolReplicaNum, toolName } = modalData;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };

  return (
    <ModalTemplate
      headerRender={
        <ModalHeader
          title={
            <div className={cx('modal-title')}>
              <span>{title}</span>
              {title && (
                <>
                  <span className={cx('divide')}>-</span>
                  <img
                    className={cx('tool-icon')}
                    src={`/images/icon/ic-${TRAINING_TOOL_TYPE[toolType]?.type}.svg`}
                    alt={`${TRAINING_TOOL_TYPE[toolType]?.type} icon`}
                  />
                  <span className={cx('tool-label')}>
                    {toolName ? toolName : TRAINING_TOOL_TYPE[toolType]?.label}
                  </span>
                  {toolReplicaNum !== undefined && toolReplicaNum > 0 && (
                    <span className={cx('replica-number')}>
                      {toolReplicaNum < 10
                        ? `0${toolReplicaNum}`
                        : toolReplicaNum}
                    </span>
                  )}
                </>
              )}
            </div>
          }
        />
      }
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
        {visualStatus?.dockerImg?.visible && (
          <div className={cx('row', 'margin-bottom-48')}>
            <label className={cx('input-label')}>
              {t('dockerImage.label')}
            </label>
            <Selectbox
              size='large'
              list={dockerState.options}
              selectedItem={dockerState.value}
              placeholder={t('dockerImage.placeholder')}
              isReadOnly={visualStatus?.dockerImg?.disable}
              onChange={dockerHandler}
              t={t}
            />
          </div>
        )}
        {/* {trainingVisible?.resourceInfoVisible && gpuSettingBoxRender()} */}
        {gpuSettingBoxRender()}
        {type === 'CREATE_TRAINING_TOOL' && (
          <div className={cx('default-box')}>
            <Checkbox
              label={t('toolsCheckOption.label')}
              checked={checkOption}
              onChange={checkOptionHandler}
            />
          </div>
        )}
        {visualStatus?.portInfo?.visible && (
          <div className={cx('row')}>
            <label className={cx('input-label')}>
              {t('portForwardingSettings.title.label')}
              <span className={cx('optional')}>- {t('optional.label')}</span>
            </label>
            {portForwardingInputRender()}
          </div>
        )}
      </div>
    </ModalTemplate>
  );
}

export default TrainingToolModalContent;
