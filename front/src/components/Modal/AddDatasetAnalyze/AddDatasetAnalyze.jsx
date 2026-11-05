import { InputText, Textarea } from '@jonathan/ui-react';

import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';

import FbRadio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { callApi, STATUS_SUCCESS } from '@src/network';

import ProcessInstance from '../AddDatasetPreprocess/ProcessInstance';
import GrayDropDown from '../BasicFeeOptionModal/GrayDropDown';
import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './AddDatasetAnalyze.module.scss';

const cx = classNames.bind(style);

const accessOption = [
  {
    label: 'public',
    value: 1,
    labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
  },
  {
    label: 'private',
    value: 0,
    labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
  },
];

const AddDatasetAnalyze = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { auth } = useSelector((state) => ({
    auth: state.auth,
  }));

  const { userName } = auth;

  const [analyzeName, setAnalyzeName] = useState('');
  const [analyzeDesc, setAnalyzeDesc] = useState('');
  const [instanceOption, setInstanceOption] = useState([
    { id: 1, name: 'Geforce 2080', max: 5, checked: false, used: '' },
    { id: 2, name: 'Geforce 1080', max: 3, checked: false, used: '' },
    { id: 3, name: 'Geforce 3060', max: 7, checked: false, used: '' },
  ]);
  const [selectedAccessType, setSelectedAccessType] = useState(1);
  const [owner, setOwner] = useState({ label: '', value: '' });
  const [ownerList, setOwnerList] = useState([]);

  const handleOwner = ({ value, label }) => {
    setOwner({ label, value });
  };

  const radioBtnHandler = (name, value) => {
    setSelectedAccessType(Number(value));
  };

  const handleInstanceCheck = ({ id }) => {
    setInstanceOption((prevOptions) =>
      prevOptions.map((option) =>
        option.id === id
          ? { ...option, checked: true }
          : { ...option, checked: false, used: '' },
      ),
    );
  };

  const handleInstanceUsed = ({ id, value }) => {
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

  const { submit, cancel, jobId, workspace_id } = data;

  const newSubmit = {
    text: submit.text,
    func: async () => {},
  };

  const fetchOptionList = async () => {
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
  };

  useEffect(() => {
    fetchOptionList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      isResize={true}
      isMinimize={true}
      type={type}
      title={`${t('analyze.label')} ${t('create.label')}`}
      customStyle={{ maxHeight: '750px' }}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={`${t('analyze.label')} ${t('name.label')}`}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            placeholder={t('analyze.name.placeholder')}
            onChange={(e) => setAnalyzeName(e.target.value)}
            name='name'
            value={analyzeName}
            // status={!validate ? 'error' : 'default'}
            // isReadOnly={type === 'EDIT_RAG'}
            options={{ maxLength: 50 }}
            autoFocus={true}
            customStyle={{ fontSize: '14px' }}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={`${t('analyze.label')} ${t('description.label')}`}
          optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <Textarea
            size='large'
            placeholder={t('analyze.desc.placeholder')}
            value={analyzeDesc}
            name='description'
            onChange={(e) => setAnalyzeDesc(e.target.value)}
            customStyle={{ fontSize: '14px' }}
            isShowMaxLength
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={`${t('analyze.label')} ${t(
            'deploymentResourceAllocation.label',
          )}`}
          labelSize='large'
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
                    handleInstanceCheck={handleInstanceCheck}
                    handleInstanceUsed={handleInstanceUsed}
                  />
                ),
              )}
            </div>
          </div>
        </InputBoxWithLabel>
        <div className={cx('bottom-box')}>
          <div className={cx('content')}>
            <InputBoxWithLabel
              labelText={t('accessType.label')}
              labelSize='large'
              disableErrorMsg
            >
              <FbRadio
                name='accessType'
                options={accessOption}
                value={selectedAccessType}
                onChange={(e) => {
                  radioBtnHandler('accessType', e.currentTarget.value);
                }}
                isLabelColor
              />
            </InputBoxWithLabel>
          </div>
          <div className={cx('content')}>
            <InputBoxWithLabel
              labelText={t('owner.label')}
              labelSize='large'
              disableErrorMsg
            >
              <GrayDropDown
                list={ownerList}
                value={owner}
                handleSelectOption={handleOwner}
                placeholder={t('owner.placeholder')}
                isCloseBorder={false}
                listCustomStyle={{ maxHeight: '110px', overflow: 'auto' }}
              />
            </InputBoxWithLabel>
          </div>
        </div>
      </div>
    </NewStyleModalFrame>
  );
};

export default AddDatasetAnalyze;
