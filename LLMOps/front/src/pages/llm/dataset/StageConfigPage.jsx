import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';

import {
  Btn, Checkbox, DataTable, Frame, Funnel, PageHeader, SectionHead, Segmented, Slider, dsBase, useDatasetNav,
} from './components';
import {
  CONVERTED, FILTER_FUNNEL, FILTER_REASONS, FILTER_REMOVED, FILTER_STEPS,
  PREPROCESS_FUNNEL, PREPROCESS_STEPS,
} from './mock';
import { SHOTS } from './lib/frames';
import { fmt } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

/**
 * 전처리 · 필터 공용 화면.
 *
 * 두 단계는 레이아웃이 같고 기능 목록과 결과 블록만 다르다. 화면을 둘로 나누면
 * 같은 코드를 두 벌 고치게 되므로 하나로 두고 stage 로 갈라 쓴다.
 *
 * 전처리는 아무것도 버리지 않고 필터만 버린다 — 그래서 필터에는 "무엇을 왜 버렸고
 * 어떻게 되살리는지"가 함께 붙는다.
 */
export default function StageConfigPage({ stage: stageProp }) {
  const { wsId, dsId } = useDatasetNav();
  const location = useLocation();
  const stage = stageProp || (location.pathname.endsWith('/filter') ? 'filter' : 'preprocess');
  const isFilter = stage === 'filter';

  const steps = isFilter ? FILTER_STEPS : PREPROCESS_STEPS;
  const funnel = isFilter ? FILTER_FUNNEL : PREPROCESS_FUNNEL;

  const [phase, setPhase] = useState('실행 후');
  const [enabled, setEnabled] = useState({ 0: true, 1: true, 2: true });
  const [selected, setSelected] = useState(0);
  const [reason, setReason] = useState(0);
  const [restored, setRestored] = useState({});
  const [params, setParams] = useState({
    retry: 2, dpi: 200, longEdge: 1024, dupTh: 95, blur: 40, nsfw: 85,
  });

  const cur = steps[selected];
  const [paramLabel, paramKey, paramMin, paramMax, paramUnit] = cur.param;
  const shownValue = paramUnit === 'ratio'
    ? `0.${params[paramKey]}`
    : `${params[paramKey]}${paramUnit ? ` ${paramUnit}` : ''}`;

  const onCount = Object.values(enabled).filter(Boolean).length;
  const restoredCount = Object.values(restored).filter(Boolean).length;

  return (
    <div className={style.page}>
      <PageHeader
        title={isFilter ? '필터' : '전처리'}
        back={{ to: `${dsBase(wsId, dsId)}/flow`, label: '파이프라인' }}
        actions={<Segmented options={['실행 전', '실행 후']} value={phase} onChange={setPhase} />}
      />

      <div className={style['stage-grid']}>
        {/* 좌: 기능 목록 + 선택한 기능의 파라미터 */}
        <div className={common['stack-lg']}>
          <div className={common.stack}>
            <SectionHead aside={<span className={[common.num, common['cell-mute']].join(' ')}>{steps.length}개 중 {onCount}개 켜짐</span>}>
              기능
            </SectionHead>
            <div className={common['card-clip']}>
              {steps.map((s, i) => (
                <div
                  key={s.k}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelected(i)}
                  onKeyDown={(e) => e.key === 'Enter' && setSelected(i)}
                  className={[style['step-item'], selected === i ? style['step-item-on'] : ''].join(' ')}
                >
                  <span className={style['step-head']}>
                    <Checkbox
                      checked={!!enabled[i]}
                      onChange={(v) => setEnabled({ ...enabled, [i]: v })}
                      label={s.k}
                    />
                    <span className={[style['step-tag'], isFilter ? style['step-tag-del'] : ''].join(' ')}>
                      {isFilter ? (enabled[i] ? `−${s.del}` : '') : '변환'}
                    </span>
                  </span>
                  <span className={style['step-desc']}>{s.desc}</span>
                </div>
              ))}
              <div className={style['step-actions']}>
                <Btn size="md" fill="outline" tone="gray">기본값</Btn>
                <Btn size="md" block onClick={() => setPhase('실행 후')}>실행</Btn>
              </div>
            </div>
          </div>

          <div className={common.stack}>
            <SectionHead>{cur.k} 설정</SectionHead>
            <div className={[common['card-pad'], common.stack].join(' ')}>
              <span>
                <span className={style['param-head']}>
                  <span className={common.label}>{paramLabel}</span>
                  <span className={style['param-value']}>{shownValue}</span>
                </span>
                <Slider
                  min={paramMin}
                  max={paramMax}
                  value={params[paramKey]}
                  onChange={(v) => setParams({ ...params, [paramKey]: v })}
                />
              </span>
            </div>
          </div>
        </div>

        {/* 우: 실행 전이면 입력, 실행 후면 결과 */}
        <div className={common['stack-lg']}>
          {phase === '실행 전' ? (
            <>
              <SectionHead>입력</SectionHead>
              <div className={[common.card, common['thumb-grid']].join(' ')}>
                {[0, 1, 2, 3, 0, 1, 2, 3].map((k, i) => (
                  // eslint-disable-next-line react/no-array-index-key
                  <span key={i} className={common.thumb}>
                    <Frame spec={SHOTS[k]} />
                    <span className={common['thumb-cap']}>asset_{1001 + i}</span>
                  </span>
                ))}
              </div>
            </>
          ) : (
            <>
              <SectionHead>처리 전후</SectionHead>
              <Funnel rows={funnel} total={funnel[0].v} />

              {!isFilter && (
                <>
                  <SectionHead>변환 결과</SectionHead>
                  <DataTable
                    cols={['데이터', '변환 전', '변환 후']}
                    rows={CONVERTED}
                  />
                </>
              )}

              {isFilter && (
                <>
                  <SectionHead>제거 사유</SectionHead>
                  <div className={common['card-clip']}>
                    {FILTER_REASONS.map((r, i) => (
                      <div
                        key={r.k}
                        role="button"
                        tabIndex={0}
                        onClick={() => setReason(i)}
                        onKeyDown={(e) => e.key === 'Enter' && setReason(i)}
                        className={[style['reason-row'], reason === i ? style['reason-row-on'] : ''].join(' ')}
                      >
                        <span className={common.cell}>{r.k}</span>
                        <span className={common.prose}>{r.why}</span>
                        <span className={[common['cell-num'], common.warn].join(' ')}>{r.n}</span>
                        <span className={common.right}>
                          <span className={common['cell-mute']} style={{ color: '#2d76f8' }}>
                            {reason === i ? '검토 중' : '보기 →'}
                          </span>
                        </span>
                      </div>
                    ))}
                  </div>

                  <SectionHead
                    aside={(
                      <span className={[common.num, common['cell-mute']].join(' ')}>
                        {FILTER_REMOVED[reason].length} / {FILTER_REASONS[reason].n}건
                      </span>
                    )}
                  >
                    제거된 항목 · {FILTER_REASONS[reason].k}
                  </SectionHead>

                  {/* 제거된 것은 버려지지 않는다 — 과하게 걸렀을 때 개별로 되살릴 수 있어야 한다. */}
                  <div className={[common.card, common['thumb-grid']].join(' ')}>
                    {FILTER_REMOVED[reason].map(([aid, shot, why]) => {
                      const kept = !!restored[aid];
                      return (
                        <span key={aid} className={[style['removed-card'], kept ? style['removed-card-kept'] : ''].join(' ')}>
                          <span className={[style['removed-shot'], kept ? style['removed-shot-kept'] : ''].join(' ')}>
                            <Frame spec={SHOTS[shot]} />
                            <span className={[style['removed-tag'], kept ? style['removed-tag-kept'] : ''].join(' ')}>
                              {kept ? '복구됨' : '제거됨'}
                            </span>
                          </span>
                          <span className={style['removed-meta']}>
                            <span className={style['removed-id']}>{aid}</span>
                            <span className={style['removed-why']}>{why}</span>
                            <button
                              type="button"
                              onClick={() => setRestored({ ...restored, [aid]: !kept })}
                              className={[style['removed-btn'], kept ? style['removed-btn-undo'] : ''].join(' ')}
                            >
                              {kept ? '다시 제거' : '복구'}
                            </button>
                          </span>
                        </span>
                      );
                    })}
                  </div>

                  <div className={[common['card-pad'], common['row-between']].join(' ')}>
                    <span className={common.prose}>
                      출력 {fmt(funnel[funnel.length - 1].v)}건 · 복구 {restoredCount}건
                    </span>
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
