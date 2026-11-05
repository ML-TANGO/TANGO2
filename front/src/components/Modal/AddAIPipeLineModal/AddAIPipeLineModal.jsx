import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import { InputText, Textarea, Tooltip } from '@jonathan/ui-react';

import Dropdown from '@src/components/atoms/Dropdown';
import FbRadio from '@src/components/atoms/input/Radio';
import Radio from '@src/components/atoms/input/Radio';
import FixGrayDropDown from '@src/components/molecules/FixGrayDropDown';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiSelect from '@src/components/molecules/MultiSelect';

import {
  getOptionsPipeline,
  getOptionsPreprocessingDataType,
  postPipeline,
} from '@src/apis/flightbase/pipeline';
import { closeModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import { calNameError } from '../AddPlayground/AddPlayground';
import NewStyleModalFrame from '../NewStyleModalFrame';

import { errorToastMessage } from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './AddAIPipeLineModal.module.scss';

const cx = classNames.bind(style);

export const nameExg = /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

const calFooterMessage = (isNameError, addState, t) => {
  const {
    name,
    pipelineField,
    pipelineType,
    fieldValueManufacture,
    fieldValueHealth,
    selectedPreprocess,
  } = addState;

  if (!name) return '이름을 입력해 주세요.';
  if (isNameError) return t('newNameRule.message');

  // Custom
  if (pipelineType === 1) return '';

  // 파이프라인 분야
  if (pipelineField === 0) {
    if (fieldValueManufacture.label === '') return t('pipeline.select.prompt');
  } else {
    if (fieldValueHealth.label === '') return t('pipeline.select.prompt');
  }

  // 데이터 유형
  if (selectedPreprocess.length === 0)
    return t('pipeline.preprocess.select.prompt');

  return '';
};

// * 파이프라인 유형 옵션
const pipelineTypeOptions = [
  {
    label: 'pipeline.create.title',
    value: 1,
  },
  {
    label: 'pipeline.use.title',
    value: 0,
  },
];

// * 파이프라인 분야 옵션
const pipelineFieldOptions = [
  {
    label: 'pipeline.healthcare.label',
    value: 1,
  },
  {
    label: 'pipeline.manufacturing.label',
    value: 0,
  },
];

const initial = {
  name: null,
  description: '',
  access: 1,
  pipelineType: 1, // 파이프라인 유형 radio
  pipelineField: 1, // 파이프라인 분야 radio
  fieldValueHealth: { label: '', value: '' }, // 분야 - 헬스케어
  fieldValueManufacture: { label: '', value: '' }, // 분야 - 제조
  trainingDataStatement: '', // 학습 데이터 명세서
  dataType: 0, // 데이터 유형 radio
  dataTypeValue: '', // 데이터 유형 선택 value
  selectedPreprocess: [], // 학습 정제 및 전처리 선택 값
  owner_id: {
    label: null,
    value: null,
  },
  user_id: [],
};

const accessTypeOptions = [
  { label: 'public', value: 1 },
  { label: 'Private', value: 0 },
];

export const getOwnerOptions = async (
  workspaceId,
  userName,
  setOwnerOptions,
  setAddState,
  setDataTypeList,
  setConversionFunctionList,
  pipelineId,
) => {
  const { result, message, status, error } = await getOptionsPipeline(
    workspaceId,
    pipelineId,
  );
  if (status === STATUS_SUCCESS) {
    const { built_in_data_types, pipeline_built_in } = result;

    const { 헬스케어: health, 제조: manufacturingData } = pipeline_built_in;
    const userList = result.user_list.slice();
    const transformUserList = userList.map((el) => {
      return {
        label: el.name,
        value: el.id,
      };
    });
    const findMyOption = transformUserList.find((el) => el.label === userName);
    const builtinDataType = built_in_data_types.map((v, index) => ({
      label: v,
      value: index,
    }));

    //헬스케어
    const healthCare = health.map((v, index) => ({
      label: v,
      value: index,
    }));

    //제조
    const manufacturing = manufacturingData.map((v, index) => ({
      label: v,
      value: index,
    }));
    setConversionFunctionList({ healthCare, manufacturing });
    setDataTypeList(builtinDataType);
    setOwnerOptions(transformUserList);
    setAddState((prev) => ({
      ...prev,
      dataTypeValue: builtinDataType[0],
      owner_id: findMyOption,
    }));
  } else {
    errorToastMessage(error, message);
  }
};

const handleInput = (type, setAddState, value) => {
  setAddState((prev) => ({
    ...prev,
    [type]: value,
  }));
};

const handleSubmit = async (
  addState,
  userList,
  workspaceId,
  type,
  handleRefresh,
  dispatch,
) => {
  const { owner_id } = addState;
  let body = {
    name: addState.name,
    description: addState.description,
    access: addState.access,
    owner_id: owner_id.value,
    workspace_id: +workspaceId,
    users_id: userList,
    type: 'advanced',
  };

  if (addState.pipelineType === 0) {
    body = {
      ...body,
      type: addState.pipelineType === 0 ? 'built-in' : 'advanced',
      built_in_type: addState.pipelineField === 0 ? '제조' : '헬스케어',
      built_in_sub_type:
        addState.pipelineField === 0
          ? addState.fieldValueManufacture.label
          : addState.fieldValueHealth.label,
      built_in_specification: addState.trainingDataStatement,
      built_in_data_type: addState.dataTypeValue.label,
      built_in_preprocessing_list: addState.selectedPreprocess,
    };
  }

  const { status, message } = await postPipeline(body);
  if (status === STATUS_SUCCESS) {
    dispatch(closeModal(type));
    handleRefresh();
  } else {
    toast.error(message);
  }
};

const initialSelectUser = [];
const initialSelectPreprocess = [];

export const TooltipContent = () => {
  return (
    <div className={cx('tooltip')}>
      <p className={cx('title')}>파이프라인 접근 권한</p>
      <div className={cx('contents')}>
        <p>
          Private으로 설정한 경우 사용자를 선택하여 특정 사용자에게만 사용
          권한을 부여할 수 있습니다.
        </p>
        <p>
          선택된 사용자는 작업 추가 또는 자동 업데이트 설정만 가능하며
          파이프라인을 수정하거나 삭제할 수 없습니다.
        </p>
        <p>단, 워크스페이스 매니저는 소유자와 동일하게 모든 권한을 가집니다.</p>
      </div>
    </div>
  );
};

// 데이터 정제 및 전처리 툴팁
export const PreprocessTooltipContent = ({ t }) => {
  return (
    <div className={cx('tooltip')}>
      <p className={cx('title')}>{t('pipeline.preprocess.warning.label')}</p>
      <div className={cx('contents')}>
        <p>{t('pipeline.preprocess.tooltip.message.first')}</p>
        <p>{t('pipeline.preprocess.tooltip.message.second')}</p>
        <p>{t('pipeline.preprocess.tooltip.message.third')}</p>
      </div>
    </div>
  );
};

const fetchConversionFunction = async (
  dType, // 선택했던 타입
  setPreprocessList,
) => {
  const response = await getOptionsPreprocessingDataType(dType);

  const { result, status } = response;

  if (status === STATUS_SUCCESS) {
    const list = result.map((v) => ({ label: v, value: v }));
    setPreprocessList([...list]);
  }
};

export default function AddAIPipeLineModal({ type, data }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const { workspaceId, handleRefresh } = data;

  const [addState, setAddState] = useState(initial);
  const { name, description, access, owner_id } = addState;
  const isNameError = calNameError(name);

  const [ownerOptions, setOwnerOptions] = useState([]);
  const [userList, setUserList] = useState([]);

  // 파이프라인 분야 selectbox list 값
  const [conversionFunctionList, setConversionFunctionList] = useState([]);

  // 데이터 정제 및 전처리 list 값
  const [preprocessList, setPreprocessList] = useState([]);

  // 데이터 유형 list 값
  const [dataTypeList, setDataTypeList] = useState([]);

  const handeUserList = ({ selectedList }) => {
    const shallowList = selectedList.slice();
    const transformList = shallowList.map(({ value }) => value);
    setUserList(transformList);
  };

  // * 데이터 정제 및 전처리 선택 핸들러
  const handePreprocessList = ({ selectedList }) => {
    if (selectedList.length === 0) return;
    const shallowList = selectedList.slice();
    const transformList = shallowList.map(({ value }) => value);
    setAddState((prev) => ({
      ...prev,
      selectedPreprocess: transformList,
    }));
  };

  const cancel = {
    text: t('cancel.label'),
    func: () => {},
  };

  const submit = {
    text: t('create.label'),
    func: () =>
      handleSubmit(
        addState,
        userList,
        workspaceId,
        type,
        handleRefresh,
        dispatch,
      ),
  };

  const footerMessage = calFooterMessage(isNameError, addState, t);
  const isValidate = !footerMessage;

  useEffect(() => {
    getOwnerOptions(
      workspaceId,
      userName,
      setOwnerOptions,
      setAddState,
      setDataTypeList,
      setConversionFunctionList,
    );
  }, [userName, workspaceId]);

  useEffect(() => {
    if (addState.pipelineType === 0 && dataTypeList.length > 0) {
      const pType = dataTypeList[addState.dataType]?.label;

      fetchConversionFunction(pType, setPreprocessList);
    }
  }, [addState.dataType, addState.pipelineType, dataTypeList]);

  return (
    <NewStyleModalFrame
      title={'AI 파이프라인 프로젝트 생성'}
      type={type}
      cancel={cancel}
      submit={submit}
      validate={isValidate}
      isResize={true}
      isMinimize={true}
      footerMessage={footerMessage}
    >
      <InputBoxWithLabel
        labelText={t('projectName.label')}
        labelSize='large'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <InputText
          size='medium'
          onChange={(e) => {
            handleInput('name', setAddState, e.target.value);
          }}
          name='projectName'
          placeholder={t('project.empty.message')}
          value={name}
          status={isNameError || name === '' ? 'error' : 'default'}
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel
        labelText={t('projectDescription.label')}
        optionalText={t('optional.label')}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <Textarea
          size='large'
          placeholder={t('project.desc.empty.message')}
          value={description}
          name='description'
          onChange={(e) =>
            handleInput('description', setAddState, e.target.value)
          }
          customStyle={{ fontSize: '14px', height: '160px' }}
          isShowMaxLength
        />
      </InputBoxWithLabel>
      {addState.pipelineType === 0 && (
        <InputBoxWithLabel // * 학습 데이터 명세서
          labelText={t('pipeline.training_data.specification')}
          optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
          style={{ marginBottom: '32px' }}
        >
          <Textarea
            size='large'
            placeholder={t('pipeline.training_data.input_specification')}
            value={addState.trainingDataStatement}
            name='statement'
            onChange={(e) =>
              handleInput('trainingDataStatement', setAddState, e.target.value)
            }
            customStyle={{ fontSize: '14px', height: '160px' }}
            isShowMaxLength
          />
        </InputBoxWithLabel>
      )}

      <InputBoxWithLabel // * 파이프라인 유형
        labelText={t('pipeline.type.title')}
        labelSize='large'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <FbRadio
          name='pipelineType'
          options={pipelineTypeOptions}
          value={addState.pipelineType}
          onChange={(e) => {
            handleInput('pipelineType', setAddState, +e.currentTarget.value);
          }}
          isLabelColor
        />
      </InputBoxWithLabel>
      {addState.pipelineType === 0 && (
        <>
          <InputBoxWithLabel // * 파이프라인 분야 -> '적용 분야'로 이름 기획 변경 됨
            labelText={t('pipeline.application.field.title')}
            labelSize='large'
            disableErrorMsg
            style={{ marginBottom: '32px' }}
          >
            <FbRadio
              name='pipelineField'
              options={pipelineFieldOptions}
              value={addState.pipelineField}
              onChange={(e) => {
                handleInput(
                  'pipelineField',
                  setAddState,
                  +e.currentTarget.value,
                );
              }}
              isLabelColor
            />
            {addState.pipelineField === 1 && (
              <FixGrayDropDown
                list={conversionFunctionList.healthCare}
                value={addState.fieldValueHealth}
                handleSelectOption={(value) => {
                  handleInput('fieldValueHealth', setAddState, value);
                }}
                placeholder={t('pipeline.select')}
                isCloseBorder={false}
                listCustomStyle={{ maxHeight: '110px', overflow: 'auto' }}
                customStyle={{ marginTop: '16px' }}
                isReadOnly={type === 'MODIFY_DATASET_PREPROCESS'}
              />
            )}

            {addState.pipelineField === 0 && (
              <FixGrayDropDown
                list={conversionFunctionList.manufacturing}
                value={addState.fieldValueManufacture}
                handleSelectOption={(value) => {
                  handleInput('fieldValueManufacture', setAddState, value);
                }}
                placeholder={t('pipeline.select')}
                isCloseBorder={false}
                listCustomStyle={{ maxHeight: '110px', overflow: 'auto' }}
                customStyle={{ marginTop: '16px' }}
                isReadOnly={type === 'MODIFY_DATASET_PREPROCESS'}
              />
            )}
          </InputBoxWithLabel>

          <InputBoxWithLabel // * 데이터 유형
            labelText={t('dataType.label')}
            labelSize='large'
            disableErrorMsg
            style={{ marginBottom: '32px' }}
          >
            <FbRadio
              name='datatype'
              options={dataTypeList}
              value={addState.dataType}
              onChange={(e) => {
                // * fetchConversionFunction

                setAddState((prev) => ({
                  ...prev,
                  selectedPreprocess: [],
                }));
                handleInput('dataType', setAddState, +e.target.value);
              }}
              customStyle={{ marginBottom: '32px' }}
              isLabelColor
            />

            <div className={cx('preprocess-title')}>
              <div>{t('pipeline.data.preprocess.label')}</div>
              <Tooltip
                icon='/src/static/images/icon/00-ic-alert-info-o.svg'
                iconCustomStyle={{
                  width: '16px',
                  height: '16px',
                  paddingBottom: '2px',
                }}
                contents={<PreprocessTooltipContent t={t} />}
                contentsAlign={{ vertical: 'top' }}
                contentsCustomStyle={{
                  width: '300px',
                  padding: '24px',
                  borderRadius: '10px',
                  border: '0.5px solid #DEE9FF',
                  background: '#FFF',
                  boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
                }}
              />
            </div>
            <MultiSelect // * 데이터 정제 및 전처리
              listLabel={t('pipeline.preprocess.available')}
              selectedLabel={t('pipeline.preprocess.added')}
              list={preprocessList}
              selectedList={initialSelectPreprocess}
              onChange={handePreprocessList}
              placeholder={t('pipeline.preprocess.input')}
            />
          </InputBoxWithLabel>
        </>
      )}

      <div className={cx('user-box')}>
        <InputBoxWithLabel
          labelText={t('accessType.label')}
          optionalText={
            <Tooltip
              icon='/src/static/images/icon/00-ic-alert-info-o.svg'
              iconCustomStyle={{
                width: '16px',
                height: '16px',
                paddingBottom: '2px',
              }}
              contents={<TooltipContent />}
              contentsAlign={{ vertical: 'top' }}
              contentsCustomStyle={{
                width: '300px',
                padding: '24px',
                borderRadius: '10px',
                border: '0.5px solid #DEE9FF',
                background: '#FFF',
                boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
              }}
            />
          }
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
          st
        >
          <Radio
            name='accesstype-input'
            value={access}
            options={accessTypeOptions}
            onChange={(e) =>
              handleInput('access', setAddState, +e.target.value)
            }
            isLabelColor
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={t('owner.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <Dropdown
            value={owner_id.value}
            list={ownerOptions}
            handleOptionClick={(option) => {
              handleInput('owner_id', setAddState, option);
            }}
            placeholder={t('project.select.label')}
            style={{ height: '38px', padding: '16px' }}
          />
        </InputBoxWithLabel>
      </div>

      {access === 0 && (
        <MultiSelect
          label='users.label'
          listLabel='availableUsers.label'
          selectedLabel='chosenUsers.label'
          list={ownerOptions} // 초기 목록
          selectedList={initialSelectUser} // 초기 선택된 목록
          onChange={handeUserList} // 변경 이벤트
          exceptItem={owner_id && owner_id.value} // 목록에서 빠질 아이템
          optional
        />
      )}
    </NewStyleModalFrame>
  );
}
