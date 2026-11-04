import { StatusCard } from '@jonathan/ui-react';

import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { callApi, STATUS_SUCCESS } from '@src/network';

import ProcessInstance from '../AddDatasetPreprocess/ProcessInstance';
import RangeBar from '../EditWorkspaceResource/RangeBar';
import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './DataResourceSettingModal.module.scss';

const cx = classNames.bind(style);

const rangeInitial = {
  cpu: 0,
  ram: 0,
};

// ** Range 핸들러 **
const handleRangeBar = (setting, value, maxValue, setRange) => {
  setRange((prev) => ({
    ...prev,
    [setting]: Number(value) >= maxValue ? maxValue : Number(value),
  }));
};

// ** [계산] validate
const calIsFooterMessage = (instanceOption) => {
  const isValidInstance = instanceOption.filter((v) => v.checked)[0];
  if (!isValidInstance) {
    return 'trainingInstance.error.message';
  }
  if (!isValidInstance.used) {
    return 'instance.allocate.message';
  }

  return null;
};

// ** 인스턴스 체크 핸들러
const handleInstanceCheck = ({ id, setInstanceOption }) => {
  setInstanceOption((prevOptions) =>
    prevOptions.map((option) =>
      option.id === id
        ? { ...option, checked: true }
        : { ...option, checked: false, used: '' },
    ),
  );
};

// ** 인스턴스 value 핸들러
const handleInstanceUsed = ({ id, value, setInstanceOption }) => {
  setInstanceOption((prevOptions) =>
    prevOptions.map((option) =>
      option.id === id
        ? {
            ...option,
            used: value,
            checked: value > 0,
          }
        : { ...option, checked: false, used: '' },
    ),
  );
};

const DataResourceSettingModal = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { auth } = useSelector((state) => ({
    auth: state.auth,
  }));

  const { userName } = auth;

  const [instanceOption, setInstanceOption] = useState([]);

  const [owner, setOwner] = useState({ label: '', value: '' });
  const [ownerList, setOwnerList] = useState([]);

  // ** 데이터 관리 range
  const [defaultRange, setDefaultRange] = useState(rangeInitial);
  const [defaultMaxRange, setDefaultMaxRange] = useState({
    cpu: 2,
    ram: 2,
  });

  const { submit, cancel, jobId, workspace_id } = data;

  const newSubmit = {
    text: submit.text,
    func: async () => {
      const instance = instanceOption.find((v) => v.checked);

      const body = {
        instance_id: instance.id,
        instance_allocate: instance.used,
        rangeCpu: defaultRange.cpu,
        rangeRam: defaultRange.ram,
      };
    },
  };

  const fetchOptionList = useCallback(async () => {
    const response = await callApi({
      url: `preprocessing/option?workspace_id=${workspace_id}`,
      method: 'get',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      const { instances, user_list, built_in_list, access } = result;

      const instanceList = instances.map(
        ({
          cpu_allocate,
          gpu_allocate,
          ram_allocate,
          instance_allocate,
          instance_id,
          instance_name,
          resource_name,
        }) => ({
          id: instance_id,
          resourceName: resource_name,
          instanceName: instance_name,
          max: instance_allocate,
          cpu: cpu_allocate,
          gpu: gpu_allocate,
          ram: ram_allocate,
          checked: false,
          used: '',
        }),
      );
      const userList = user_list.map(({ id, name }) => ({
        label: name,
        value: id,
      }));

      const curOwner = userList.filter((v) => userName === v.label)[0];
      setOwnerList(userList);
      setInstanceOption(instanceList);
      setOwner(curOwner);
    }
  }, [userName, workspace_id]);

  useEffect(() => {
    fetchOptionList();
  }, [fetchOptionList]);

  const isFooterMessage = calIsFooterMessage(instanceOption);

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      isResize={true}
      isMinimize={true}
      type={type}
      title={t('dataResourceManagementSettings.label')}
      customStyle={{ maxHeight: '750px' }}
      validate={!isFooterMessage}
      footerMessage={t(isFooterMessage ?? '')}
    >
      <div className={cx('notice')}>
        {t('dataManagementSettingNotice.message')}
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('instanceSetting.label')}
          labelSize='large'
          labelStyle={{
            marginBottom: '16px',
          }}
          disableErrorMsg
        >
          <div className={cx('resource-box')}>
            <div className={cx('header')}>
              <span className={cx('first')}>{t('instanceName.label')}</span>
              <span className={cx('second')}>{t('totalAmount.label')}</span>
              <span className={cx('third')}>{t('allocation.label')}</span>
            </div>
            <div className={cx('gray-line')}></div>
            <div className={cx('instance-box')}>
              {instanceOption.map(
                ({
                  id,
                  max,
                  checked,
                  used,
                  resourceName,
                  instanceName,
                  cpu,
                  gpu,
                  ram,
                }) => (
                  <ProcessInstance
                    key={id}
                    instanceName={instanceName}
                    resourceName={resourceName}
                    id={id}
                    max={max}
                    checked={checked}
                    used={used}
                    cpu={cpu}
                    ram={ram}
                    gpu={gpu}
                    handleInstanceCheck={({ id }) => {
                      handleInstanceCheck({ id, setInstanceOption });
                    }}
                    handleInstanceUsed={({ id, value }) => {
                      handleInstanceUsed({ id, value, setInstanceOption });
                    }}
                  />
                ),
              )}
            </div>
          </div>
        </InputBoxWithLabel>

        <InputBoxWithLabel
          labelText={t('dataManagementCpuRamLimit.label')}
          labelSize='large'
          labelStyle={{
            marginBottom: '16px',
          }}
          disableErrorMsg
        >
          {/* <GrayDropDown
                list={ownerList}
                value={owner}
                handleSelectOption={handleOwner}
                placeholder={t('owner.placeholder')}
                isCloseBorder={false}
                listCustomStyle={{ maxHeight: '110px', overflow: 'auto' }}
              /> */}
          <div className={cx('range')}>
            <RangeBar
              label={'CPU Cores'}
              setting={'cpu'}
              range={defaultRange}
              handleRangeBar={(setting, value, maxValue) =>
                handleRangeBar(setting, value, maxValue, setDefaultRange)
              }
              max={defaultMaxRange.cpu}
              step={1}
              unit={t('eaOnly.label')}
            />
            <RangeBar
              label={'RAM'}
              setting={'ram'}
              range={defaultRange}
              handleRangeBar={(setting, value, maxValue) =>
                handleRangeBar(setting, value, maxValue, setDefaultRange)
              }
              max={defaultMaxRange.ram}
              unit={'GB'}
            />
          </div>
        </InputBoxWithLabel>

        <InputBoxWithLabel
          labelText={`${t('dataStorage.label')} ${t('information.label')}`}
          labelSize='large'
          labelStyle={{
            marginBottom: '16px',
          }}
          disableErrorMsg
        >
          <div className={cx('storage-info')}>
            <div className={cx('storage-title')}>
              <div className={cx('head')}>유형</div>
              <div className={cx('head')}>이름</div>
              <div className={cx('head')}>용량</div>
            </div>
            <div className={cx('storage-content')}>
              <div className={cx('cont')}>
                <StatusCard
                  // text={systemType === 'nfs' ? t('network.label') : t('local')}
                  // status={systemType === 'nfs' ? 'yellow' : 'green'}
                  text={t('network.label')}
                  status={'blue'}
                  size='x-small'
                  type='default'
                />
              </div>
              <div className={cx('cont')}>stroage-local-nfx</div>
              <div className={cx('cont')}>4 GB</div>
            </div>
          </div>
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
};

export default DataResourceSettingModal;
