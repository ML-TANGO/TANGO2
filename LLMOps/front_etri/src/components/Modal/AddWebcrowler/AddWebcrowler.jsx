import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputText } from '@tango/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { closeModal, openModal } from '@src/store/modules/modal';

import NameInput from '../DataCollectModal/NameInput/NameInput';
import useNameInput from '../DataCollectModal/NameInput/useNameInput';
import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from './AddWebcrowler.module.scss';

const cx = classNames.bind(style);

const calFooterMessage = (name, isValidateName, url, t) => {
  if (!name) return '웹 크롤러 이름을 입력해 주세요';
  if (name === '') return '웹 크롤러 이름을 입력해 주세요';
  if (!isValidateName) return t('newNameRule.message');
  if (!url) return '웹 크롤러 URL을 입력해 주세요';
  return '';
};

const calIsErrorUrl = (url, isValidateUrl) => {
  if (url === undefined) return false;
  return !isValidateUrl;
};

const calIsValidateUrl = (url) => {
  if (!url) return false;
  if (url.length === 0) return false;
  return true;
};

const calIsValidateSubmitBtn = (isValidateName, isValidateUrl) => {
  if (!isValidateName || !isValidateUrl) return false;
  return true;
};

export const ModifyButton = ({ handleModifyButton }) => {
  return (
    <button className={cx('edit-btn')} onClick={() => handleModifyButton()}>
      <img src='/images/icon/new-gray-pen.svg' alt='edit-icon' />
    </button>
  );
};

export const DeleteButton = ({ handleDeleteButton }) => {
  return (
    <button className={cx('trash-btn')} onClick={handleDeleteButton}>
      <img src='/src/static/images/icon/00-new-trash.svg' alt='trash-icon' />
    </button>
  );
};

// ** 삭제 버튼 핸들러 **
export const handleCrawlerDeleteButton = (url, name, setCollectMethodList) => {
  setCollectMethodList((prev) => {
    const shallowList = prev['crawling'].slice();
    const findIndex = shallowList.findIndex(
      ({ first, second }) => first === name && second === url,
    );
    shallowList.splice(findIndex, 1);
    return {
      ...prev,
      crawling: shallowList,
    };
  });
};

export default function AddWebcrowler({ data, type }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const { collectMethodList, setCollectMethodList, editName, editUrl } = data;

  // ** [수집 이름] **
  const labelText = '웹 크롤러 이름';
  const placeholder = '웹 크롤러 이름을 입력하세요';
  const {
    name,
    isValidateName,
    isError: isNameError,
    handleName,
  } = useNameInput();

  // ** [웹크롤러] **
  const [url, setUrl] = useState(undefined);
  const isValidateUrl = calIsValidateUrl(url);
  const isErrorUrl = calIsErrorUrl(url, isValidateUrl);

  const footerMessage = calFooterMessage(name, isValidateName, url, t);
  const isValidateSubmitBtn = calIsValidateSubmitBtn(
    isValidateName,
    isValidateUrl,
  );

  // ** URL 핸들러 **
  const handleUrl = useCallback((e) => {
    setUrl(e.target.value);
  }, []);

  // ** 수정 버튼 핸들러 **
  const handleModifyButton = () => {
    dispatch(
      openModal({
        modalType: 'ADD_WEB_CROWLER_MODAL',
        modalData: {
          editName: name,
          editUrl: url,
          setCollectMethodList,
        },
      }),
    );
  };

  const submit = {
    text: editName ? t('update.label') : t('add.label'),
    func: () => {
      setCollectMethodList((prev) => {
        const shallowList = prev['crawling'].slice();

        if (!editName) {
          shallowList.push({
            first: name,
            second: url,
            third: <ModifyButton handleModifyButton={handleModifyButton} />,
            fourth: (
              <DeleteButton
                handleDeleteButton={() =>
                  handleCrawlerDeleteButton(url, name, setCollectMethodList)
                }
              />
            ),
          });
        } else {
          const findValueIdx = shallowList.findIndex(
            ({ first, second }) => first === editName && second === editUrl,
          );
          shallowList[findValueIdx].first = name;
          shallowList[findValueIdx].name = name;
          shallowList[findValueIdx].second = url;
          shallowList[findValueIdx].url = url;
          shallowList[findValueIdx].third = (
            <ModifyButton handleModifyButton={handleModifyButton} />
          );
          shallowList[findValueIdx].fourth = (
            <DeleteButton
              handleDeleteButton={() =>
                handleCrawlerDeleteButton(url, name, setCollectMethodList)
              }
            />
          );
        }

        prev['crawling'] = shallowList;
        return prev;
      });
      dispatch(closeModal(type));
    },
  };

  // ** 사이드 이펙트 수정 **
  useEffect(() => {
    if (editName && editUrl) {
      handleName(editName);
      setUrl(editUrl);
    }
  }, [editName, editUrl, handleName]);

  return (
    <NewStyleModalFrame
      title={editName ? '웹 크롤러 수정' : '웹 크롤러 추가'}
      type={type}
      submit={submit}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={isValidateSubmitBtn}
      footerMessage={footerMessage}
      customStyle={{ width: '568px' }}
    >
      <NameInput
        value={name}
        labelText={labelText}
        placeholder={placeholder}
        isError={isNameError}
        handleName={handleName}
      />
      <InputBoxWithLabel
        labelText={'웹 크롤러 URL'}
        labelSize='large'
        disableErrorMsg
      >
        <InputText
          placeholder={'웹 크롤러 URL을 입력하세요'}
          value={url}
          onChange={handleUrl}
          status={isErrorUrl ? 'error' : 'default'}
          options={{ maxLength: 50 }}
          customStyle={{ fontSize: '14px' }}
          disableLeftIcon
          disableClearBtn
        />
      </InputBoxWithLabel>
    </NewStyleModalFrame>
  );
}
