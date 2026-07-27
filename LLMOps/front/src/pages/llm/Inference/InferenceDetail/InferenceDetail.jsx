import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import TestComponent from '@src/components/Modal/PlaygroundTestModal/TestComponent';
import DualDirectInference from './DualDirectInference';
import DualBatchInference from './DualBatchInference';
import {
  getDetailPlayground,
  getPlaygroundStatusSync,
} from '@src/apis/llm/playground';
import useIntervalCall from '@src/hooks/useIntervalCall';
import { startPath } from '@src/store/modules/breadCrumb';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './InferenceDetail.module.scss';

const cx = classNames.bind(style);

// 배포 상태 라벨 — InferenceMenu 배지와 동일 어휘(running/installing/pending/stop).
const STATUS_LABEL = {
  running: { label: '실행 중', cls: 'running' },
  installing: { label: '준비 중', cls: 'installing' },
  pending: { label: '대기 중', cls: 'installing' },
  stop: { label: '정지', cls: 'stop' },
};
const statusOf = (s) =>
  STATUS_LABEL[s] ?? { label: '확인 중', cls: 'installing' };

// 추론 상세(Inference detail, D6 v3 Tier-1) — 배포 config 없는 lean consume 화면.
//   배포(provision)는 "배포" 탭. 여기선 "띄운 배포에 질의"만.
//   기존 PlaygroundTestModal 의 TestComponent(PromptCom/DatasetCom/ExternalTestCom)를
//   모달 셸 없이 인라인 재사용 — 실 백엔드(postPlaygroundTestChat) 그대로.
//   redux 미오염: TestComponent 는 prop 컴포넌트, 하위는 auth.userName 만 읽음 →
//   getDetailPlayground 로 name/training_type 만 로컬 fetch (전체 payload dispatch X).
//   실시간 질문 ↔ 데이터셋 일괄 모드 토글. 외부 모델은 ExternalTestCom 자동.
//   (이중모델 D2 + 정량 메트릭 = Tier-2, SP-7/SP-5 의존.)
const InferenceDetail = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId, did: playgroundId } = match.params;

  const [info, setInfo] = useState(null); // { name, owner }
  const [trainingType, setTrainingType] = useState('');
  const [dual, setDual] = useState(null); // 이중 세션이면 { prompt_gen_model_name, inference_model_name, ... }
  const [loading, setLoading] = useState(true);
  // 모드: 'realtime'(실시간 질문) | 'dataset'(데이터셋 일괄)
  // 기존 모달 규약 매핑 → integratedTestValue: true=DatasetCom / false=PromptCom
  const [mode, setMode] = useState('realtime');

  // 배포(파드) 상태 — status-sync 폴링(5s, 탭 비활성 시 자동 정지). running 되면 폴링 종료.
  //   세션(부모) 상태는 이중이면 부모+자식 합산값(BE get_playground_status), LLM1 은 자식 개별 조회.
  const [sessionStatus, setSessionStatus] = useState(null);
  const [childStatus, setChildStatus] = useState(null);   // LLM1(자식) 실측
  const [parentStatus, setParentStatus] = useState(null); // LLM2(부모 단독, skip_dual)
  const [firstPollDone, setFirstPollDone] = useState(false);

  const isExternal = trainingType === 'external';
  const isDual = dual?.mode === 'dual';
  const integratedTestValue = mode === 'dataset';
  // 잠금 규칙:
  //   - 이중 세션에만 적용(단일은 목록이 이미 running 만 노출 → 기존 동작 회귀 방지).
  //   - 첫 폴링이 끝나기 전엔 잠금(그 사이 클릭해 준비 안 된 파드로 질의하는 경합 차단).
  //   - 폴링이 끝난 뒤 상태 불명(null=조회 실패)이면 잠그지 않음(fail-open, 영구잠김 방지).
  const isLocked =
    isDual && (!firstPollDone || (sessionStatus != null && sessionStatus !== 'running'));
  const childPlaygroundId = dual?.prompt_gen_playground_id;

  const pollStatus = useCallback(async () => {
    if (!playgroundId) return true;
    const res = await getPlaygroundStatusSync(playgroundId);
    const st = res.status === STATUS_SUCCESS ? res.result?.status : null;
    if (st) setSessionStatus(st);
    // 이중이면 LLM1(자식)·LLM2(부모 단독) 를 각각 실측 — 세션 합산값만으로는 어느 쪽이 지연인지 모름.
    if (childPlaygroundId) {
      const cres = await getPlaygroundStatusSync(childPlaygroundId);
      if (cres.status === STATUS_SUCCESS)
        setChildStatus(cres.result?.status ?? null);
      const pres = await getPlaygroundStatusSync(playgroundId, true);
      if (pres.status === STATUS_SUCCESS)
        setParentStatus(pres.result?.status ?? null);
    }
    setFirstPollDone(true);
    return st !== 'running'; // running 도달 시 폴링 중단(false = stop)
  }, [playgroundId, childPlaygroundId]);

  useIntervalCall(pollStatus, 5000);

  const fetchDetail = useCallback(async () => {
    const { result, status, error, message } =
      await getDetailPlayground(playgroundId);
    if (status === STATUS_SUCCESS) {
      setInfo({
        name: result?.info?.name ?? '-',
        owner: result?.info?.owner ?? '-',
      });
      setTrainingType(result?.model?.training_type ?? '');
      setDual(result?.dual ?? null);
      setLoading(false);
      return;
    }
    errorToastMessage(error, message);
    setLoading(false);
  }, [playgroundId]);

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Inference' } }]));
    fetchDetail();
  }, [dispatch, fetchDetail]);

  const goBack = () => {
    history.push(`/user/workspace/${workspaceId}/inference`);
  };

  return (
    <div className={cx('inference-detail')}>
      <div className={cx('header')}>
        <button type='button' className={cx('back-btn')} onClick={goBack}>
          ← {t('inference.backToList')}
        </button>
        <div className={cx('header-info')}>
          <h1 className={cx('title')}>{info?.name ?? ''}</h1>
          {info?.owner && info.owner !== '-' && (
            <span className={cx('owner')}>{info.owner}</span>
          )}
          {isDual && (
            <div className={cx('meta-row')}>
              {dual?.prompt_gen_model_name && (
                <span className={cx('meta-tag', 'prompt')}>
                  📝 프롬프트: {dual.prompt_gen_model_name}
                </span>
              )}
              {dual?.inference_model_name && (
                <span className={cx('meta-tag', 'inference')}>
                  🤖 추론: {dual.inference_model_name}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {!loading && !info && (
        <p className={cx('not-found')}>{t('inference.detail.notFound')}</p>
      )}

      {!loading && info && (
        <>
          {/* 모드 토글 — 단일 외부 모델(ExternalTestCom)은 단일 모드라 숨김.
              이중 세션은 외부 SDS LLM2 여도 실시간/배치 둘 다 지원 → 노출. */}
          {(!isExternal || isDual) && (
            <div className={cx('mode-tabs')}>
              <button
                type='button'
                className={cx('tab', mode === 'realtime' && 'active')}
                onClick={() => setMode('realtime')}
              >
                {t('inference.mode.realtime')}
              </button>
              <button
                type='button'
                className={cx('tab', mode === 'dataset' && 'active')}
                onClick={() => setMode('dataset')}
              >
                {t('inference.mode.dataset')}
              </button>
            </div>
          )}
          {/* 배포(파드) 상태 — 준비 전에는 추론 입력을 잠금(질의 실패 방지) */}
          <div className={cx('status-bar')}>
            <span className={cx('status-item')}>
              배포 상태
              <span className={cx('status', statusOf(sessionStatus).cls)}>
                ● {statusOf(sessionStatus).label}
              </span>
            </span>
            {isDual && (
              <>
                <span className={cx('status-item')}>
                  📝 LLM1
                  <span className={cx('status', statusOf(childStatus).cls)}>
                    ● {statusOf(childStatus).label}
                  </span>
                </span>
                <span className={cx('status-item')}>
                  🤖 LLM2
                  <span className={cx('status', statusOf(parentStatus).cls)}>
                    ● {statusOf(parentStatus).label}
                  </span>
                </span>
              </>
            )}
            {isLocked && (
              <span className={cx('status-hint')}>
                파드가 기동 중입니다. 준비되면 자동으로 추론이 활성화됩니다.
              </span>
            )}
          </div>

          <div className={cx('test-panel', isLocked && 'locked')}>
            {isDual ? (
              // 이중 세션 — LLM2 가 외부 SDS(VLM)면 isExternal 로 이미지+AIS 입력 노출(text→SDS).
              mode === 'realtime' ? (
                <DualDirectInference
                  playgroundId={playgroundId}
                  promptModelName={dual?.prompt_gen_model_name}
                  inferenceModelName={dual?.inference_model_name}
                  isExternal={isExternal}
                />
              ) : (
                <DualBatchInference
                  playgroundId={playgroundId}
                  isExternal={isExternal}
                />
              )
            ) : (
              <TestComponent
                integratedTestValue={integratedTestValue}
                playgroundId={playgroundId}
                isExternal={isExternal}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default InferenceDetail;
