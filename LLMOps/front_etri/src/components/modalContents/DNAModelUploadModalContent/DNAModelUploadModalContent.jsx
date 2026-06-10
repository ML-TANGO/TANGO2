// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Textarea, Selectbox } from '@jonathan/ui-react';
import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import ModalTemplate from '@src/components/templates/ModalTemplate';
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
import ModalFooter from '@src/components/organisms/modal/ModalFooter';

// CSS Module
import classNames from 'classnames/bind';
import style from './DNAModelUploadModalContent.module.scss';
const cx = classNames.bind(style);

/**
 * DNA 추론 모델 업로드 모달
 */
function DNAModelUploadModalContent({
  type,
  modalData,
  isValidate,
  bmOptions,
  bm,
  desc,
  checkpoint,
  checkpointOptions,
  radioBtnHandler,
  selectInputHandler,
  textInputHandler,
  onSubmit,
}) {
  // 다국어
  const { t } = useTranslation();

  // 모달 제목
  const title = t('uploadDNAModel.label');

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
        <InputBoxWithLabel labelText='BM' labelSize='large'>
          <Radio options={bmOptions} value={bm} onChange={radioBtnHandler} />
        </InputBoxWithLabel>
        <InputBoxWithLabel labelText={t('checkpoint.label')} labelSize='large'>
          <Selectbox
            size='large'
            list={checkpointOptions}
            selectedItem={checkpoint}
            placeholder={t('checkpoint.placeholder')}
            onChange={(e) => {
              selectInputHandler(e);
            }}
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel labelText={t('description.label')} labelSize='large'>
          <Textarea
            size='large'
            placeholder={t('description.label')}
            value={desc}
            onChange={textInputHandler}
          />
        </InputBoxWithLabel>
      </div>
    </ModalTemplate>
  );
}

export default DNAModelUploadModalContent;
