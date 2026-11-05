import React, { useCallback, useEffect, useRef, useState } from 'react';

import {
  getFlow,
  getGateSummary,
  getStage,
  runStage,
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
import RunPanel from './components/RunPanel';
import { fmt } from './lib/format';
import { findStageNode, upstreamRunOf } from './lib/stage';
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
  const [flow, setFlow] = useState(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState('');

  const load = useCallback(async () => {
    const [sum, st, fl] = await Promise.all([
      getGateSummary(dsId),
      getStage(dsId, 'gate'),
      getFlow(dsId),
    ]);
    if (fl.status === STATUS_SUCCESS) setFlow(fl.result);
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

  const persist = async () => {
    const res = await saveGateConfig(dsId, {
      thresholds: Object.fromEntries(
        Object.entries(thresholds).map(([k, v]) => [k, toRatio(v)]),
      ),
      max_regenerate: Number(maxRegenerate) || 0,
    });
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return false;
    }
    return true;
  };

  const save = async () => {
    setBusy(true);
    const ok = await persist();
    setBusy(false);
    // 임계값이 바뀌면 통과율·미달 분포가 통째로 달라진다 — 저장 후 다시 읽어야
    // 화면의 숫자가 방금 저장한 기준을 반영한다.
    if (ok) load();
  };

  // 심사는 이 화면에서 시작한다. 예전엔 실행 버튼이 캔버스 드로어에만 있어, 생성을 마친
  // 사용자가 '저장 · 재심사'(이미 채점된 레코드에 기준만 다시 적용)를 누르고 심사가
  // 시작되길 기다렸다. 잡은 저장된 임계값을 읽으므로 저장 후 실행한다. 심사 모델 서빙은
  // BE 가 준비한다(그동안 실행은 running 으로 보인다).
  const run = async (dryRun) => {
    setBusy(true);
    if (!(await persist())) {
      setBusy(false);
      return;
    }
    const res = await runStage(dsId, 'gate', {
      dry_run: dryRun,
      sample_size: 10,
    });
    if (res.status !== STATUS_SUCCESS) {
      setBusy(false);
      errorToastMessage(res.error, res.message);
      return;
    }
    // 새 실행(running)을 읽어 온 뒤에 버튼을 푼다 — 먼저 풀면 그 틈에 한 번 더 눌려
    // 심사 잡이 두 번 뜬다(BE run_stage 에 실행 중 중복 가드가 없다).
    await load();
    setBusy(false);
  };

  const nodes = flow?.nodes || [];
  const { node, index } = findStageNode(nodes, 'gate');
  const running = node?.latest_run?.status === 'running';

  // 실행 중이면 흐름만 10초마다 다시 읽는다(캔버스와 같은 주기 — BE 리콘사일러가 20초마다
  // 마감한다). load 전체를 부르면 저장 안 한 임계값이 덮인다. 끝나면 통과율 · 미달 분포가
  // 바뀌므로 그때 한 번 전부 다시 읽는다.
  const wasRunning = useRef(false);
  useEffect(() => {
    if (wasRunning.current && !running) load();
    wasRunning.current = running;
    if (!running) return undefined;
    const t = setInterval(async () => {
      const fl = await getFlow(dsId);
      if (fl.status === STATUS_SUCCESS) setFlow(fl.result);
    }, 10000);
    return () => clearInterval(t);
  }, [running, dsId, load]);

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

  // 흐름을 못 읽었으면 실행 중인지 알 수 없다 — 그 상태로 누르면 중복 실행이 된다.
  const runDisabled = busy || running || !flow || axes.length === 0;

  return (
    <div className={style.page}>
      <PageHeader
        title='VLM 심사'
        back={{ to: `${dsBase(wsId, dsId)}/flow`, label: '파이프라인' }}
        actions={
          <span className={style.toolbar}>
            <Btn
              size='md'
              fill='outline'
              tone='gray'
              onClick={() => run(true)}
              disabled={runDisabled}
            >
              미리보기 10건
            </Btn>
            <Btn size='md' onClick={() => run(false)} disabled={runDisabled}>
              {running ? '심사중…' : '전체 심사'}
            </Btn>
          </span>
        }
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

            {/* 모델을 다시 부르지 않는다 — 이미 채점된 레코드에 기준만 다시 적용한다.
                '재심사'라고 쓰면 심사가 시작되는 것으로 읽힌다(심사 시작은 위 버튼). */}
            <Btn block onClick={save} disabled={busy || axes.length === 0}>
              {busy ? '저장 중…' : '저장 · 기준 다시 적용'}
            </Btn>
          </div>
        </div>

        <div className={common.stack}>
          <SectionHead
            aside={
              // 축별 막대의 합(한 레코드가 여러 축에서 걸린다)은 이 수보다 크다.
              // 설명이 없으면 헤더 숫자가 틀린 것처럼 보인다.
              <span className={[common.num, common['cell-mute']].join(' ')}>
                미달 {fmt(failTotal)}건 · 한 건이 여러 축에 걸릴 수 있음
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

      {/* 실행 결과 — 다른 노드 화면과 같은 것을 본다. 미리보기는 레코드에 적재되지 않아
          위 통과율에는 안 잡히고 여기서만 보인다. */}
      <div className={common.stack}>
        <SectionHead>심사 결과</SectionHead>
        <RunPanel
          datasetId={dsId}
          node={node}
          upstreamRun={upstreamRunOf(nodes, flow?.flow, index)}
        />
      </div>
    </div>
  );
}
