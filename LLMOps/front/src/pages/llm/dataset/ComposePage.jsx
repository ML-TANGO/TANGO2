import React, { useState } from 'react';

import {
  Badge, Btn, Checkbox, DatasetTabs, PageHeader, ProgressBar,
  SectionHead, Select, Slider, listBase, useDatasetNav,
} from './components';
import { MIX, POOL, VERIFY_FAILS, VERIFY_ROWS } from './mock';
import { allocate, fmt, tokenTotals } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

const SPLIT_COLOR = ['#2d76f8', '#93baff', '#dee9ff'];
const SPLIT_KEYS = ['train', 'validation', 'test'];

/**
 * 구성 · 분할.
 *
 * 분리 기준이 '문서 ID' 가 기본인 이유: 같은 문서의 다른 페이지가 train 과 test 로
 * 갈리면 사실상 정답을 미리 본 셈이라 평가 점수가 부풀려진다.
 *
 * 학습 형식 검사를 통과해야 데이터셋을 만들 수 있게 막는다. 형식 오류는 학습을
 * 시작하고 한참 뒤에 터지는데, 그때는 GPU 시간을 이미 버린 뒤다.
 */
export default function ComposePage() {
  const { wsId, dsId, go } = useDatasetNav();

  const [weights, setWeights] = useState(Object.fromEntries(MIX.map((m) => [m.k, m.v])));
  const [split, setSplit] = useState({ train: 80, validation: 10, test: 10 });
  const [splitBy, setSplitBy] = useState('문서 ID');
  const [verify, setVerify] = useState('idle');
  const [failOpen, setFailOpen] = useState(false);

  const { counts } = allocate(MIX, weights, POOL);
  const totals = tokenTotals(MIX, counts);
  const splitSum = SPLIT_KEYS.reduce((acc, k) => acc + split[k], 0) || 1;
  const weightSum = Object.values(weights).reduce((a, b) => a + b, 0) || 1;

  const runVerify = () => {
    setVerify('busy');
    setTimeout(() => setVerify('done'), 1200);
  };

  return (
    <div className={style.page}>
      <PageHeader
        title={dsId}
        back={{ to: listBase(wsId), label: '데이터셋 목록' }}
      />
      <DatasetTabs active="구성 · 분할" />

      <div className={style['compose-grid']}>
        <div className={common['stack-lg']}>
          <div className={common.stack}>
            <SectionHead aside={<span className={[common.num, common['cell-mute']].join(' ')}>풀 {fmt(POOL)}</span>}>
              구성
            </SectionHead>
            <div className={common['card-pad']} style={{ paddingTop: 8 }}>
              {MIX.map((m) => (
                <span key={m.k} className={style['mix-row']}>
                  <span className={[common.num, common['cell-mute'], common.truncate].join(' ')}>{m.k}</span>
                  <Slider min={0} max={50} value={weights[m.k]} onChange={(v) => setWeights({ ...weights, [m.k]: v })} />
                  <span className={common['cell-num']}>{Math.round((weights[m.k] / weightSum) * 100)}%</span>
                  <span className={[common['cell-num'], common.mute].join(' ')}>{fmt(counts[m.k])}</span>
                </span>
              ))}

              {/* 합계가 항상 풀과 정확히 맞는다 — 잔여분을 가장 큰 유형에 몰아준 결과다. */}
              <span className={style.totals}>
                {[
                  ['건수', fmt(totals.recs)],
                  ['이미지 토큰', `${(totals.img / 1e6).toFixed(2)}M`],
                  ['텍스트 토큰', `${(totals.txt / 1e6).toFixed(2)}M`],
                  ['합계', `${((totals.img + totals.txt) / 1e6).toFixed(2)}M`],
                ].map(([k, v]) => (
                  <span key={k} className={style['total-cell']}>
                    <span className={style['total-value']}>{v}</span>
                    <span className={common['tile-label']}>{k}</span>
                  </span>
                ))}
              </span>
            </div>
          </div>

          <div className={common.stack}>
            <SectionHead
              aside={(
                <span className={[common.num, common['cell-mute']].join(' ')}>
                  {split.train} : {split.validation} : {split.test}
                </span>
              )}
            >
              분할
            </SectionHead>

            <div className={[common['card-pad'], common.stack].join(' ')}>
              {SPLIT_KEYS.map((k) => (
                <span key={k} className={style['split-row']}>
                  <span className={[common.num, common['cell-mute']].join(' ')}>{k}</span>
                  <Slider min={0} max={100} value={split[k]} onChange={(v) => setSplit({ ...split, [k]: v })} />
                  <span className={common['cell-num']}>{Math.round((split[k] / splitSum) * 100)}%</span>
                  <span className={[common['cell-num'], common.mute].join(' ')}>
                    {fmt(Math.round((totals.recs * split[k]) / splitSum))}
                  </span>
                </span>
              ))}

              <span className={style['split-bar']}>
                {SPLIT_KEYS.map((k, i) => (
                  <i key={k} style={{ width: `${(split[k] / splitSum) * 100}%`, background: SPLIT_COLOR[i] }} />
                ))}
              </span>

              <span className={[style['split-row'], common.divider].join(' ')} style={{ gridTemplateColumns: '110px minmax(0,1fr)', paddingTop: 16 }}>
                <span className={common.label}>분리 기준</span>
                <span style={{ maxWidth: 220 }}>
                  <Select value={splitBy} onChange={setSplitBy} options={['문서 ID', '이미지', '무작위']} />
                </span>
              </span>

              {/* 누출 검사 — 같은 문서가 갈리거나 평가 문항이 학습에 섞이면 점수가 거짓이 된다. */}
              <span className={common.stack}>
                {[['페이지 갈림', '0건 · 통과'], ['평가 문항 섞임', '0건 · 통과']].map(([k, v]) => (
                  <span key={k} className={style['check-line']}>
                    <span className={common.label}>{k}</span>
                    <Badge tone="pass">{v}</Badge>
                  </span>
                ))}
              </span>
            </div>
          </div>
        </div>

        <div className={common.stack}>
          <SectionHead>학습 형식 검사</SectionHead>
          <div className={[common['card-pad'], common.stack].join(' ')}>
            {verify === 'idle' && (
              <>
                {['Qwen3-VL', 'Gemma 3', 'HuggingFace messages'].map((k) => (
                  <Checkbox key={k} checked onChange={() => {}} label={k} />
                ))}
                <span className={common.prose}>실제 모델이 읽을 수 있는지 미리 확인합니다.</span>
              </>
            )}

            {verify === 'busy' && <ProgressBar value={64} height={8} />}

            {verify === 'done' && (
              <>
                {VERIFY_ROWS.map((v) => (
                  <span key={v.k} className={style['check-line']}>
                    <span className={common.label}>{v.k}</span>
                    <Badge tone={v.tone}>{v.v}</Badge>
                  </span>
                ))}

                {!failOpen ? (
                  <button type="button" className={style['link-btn']} onClick={() => setFailOpen(true)}>
                    실패 {VERIFY_FAILS.length}건 보기 →
                  </button>
                ) : (
                  <span className={common.stack}>
                    {VERIFY_FAILS.map((v) => (
                      <button
                        key={v.rid}
                        type="button"
                        className={style['fail-link']}
                        onClick={() => go(`/record/${v.rid}`)}
                      >
                        {v.rid} — {v.why}
                      </button>
                    ))}
                  </span>
                )}
              </>
            )}

            <Btn block fill="outline" disabled={verify !== 'idle'} onClick={runVerify}>
              {verify === 'done' ? '검사 완료' : verify === 'busy' ? '검사 중…' : '학습 형식 미리 검사'}
            </Btn>
          </div>

          <div className={[common['card-pad'], common['row-between']].join(' ')}>
            <span className={common.prose}>
              {verify === 'done' ? `검사 완료 · ${fmt(totals.recs)}건` : '학습 형식 검사를 마쳐야 만들 수 있습니다'}
            </span>
            <Btn size="md" disabled={verify !== 'done'} onClick={() => go('/compose/history')}>
              데이터셋 v0.4.0 생성
            </Btn>
          </div>
        </div>
      </div>
    </div>
  );
}
