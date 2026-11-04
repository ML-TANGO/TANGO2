import { getRagSetting } from '@src/apis/llm/rag';
import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { calDiffProjectTemplate } from '@src/components/pageContents/llm/PromptContent/PromptContent/PromptInfo/PromptInfo';
import RagContent from '@src/components/pageContents/llm/RagContent/RagContent';
import RagHeader from '@src/components/pageContents/llm/RagContent/RagHeader';
import RagTab from '@src/components/pageContents/llm/RagContent/RagTab';

import { handleRagReset, handleSetRagState } from '@src/store/modules/llmRag';
import { handleOpenPopup } from '@src/store/modules/popupState';

import { STATUS_SUCCESS } from '@src/network';

// CSS Module
import classNames from 'classnames/bind';
import style from './RagDetailPage.module.scss';

const cx = classNames.bind(style);

const tabList = [
  {
    label: '설정',
    value: 0,
  },
  {
    label: '검색',
    value: 1,
  },
  {
    label: '문서',
    value: 2,
  },
];

export const getRagDataInfo = async (ragId, dispatch) => {
  const { result, message, status } = await getRagSetting(ragId);
  if (status === STATUS_SUCCESS) {
    const { info, instance, setting } = result;

    dispatch(
      handleSetRagState({
        type: 'all',
        info: {
          ...info,
        },
        setting: {
          ...setting,
        },
        instance: {
          ...instance,
        },
        rerankerSwitch: setting?.reranker_model ? true : false,
      }),
    );
  } else {
    toast.error(message);
  }
};

export default function RagDetailPage() {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();

  const match = useRouteMatch();
  const { id: workspaceId, rid: ragId } = match.params;

  const { info, setting, rerankerSwitch } = useSelector(
    (state) => state.llmRag,
    shallowEqual,
  );

  // const isDiff = calDiffProjectTemplate(
  //   system_message,
  //   user_message,
  //   server_system_message,
  //   server_user_message,
  // );

  // const [selectedTab, setSelectedTab] = useState(
  //   history.action === 'POP' ? 1 : 0,
  // );

  const [selectedTab, setSelectedTab] = useState(0);
  const handleTab = useCallback(
    (value) => {
      // ** 탭으로 이동 시 **
      // if (value !== 0) {
      //   dispatch(
      //     handleOpenPopup({
      //       type: 'delete',
      //       popupTitle: '프롬프트 입력 종료',
      //       popupContents:
      //         '프롬프트 입력을 종료하시겠습니까?\n커밋하지 않은 내용은 복구할 수 없습니다.',
      //       cancelBtnLabel: t('cancel.label'),
      //       submitBtnLabel: t('end.label'),
      //       handleSubmit: () => {
      //         setSelectedTab(value);
      //       },
      //     }),
      //   );
      //   return;
      // }
      setSelectedTab(value);
    },
    [dispatch, t],
  );

  useEffect(() => {
    getRagDataInfo(ragId, dispatch);

    return () => {
      dispatch(handleRagReset());
    };
  }, [dispatch, ragId, workspaceId]);

  return (
    <div className={cx('rag-detail-cont')}>
      <RagHeader selectedTab={selectedTab} />
      <RagTab
        tabList={tabList}
        selectedTab={selectedTab}
        handleTab={handleTab}
      />
      <RagContent selectedTab={selectedTab} />
    </div>
  );
}
