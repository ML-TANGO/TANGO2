import { InputText, Textarea } from '@tango/ui-react';

import { useTranslation } from 'react-i18next';

import GpuSelectBox from '@src/components/molecules/GpuSelectBox';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiSelect from '@src/components/molecules/MultiSelect';
import ModalFooter from '@src/components/organisms/modal/ModalFooter';
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
import ModalTemplate from '@src/components/templates/ModalTemplate';

import classNames from 'classnames/bind';
import style from './UserWorkSpaceModal.module.scss';

const cx = classNames.bind(style);

const UserWorkSpaceModal = ({ data, type }) => {
  const { t } = useTranslation();

  const { submit, cancel } = data;

  return (
    <ModalTemplate
      headerRender={<ModalHeader title={'워크스페이스 생성'} />}
      footerRender={
        <ModalFooter
          type={type}
          submit={{ text: '생성', func: () => {} }}
          cancel={cancel}
          isValidate={true}
        />
      }
    >
      <div className={cx('modal-content')}>
        <InputBoxWithLabel
          labelText={t('workspaceName.label')}
          labelSize='large'
          // errorMsg={}
        >
          <InputText
            size='large'
            placeholder={t('workspaceName.placeholder')}
            onChange={() => {}}
            name='workspace'
            value={''}
            // value={workspace}
            // status={workspaceError ? 'error' : 'default'}
            // isReadOnly={type === 'EDIT_WORKSPACE'}
            isLowercase
            options={{ maxLength: 50 }}
            autoFocus={true}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={t('workspaceDescription.label')}
          optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='large'
          // errorMsg={t(descriptionError)}
        >
          <Textarea
            size='large'
            placeholder={t('workspaceDescription.placeholder')}
            // value={description}
            value={''}
            name='description'
            // onChange={inputHandler}
            onChange={() => {}}
            // error={descriptionError}
            // status={descriptionError ? 'error' : 'default'}
            isShowMaxLength
          />
        </InputBoxWithLabel>
        <div className={cx('input-group')}>
          <div className={cx('group-title')}>
            <span className={cx('text')}>
              {t('workspaceResourceSetting.label')}
            </span>
          </div>

          <div>
            {t('instanceAllocation.label')}
            <GpuSelectBox
            // models={instanceList}
            // checkboxHandler={checkboxHandler}
            // gpuSelectedOptions={gpuSelectedOptions}
            // onChangeGpuInputValue={onChangeGpuInputValue}
            // inputValue={gpuInputValues}
            // edit={type === 'EDIT_WORKSPACE'}
            // type={type}
            />
          </div>
        </div>
        <div className={cx('row')}>
          {/* <StorageSelect
          // list={storageList}
          // type={type}
          // prevStorageModel={prevStorageModel}
          // storageSelectHandler={storageSelectHandler}
          // storageSelectedModel={storageSelectedModel}
          // mainStorageSelectedModel={mainStorageSelectedModel}
          // dataStorageSelectedModel={dataStorageSelectedModel}
          // storageInputValueHandler={storageInputValueHandler}
          // storageInputValue={storageInputValue}
          // storageInputHandler={storageInputHandler}
          // storageError={storageError}
          // storageMessage={storageMessage}
          // barData={storageBarState}
          // storageBarData={storageBarData}
          // editStorageAvailableSize={editStorageAvailableSize}
          // createStorageAvailableSize={createStorageAvailableSize}
          // workspaceUsage={workspaceUsage}
          // mainStorageValue={mainStorageValue}
          // dataStorageValue={dataStorageValue}
          // t={t}
          /> */}
        </div>
        <div className={cx('row')}>
          <MultiSelect
            label='users.label'
            listLabel='availableUsers.label'
            selectedLabel='chosenUsers.label'
            list={[]}
            onChange={() => {
              return {
                list: [],
                selectedList: [],
              };
            }}
            selectedList={[]} // 초기 선택된 목록
            optional
          />
        </div>
      </div>
    </ModalTemplate>
  );
};

export default UserWorkSpaceModal;
