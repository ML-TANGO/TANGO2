// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Textarea, Selectbox } from '@jonathan/ui-react';
import File from '@src/components/molecules/File';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// Templates
import ModalTemplate from '@src/components/templates/ModalTemplate';

// Organisms
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
import ModalFooter from '@src/components/organisms/modal/ModalFooter';

// CSS module
import classNames from 'classnames/bind';
import style from './UploadCheckpointModalContent.module.scss';
const cx = classNames.bind(style);

/**
 * 체크포인트 업로드 모달 컨텐츠 컴포넌트
 * @param {Object} props - 노드 모달 폼 데이터
 * @param {'ADD_NODE' | 'EDIT_NODE' | 'ADD_STORAGE_NODE' | 'EDIT_STORAGE_NODE'} props.type - 모달 타입
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
function UploadCheckpointModalContent({
  type,
  modalData,
  title,
  isValidate,
  onSubmit,
  fileList,
  desc,
  model,
  modelOptions,
  fileInputHandler,
  textInputHandler,
  selectInputHandler,
  removeFile,
}) {
  const { t } = useTranslation();
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
        <File
          name='files'
          onChange={fileInputHandler}
          value={fileList}
          error={null}
          btnText='file.label'
          onRemove={removeFile}
          index={0}
        />
        <InputBoxWithLabel labelText={t('model.label')} labelSize='large'>
          <Selectbox
            list={modelOptions}
            selectedItem={model}
            placeholder={t('builtInModelForUpload.placeholder')}
            onChange={selectInputHandler}
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={t('description.label')}
          labelSize='large'
          disableErrorMsg
        >
          <Textarea
            size='large'
            placeholder={t('description.label')}
            name='desc'
            value={desc}
            onChange={textInputHandler}
          />
        </InputBoxWithLabel>
      </div>
    </ModalTemplate>
  );
}

export default UploadCheckpointModalContent;
