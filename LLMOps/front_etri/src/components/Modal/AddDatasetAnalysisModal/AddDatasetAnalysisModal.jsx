import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';

import { InputText, Textarea } from '@tango/ui-react';

import FbRadio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiSelect from '@src/components/molecules/MultiSelect';

import {
  getAnalyzerInfo,
  getOptionsAnalyzer,
  postAnalyzer,
  putAnalyzer,
} from '@src/apis/flightbase/dataset/analysis';
import { closeModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';

import GrayDropDown from '../BasicFeeOptionModal/GrayDropDown';
import NewStyleModalFrame from '../NewStyleModalFrame';
import ProcessInstance from './ProcessInstance';
import ProcessToolTip from './ProcessToolTip';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './AddDatasetAnalysisModal.module.scss';

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

// ** [계산] validate
const calIsFooterMessage = (instanceOption, analysisName, owner) => {
  const isValidInstance = instanceOption.filter((v) => v.checked)[0];
  const forbiddenChars = /[\\<>:*?"'|:;`{}()^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

  if (!analysisName) {
    return 'analyzeName.warn.message';
  }
  if (analysisName && forbiddenChars.test(analysisName)) {
    return 'newNameRule.message';
  }
  if (!isValidInstance || !isValidInstance.used) {
    return 'analyzeInstance.warn.message';
  }
  if (!owner.label) {
    return 'analyzeOwner.warn.message';
  }
  return null;
};
// ** handler user select
const onSelectUser = (setState, list) => {
  setState(list);
};

// ** [get] 분석 프로젝트 옵션
const fetchOptionList = async ({
  setOwnerList,
  setInstanceOption,
  setOwner,
  userName,
  wid,
  isAddMode,
  project_id,
  setSelectedUserList,
  setAnalysisName,
  setAnalysisDesc,
  setSelectedAccessType,
}) => {
  const response = await getOptionsAnalyzer(wid);

  const { result, status, error, message } = response;

  if (status === STATUS_SUCCESS) {
    const {
      instance_list: instances,
      user_list,
      built_in_list,
      access,
    } = result;

    const instanceList = instances.map(
      ({
        cpu_allocate,
        gpu_allocate,
        ram_allocate,
        instance_total,
        gpu_name,
        instance_id,
        instance_name,
        resource_name,
      }) => ({
        id: instance_id,
        resourceName: resource_name,
        instanceName: instance_name,
        gpuName: gpu_name,
        max: instance_total,
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

    setOwnerList(userList);

    const curOwner = userList.filter((v) => userName === v.label)[0];

    setInstanceOption(instanceList);
    // setBuiltInList(builtInList);
    setOwner(curOwner);

    if (!isAddMode) {
      getDetailInfo({
        ownerList: userList,
        project_id,
        setOwnerList,
        setSelectedUserList,
        setAnalysisName,
        setAnalysisDesc,
        setSelectedAccessType,
        setInstanceOption,
        setOwner,
      });
    }
  } else {
    errorToastMessage(error, message);
  }
};

const getDetailInfo = async ({
  ownerList,
  project_id,
  setSelectedUserList,
  setOwnerList,
  setAnalysisName,
  setAnalysisDesc,
  setInstanceOption,
  setOwner,
  setSelectedAccessType,
}) => {
  if (ownerList.length < 1) return;

  const response = await getAnalyzerInfo(project_id);

  const { result, status } = response;

  if (status === STATUS_SUCCESS) {
    const {
      name,
      description,
      instance: instanceInfo,
      owner,
      access,
      users,
    } = result;
    const { instance_id, instance_allocate } = instanceInfo;
    if (access === 0 && users) {
      const prevSelectedUsers = users.map((v) => {
        return {
          label: v.user_name,
          value: v.user_id,
        };
      });

      setSelectedUserList(prevSelectedUsers);

      const newOwenrList = [
        ...ownerList.filter(
          (owner) =>
            !prevSelectedUsers.some((prev) => prev.value === owner.value),
        ),
        ...prevSelectedUsers.filter(
          (prev) => !ownerList.some((owner) => owner.value === prev.value),
        ),
      ];

      setOwnerList(newOwenrList);
    }
    setAnalysisName(name);
    setAnalysisDesc(description);
    setInstanceOption((prev) =>
      prev.map((option) =>
        `${option.id}` === `${instance_id}`
          ? { ...option, checked: true, used: instance_allocate }
          : { ...option },
      ),
    );

    const prevOwner = ownerList.filter((v) => v.label === owner)[0];
    setOwner(prevOwner);
    setSelectedAccessType(access);
  }
};

const AddDatasetAnalysis = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { auth } = useSelector((state) => ({
    auth: state.auth,
  }));

  const { submit, cancel, workspace_id: wid, project_id, modalType } = data;
  const { userName } = auth;

  const [analysisName, setAnalysisName] = useState('');
  const [analysisDesc, setAnalysisDesc] = useState('');
  const [instanceOption, setInstanceOption] = useState([]);

  const [selectedAccessType, setSelectedAccessType] = useState(1);
  const [owner, setOwner] = useState({ label: '', value: '' });
  const [ownerList, setOwnerList] = useState([]);
  const [userList, setUserList] = useState([]);
  const [selectedUserList, setSelectedUserList] = useState([
    // 수정 시 사용 & 멀티셀렉 렌더링시 setUserList에 넣어줌.
  ]);
  const [validate, setValidate] = useState(false);

  const handleOwner = ({ value, label }) => {
    setOwner({ label, value });
  };

  const radioBtnHandler = (name, value) => {
    setSelectedAccessType(Number(value));
  };

  // ** 사용자[선택 항목] **
  // const userList = useRef([]);
  // const handleSelectedUserList = useCallback((selectedList) => {
  //   userList.current = selectedList;
  // }, []);
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const isAddMode = modalType === 'ADD_DATASET_ANALYSIS';
      const instance = instanceOption.find((v) => v.checked);
      const body = {
        name: analysisName,
        owner_id: owner.value,
        instance_id: instance.id,
        instance_allocate: instance.used,
        access: selectedAccessType,
        description: analysisDesc,
        users_id: userList.map(({ value }) => value),
      };
      if (isAddMode) {
        Object.assign(body, {
          workspace_id: +wid,
          // preprocessing_type: BUILT_IN_TYPE[selectedBuiltInType],
          user_list: [],
        });
      } else {
        Object.assign(body, {
          id: project_id,
          user_list: [],
        });
      }

      let res;

      if (isAddMode) {
        res = await postAnalyzer(body);
      } else {
        res = await putAnalyzer(body);
      }

      const { status, error, message } = res;

      if (status === STATUS_SUCCESS) {
        dispatch(closeModal('ADD_DATASET_ANALYSIS'));
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

  useEffect(() => {
    if (wid) {
      fetchOptionList({
        setOwnerList,
        setInstanceOption,
        setOwner,
        userName,
        wid,
        isAddMode: modalType === 'ADD_DATASET_ANALYSIS',
        project_id,
        setSelectedUserList,
        setAnalysisName,
        setAnalysisDesc,
        setSelectedAccessType,
      });
    }
  }, [modalType, project_id, userName, wid]);

  useEffect(() => {
    const isValidInstance = instanceOption.filter((v) => v.checked)[0];
    if (
      !analysisName ||
      !isValidInstance ||
      !isValidInstance.used ||
      !owner.label
    ) {
      setValidate(false);
      return;
    }

    setValidate(true);
  }, [analysisName, instanceOption, owner]);

  const isFooterMessage = calIsFooterMessage(
    instanceOption,
    analysisName,
    owner,
  );

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      isResize={true}
      isMinimize={true}
      type={type}
      title={`${t('analyze.label')} ${
        project_id ? t('update.label') : t('create.label')
      }`}
      footer
      customStyle={{ maxHeight: '750px' }}
      validate={!isFooterMessage}
      footerMessage={t(isFooterMessage ?? '')}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={`${t('analyze.label')} ${t('name.label')}`}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            placeholder={t('analyze.name.placeholder')}
            onChange={(e) => setAnalysisName(e.target.value)}
            name='workspace'
            value={analysisName}
            // value={'ggsdgssdg'}
            // status={!validate ? 'error' : 'default'}
            isReadOnly={modalType === 'EDIT_DATASET_ANALYSIS'}
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
          labelText={`${t('analyze.label')} ${t('description.label')}`}
          optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <Textarea
            size='large'
            placeholder={t('analyze.desc.placeholder')}
            value={analysisDesc}
            name='description'
            onChange={(e) => setAnalysisDesc(e.target.value)}
            customStyle={{ fontSize: '14px' }}
            isShowMaxLength
          />
        </InputBoxWithLabel>
      </div>
      <InputBoxWithLabel
        labelText={t('analyzeResourceSetting.label')}
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
      {selectedAccessType === 0 && (
        <div className={cx('users')}>
          <MultiSelect
            label='users.label'
            listLabel='availableUsers.label'
            selectedLabel='chosenUsers.label'
            list={ownerList} // 초기 목록
            selectedList={selectedUserList} // 초기 선택된 목록
            onChange={({ selectedList }) => {
              onSelectUser(setUserList, selectedList);
            }} // 변경 이벤트
            exceptItem={owner && owner.value} // 목록에서 빠질 아이템
            optional
            style={{ marginTop: '32px' }}
          />
        </div>
      )}
    </NewStyleModalFrame>
  );
};

export default AddDatasetAnalysis;
