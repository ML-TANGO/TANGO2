// 다단계 학습 레시피(manifest.recipe, SP-10) — master-detail 파이프라인.
//
// 상단: 가로 phase 카드 행(선택 가능, 상태 배지). 클릭 → 선택. 실행 중 phase 는
// 자동 선택(모니터링 따라가기).
// 하단: 선택 phase 의 상세 패널 — 상태별로 다른 UI.
//   - 실행중/대기(활성 job): 라이브 모니터링(부모가 monitoringSlot 으로 주입: 그래프/진행).
//   - 완료(done): 커밋 요약 + params(readonly).
//   - idle: params 편집 + 실행 버튼(체인 게이트).
//
// 한 모델은 단일 externalJobId 만 추적 → 한 번에 한 phase 만 실행. 완료 phase 는
// 세션이 아니라 커밋(`{phase.id}-{ts}`)에서 derive → cross-reload 생존.

import { Fragment, useCallback, useEffect, useState } from 'react';

import { ButtonV2 } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from './RecipePipeline.module.scss';

const cx = classNames.bind(style);

// SSE fine_tuning_status.status (running|pending|done|stop|error) + idle.
const STATUS_KEYS = {
  running: 'externalTraining.recipe.status.running',
  pending: 'externalTraining.recipe.status.pending',
  done: 'externalTraining.recipe.status.done',
  error: 'externalTraining.recipe.status.error',
  stop: 'externalTraining.recipe.status.stop',
  idle: 'externalTraining.recipe.status.idle',
};

const phaseStatusOf = (phase, activePhaseId, activePhaseStatus, donePhases) => {
  if (phase.id === activePhaseId && activePhaseStatus) return activePhaseStatus;
  if (donePhases.has(phase.id)) return 'done';
  return 'idle';
};

const RecipePipeline = ({
  phases,
  activePhaseId,
  activePhaseStatus,
  donePhases,
  phaseCommitMap,
  onRunPhase,
  monitoringSlot,
  t,
}) => {
  const done = donePhases || new Set();
  const commitMap = phaseCommitMap || {};

  // phase 별 편집 가능 params (JSON 텍스트). 프리셋으로 초기화.
  const [paramsText, setParamsText] = useState(() => {
    const m = {};
    phases.forEach((p) => {
      try {
        m[p.id] = JSON.stringify(p.params || {}, null, 2);
      } catch (_) {
        m[p.id] = '{}';
      }
    });
    return m;
  });
  // optional phase 포함 토글 — 기본: optional 이면 off.
  const [included, setIncluded] = useState(() => {
    const m = {};
    phases.forEach((p) => {
      m[p.id] = !p.optional;
    });
    return m;
  });
  const [paramsError, setParamsError] = useState({});

  // 선택 phase — 기본: 활성(실행 중) phase → 없으면 첫 미완료 → 없으면 첫 phase.
  const [selectedPhaseId, setSelectedPhaseId] = useState(() => {
    if (activePhaseId) return activePhaseId;
    const pending = phases.find((p) => !done.has(p.id));
    return (pending || phases[0] || {}).id;
  });

  // 실행 phase 가 바뀌면 그 phase 를 자동 선택(모니터링 따라가기).
  useEffect(() => {
    if (activePhaseId) setSelectedPhaseId(activePhaseId);
  }, [activePhaseId]);

  // 커밋이 비동기로 늦게 도착(리로드 시 fetchRecipeCommits)할 수 있다 — 마운트
  // 시점엔 donePhases 가 비어 phase[0] 가 잡힐 수 있으므로, done 이 채워지고
  // 활성 job 이 없을 때 현재 선택이 이미 완료된 phase 면 첫 미완료로 보정한다
  // (code-review: 부분 완료 레시피 리로드 시 done 카드가 선택되는 것 방지).
  useEffect(() => {
    if (activePhaseId) return; // 실행 중이면 위 effect 가 우선.
    if (done.size === 0) return; // 아직 완료 없음 → 초기 기본값 유지.
    setSelectedPhaseId((prev) => {
      if (phases.find((p) => p.id === prev && !done.has(p.id))) return prev;
      const pending = phases.find((p) => !done.has(p.id));
      return (pending || phases[phases.length - 1] || { id: prev }).id;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [donePhases, activePhaseId]);

  // 실행 중(running/pending)이면 모든 phase 의 실행 버튼 비활성(한 번에 한 job).
  const anyRunning =
    activePhaseStatus === 'running' || activePhaseStatus === 'pending';

  const canRun = useCallback(
    (phase) => {
      if (!included[phase.id]) return false;
      if (anyRunning) return false;
      if (phase.chain_from && !done.has(phase.chain_from)) return false;
      return true;
    },
    [included, anyRunning, done],
  );

  // 편집된 params 가 유효한 JSON object 일 때만 실행 — 깨진/비-object JSON 은
  // 오류 표시 후 차단(의도와 다른 파라미터로 비싼 학습이 도는 것 방지).
  const handleRun = useCallback(
    (phase) => {
      let parsed;
      try {
        parsed = JSON.parse(paramsText[phase.id]);
      } catch (_) {
        parsed = undefined;
      }
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        setParamsError((s) => ({ ...s, [phase.id]: true }));
        return;
      }
      setParamsError((s) => ({ ...s, [phase.id]: false }));
      onRunPhase(phase, parsed);
    },
    [paramsText, onRunPhase],
  );

  const selectedPhase =
    phases.find((p) => p.id === selectedPhaseId) || phases[0] || null;
  const selectedStatus = selectedPhase
    ? phaseStatusOf(selectedPhase, activePhaseId, activePhaseStatus, done)
    : 'idle';
  const selExcluded = selectedPhase ? !included[selectedPhase.id] : false;
  const selBlockedByChain =
    selectedPhase &&
    selectedPhase.chain_from &&
    !done.has(selectedPhase.chain_from);

  return (
    <div className={cx('recipe')}>
      {/* 카드 행 — 선택 가능 (상태 배지만, 편집/실행은 상세 패널) */}
      <div className={cx('pipeline')}>
        {phases.map((phase, idx) => {
          const st = phaseStatusOf(phase, activePhaseId, activePhaseStatus, done);
          const excluded = !included[phase.id];
          const selected = phase.id === selectedPhaseId;
          return (
            <Fragment key={phase.id}>
              {idx > 0 ? <div className={cx('connector')}>→</div> : null}
              <button
                type='button'
                className={cx(
                  'card',
                  `st-${st}`,
                  excluded && 'excluded',
                  selected && 'selected',
                )}
                onClick={() => setSelectedPhaseId(phase.id)}
              >
                <div className={cx('card-head')}>
                  <span className={cx('phase-label')}>{phase.label}</span>
                  <span className={cx('badge', `badge-${st}`)}>
                    {t(STATUS_KEYS[st] || STATUS_KEYS.idle)}
                  </span>
                </div>
                {phase.optional ? (
                  <div className={cx('opt-tag')}>
                    {t('externalTraining.recipe.optional.label')}
                  </div>
                ) : null}
              </button>
            </Fragment>
          );
        })}
      </div>

      {/* 상세 패널 — 선택 phase 의 상태별 UI */}
      {selectedPhase ? (
        <div className={cx('detail')}>
          <div className={cx('detail-head')}>
            <span className={cx('detail-title')}>{selectedPhase.label}</span>
            <span className={cx('badge', `badge-${selectedStatus}`)}>
              {t(STATUS_KEYS[selectedStatus] || STATUS_KEYS.idle)}
            </span>
          </div>
          {selectedPhase.description ? (
            <div className={cx('phase-desc')}>{selectedPhase.description}</div>
          ) : null}

          {selectedStatus === 'running' || selectedStatus === 'pending' ? (
            // 실행 중 — 라이브 모니터링(부모 주입: 그래프/진행). W&B/Job ID 는 메타 패널.
            <div className={cx('detail-monitor')}>{monitoringSlot}</div>
          ) : selectedStatus === 'done' ? (
            // 완료 — 커밋 요약 + params(readonly).
            <div className={cx('detail-done')}>
              <div className={cx('commit-row')}>
                <span className={cx('commit-label')}>
                  {t('externalTraining.recipe.commit.label')}
                </span>
                <span className={cx('commit-name')}>
                  {commitMap[selectedPhase.id] || '-'}
                </span>
              </div>
              <textarea
                className={cx('params-textarea')}
                value={paramsText[selectedPhase.id]}
                readOnly
                spellCheck={false}
              />
            </div>
          ) : (
            // idle — params 편집 + 실행(체인 게이트).
            <div className={cx('detail-edit')}>
              {selectedPhase.optional ? (
                <label className={cx('opt-toggle')}>
                  <input
                    type='checkbox'
                    checked={!!included[selectedPhase.id]}
                    onChange={(e) =>
                      setIncluded((s) => ({
                        ...s,
                        [selectedPhase.id]: e.target.checked,
                      }))
                    }
                  />
                  {t('externalTraining.recipe.optional.label')}
                </label>
              ) : null}
              <textarea
                className={cx('params-textarea')}
                value={paramsText[selectedPhase.id]}
                onChange={(e) => {
                  const v = e.target.value;
                  setParamsText((s) => ({ ...s, [selectedPhase.id]: v }));
                  if (paramsError[selectedPhase.id]) {
                    setParamsError((s) => ({ ...s, [selectedPhase.id]: false }));
                  }
                }}
                spellCheck={false}
                disabled={selExcluded}
              />
              {paramsError[selectedPhase.id] ? (
                <div className={cx('params-error')}>
                  {t('externalTraining.recipe.invalidJson.label')}
                </div>
              ) : null}
              {selBlockedByChain && !selExcluded ? (
                <div className={cx('chain-hint')}>
                  {t('externalTraining.recipe.chainGate.label')}
                </div>
              ) : null}
              <div className={cx('detail-foot')}>
                <ButtonV2
                  type='solid'
                  size='m'
                  colorType='skyblue'
                  label={t('externalTraining.recipe.run.label')}
                  onClick={() => handleRun(selectedPhase)}
                  disabled={!canRun(selectedPhase)}
                />
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
};

export default RecipePipeline;
