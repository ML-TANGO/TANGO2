import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { Badge } from '@jonathan/ui-react';

import DeployDetailHeader from '@src/components/pageContents/llm/DeployDetail/DeployDetailHeader';
import Tab from '@src/components/molecules/Tab';
import TestComponent from '@src/components/Modal/PlaygroundTestModal/TestComponent';
import DualDirectInference from './DualDirectInference';
import BatchInference from './BatchInference';
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

// 모드 탭 — Tab 이 내부에서 t(label) 하므로 i18n 키를 그대로 넘긴다.
const TAB_OPTIONS = [
  { label: 'inference.mode.realtime', value: 'realtime' },
  { label: 'inference.mode.dataset', value: 'dataset' },
];

// 추론 상세(Inference detail, D6 v3 Tier-1) — 배포 config 없는 lean consume 화면.
//   배포(provision)는 "배포" 탭. 여기선 "띄운 배포에 질의"만.
//   레이아웃은 형제 배포 상세(PlaygroundDetail·Standalone·Edge)와 동형:
//   DeployDetailHeader → Tab(type='c') → content. 상태 배지는 조나단 Badge 가
//   플랫폼 상태 어휘(running/installing/pending/stop)를 type 으로 직접 지원해 매핑 없이 사용.
//   기존 PlaygroundTestModal 의 TestComponent(PromptCom/DatasetCom/ExternalTestCom)를
//   모달 셸 없이 인라인 재사용 — 실 백엔드(postPlaygroundTestChat) 그대로.
//   redux 미오염: TestComponent 는 prop 컴포넌트, 하위는 auth.userName 만 읽음 →
//   getDetailPlayground 로 name/training_type 만 로컬 fetch (전체 payload dispatch X).
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

  // 배포(파드) 상태 — status-sync 폴링(10s, 탭 비활성 시 자동 정지).
  //   세션(부모) 상태는 이중이면 부모+자식 합산값(BE get_playground_status), LLM1 은 자식 개별 조회.
  const [sessionStatus, setSessionStatus] = useState(null);
  const [childStatus, setChildStatus] = useState(null); // LLM1(자식) 실측
  const [parentStatus, setParentStatus] = useState(null); // LLM2(부모 단독, skip_dual)
  const [firstPollDone, setFirstPollDone] = useState(false);

  const isExternal = trainingType === 'external';
  const isDual = dual?.mode === 'dual';
  const integratedTestValue = mode === 'dataset';
  // 일괄 모드에서 SSE 배치 패널(BatchInference)을 쓰는 경우 — 이중 전체 + 단독 외부(SDS).
  //   단독 내부는 기존 TestComponent/DatasetCom 경로를 그대로 둔다(동작 회귀 방지).
  const useBatchPanel = mode === 'dataset' && (isDual || isExternal);
  // 잠금 규칙:
  //   - 이중 세션에만 적용(단일은 목록이 이미 running 만 노출 → 기존 동작 회귀 방지).
  //   - 첫 폴링이 끝나기 전엔 잠금(그 사이 클릭해 준비 안 된 파드로 질의하는 경합 차단).
  //   - 폴링이 끝난 뒤 상태 불명(null=조회 실패)이면 잠그지 않음(fail-open, 영구잠김 방지).
  const isLocked =
    isDual &&
    (!firstPollDone || (sessionStatus != null && sessionStatus !== 'running'));
  const pollStatus = useCallback(async () => {
    if (!playgroundId) return true;
    const res = await getPlaygroundStatusSync(playgroundId);
    const st = res.status === STATUS_SUCCESS ? res.result?.status : null;
    if (st) setSessionStatus(st);
    // 새 계약은 집계+LLM1/LLM2 실측을 한 번에 내려준다. skip_dual은 구 호출자만 유지한다.
    if (res.status === STATUS_SUCCESS) {
      const statuses = new Map(
        (res.result?.components || []).map((component) => [
          component.role,
          component.status,
        ]),
      );
      setChildStatus(statuses.get('prompt_gen') ?? null);
      setParentStatus(statuses.get('inference') ?? null);
    }
    setFirstPollDone(true);
    return true; // 실행 뒤 장애 전이도 새로고침 없이 반영해야 하므로 관찰을 유지한다.
  }, [playgroundId]);

  useIntervalCall(pollStatus, 10000);

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

  // 상태 배지 — 상태 미확인(null: 최초 폴링 전이거나 조회 실패)만 중립 배지로.
  const statusBadge = (status) =>
    status ? (
      <Badge type={status} label={t(status)} size='sm' />
    ) : (
      <Badge type='gray' label='확인 중' size='sm' />
    );

  return (
    <div className={cx('inference-detail')}>
      <DeployDetailHeader
        title={info?.name ?? ''}
        onBack={goBack}
        backLabel={t('inference.backToList')}
        right={
          <>
            <Badge
              type={isDual ? 'blue' : 'gray'}
              label={isDual ? '이중 모델' : '단일 모델'}
              size='sm'
            />
            {info?.owner && info.owner !== '-' && (
              <span className={cx('owner')}>{info.owner}</span>
            )}
          </>
        }
      />

      {!loading && !info && (
        <p className={cx('not-found')}>{t('inference.detail.notFound')}</p>
      )}

      {!loading && info && (
        <>
          {/* 모드 토글 — 단독 SDS 도 데이터셋 일괄을 지원하므로(batch_stream 단독 모드)
              모든 배포 유형에 실시간/일괄 두 탭을 노출한다. */}
          <div className={cx('tab-bar')}>
            <Tab
              type='c'
              sidePaddingNone
              option={TAB_OPTIONS}
              select={{ value: mode }}
              tabHandler={({ value }) => setMode(value)}
            />
          </div>

          {/* 배포(파드) 상태 — 준비 전에는 추론 입력을 잠금(질의 실패 방지) */}
          <div className={cx('status-card')}>
            <span className={cx('status-item')}>
              <span className={cx('status-label')}>배포 상태</span>
              {statusBadge(sessionStatus)}
            </span>
            {isDual && (
              <>
                <span className={cx('status-item')}>
                  <span className={cx('status-label')}>
                    LLM1 · 프롬프트 생성
                    {dual?.prompt_gen_model_name
                      ? ` (${dual.prompt_gen_model_name})`
                      : ''}
                  </span>
                  {statusBadge(childStatus)}
                </span>
                <span className={cx('status-item')}>
                  <span className={cx('status-label')}>
                    LLM2 · 추론
                    {dual?.inference_model_name
                      ? ` (${dual.inference_model_name})`
                      : ''}
                  </span>
                  {statusBadge(parentStatus)}
                </span>
              </>
            )}
            {isLocked && (
              <span className={cx('status-hint')}>
                파드가 기동 중입니다. 준비되면 자동으로 추론이 활성화됩니다.
              </span>
            )}
          </div>

          {/* 배치 패널은 결과 표가 다열이라 전폭(wide) — 실시간은 모달 유래 720px 유지. */}
          <div
            className={cx(
              'content-cont',
              useBatchPanel && 'wide',
              isLocked && 'locked',
            )}
          >
            {useBatchPanel ? (
              // 이중 + 단독 외부(SDS) 공용 — 모드 판별은 BE(resolve_dual_prompt_gen)가 한다.
              <BatchInference
                playgroundId={playgroundId}
                isExternal={isExternal}
                isDual={isDual}
              />
            ) : isDual ? (
              // 이중 실시간 — LLM2 가 외부 SDS(VLM)면 isExternal 로 이미지+AIS 입력 노출(text→SDS).
              <DualDirectInference
                playgroundId={playgroundId}
                promptModelName={dual?.prompt_gen_model_name}
                inferenceModelName={dual?.inference_model_name}
                isExternal={isExternal}
              />
            ) : (
              // 단독 — 실시간(PromptCom/ExternalTestCom) + 내부 모델의 데이터셋 일괄(DatasetCom).
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
