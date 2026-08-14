import React, { useState } from 'react';

import {
  Badge, Btn, PageHeader, ProgressBar, SectionHead, Slider, Textfield, dsBase, useDatasetNav,
} from './components';
import { GATE_FAILS, GATE_PASS } from './mock';
import { AXES, PASS_RANGE, fmt, isPassRateOut } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

/**
 * VLM 심사.
 *
 * 통과율을 정상 범위(40–85%) 막대 위에 찍는다. 통과율이 높다고 좋은 것이 아니다 —
 * 85% 를 넘으면 게이트가 헐거워 사실상 아무것도 거르지 못하고 있다는 뜻이다.
 *
 * 축별 미달 분포에서 가장 많이 걸린 축이 다음에 고칠 곳이고, 그 조치는 임계값을
 * 낮추는 것이 아니라 생성 프롬프트에 제약을 더하는 쪽이다.
 */
export default function GatePage() {
  const { wsId, dsId, go } = useDatasetNav();
  const [thresholds, setThresholds] = useState({ align: 75, imgdep: 80, answer: 80, unique: 70 });
  const [maxRegenerate, setMaxRegenerate] = useState('3');

  const [lo, hi] = PASS_RANGE;
  const out = isPassRateOut(GATE_PASS);
  const max = Math.max(...GATE_FAILS.map((x) => x[1]));
  const top = GATE_FAILS.find((x) => x[1] === max);
  const failTotal = GATE_FAILS.reduce((acc, x) => acc + x[1], 0);

  return (
    <div className={style.page}>
      <PageHeader
        title="VLM 심사"
        back={{ to: `${dsBase(wsId, dsId)}/flow`, label: '파이프라인' }}
      />

      <div className={common.stack}>
        <SectionHead>통과율</SectionHead>
        <div className={[common.card, style['gate-hero']].join(' ')}>
          <span className={style['gate-rate-row']}>
            <span className={[style['gate-rate'], out ? style['gate-rate-out'] : ''].join(' ')}>{GATE_PASS}%</span>
            <Badge tone={out ? 'fail' : 'pass'} size="lg">{out ? '범위 밖' : '정상'}</Badge>
          </span>
          <span className={style['gate-gauge']}>
            <i className={style['list-gauge-band']} style={{ left: `${lo}%`, right: `${100 - hi}%` }} />
            <i
              className={style['list-gauge-mark']}
              style={{ left: `${GATE_PASS}%`, top: -4, height: 22, width: 3, background: out ? '#d91a0c' : '#121619' }}
            />
          </span>
          <span className={style['gate-gauge-legend']}>
            <span>0%</span>
            <span style={{ color: '#164abe' }}>{lo}–{hi}%</span>
            <span>100%</span>
          </span>
        </div>
      </div>

      <div className={style['gate-grid']}>
        <div className={common.stack}>
          <SectionHead>축별 기준값</SectionHead>
          <div className={[common['card-pad'], common.stack].join(' ')}>
            {AXES.map((a) => (
              <span key={a.k} className={style['threshold-row']}>
                <span className={common.label} style={{ whiteSpace: 'nowrap' }}>{a.label}</span>
                <Slider
                  min={50}
                  max={95}
                  value={thresholds[a.k]}
                  onChange={(v) => setThresholds({ ...thresholds, [a.k]: v })}
                />
                <span className={common['cell-num']}>0.{thresholds[a.k]}</span>
              </span>
            ))}

            <span className={common.divider} style={{ paddingTop: 16 }}>
              <span className={style['threshold-row']} style={{ gridTemplateColumns: 'minmax(0,1fr) 90px' }}>
                <span className={common.label}>재생성 최대 횟수</span>
                <Textfield value={maxRegenerate} onChange={setMaxRegenerate} />
              </span>
            </span>

            <Btn block>저장 · 재심사</Btn>
          </div>
        </div>

        <div className={common.stack}>
          <SectionHead aside={<span className={[common.num, common['cell-mute']].join(' ')}>{fmt(failTotal)}건</span>}>
            축별 미달 분포
          </SectionHead>
          <div className={common['card-pad']} style={{ paddingTop: 8 }}>
            {GATE_FAILS.map(([k, n]) => {
              const isTop = n === max;
              return (
                <span key={k} className={style['fail-row']}>
                  <span className={[common.label, isTop ? common.danger : ''].join(' ')} style={{ whiteSpace: 'nowrap' }}>
                    {k}
                  </span>
                  <ProgressBar value={Math.round((n / max) * 100)} tone={isTop ? 'red' : 'primary'} height={10} />
                  <span className={[common['cell-num'], isTop ? common.danger : ''].join(' ')}>{fmt(n)}</span>
                  <span className={common.right}>{isTop && <Badge tone="fail">최다</Badge>}</span>
                </span>
              );
            })}

            {/* 임계값을 낮추면 숫자는 좋아지지만 데이터는 나빠진다 — 생성 쪽을 고치게 유도한다. */}
            <span className={style['gate-cta']}>
              <span className={common.body} style={{ fontFamily: 'SpoqaB', color: '#164abe' }}>
                {top[0]} {fmt(top[1])}건
              </span>
              <Btn size="md" onClick={() => go('/flow/generate')}>생성에서 제약 추가 →</Btn>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
