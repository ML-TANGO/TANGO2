import React, { useCallback, useEffect, useState } from 'react';

import {
  getGateSummary,
  getStage,
  saveGateConfig,
} from '@src/apis/llm/dataset';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import {
  Badge,
  Btn,
  PageHeader,
  ProgressBar,
  SectionHead,
  Slider,
  Textfield,
  dsBase,
  useDatasetNav,
} from './components';
import { fmt } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

/**
 * VLM 심사.
 *
 * 통과율을 정상 범위 막대 위에 찍는다. 통과율이 높다고 좋은 것이 아니다 — 상한을
 * 넘으면 게이트가 헐거워 사실상 아무것도 거르지 못하고 있다는 뜻이다.
 *
 * 축별 미달 분포에서 가장 많이 걸린 축이 다음에 고칠 곳이고, 그 조치는 임계값을
 * 낮추는 것이 아니라 생성 프롬프트에 제약을 더하는 쪽이다.
 *
 * 축 · 임계값 · 정상 범위는 전부 서버가 정본이다. 프리셋마다 축이 다르고(범용 4축 vs
 * 해양 4축) FE 가 목록을 들고 있으면 해양 데이터셋에서 엉뚱한 축을 보여준다.
 */

// 임계값은 서버에서 0~1 실수로 오간다. 슬라이더는 정수라 화면에서만 100 배로 다룬다.
const toPct = (v) => Math.round((v ?? 0) * 100);
const toRatio = (v) => Number(v) / 100;

export default function GatePage() {
  const { wsId, dsId, go } = useDatasetNav();

  const [summary, setSummary] = useState(null);
  const [range, setRange] = useState([50, 95]);
  const [thresholds, setThresholds] = useState({});
  const [maxRegenerate, setMaxRegenerate] = useState('3');
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState('');

  const load = useCallback(async () => {
    const [sum, st] = await Promise.all([
      getGateSummary(dsId),
      getStage(dsId, 'gate'),
    ]);
    if (sum.status !== STATUS_SUCCESS) {
      setFailed(sum.message || '심사 현황을 불러오지 못했습니다');
      errorToastMessage(sum.error, sum.message);
      return;
    }
    setFailed('');
    setSummary(sum.result);
    setThresholds(
      Object.fromEntries(
        Object.entries(sum.result?.thresholds || {}).map(([k, v]) => [
          k,
          toPct(v),
        ]),
      ),
    );
    if (st.status === STATUS_SUCCESS) {
      const r = st.result?.threshold_range;
      if (Array.isArray(r)) setRange([toPct(r[0]), toPct(r[1])]);
      const saved = st.result?.config?.max_regenerate;
      if (saved !== null && saved !== undefined)
        setMaxRegenerate(String(saved));
    }
  }, [dsId]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    setBusy(true);
    const res = await saveGateConfig(dsId, {
      thresholds: Object.fromEntries(
        Object.entries(thresholds).map(([k, v]) => [k, toRatio(v)]),
      ),
      max_regenerate: Number(maxRegenerate) || 0,
    });
    setBusy(false);
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return;
    }
    // 임계값이 바뀌면 통과율·미달 분포가 통째로 달라진다 — 저장 후 다시 읽어야
    // 화면의 숫자가 방금 저장한 기준을 반영한다.
    load();
  };

  if (failed) {
    return (
      <div className={style.page}>
        <PageHeader
          title='VLM 심사'
          back={{ to: `${dsBase(wsId, dsId)}/flow`, label: '파이프라인' }}
        />
        <div className={common['card-pad']}>
          <span className={common.prose}>{failed}</span>
        </div>
      </div>
    );
  }

  const axes = summary?.axes || [];
  const passRate = summary?.pass_rate ?? 0;
  const out = summary?.pass_rate_flag === 'out_of_range';
  const [lo, hi] = summary?.pass_rate_range || [40, 85];
  const fails = summary?.fail_distribution || {};
  const failTotal = summary?.failed_total ?? 0;
  const maxFail = Math.max(1, ...Object.values(fails));
  const topKey = summary?.top_fail_axis || null;
  const topAxis = axes.find((a) => a.key === topKey) || null;

  return (
    <div className={style.page}>
      <PageHeader
        title='VLM 심사'
        back={{ to: `${dsBase(wsId, dsId)}/flow`, label: '파이프라인' }}
      />

      <div className={common.stack}>
        <SectionHead
          aside={
            <span className={[common.num, common['cell-mute']].join(' ')}>
              전체 {fmt(summary?.total ?? 0)}건
            </span>
          }
        >
          통과율
        </SectionHead>
        <div className={[common.card, style['gate-hero']].join(' ')}>
          <span className={style['gate-rate-row']}>
            <span
              className={[
                style['gate-rate'],
                out ? style['gate-rate-out'] : '',
              ].join(' ')}
            >
              {passRate}%
            </span>
            <Badge tone={out ? 'fail' : 'pass'} size='lg'>
              {out ? '범위 밖' : '정상'}
            </Badge>
          </span>
          <span className={style['gate-gauge']}>
            <i
              className={style['list-gauge-band']}
              style={{ left: `${lo}%`, right: `${100 - hi}%` }}
            />
            <i
              className={style['list-gauge-mark']}
              style={{
                left: `${passRate}%`,
                top: -4,
                height: 22,
                width: 3,
                background: out ? '#d91a0c' : '#121619',
              }}
            />
          </span>
          <span className={style['gate-gauge-legend']}>
            <span>0%</span>
            <span style={{ color: '#164abe' }}>
              {lo}–{hi}%
            </span>
            <span>100%</span>
          </span>
        </div>
      </div>

      <div className={style['gate-grid']}>
        <div className={common.stack}>
          <SectionHead>축별 기준값</SectionHead>
          <div className={[common['card-pad'], common.stack].join(' ')}>
            {axes.map((a) => (
              <span key={a.key} className={style['threshold-row']}>
                <span className={common.label} style={{ whiteSpace: 'nowrap' }}>
                  {a.label}
                </span>
                <Slider
                  min={range[0]}
                  max={range[1]}
                  value={thresholds[a.key] ?? range[0]}
                  onChange={(v) => setThresholds({ ...thresholds, [a.key]: v })}
                />
                <span className={common['cell-num']}>
                  0.{thresholds[a.key] ?? range[0]}
                </span>
              </span>
            ))}

            <span className={common.divider} style={{ paddingTop: 16 }}>
              <span
                className={style['threshold-row']}
                style={{ gridTemplateColumns: 'minmax(0,1fr) 90px' }}
              >
                <span className={common.label}>재생성 최대 횟수</span>
                <Textfield value={maxRegenerate} onChange={setMaxRegenerate} />
              </span>
            </span>

            <Btn block onClick={save} disabled={busy || axes.length === 0}>
              {busy ? '저장 중…' : '저장 · 재심사'}
            </Btn>
          </div>
        </div>

        <div className={common.stack}>
          <SectionHead
            aside={
              <span className={[common.num, common['cell-mute']].join(' ')}>
                {fmt(failTotal)}건
              </span>
            }
          >
            축별 미달 분포
          </SectionHead>
          <div className={common['card-pad']} style={{ paddingTop: 8 }}>
            {axes.map((a) => {
              const n = fails[a.key] || 0;
              const isTop = a.key === topKey && n > 0;
              return (
                <span key={a.key} className={style['fail-row']}>
                  <span
                    className={[common.label, isTop ? common.danger : ''].join(
                      ' ',
                    )}
                    style={{ whiteSpace: 'nowrap' }}
                  >
                    {a.label}
                  </span>
                  <ProgressBar
                    value={Math.round((n / maxFail) * 100)}
                    tone={isTop ? 'red' : 'primary'}
                    height={10}
                  />
                  <span
                    className={[
                      common['cell-num'],
                      isTop ? common.danger : '',
                    ].join(' ')}
                  >
                    {fmt(n)}
                  </span>
                  <span className={common.right}>
                    {isTop && <Badge tone='fail'>최다</Badge>}
                  </span>
                </span>
              );
            })}

            {/* 임계값을 낮추면 숫자는 좋아지지만 데이터는 나빠진다 — 생성 쪽을 고치게 유도한다. */}
            {topAxis && (
              <span className={style['gate-cta']}>
                <span
                  className={common.body}
                  style={{ fontFamily: 'SpoqaB', color: '#164abe' }}
                >
                  {topAxis.label} {fmt(fails[topKey] || 0)}건
                </span>
                <Btn size='md' onClick={() => go('/flow/generate')}>
                  생성에서 제약 추가 →
                </Btn>
              </span>
            )}
            {axes.length === 0 && (
              <span className={common.prose}>
                아직 심사한 레코드가 없습니다.
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
