import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { Prompt, useHistory } from 'react-router-dom';

import { handleOpenPopup } from '@src/store/modules/popupState';

import { calEqualValue } from '../PlaygroundButtonCont/util';

export default function OutsideWarn() {
  const dispatch = useDispatch();
  const { t } = useTranslation();
  const history = useHistory();

  const { info, model, rag, prompt } = useSelector(
    (state) => state.llmPlayground,
    shallowEqual,
  );
  const originValue = useSelector(
    (state) => state.llmPlaygroundResetValue,
    shallowEqual,
  );

  let historyGo;
  const [isHistoryAllow, setIsHistoryAllow] = useState(false);
  const isEqual = calEqualValue(info, model, rag, prompt, originValue);

  const handleLeavePopup = (location) => {
    dispatch(
      handleOpenPopup({
        type: 'delete',
        popupTitle: t('playground.leavepopup.title'),
        popupContents: t('playground.leavepopup.content'),
        cancelBtnLabel: t('cancel.label'),
        submitBtnLabel: t('end.label'),
        handleCancel: () => {
          setIsHistoryAllow(false);
        },
        handleSubmit: () => {
          setIsHistoryAllow(true);
          historyGo = setTimeout(() => {
            history.push(location.pathname);
          }, 0);
        },
      }),
    );
  };

  // ** [액션] Prompt when 조건일 때 history 방지 **
  const handlePromptMessage = (location, handleLeavePopup) => {
    if (location.state) return true;
    handleLeavePopup(location);
    return false; // 이동 차단
  };

  // ** [액션] Prompt when 조건일 때 history 방지 **
  useEffect(() => {
    return () => {
      if (historyGo) {
        clearTimeout(historyGo);
      }
    };
  }, [historyGo]);

  return (
    <Prompt
      when={false}
      message={(location) => handlePromptMessage(location, handleLeavePopup)}
    />
  );
}
