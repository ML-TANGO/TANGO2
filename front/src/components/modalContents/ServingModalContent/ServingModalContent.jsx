import { useTranslation } from 'react-i18next';

// Templates
import ModalTemplate from '@src/components/templates/ModalTemplate';

// Organisms
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
import ModalFooter from '@src/components/organisms/modal/ModalFooter';
import { InputText, Textarea } from '@jonathan/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './ServingModalContent.module.scss';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
const cx = classNames.bind(style);

function ServingModalContent({
  groupNameStatus,
  groupName,
  description,
  type,
  nameInputHandler,
  descriptionInputHandler,
  modalData,
  createStatus,
  status,
}) {
  const { t } = useTranslation();

  const { submit, cancel } = modalData;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      submit.func(groupName, description);
    },
  };

  return (
    <ModalTemplate
      headerRender={
        <ModalHeader
          title={
            status === 'create'
              ? t('template.groupCreate.label')
              : t('template.groupEdit.label')
          }
        />
      }
      footerRender={
        <ModalFooter
          submit={newSubmit}
          cancel={cancel}
          type={type}
          modalData={modalData}
          isValidate={groupName !== '' && !createStatus}
        />
      }
      customStyle={{
        component: {
          width: '670px',
        },
        position: {
          top: '180px',
        },
      }}
    >
      <div className={cx('container')}>
        <label className={cx('title-container')}>
          <p className={cx('name')}>{t('template.groupCreateName.label')}</p>
          <div className={cx('count')}>
            <p>{groupName.length}</p>/50
          </div>
        </label>
        <InputText
          size='large'
          name='imageName'
          status={groupNameStatus ? 'error' : 'default'}
          value={groupName}
          options={{ maxLength: 50 }}
          placeholder={t('template.groupCreateInput.label')}
          onChange={nameInputHandler}
          onClear={() => {
            nameInputHandler({ target: { value: '', name: 'imageName' } });
          }}
          disableLeftIcon={true}
          disableClearBtn={false}
          autoFocus
        />
        <div className={cx('error-message')}>{groupNameStatus}</div>
        <InputBoxWithLabel
          labelText={t('template.searchPlaceholderDescription.label')}
          optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='large'
          disableErrorMsg
        >
          <Textarea
            size='large'
            placeholder={t('template.groupCreateInputDescription.label')}
            value={description}
            name='deploymentDesc'
            onChange={descriptionInputHandler}
            maxLength={1000}
            isShowMaxLength
          />
        </InputBoxWithLabel>
      </div>
    </ModalTemplate>
  );
}
export default ServingModalContent;
