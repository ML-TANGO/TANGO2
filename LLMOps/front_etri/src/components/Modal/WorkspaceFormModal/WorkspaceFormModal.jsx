// Components
import { useCallback, useEffect, useRef, useState } from 'react';
// i18n
import { withTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import {
  DateRangePicker,
  InputText,
  Selectbox,
  Textarea,
} from '@tango/ui-react';

import dayjs from 'dayjs';

import DateCell from '@src/components/atoms/DateCell';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiSelect from '@src/components/molecules/MultiSelect';
import ResourceSetting from '@src/components/molecules/ResourceSetting';

import { openConfirm } from '@src/store/modules/confirm';
import { closeModal } from '@src/store/modules/modal';

import NewStyleModalFrame from '../NewStyleModalFrame';

// Utils
import { convertSizeTo } from '@src/utils';

// CSS module
import classNames from 'classnames/bind';
import style from './WorkspaceFormModal.module.scss';

const cx = classNames.bind(style);

const WorkspaceFormModal = ({
  isAdmin,
  inputHandler,
  calenderDetector,
  calenderMountDetector,
  calendarHandler,
  selectManager,
  multiSelectHandler,
  onSubmit,
  data,
  type,
  workspace,
  workspaceError,
  description,
  descriptionError,
  startdatetime,
  enddatetime,
  minDate,
  instanceList,
  periodError,
  gpuSelectedOptions,
  gpuInputValues,
  storageInputValueHandler,
  mainStorageValue,
  dataStorageValue,
  checkboxHandler,
  onChangeGpuInputValue,
  manager,
  managerList,
  managerError,
  validate,
  userGroupOptions,
  selectedList,
  gpuTotal,
  gpuFreeMap,
  storageList,
  storageInputValue,
  storageBarData,
  storageError,
  storageMessage,
  storageSelectedModel,
  mainStorageSelectedModel,
  dataStorageSelectedModel,
  storageSelectHandler,
  storageInputHandler,
  prevStorageModel,
  editStorageAvailableSize,
  workspaceUsage,
  createStorageAvailableSize,
  t,
  footerMessage,
  prevWorkspaceInfo,
  totalStorageInputValue,
  prevMainStorageVolume,
  prevDataStorageVolume,
}) => {
  const dispatch = useDispatch();
  const { submit, cancel } = data;
  const scrollRef = useRef();

  const {
    main_storage_size,
    main_storage_id,
    data_storage_size,
    data_storage_id,
  } = prevWorkspaceInfo;

  const [storageBarState, setStorageBarState] = useState([]);
  const newSubmit = {
    text: submit.text,
    func:
      !isAdmin && type === 'EDIT_WORKSPACE'
        ? async () => {
            await dispatch(
              openConfirm({
                content: 'workspace.edit.popup.message',
                submit: {
                  text: 'continue.label',
                  func: () => {
                    onSubmit(submit.func);
                    dispatch(closeModal(type));
                  },
                },
                cancel: {
                  text: 'cancel.label',
                },
                notice: t('deleteDeploymentPopup.content.message'),
                contentCustomStyle: {
                  color: '#121619',
                  padding: '0px',
                  fontWeight: 700,
                },
                submitBtnStyle: {
                  backgroundColor: '#2D76F8',
                },
              }),
            );
            return false;
          }
        : async () => {
            const res = await onSubmit(submit.func);
            return res;
          },
  };
  const scrollHandler = () => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const changeStorageBarData = useCallback(() => {
    if (storageSelectedModel?.share === 0 || prevStorageModel[0]?.share === 0) {
      let barData;
      let currUsage = 0;
      let editcurrUsage = 0;

      if (storageBarData.otherUsage) {
        currUsage = Math.ceil(
          Number(
            convertSizeTo(storageBarData.currUsage?.usage, 'GiB').split(
              ' GiB',
            )[0],
          ),
        );
        editcurrUsage = Math.ceil(
          Number(
            convertSizeTo(storageBarData.currUsage?.usage, 'GiB').split(
              ' GiB',
            )[0],
          ),
        );

        if (currUsage > storageInputValue) {
          currUsage = 0;
        } else {
          currUsage = storageInputValue - currUsage;
        }
      }

      if (storageBarData.otherUsage && type === 'EDIT_WORKSPACE') {
        let otherUsage = Number(
          convertSizeTo(storageBarData.otherUsage.usage, 'GiB')?.split(
            ' GiB',
          )[0],
        );

        let currUsageGib = Number(
          convertSizeTo(storageBarData.currUsage.usage, 'GiB')?.split(
            ' GiB',
          )[0],
        );

        let availableUsage = Number(
          convertSizeTo(prevStorageModel[0]?.size, 'GiB')?.split(' GiB')[0],
        );

        let availableUsageValue =
          availableUsage - (otherUsage + currUsageGib + storageInputValue);

        if (availableUsageValue < 0) {
          availableUsageValue = 0;
        }

        if (storageInputValue > currUsageGib) {
          editcurrUsage = storageInputValue - currUsageGib;
        } else {
          editcurrUsage = 0;
        }
        editcurrUsage = storageInputValue;
        let allocationUsageWidth =
          (storageInputValue /
            Number(
              convertSizeTo(prevStorageModel[0]?.size, 'GiB')?.split(' GiB')[0],
            )) *
          100;

        if (allocationUsageWidth !== 0) {
          if (allocationUsageWidth <= storageBarData.currUsage.pcent) {
            allocationUsageWidth = 0;
          } else if (allocationUsageWidth > storageBarData.currUsage.pcent) {
            allocationUsageWidth =
              allocationUsageWidth - storageBarData.currUsage.pcent;
          }
        }

        barData = [
          {
            title: 'storageOtherWorkspaceUsage.label',
            color: '#C1C1C1',
            width: storageBarData.otherUsage.pcent,
            usage: convertSizeTo(storageBarData.otherUsage.usage, 'GiB'),
          },
          {
            title: 'storageCurrUsage.label',
            color: '#2d76f8',
            width: storageBarData.currUsage.pcent,
            usage: convertSizeTo(storageBarData.currUsage.usage, 'GiB'),
          },
          {
            title: 'additionalAllocationCapacity.label',
            color: '#93BAFF',
            width: allocationUsageWidth,
            usage: editcurrUsage === '' ? 0 + ' GiB' : editcurrUsage + ' GiB',
          },
          {
            title: 'storageAvailableCapacity.label',
            color: '#FFFFFF',
            width: '',
            usage: availableUsageValue + ' GiB',
          },
        ];
      } else if (
        storageBarData.otherUsage &&
        type === 'CREATE_WORKSPACE' &&
        storageSelectedModel.share === 0
      ) {
        let availableUsage = Number(
          convertSizeTo(storageSelectedModel?.usage.size, 'GiB')?.split(
            ' GiB',
          )[0],
        );
        let otherUsage = Number(
          convertSizeTo(storageBarData.otherUsage.usage, 'GiB')?.split(
            ' GiB',
          )[0],
        );

        if (currUsage + otherUsage >= availableUsage) {
          if (currUsage > otherUsage) {
            currUsage = availableUsage - otherUsage;
          } else if (currUsage < otherUsage) {
            currUsage = otherUsage - currUsage;
          }
          availableUsage = 0;
        } else {
          availableUsage = availableUsage - (otherUsage + currUsage);
        }

        let allocationUsageWidth =
          (storageInputValue /
            Number(
              convertSizeTo(storageSelectedModel?.size, 'GiB')?.split(
                ' GiB',
              )[0],
            )) *
          100;

        barData = [
          {
            title: 'storageOtherWorkspaceUsage.label',
            color: '#C1C1C1',
            width: storageBarData.otherUsage.pcent,
            usage: storageBarData.otherUsage.usage,
          },
          {
            title: 'allocationCapacity.label',
            color: '#93BAFF',
            width: allocationUsageWidth,
            usage: currUsage + ' GiB',
          },
          {
            title: 'storageAvailableCapacity.label',
            color: '#FFFFFF',
            width: '',
            usage: availableUsage + 'GiB',
          },
        ];
      }

      setStorageBarState(barData);
    }
  }, [
    prevStorageModel,
    storageBarData,
    storageInputValue,
    storageSelectedModel,
    type,
  ]);

  useEffect(() => {
    changeStorageBarData();
  }, [storageBarData, prevStorageModel, changeStorageBarData]);

  const titleValue = (type, isAdmin) => {
    if (type === 'CREATE_WORKSPACE') {
      return t('createWorkspaceForm.title.label');
    }

    if (isAdmin) return t('editWorkspaceForm.title.label');
    return t('editWorkspaceForm.request.title.label');
  };

  const calFooterMessage = (
    footerMessage,
    workspaceError,
    descriptionError,
    t,
  ) => {
    if (workspaceError) return t(workspaceError);
    if (descriptionError) return t(descriptionError);
    return footerMessage;
  };

  return (
    <NewStyleModalFrame
      type={type}
      submit={newSubmit}
      cancel={cancel}
      validate={validate}
      isResize={true}
      isMinimize={true}
      title={titleValue(type, isAdmin)}
      footerMessage={calFooterMessage(
        footerMessage,
        workspaceError,
        descriptionError,
        t,
      )}
      customStyle={{
        width: '664px',
      }}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('workspaceName.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            placeholder={t('workspaceName.placeholder')}
            onChange={inputHandler}
            name='workspace'
            value={workspace}
            status={workspaceError ? 'error' : 'default'}
            isReadOnly={type === 'EDIT_WORKSPACE'}
            options={{ maxLength: 50 }}
            autoFocus={true}
            customStyle={{ fontSize: '14px' }}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('workspaceDescription.label')}
          optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <Textarea
            size='large'
            placeholder={t('workspaceDescription.placeholder')}
            value={description}
            name='description'
            onChange={inputHandler}
            error={descriptionError}
            status={descriptionError ? 'error' : 'default'}
            customStyle={{ fontSize: '14px' }}
            isShowMaxLength
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')} style={{ maxHeight: 'none' }}>
        <InputBoxWithLabel
          labelText={t('workspaceResourceSetting.label')}
          labelSize='large'
          disableErrorMsg
        >
          <ResourceSetting
            // ** 인스턴스 설정 [가져다 붙임] **
            isInstance
            models={instanceList}
            checkboxHandler={checkboxHandler}
            gpuSelectedOptions={gpuSelectedOptions}
            onChangeGpuInputValue={onChangeGpuInputValue}
            inputValue={gpuInputValues}
            edit={type === 'EDIT_WORKSPACE'}
            type={type}
            // ** Storage **
            isStorage
            list={storageList}
            prevStorageModel={prevStorageModel}
            storageSelectHandler={storageSelectHandler}
            storageSelectedModel={storageSelectedModel}
            mainStorageSelectedModel={mainStorageSelectedModel}
            dataStorageSelectedModel={dataStorageSelectedModel}
            storageInputValueHandler={storageInputValueHandler}
            storageInputValue={storageInputValue}
            storageInputHandler={storageInputHandler}
            storageError={storageError}
            storageMessage={storageMessage}
            barData={storageBarState}
            storageBarData={storageBarData}
            editStorageAvailableSize={editStorageAvailableSize}
            createStorageAvailableSize={createStorageAvailableSize}
            workspaceUsage={workspaceUsage}
            mainStorageValue={mainStorageValue}
            dataStorageValue={dataStorageValue}
            prevMainStorage={main_storage_size}
            prevDataStorage={data_storage_size}
            prev_main_storage_id={main_storage_id}
            prev_data_storage_id={data_storage_id}
            totalStorageInputValue={totalStorageInputValue}
            prevMainStorageVolume={prevMainStorageVolume}
            prevDataStorageVolume={prevDataStorageVolume}
          />
        </InputBoxWithLabel>
      </div>

      {/** 유효기간  달력 */}
      <div className={cx('row')} ref={scrollRef}>
        <div className={cx('flex-cont')}>
          <div className={cx('calendar')}>
            <label>{t('expiration.label')}</label>
            <DateRangePicker
              status={periodError === null ? '' : periodError !== '' && 'error'}
              t={t}
              size='medium'
              inputSize='medium'
              from={startdatetime.format('YYYY-MM-DD')}
              to={enddatetime.format('YYYY-MM-DD')}
              // minDate={minDate.format('YYYY-MM-DD')}
              onSubmit={calendarHandler}
              onCellRender={(d, propItem) => {
                return (
                  <DateCell
                    gpuFreeMap={gpuFreeMap}
                    d={dayjs(d)}
                    propItem={propItem}
                    gpuTotal={gpuTotal}
                  />
                );
              }}
              cancelLabel='cancel.label'
              submitLabel='confirm.label'
              onCalendarMount={calenderMountDetector}
              onCalendarChangeDetector={calenderDetector}
              scrollHandler={scrollHandler}
              customStyle={{
                primaryType: {
                  inputForm: {
                    display: 'flex',
                    justifyContent: 'space-evenly',
                    width: '100%',
                    color: '#121619',
                    borderRadius: '8px',
                  },
                  inputFont: {
                    fontSize: '14px',
                    fontWeight: 500,
                  },
                },
              }}
            />
          </div>
          <div className={cx('manager')}>
            <InputBoxWithLabel
              labelText={t('workspaceManager.label')}
              labelSize='large'
              disableErrorMsg
              // errorMsg={t(managerError)}
            >
              <Selectbox
                type='search'
                size='medium'
                list={managerList.map(({ id, name }) => ({
                  label: name,
                  value: id,
                }))}
                placeholder={t('workspaceManager.placeholder')}
                name='manager'
                selectedItem={manager}
                onChange={selectManager}
                status={managerError ? 'error' : 'default'}
                customStyle={{
                  fontStyle: {
                    selectbox: {
                      color: '#121619',
                      textShadow: 'None',
                      fontSize: '14px',
                    },
                    list: {
                      fontSize: '14px',
                    },
                  },
                }}
              />
            </InputBoxWithLabel>
          </div>
        </div>
      </div>
      <div className={cx('row')}>
        <MultiSelect
          label='users.label'
          listLabel='availableUsers.label'
          selectedLabel='chosenUsers.label'
          list={userGroupOptions} // 초기 목록
          selectedList={selectedList} // 초기 선택된 목록
          onChange={multiSelectHandler} // 변경 이벤트
          exceptItem={manager && manager.value} // 목록에서 빠질 아이템
          optional
        />
      </div>
    </NewStyleModalFrame>
  );
};

export default withTranslation()(WorkspaceFormModal);
