import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { ButtonV2, InputText } from '@jonathan/ui-react';

import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { closeModal, openModal } from '@src/store/modules/modal';
import useInputs from '@src/hooks/useInputs';

import { DeleteButton, ModifyButton } from '../AddWebcrowler/AddWebcrowler';
import NameInput from '../DataCollectModal/NameInput/NameInput';
import useNameInput from '../DataCollectModal/NameInput/useNameInput';
import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './AddCustomApiModal.module.scss';

const cx = classNames.bind(style);

const calDuplicateIndex = (requestParameter, map) => {
  const duplicatesWithIndexes = [];
  const shallowList = requestParameter.slice();

  shallowList.forEach((item, index) => {
    if (map.has(item.key)) {
      map.get(item.key).push(index);
    } else {
      map.set(item.key, [index]);
    }
  });

  map.forEach((indices) => {
    if (indices.length > 1) {
      duplicatesWithIndexes.push(...indices);
    }
  });

  return duplicatesWithIndexes;
};

const calFooterMessage = (
  name,
  apiUrl,
  apiKey,
  provider,
  pageUrl,
  requestParameter,
  duplicateIndexList,
) => {
  if (!name) return 'API 이름을 입력해 주세요.';
  if (!apiUrl) return 'API URL을 입력해 주세요.';
  if (!apiKey) return 'API Key를 입력해 주세요.';
  if (!provider) return '제공기관을 입력해 주세요.';
  if (!pageUrl) return '상세 설명 페이지 URL을 입력해 주세요.';

  if (requestParameter.length === 0) return '요청 변수를 추가해 주세요.';
  if (duplicateIndexList.length !== 0)
    return '중복되는 요청변수 항목명이 있습니다.';
  const nullRequestParameterList = requestParameter.find((info) => {
    return !info.key || !info.value;
  });
  if (nullRequestParameterList) return '요청 변수를 추가해 주세요.';

  return '';
};

// ** 수정 버튼 핸들러 **
export const handleModifyCustomApiButton = (
  name,
  apiUrl,
  apiKey,
  provider,
  pageUrl,
  requestValue,
  formValue,
  requestParameter,
  setCollectMethodList,
  dispatch,
) => {
  dispatch(
    openModal({
      modalType: 'ADD_CUSTOM_API_MODAL',
      modalData: {
        editName: name,
        editUrl: apiUrl,
        editApiKey: apiKey,
        editProvider: provider,
        editPageUrl: pageUrl,
        editRequestValue: requestValue,
        editFormValue: formValue,
        editRequestParameter: requestParameter,
        setCollectMethodList,
      },
    }),
  );
};

// ** 삭제 버튼 핸들러 **
export const handleDeleteCustomApiButton = (
  name,
  apiUrl,
  setCollectMethodList,
) => {
  setCollectMethodList((prev) => {
    const shallowList = prev['public_api'].slice();
    const findIndex = shallowList.findIndex(
      ({ first, second }) => first === name && second === apiUrl,
    );
    shallowList.splice(findIndex, 1);
    return {
      ...prev,
      public_api: shallowList,
    };
  });
};

export default function AddCustomApiModal({ data, type }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const {
    editName,
    editUrl,
    editApiKey,
    editProvider,
    editPageUrl,
    editRequestValue,
    editFormValue,
    editRequestParameter,
    setCollectMethodList,
  } = data;

  // ** [API 이름] **
  const labelText = 'API 이름';
  const placeholder = 'API 이름을 입력하세요';
  const { name, isError, handleName } = useNameInput();

  // ** [URL, Key, 제공기관, 상세 설명 페이지 URL, 요청 방식] **
  const { inputs, handleInputs } = useInputs({
    apiUrl: editUrl ?? '',
    apiKey: editApiKey ?? '',
    provider: editProvider ?? '',
    pageUrl: editPageUrl ?? '',
  });

  // ** 요청 방식 **
  const requestOptions = useMemo(() => {
    return [
      {
        label: 'GET',
        value: 0,
      },
      {
        label: 'POST',
        value: 1,
      },
    ];
  }, []);
  const [requestValue, setRequestValue] = useState(editRequestValue ?? 0);
  const handleRequestOption = useCallback((e) => {
    setRequestValue(+e.target.value);
  }, []);

  // ** 요청 방식 폼 **
  const requestFormOptions = useMemo(() => {
    return [
      { label: 'Form', value: 0 },
      { label: 'Body', value: 1 },
    ];
  }, []);
  const [formValue, setFormValue] = useState(editFormValue ?? 0);
  const handleFormOption = useCallback((e) => {
    setFormValue(+e.target.value);
  }, []);
  // ** [요청 변수] **
  const map = new Map();
  const [requestParameter, setRequestParameter] = useState(
    editRequestParameter ?? [
      {
        key: '',
        value: '',
      },
    ],
  );
  const duplicateIndexList = calDuplicateIndex(requestParameter, map);
  const footerMessage = calFooterMessage(
    name,
    inputs.apiUrl,
    inputs.apiKey,
    inputs.provider,
    inputs.pageUrl,
    requestParameter,
    duplicateIndexList,
  );

  const handleOnChangeParameter = useCallback((e, type, idx) => {
    setRequestParameter((prev) => {
      const list = prev.slice();
      const changeItem = list[idx];
      changeItem[type] = e.target.value;
      return list;
    });
  }, []);

  const handleDeleteParameterBtn = useCallback((idx) => {
    setRequestParameter((prev) => {
      const list = prev.slice();
      list.splice(idx, 1);
      return list;
    });
  }, []);

  const handleAddParameterBtn = useCallback(() => {
    setRequestParameter((prev) => {
      const list = prev.slice();
      list.push({
        key: '',
        value: '',
      });
      return list;
    });
  }, []);

  const handleSubmit = () => {
    setCollectMethodList((prev) => {
      const publicList = prev.public_api.slice();

      if (editName) {
        const findValueIdx = publicList.findIndex(
          ({ first, second }) => first === editName && second === editUrl,
        );
        publicList[findValueIdx].first = name;
        publicList[findValueIdx].second = inputs.apiUrl;
        publicList[findValueIdx].third = (
          <ModifyButton
            handleModifyButton={() =>
              handleModifyCustomApiButton(
                name,
                inputs.apiUrl,
                inputs.apiKey,
                inputs.provider,
                inputs.pageUrl,
                requestValue,
                formValue,
                requestParameter,
                setCollectMethodList,
                dispatch,
              )
            }
          />
        );
        publicList[findValueIdx].fourth = (
          <DeleteButton
            handleDeleteButton={() =>
              handleDeleteCustomApiButton(
                name,
                inputs.apiUrl,
                setCollectMethodList,
              )
            }
          />
        );
        publicList[findValueIdx].info = {
          type: 'custom',
          ...inputs,
          name,
          requestParameter,
          formValue,
          requestValue,
          apiType: 'custom',
        };
      } else {
        publicList.push({
          first: name,
          second: inputs.apiUrl,
          third: (
            <ModifyButton
              handleModifyButton={() =>
                handleModifyCustomApiButton(
                  name,
                  inputs.apiUrl,
                  inputs.apiKey,
                  inputs.provider,
                  inputs.pageUrl,
                  requestValue,
                  formValue,
                  requestParameter,
                  setCollectMethodList,
                  dispatch,
                )
              }
            />
          ),
          fourth: (
            <button
              className={cx('trash-btn')}
              onClick={() =>
                handleDeleteCustomApiButton(
                  name,
                  inputs.apiUrl,
                  setCollectMethodList,
                )
              }
            >
              <img
                src='/src/static/images/icon/00-new-trash.svg'
                alt='trash-icon'
              />
            </button>
          ),
          info: {
            type: 'custom',
            ...inputs,
            name,
            requestParameter,
            formValue,
            requestValue,
            apiType: 'custom',
          },
        });
      }
      return {
        ...prev,
        public_api: publicList,
      };
    });
    dispatch(closeModal(type));
  };

  useEffect(() => {
    handleName(editName);
  }, [editName, handleName]);

  return (
    <NewStyleModalFrame
      title={editName ? 'Custom API 수정' : 'Custom API 추가'}
      type={type}
      submit={{
        text: t('add.label'),
        func: () => handleSubmit(),
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={!footerMessage}
      footerMessage={footerMessage}
      customStyle={{ width: '568px', height: '866px' }}
    >
      <NameInput
        value={name}
        labelText={labelText}
        placeholder={placeholder}
        isError={isError}
        handleName={handleName}
      />
      <InputBoxWithLabel
        labelText={'API URL'}
        labelSize='large'
        disableErrorMsg
      >
        <InputText
          name='apiUrl'
          placeholder={'API URL을 입력하세요'}
          value={inputs.apiUrl}
          onChange={handleInputs}
          customStyle={{ fontSize: '14px', marginBottom: '32px' }}
          disableLeftIcon
          disableClearBtn
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel labelText='API Key' labelSize='large' disableErrorMsg>
        <InputText
          name='apiKey'
          placeholder={'API Key를 입력하세요'}
          value={inputs.apiKey}
          onChange={handleInputs}
          customStyle={{ fontSize: '14px', marginBottom: '32px' }}
          disableLeftIcon
          disableClearBtn
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel labelText='제공기관' labelSize='large' disableErrorMsg>
        <InputText
          placeholder={'제공기관을 입력하세요'}
          name='provider'
          value={inputs.provider}
          onChange={handleInputs}
          customStyle={{ fontSize: '14px', marginBottom: '32px' }}
          disableLeftIcon
          disableClearBtn
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel
        labelText='상세 설명 페이지 URL'
        labelSize='large'
        disableErrorMsg
      >
        <InputText
          placeholder={'상세 설명 페이지 URL을 입력하세요'}
          name='pageUrl'
          value={inputs.pageUrl}
          onChange={handleInputs}
          // status={isError ? 'error' : 'default'}
          customStyle={{ fontSize: '14px', marginBottom: '32px' }}
          disableLeftIcon
          disableClearBtn
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel
        labelText='요청 방식'
        labelSize='large'
        disableErrorMsg
      >
        <Radio
          name='request'
          value={requestValue}
          options={requestOptions}
          onChange={handleRequestOption}
          customStyle={{ fontSize: '14px', marginBottom: '32px' }}
          isLabelColor
        />
      </InputBoxWithLabel>
      {requestValue === 1 && (
        <InputBoxWithLabel
          labelText='요청 데이터 형식'
          labelSize='large'
          disableErrorMsg
        >
          <Radio
            name='request-form'
            value={formValue}
            options={requestFormOptions}
            onChange={handleFormOption}
            customStyle={{ fontSize: '14px', marginBottom: '32px' }}
            isLabelColor
          />
        </InputBoxWithLabel>
      )}
      <InputBoxWithLabel
        labelText={'요청변수'}
        labelSize='large'
        disableErrorMsg
      >
        <div className={cx('table')}>
          <div className={cx('thead')}>
            <span>요청변수 항목명</span>
            <span>요청변수 값</span>
            <span>삭제</span>
          </div>
          <ul className={cx('list')}>
            {requestParameter.map((info, idx) => {
              const { key, value } = info;
              const status = duplicateIndexList.includes(idx) && 'error';

              return (
                <li className={cx('item')} key={idx}>
                  <InputText
                    value={key}
                    onChange={(e) => handleOnChangeParameter(e, 'key', idx)}
                    size='small'
                    status={status}
                  />
                  <InputText
                    value={value}
                    onChange={(e) => handleOnChangeParameter(e, 'value', idx)}
                    size='small'
                    status={status}
                  />
                  <button
                    className={cx('trash-btn')}
                    onClick={() => handleDeleteParameterBtn(idx)}
                  >
                    <img src='/src/static/images/icon/delete-gray.svg' alt='' />
                  </button>
                </li>
              );
            })}
          </ul>
          <div className={cx('btn-cont')}>
            <ButtonV2
              label='요청 변수 추가'
              type='clear'
              icon='/src/static/images/icon/plus-blue.svg'
              onClick={handleAddParameterBtn}
            />
          </div>
        </div>
      </InputBoxWithLabel>
    </NewStyleModalFrame>
  );
}
