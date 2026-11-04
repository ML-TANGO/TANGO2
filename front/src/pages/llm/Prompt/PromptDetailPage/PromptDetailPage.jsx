import { getPromptItemInfo } from '@src/apis/llm/prompt';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import PromptContent from '@src/components/pageContents/llm/PromptContent/PromptContent';
import { calDiffProjectTemplate } from '@src/components/pageContents/llm/PromptContent/PromptContent/PromptInfo/PromptInfo';
import PromptHeader from '@src/components/pageContents/llm/PromptContent/PromptHeader';
import PromptTab from '@src/components/pageContents/llm/PromptContent/PromptTab';

import {
  handlePromptReset,
  handleSetPromptState,
} from '@src/store/modules/llmprompt';
import { handleOpenPopup } from '@src/store/modules/popupState';

import { STATUS_SUCCESS } from '@src/network';

// CSS Module
import classNames from 'classnames/bind';
import style from './PromptDetailPage.module.scss';

const cx = classNames.bind(style);

export const getPromptDataInfo = async (promptId, dispatch) => {
  const { result, message, status } = await getPromptItemInfo(promptId);
  if (status === STATUS_SUCCESS) {
    dispatch(
      handleSetPromptState({
        type: 'all',
        info: {
          ...result,
          system_message: result.system_message ?? '',
          user_message: result.user_message ?? '',
        },
        originInfo: {
          ...result,
          system_message: result.system_message ?? '',
          user_message: result.user_message ?? '',
        },
      }),
    );
  } else {
    toast.error(message);
  }
};

export default function PromptDetail() {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();

  const match = useRouteMatch();
  const { id: workspaceId, did: promptId } = match.params;

  const { info } = useSelector((state) => state.llmprompt, shallowEqual);
  const {
    system_message: server_system_message,
    user_message: server_user_message,
  } = useSelector((state) => state.llmprompt.originInfo, shallowEqual);
  const { system_message, user_message } = info;

  const tabList = useMemo(() => {
    return [
      {
        label: t('information.label'),
        value: 0,
      },
      {
        label: t('commitList.label'),
        value: 1,
      },
    ];
  }, [t]);

  // ** [데이터] 프로젝트 템플릿 변경 사항 **
  const isDiff = calDiffProjectTemplate(
    system_message,
    user_message,
    server_system_message,
    server_user_message,
  );

  const [selectedTab, setSelectedTab] = useState(
    history.action === 'POP' ? 1 : 0,
  );

  const handleTab = useCallback(
    (value) => {
      // ** 탭으로 이동 시 **
      if (isDiff && value === 1) {
        dispatch(
          handleOpenPopup({
            type: 'delete',
            popupTitle: t('prompt.popup.title'),
            popupContents: t('prompt.popup.message'),
            cancelBtnLabel: t('cancel.label'),
            submitBtnLabel: t('end.label'),
            handleSubmit: () => {
              setSelectedTab(1);
            },
          }),
        );
        return;
      }
      setSelectedTab(value);
    },
    [dispatch, isDiff, t],
  );

  useEffect(() => {
    getPromptDataInfo(promptId, dispatch);

    return () => {
      dispatch(handlePromptReset());
    };
  }, [dispatch, promptId, workspaceId]);

  return (
    <div className={cx('prompt-detail-cont')}>
      <PromptHeader selectedTab={selectedTab} />
      <PromptTab
        tabList={tabList}
        selectedTab={selectedTab}
        handleTab={handleTab}
      />
      <PromptContent selectedTab={selectedTab} />
    </div>
  );
}
