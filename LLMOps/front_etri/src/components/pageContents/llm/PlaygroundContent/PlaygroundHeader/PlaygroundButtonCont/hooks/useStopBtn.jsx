import { useState } from 'react';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { postPlaygroundsStop } from '@src/apis/llm/playground';
import { handleOpenPopup } from '@src/store/modules/popupState';
import { STATUS_SUCCESS } from '@src/network';

import { calIsCompleteRunning, calIsStopBtn } from '../util';

export default function useStopbtn() {
  const dispatch = useDispatch();
  const { status } = useSelector((state) => state.llmPlayground, shallowEqual);
  const { status: statusType } = status;

  const match = useRouteMatch();
  const { did: playgroundId } = match.params;

  const isCompleteRunning = calIsCompleteRunning(status);
  const isStopBtn = calIsStopBtn(statusType);

  // ** [액션] 정지 버튼 핸들러 **
  const [isStopLoading, setStopLoading] = useState(false);
  const handleStop = async (t) => {
    dispatch(
      handleOpenPopup({
        type: 'delete',
        popupTitle: isCompleteRunning
          ? t('playground.stopBtn.disabled')
          : t('playground.stopBtn.deploystop'),
        popupContents: isCompleteRunning
          ? t('playground.stopBtn.deploystop.message1')
          : t('playground.stopBtn.deploystop.message2'),
        cancelBtnLabel: t('cancel.label'),
        submitBtnLabel: t('end.label'),
        handleSubmit: async () => {
          if (isStopLoading) return;
          setStopLoading(true);
          const { status, message } = await postPlaygroundsStop(playgroundId);
          if (status !== STATUS_SUCCESS) {
            toast.error(message);
          }
          setStopLoading(false);
        },
      }),
    );
  };

  return { isStopBtn, isStopLoading, handleStop };
}
