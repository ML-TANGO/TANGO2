import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';

import { openModal } from '@src/store/modules/modal';

import { calIsDeployLoading } from '../../PlaygroundHeader';

import {
  calEqualValue,
  calIsCompleteRunning,
  calIsDeployBtn,
  getDetailPlaygroundInfo,
} from '../util';

const useDeployBtn = () => {
  const dispatch = useDispatch();

  const match = useRouteMatch();
  const { params } = match;
  const playgroundId = params.did;

  const { status } = useSelector((state) => state.llmPlayground, shallowEqual);
  const { status: statusType, init_deployment } = status;
  const { info, model, rag, prompt } = useSelector(
    (state) => state.llmPlayground,
    shallowEqual,
  );

  const originValue = useSelector(
    (state) => state.llmPlaygroundResetValue,
    shallowEqual,
  );

  const isEqual = calEqualValue(info, model, rag, prompt, originValue);

  const isDeployLoading = calIsDeployLoading(statusType);
  const isDeployBtn = calIsDeployBtn(model, rag, prompt, isEqual, statusType);
  const isCompleteRunning = calIsCompleteRunning(status);

  // ** [액션] 배포 버튼 핸들러 **
  const handleDeploy = () => {
    if (['installing'].includes(statusType)) return;
    dispatch(
      openModal({
        modalType: 'PLAYGROUND_DEPLOY',
        modalData: {
          playgroundId,
          getDetailPlaygroundInfo,
          isDeployState: {
            embedding_huggingface_model_id: rag.embedding_huggingface_model_id,
            reranker_huggingface_model_id: rag.reranker_huggingface_model_id,
            init_deployment,
          },
        },
      }),
    );
  };

  return {
    init_deployment,
    isDeployLoading,
    isDeployBtn,
    isCompleteRunning,
    handleDeploy,
  };
};

export default useDeployBtn;
