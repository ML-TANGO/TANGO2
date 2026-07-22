import { useState } from 'react';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { getDeploymentApi } from '@src/apis/flightbase/deployment';
import { postPlaygroundsStop } from '@src/apis/llm/playground';
import { handleOpenPopup } from '@src/store/modules/popupState';
import { STATUS_SUCCESS } from '@src/network';

import { calIsCompleteRunning, calIsStopBtn } from '../util';

export default function useStopbtn() {
  const dispatch = useDispatch();
  const { status, info } = useSelector((state) => state.llmPlayground, shallowEqual);
  const { status: statusType } = status;
  const deploymentId = info?.deployment_id ?? null;

  const match = useRouteMatch();
  const { did: playgroundId } = match.params;

  const isCompleteRunning = calIsCompleteRunning(status);
  const isStopBtn = calIsStopBtn(statusType);

  // ** [액션] 정지 버튼 핸들러 **
  const [isStopLoading, setStopLoading] = useState(false);
  const handleStop = async (t) => {
    // 게시 상태 확인 — 게시 중이면 "중지 시 외부 API 도 함께 종료" 경고를 안내(중지 자체는 진행).
    //   BE stop 이 게시를 자동 teardown 하므로 잔존 엔드포인트 없음. 게시상태는 redux 미보관 → 클릭 시점 실시간 조회.
    //   조회 실패 시 경고 없이 기본 중지 확인으로 진행(fail-open).
    let publishedWarn = false;
    if (deploymentId) {
      try {
        const pub = await getDeploymentApi(deploymentId);
        publishedWarn = pub.status === STATUS_SUCCESS && !!pub.result?.enabled;
      } catch {
        // 게시상태 조회 실패 → 경고 없이 기본 중지 플로우
      }
    }
    dispatch(
      handleOpenPopup({
        type: 'delete',
        popupTitle: isCompleteRunning
          ? t('playground.stopBtn.disabled')
          : t('playground.stopBtn.deploystop'),
        popupContents: publishedWarn
          ? '이 배포를 중지하면 게시된 외부 API 도 함께 종료됩니다. 계속하시겠습니까?'
          : isCompleteRunning
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
