import { useEffect, useRef, useState } from 'react';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';

import PlaygroundHeader from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundHeader';
import PlaygroundInfo from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundInfo';
import PlaygroundExternalApi from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundExternalApi';
import PlaygroundInstanceSettingInfo from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundInstanceSettingInfo';
import PlaygroundModel from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundModel';
import PlaygroundModelParameterSetting from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundModelParameterSetting';
import PlaygroundMonitoring from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundMonitoring';
import DeployDetailShell from '@src/components/pageContents/llm/DeployDetail/DeployDetailShell';

// [엑셀러레이터 미사용] getPlaygroundCheckAccel 제거 (apis 정의는 유지)
import {
  getDetailPlayground,
  getNormalizedPlaygroundDetail,
} from '@src/apis/llm/playground';
import {
  handleReset,
  handleSetPlaygroundState,
  initialLLMPlaygroundState,
} from '@src/store/modules/llmPlayground';
import {
  handleOriginReset,
  handleOriginValue,
} from '@src/store/modules/llmPlaygroundResetValue';
import { STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './PlaygroundDetail.module.scss';

const cx = classNames.bind(style);

// ** [GET] 플레이그라운드 데이터 **
const getDetailPlaygroundInfo = async (
  dispatch,
  playgroundId,
  prefetchedResult = null,
) => {
  const { result, message, status, error } = prefetchedResult
    ? {
        result: prefetchedResult,
        message: '',
        status: STATUS_SUCCESS,
        error: null,
      }
    : await getDetailPlayground(playgroundId);
  // [엑셀러레이터 미사용] /check-accel 호출 제거 (하드코딩 IP 115.71.36.50 로
  //   나가던 요청). 실패 시 catch 가 주던 값과 동일하게 고정 → 아래
  //   accellator=false / isAccellator=false 로 기존 동작과 같음.
  // const { data } = await getPlaygroundCheckAccel();
  const data = { result: 'error' };

  if (status === STATUS_SUCCESS) {
    const payload = {
      type: 'all',
      info: result.info
        ? {
            id: result.info.id,
            create_datetime: result.info.create_datetime,
            description: result.info.description ?? '-',
            name: result.info.name,
            owner: result.info.owner,
            update_datetime: result.info.update_datetime,
            access: result.info.access,
            users: result.info.users ?? [],
            deployment_id: result.info.deployment_id ?? null,
          }
        : initialLLMPlaygroundState.info,
      accellator: data.result === 'running' ? true : false,
      isAccellator: data.result !== 'error' ? true : false,
      info_instance: {
        model: result.info_instance?.model
          ? result.info_instance.model
          : initialLLMPlaygroundState.info_instance.model,
        embedding: result.info_instance?.embedding
          ? result.info_instance?.embedding
          : initialLLMPlaygroundState.info_instance.embedding,
        reranker: result.info_instance?.reranker
          ? result.info_instance.reranker
          : initialLLMPlaygroundState.info_instance.reranker,
        immediately_status: result.info_instance?.immediately_status
          ? result.info_instance.immediately_status
          : initialLLMPlaygroundState.info.immediately_status,
      },
      info_request: result.info_request.method
        ? result.info_request
        : initialLLMPlaygroundState.info_request,
      model: result.model
        ? {
            model_type: result.model.model_type,
            serving_system: result.model.serving_system ?? 'vllm',
            model_huggingface_id: result.model.model_hf_id,
            model_allm_id: result.model.model_allm_id,
            model_allm_name: result.model.model_allm_name,
            model_allm_commit_id: result.model.model_allm_commit_id,
            model_allm_commit_name: result.model.model_allm_commit_name,
            training_type: result.model.training_type ?? '',
            model_temperature: result.model_parameter.temperature,
            model_top_p: result.model_parameter.top_p,
            model_top_k: result.model_parameter.top_k,
            model_repetition_penalty: result.model_parameter.repetition_penalty,
            model_max_new_tokens: result.model_parameter.max_new_tokens,
            description: result.model.description ?? '-',
            commit: result.model.commit ?? '-',
            access: result.model.access ?? '-',
            create_datetime:
              result.model.create_datetime ?? '0000-00-00 00:00:00',
            update_datetime: result.model.update_datetime,
          }
        : initialLLMPlaygroundState.model,
      rag: result.rag
        ? {
            is_rag: !!result.rag.id,
            rag_id: result.rag.id,
            rag_name: result.rag.name ?? '',
            chunk_len: result.rag.chunk_len,
            chunk_max: result.rag.chunk_max,
            docs_total_count: result.rag.docs_total_count,
            docs_total_size: result.rag.docs_total_size,
            rag_doc_list: result.rag.rag_doc_list,
            embedding_huggingface_model_id:
              result.rag.embedding_huggingface_model_id,
            reranker_huggingface_model_id:
              result.rag.reranker_huggingface_model_id,
          }
        : initialLLMPlaygroundState.rag,
      prompt: result.prompt
        ? {
            is_prompt: !!result.prompt.name,
            prompt_id: result.prompt.id,
            prompt_name: result.prompt.name,
            prompt_commit_name: result.prompt.commit_name,
            prompt_system_message: result.prompt.system_message,
            prompt_user_message: result.prompt.user_message,
          }
        : initialLLMPlaygroundState.prompt,
    };

    dispatch(handleSetPlaygroundState(payload));
    dispatch(handleOriginValue(payload));
  } else {
    errorToastMessage(error, message);
  }
};

const PlaygroundDetail = () => {
  const dispatch = useDispatch();
  const match = useRouteMatch();

  const { params } = match;
  const playgroundId = params.did;
  const workspaceId = params.id;

  const { name } = useSelector(
    (state) => state.llmPlayground.info,
    shallowEqual,
  );
  const { init_deployment } = useSelector(
    (state) => state.llmPlayground.status,
    shallowEqual,
  );

  const [deployment, setDeployment] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [detailLoading, setDetailLoading] = useState(true);

  // Redux 데이터 계약은 그대로 두고, 공용 shell의 식별/오류 상태만 id 기반 정규화 모델로 공급한다.
  useEffect(() => {
    let cancelled = false;
    setDetailLoading(true);
    setDetailError('');
    getNormalizedPlaygroundDetail(playgroundId, workspaceId)
      .then((normalized) => {
        if (cancelled) return;
        if (normalized.mode !== 'single') {
          throw new Error('이 경로는 단일모델 배포 상세 전용입니다.');
        }
        getDetailPlaygroundInfo(
          dispatch,
          +playgroundId,
          normalized.rawDetail,
        );
        setDeployment(normalized);
        setDetailError('');
      })
      .catch((error) => {
        if (!cancelled) setDetailError(error.message);
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dispatch, playgroundId, workspaceId]);

  // ! [사이드 이펙트] 초기 데이터 렌더 **
  const eventSourceRef = useRef(null);
  useEffect(() => {
    loadModalComponent('IMPORT_MODEL_PLAYGROUND');
    loadModalComponent('IMPORT_COMMIT_MODAL');
    loadModalComponent('IMPORT_RAG');
    loadModalComponent('IMPORT_PROMPT');
    loadModalComponent('PLAYGROUND_DEPLOY');

    return () => {
      dispatch(handleReset());
      dispatch(handleOriginReset());
    };
  }, [dispatch, playgroundId]);

  const sections = {
    INFO: (
      <div className={cx('content-cont')}>
        <PlaygroundInfo />
      </div>
    ),
    MODEL: (
      <div className={cx('model-cont')}>
        <PlaygroundModel workspaceId={workspaceId} />
        <PlaygroundModelParameterSetting />
        <div className={cx('stacked-col')}>
          <PlaygroundInstanceSettingInfo />
          <PlaygroundExternalApi />
        </div>
        {/* <PlaygroundRag workspaceId={workspaceId} playgroundId={playgroundId} /> */}
        {/* <PlaygroundPrompt workspaceId={workspaceId} /> */}
      </div>
    ),
    MONITOR: <PlaygroundMonitoring />,
  };

  return (
    <div className={cx('playground-cont')}>
      <DeployDetailShell
        deployment={deployment}
        loading={detailLoading}
        error={detailError}
        monitorDisabled={!init_deployment}
        header={
          detailLoading || detailError ? null : (
            <PlaygroundHeader
              title={name}
              getDetailPlaygroundInfo={getDetailPlaygroundInfo}
              eventSourceRef={eventSourceRef}
              skipFirstDetailRefresh
            />
          )
        }
        sections={sections}
      />
    </div>
  );
};

export default PlaygroundDetail;
