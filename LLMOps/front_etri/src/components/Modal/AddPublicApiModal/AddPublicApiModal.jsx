import React, { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { ButtonV2, InputText } from '@tango/ui-react';

import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { closeModal, openModal } from '@src/store/modules/modal';
import useInputs from '@src/hooks/useInputs';

import { DeleteButton, ModifyButton } from '../AddWebcrowler/AddWebcrowler';
import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from './AddPublicApiModal.module.scss';

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

// ** 수정 버튼 핸들러 **
export const handleModifyPublicApiButton = (
  requestParameter,
  id,
  inputs,
  requestValue,
  setCollectMethodList,
  setSelectedApiList,
  dispatch,
) => {
  const transformParameter = requestParameter.slice().reduce((acc, cur) => {
    acc[cur.key] = cur.value;
    return acc;
  }, {});

  const itemInfo = {
    id,
    name: inputs.name,
    url: inputs.apiUrl,
    providing_organization: inputs.provider,
    detail_url: inputs.pageUrl,
    method: requestValue,
    jsonData: transformParameter,
  };
  dispatch(
    openModal({
      modalType: 'ADD_PUBLIC_API_MODAL',
      modalData: {
        submit: () => {},
        setCollectMethodList,
        setSelectedApiList,
        itemInfo,
        isEdit: true,
      },
    }),
  );
};

// ** 삭제 버튼 핸들러 **
export const handleDeletePublicApiButton = (
  inputs,
  setCollectMethodList,
  setSelectedApiList,
) => {
  setCollectMethodList((prev) => {
    const shallowList = prev['public_api'].slice();
    const findIndex = shallowList.findIndex(
      ({ first, second }) => first === inputs.name && second === inputs.apiUrl,
    );
    shallowList.splice(findIndex, 1);
    return {
      ...prev,
      public_api: shallowList,
    };
  });
  setSelectedApiList((prev) => {
    const shallowList = prev.slice();
    const findIndex = shallowList.findIndex(
      ({ name, url }) => name === inputs.name && url === inputs.apiUrl,
    );
    shallowList.splice(findIndex, 1);
    return shallowList;
  });
};

export default function AddPublicApiModal({ data, type }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const { submit, setCollectMethodList, setSelectedApiList, itemInfo } = data;

  const {
    id,
    name: editName,
    url,
    providing_organization,
    detail_url,
    method,
    jsonData,
  } = itemInfo;

  // ** [API 이름] **
  const labelText = 'API 이름';
  const placeholder = 'API 이름을 입력하세요';

  // ** [URL, Key, 제공기관, 상세 설명 페이지 URL, 요청 방식] **
  const { inputs, handleInputs } = useInputs({
    name: editName,
    apiUrl: url,
    provider: providing_organization,
    pageUrl: detail_url,
  });
  const { apiUrl, provider, pageUrl } = inputs;

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
  const [requestValue, setRequestValue] = useState(method === 'GET' ? 0 : 1);
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
  const [formValue, setFormValue] = useState(0);
  const handleFormOption = useCallback((e) => {
    setFormValue(+e.target.value);
  }, []);

  const transformParameter = Object.keys(jsonData).reduce((acc, key) => {
    acc.push({ key, value: jsonData[key] });
    return acc;
  }, []);

  // ** [요청 변수] **
  const map = new Map();
  const [requestParameter, setRequestParameter] = useState(transformParameter);
  const duplicateIndexList = calDuplicateIndex(requestParameter, map);

  const calFooterMessage = (inputs, duplicateIndexList) => {
    if (!inputs.name) return 'API 이름을 입력해 주세요';
    if (duplicateIndexList.length) return '중복된 요청 변수가 있습니다.';
    return '';
  };
  const footerMessage = calFooterMessage(inputs, duplicateIndexList);

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

  return (
    <NewStyleModalFrame
      title={data.isEdit ? '공개 API 데이터 수정' : '공개 API 데이터 추가'}
      type={type}
      submit={{
        text: data.isEdit ? t('update.label') : t('add.label'),
        func: !data.isEdit
          ? () => {
              setCollectMethodList((prev) => {
                const publicApiList = prev.public_api.slice();
                publicApiList.push({
                  id,
                  first: inputs.name,
                  second: apiUrl,
                  third: (
                    <ModifyButton
                      handleModifyButton={() =>
                        handleModifyPublicApiButton(
                          requestParameter,
                          id,
                          inputs,
                          requestValue,
                          setCollectMethodList,
                          setSelectedApiList,
                          dispatch,
                        )
                      }
                    />
                  ),
                  fourth: (
                    <DeleteButton
                      handleDeleteButton={() =>
                        handleDeletePublicApiButton(
                          inputs,
                          setCollectMethodList,
                          setSelectedApiList,
                        )
                      }
                    />
                  ),
                  info: {
                    name: inputs.name,
                    apiUrl,
                    provider,
                    pageUrl,
                    requestParameter,
                    apiType: 'public',
                  },
                });
                return {
                  ...prev,
                  public_api: publicApiList,
                };
              });
              submit();
            }
          : () => {
              // ** Edit
              setCollectMethodList((prev) => {
                const publicApiList = prev.public_api.slice();
                const isValueIndex = publicApiList.findIndex(
                  (info) => info.id === itemInfo.id,
                );
                const newItem = {
                  id,
                  first: inputs.name,
                  second: apiUrl,
                  third: (
                    <ModifyButton
                      handleModifyButton={() =>
                        handleModifyPublicApiButton(
                          requestParameter,
                          id,
                          inputs,
                          requestValue,
                          setCollectMethodList,
                          setSelectedApiList,
                          dispatch,
                        )
                      }
                    />
                  ),
                  fourth: (
                    <DeleteButton
                      handleDeleteButton={() =>
                        handleDeletePublicApiButton(
                          inputs,
                          setCollectMethodList,
                          setSelectedApiList,
                        )
                      }
                    />
                  ),
                  info: {
                    name: inputs.name,
                    apiUrl,
                    provider,
                    pageUrl,
                    requestParameter,
                    apiType: 'public',
                  },
                };
                publicApiList.splice(isValueIndex, 1, newItem);
                return {
                  ...prev,
                  public_api: publicApiList,
                };
              });
              dispatch(closeModal(type));
            },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={!footerMessage}
      footerMessage={footerMessage}
      customStyle={{ width: '568px', height: '890px' }}
    >
      <InputBoxWithLabel
        labelText={labelText}
        labelSize='large'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <InputText
          name='name'
          placeholder={placeholder}
          value={inputs.name}
          onChange={handleInputs}
          status={!inputs.name ? 'error' : 'default'}
          options={{ maxLength: 50 }}
          autoFocus={true}
          customStyle={{ fontSize: '14px' }}
          disableLeftIcon
          disableClearBtn
        />
      </InputBoxWithLabel>
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
          options={{ maxLength: 50 }}
          autoFocus={true}
          customStyle={{ fontSize: '14px', marginBottom: '32px' }}
          disableLeftIcon
          disableClearBtn
          isReadOnly={true}
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel labelText='제공기관' labelSize='large' disableErrorMsg>
        <InputText
          placeholder={'제공기관을 입력하세요'}
          name='provider'
          value={inputs.provider}
          onChange={handleInputs}
          options={{ maxLength: 50 }}
          customStyle={{ fontSize: '14px', marginBottom: '32px' }}
          disableLeftIcon
          disableClearBtn
          isReadOnly={true}
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
          options={{ maxLength: 50 }}
          customStyle={{ fontSize: '14px', marginBottom: '32px' }}
          disableLeftIcon
          disableClearBtn
          isReadOnly={true}
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
