import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';

import { InputText, Textarea } from '@tango/ui-react';

import FbRadio from '@src/components/atoms/input/Radio';
import FixGrayDropDown from '@src/components/molecules/FixGrayDropDown';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiSelect from '@src/components/molecules/MultiSelect';

import { closeModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';

import GrayDropDown from '../BasicFeeOptionModal/GrayDropDown';
import NewStyleModalFrame from '../NewStyleModalFrame';
import ProcessInstance from './ProcessInstance';
import ProcessToolTip from './ProcessToolTip';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './AddDatasetPreprocessModal.module.scss';

import info from '@src/static/images/icon/00-ic-gray-info.svg';

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

const PROCESS_RULE = ['advanced', 'built-in'];

const nameExg = /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

const AddDatasetPreprocessModal = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { auth } = useSelector((state) => ({
    auth: state.auth,
  }));

  const { userName } = auth;

  const [processName, setProcessName] = useState('');
  const [processDesc, setProcessDesc] = useState('');
  const [instanceOption, setInstanceOption] = useState([]);

  const [selectedAccessType, setSelectedAccessType] = useState(1);
  const [selectedProcessRule, setSelectedProcessRule] = useState(0);
  const [dataType, setDataType] = useState(0);
  const [dataTypeList, setDataTypeList] = useState([]);
  const [owner, setOwner] = useState({ label: '', value: '' });
  const [ownerList, setOwnerList] = useState([]);
  const [conversionFunction, setConversionFunction] = useState({
    label: '',
    value: '',
  });
  const [conversionFunctionList, setConversionFunctionList] = useState([]);
  const [validate, setValidate] = useState(false);
  const [footerMessage, setFooterMessage] = useState('');
  // 기존에 선택된 사용자
  const [initialSelectUser, setIntialSelectUser] = useState([]);
  // 선택된 사용자
  const [selectedUser, setSelectedUser] = useState([]);
  // 할당 가능한 사용자
  const [allocateUser, setAllocateUser] = useState([]);

  const processRuleOption = [
    {
      label: 'Custom 전처리 룰',
      value: 0,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
      disabled: type === 'MODIFY_DATASET_PREPROCESS',
    },
    {
      label: 'Built-in 전처리 룰',
      value: 1,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
      disabled: type === 'MODIFY_DATASET_PREPROCESS',
    },
  ];

  const handleOwner = ({ value, label }) => {
    setOwner({ label, value });
  };

  const handleBuiltIn = ({ value, label }) => {
    setConversionFunction({ label, value });
  };

  const radioBtnHandler = (name, value) => {
    setSelectedAccessType(Number(value));
  };

  const processRuleRadioBtnHandler = (name, value) => {
    setSelectedProcessRule(Number(value));
  };

  const builtInTypeRadioHandler = (name, value) => {
    setDataType(Number(value));
  };
  const { submit, cancel, workspace_id, project_id } = data;

  const newSubmit = {
    text: submit.text,
    func: async () => {
      const isAddMode = type === 'ADD_DATASET_PREPROCESS';
      const instance = instanceOption.find((v) => v.checked);

      const body = {
        owner_id: owner.value,
        instance_id: instance.id,
        instance_allocate: instance.used,
        access: selectedAccessType,
        description: processDesc,
        user_list: selectedUser
          .map((v) => v.value)
          .filter((v) => v !== owner.value),
      };

      if (isAddMode) {
        Object.assign(body, {
          preprocessing_name: processName,
          preprocessing_type: PROCESS_RULE[selectedProcessRule],
          workspace_id: Number(workspace_id),
          ...(selectedAccessType === 1 && {
            built_in_data_tf: conversionFunction.value,
            built_in_data_type: dataTypeList[dataType].label,
          }),
        });
      } else {
        Object.assign(body, {
          preprocessing_id: project_id,
        });
      }

      const response = await callApi({
        url: 'preprocessing',
        method: isAddMode ? 'post' : 'put',
        body,
      });

      const { status, message, error } = response;

      if (status === STATUS_SUCCESS) {
        dispatch(
          closeModal(
            isAddMode ? 'ADD_DATASET_PREPROCESS' : 'MODIFY_DATASET_PREPROCESS',
          ),
        );
        submit.func();
      } else {
        errorToastMessage(error, message);
      }
    },
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

  const multiSelectHandler = ({ selectedList }) => {
    setSelectedUser(selectedList);
  };

  const fetchOptionList = async () => {
    const response = await callApi({
      url: `preprocessing/option?workspace_id=${workspace_id}`,
      method: 'get',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      const { instances, user_list, built_in_data_tfs, built_in_data_types } =
        result;

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
      const dataTypeList = built_in_data_types.map((v, index) => ({
        label: v,
        value: index,
        labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
        disabled: type === 'MODIFY_DATASET_PREPROCESS',
      }));
      setOwnerList(userList);
      setAllocateUser(userList);
      setInstanceOption(instanceList);
      setDataTypeList(dataTypeList);
      setOwner(curOwner);
    }
  };

  const getDetailInfo = async () => {
    if (!project_id || !ownerList.length || !dataTypeList.length) return;

    const response = await callApi({
      url: `preprocessing/${project_id}`,
      method: 'get',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      const {
        name,
        description,
        instance_info,
        owner_name,
        access,
        private_user_list,
        type,
        built_in_data_tf,
        built_in_data_type,
      } = result;
      const { instance_id, instance_allocate } = instance_info;
      setProcessName(name);
      setProcessDesc(description);
      setInstanceOption((prev) =>
        prev.map((option) =>
          option.id === instance_id
            ? { ...option, checked: true, used: instance_allocate }
            : { ...option },
        ),
      );
      const prevOwner = ownerList.filter((v) => v.label === owner_name)[0];
      setOwner(prevOwner);
      setSelectedAccessType(access);
      const privateUser = private_user_list.map(({ id, user_name }) => ({
        label: user_name,
        value: id,
      }));
      const privateOwnerIds = private_user_list.map(({ id }) => id);
      setAllocateUser(
        ownerList.filter(({ value }) => !privateOwnerIds.includes(value)),
      );
      setIntialSelectUser(privateUser);
      setSelectedProcessRule(type === 'advanced' ? 0 : 1);

      if (type === 'built-in') {
        const dataTypeIndex = dataTypeList.findIndex(
          (v) => v.label === built_in_data_type,
        );
        setDataType(dataTypeIndex);
        setConversionFunction({
          label: built_in_data_tf,
          value: built_in_data_tf,
        });
      }
    }
  };

  const fetchConversionFunction = async () => {
    if (!dataTypeList || !dataTypeList.length) return;

    const dType = dataTypeList[dataType].label;

    const response = await callApi({
      url: `options/preprocessing/built-in-tfs?data_type=${dType}`,
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      const list = result.map((v) => ({ label: v, value: v }));
      setConversionFunctionList([...list]);

      if (type !== 'MODIFY_DATASET_PREPROCESS') {
        setConversionFunction({ label: '', value: '' });
      }
    }
  };

  useEffect(() => {
    fetchOptionList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchConversionFunction();
  }, [dataType, selectedProcessRule]);

  useEffect(() => {
    getDetailInfo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ownerList, dataTypeList]);

  const handleFooterMessage = () => {
    const isValidInstance = instanceOption.find((v) => v.checked);

    const validationMessages = [
      {
        condition: !processName || nameExg.test(processName),
        message: '전처리 이름을 입력해 주세요.',
      },
      { condition: !isValidInstance, message: '인스턴스를 선택해 주세요.' },
      {
        condition: isValidInstance && !isValidInstance.used,
        message: '인스턴스 할당량을 입력해 주세요.',
      },
      {
        condition: selectedProcessRule === 1 && !conversionFunction.label,
        message: '전처리 함수를 선택해 주세요.',
      },
    ];

    const invalid = validationMessages.find(({ condition }) => condition);

    if (invalid) {
      setFooterMessage(invalid.message);
      return;
    }

    setFooterMessage('');
  };

  useEffect(() => {
    handleFooterMessage();
    const isValidInstance = instanceOption.filter((v) => v.checked)[0];
    if (
      !processName ||
      !isValidInstance ||
      !isValidInstance.used ||
      !owner.label ||
      (selectedProcessRule === 1 && conversionFunction.label === '')
    ) {
      setValidate(false);
      return;
    }

    setValidate(true);

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    processName,
    instanceOption,
    owner,
    selectedProcessRule,
    conversionFunction,
  ]);

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      isResize={true}
      isMinimize={true}
      type={type}
      title={`${t('preprocess.label')} ${
        project_id ? t('update.label') : t('create.label')
      }`}
      customStyle={{ maxHeight: '750px' }}
      validate={validate}
      footerMessage={footerMessage}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={`${t('preprocess.label')} ${t('name.label')}`}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            placeholder={t('preprocessName.placeholder')}
            onChange={(e) => setProcessName(e.target.value)}
            name='workspace'
            value={processName}
            status={nameExg.test(processName) ? 'error' : 'default'}
            isReadOnly={type === 'MODIFY_DATASET_PREPROCESS'}
            options={{ maxLength: 50 }}
            autoFocus={true}
            customStyle={{ fontSize: '14px' }}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={`${t('preprocess.label')} ${t('description.label')}`}
          optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <Textarea
            size='large'
            placeholder={t('preprocessDesc.placeholder')}
            value={processDesc}
            name='description'
            onChange={(e) => setProcessDesc(e.target.value)}
            customStyle={{ fontSize: '14px' }}
            isShowMaxLength
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={`${t('preprocess.label')} ${t(
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
        <InputBoxWithLabel
          labelText={t('preprocess.option.label')}
          labelSize='large'
          disableErrorMsg
        >
          <FbRadio
            name='process-rule'
            options={processRuleOption}
            value={selectedProcessRule}
            onChange={(e) => {
              processRuleRadioBtnHandler('process-rule', e.currentTarget.value);
            }}
            isLabelColor
          />
        </InputBoxWithLabel>
        {selectedProcessRule === 1 && (
          <InputBoxWithLabel
            labelText={t('dataType.label')}
            labelSize='large'
            disableErrorMsg
          >
            <FbRadio
              name='data-type'
              options={dataTypeList}
              value={dataType}
              onChange={(e) => {
                builtInTypeRadioHandler('data-type', e.currentTarget.value);
              }}
              isLabelColor
            />
            <FixGrayDropDown
              list={conversionFunctionList}
              value={conversionFunction}
              handleSelectOption={handleBuiltIn}
              placeholder={t('전처리 함수를 선택하세요')}
              isCloseBorder={false}
              listCustomStyle={{ maxHeight: '110px', overflow: 'auto' }}
              customStyle={{ marginTop: '16px' }}
              isReadOnly={type === 'MODIFY_DATASET_PREPROCESS'}
            />
          </InputBoxWithLabel>
        )}
        <div className={cx('bottom-box')}>
          <div className={cx('content')}>
            <div className={cx('text')}>
              <span>{t('accessType.label')}</span>
              <ProcessToolTip
                icon={info}
                position={'up'}
                iconStyle={{ transform: 'translateY(2px)' }}
                customStyle={{
                  height: '290px',
                  transform: 'translate(10px, -100px)',
                }}
                contents={
                  <div className={cx('tool-tip')}>
                    <div className={cx('header')}>데이터 전처리 접근 권한</div>
                    <div className={cx('info-box')}>
                      <span className={cx('info')}>
                        Private으로 설정한 경우 사용자를 선택하여 특정
                        사용자에게만 사용 권한을 부여할 수 있습니다.
                      </span>
                      <span className={cx('info')}>
                        선택된 사용자는 JOB 생성 또는&nbsp;
                        <span className={cx('red-text')}>
                          Jupyter Notebook 사용만&nbsp;
                        </span>
                        가능하며 데이터 전처리를 수정하거나 삭제할 수 없습니다.
                      </span>
                      <span className={cx('info')}>
                        단, 워크스페이스 매니저는 소유자와 동일하게 모든 권한을
                        가집니다.
                      </span>
                    </div>
                  </div>
                }
              />
            </div>
            <FbRadio
              name='accessType'
              options={accessOption}
              value={selectedAccessType}
              onChange={(e) => {
                radioBtnHandler('accessType', e.currentTarget.value);
              }}
              isLabelColor
            />
          </div>
          <div className={cx('content')}>
            <InputBoxWithLabel
              labelText={t('owner.label')}
              labelSize='large'
              disableErrorMsg
            >
              <FixGrayDropDown
                list={ownerList}
                value={owner}
                handleSelectOption={handleOwner}
                placeholder={t('owner.placeholder')}
                isCloseBorder={false}
                listCustomStyle={{ maxHeight: '110px', overflow: 'auto' }}
                isReadOnly={type === 'MODIFY_DATASET_PREPROCESS'}
              />
            </InputBoxWithLabel>
          </div>
        </div>

        {selectedAccessType === 0 && (
          <MultiSelect
            // innerRef={setRef}
            label='users.label'
            listLabel='availableUsers.label'
            selectedLabel='chosenUsers.label'
            list={allocateUser} // 초기 목록
            selectedList={initialSelectUser} // 초기 선택된 목록
            onChange={multiSelectHandler} // 변경 이벤트
            exceptItem={owner && owner.value} // 목록에서 빠질 아이템
            optional
          />
        )}
      </div>
    </NewStyleModalFrame>
  );
};

export default AddDatasetPreprocessModal;
