import React, { useState } from 'react';

import {
  Badge, Btn, DataTable, DatasetTabs, Frame, GateRibbon, PageHeader, ProgressBar,
  SectionHead, listBase, useDatasetNav,
} from './components';
import { COVERAGE, RECORDS, UMAP_GAPS, UMAP_LABEL, UMAP_POS } from './mock';
import { SHOTS } from './lib/frames';
import { AXES, CAP_COLOR, FLAG_TONE, THRESHOLDS, fmt } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

/**
 * 결정론 산점도.
 *
 * 매번 같은 그림이 나와야 한다. 분포가 새로고침할 때마다 달라지면 "저번보다 나빠졌나"를
 * 판단할 수 없다. 그래서 난수 대신 고정 시드 LCG 를 쓴다.
 */
function scatter() {
  let seed = 20260806;
  const rnd = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    return seed / 0x7fffffff;
  };
  // 균등난수 4개를 더해 대략 정규분포 모양으로 만든다(군집이 뭉치게).
  const gauss = () => (rnd() + rnd() + rnd() + rnd() - 2) / 1.4;

  const pts = [];
  COVERAGE.forEach((c) => {
    const p = UMAP_POS[c.k];
    for (let i = 0; i < Math.round(c.pct * 6); i += 1) {
      pts.push({ x: p[0] + gauss() * 26, y: p[1] + gauss() * 20, k: c.k });
    }
  });
  return pts;
}

const POINTS = scatter();

/**
 * 분포 분석.
 *
 * 레코드 수와 원본 데이터 수를 나란히 보여준다. 둘을 함께 봐야 "데이터가 없어서"인지
 * "데이터는 있는데 생성이 안 돼서"인지가 갈리고, 조치가 업로드냐 생성이냐로 나뉜다.
 */
export default function AnalysisPage() {
  const { wsId, dsId, go } = useDatasetNav();
  const [selected, setSelected] = useState(4);

  const cap = COVERAGE[selected];
  const rec = RECORDS.find((r) => r.cap === cap.k) || RECORDS[0];

  return (
    <div className={style.page}>
      <PageHeader
        title={dsId}
        back={{ to: listBase(wsId), label: '데이터셋 목록' }}
      />
      <DatasetTabs active="분포 분석" />

      <div className={common.stack}>
        <SectionHead aside={<span className={common.prose}>데이터 수와 레코드 수를 함께 봐야 원인이 갈립니다</span>}>
          데이터 유형
        </SectionHead>

        <DataTable
          cols={['데이터 유형', '비율', '%', '레코드', '데이터', '판정', '조치']}
          onRowClick={setSelected}
          rows={COVERAGE.map((c) => {
            const bad = c.flag !== '충분';
            return [
              {
                node: (
                  <span className={[common.num, bad ? common.danger : common['cell-mute']].join(' ')}>
                    {c.k}
                  </span>
                ),
              },
              {
                node: (
                  <ProgressBar
                    value={Math.min(100, Math.round((c.pct / 45) * 100))}
                    tone={c.flag === '데이터 없음' ? 'red' : bad ? 'orange' : 'primary'}
                  />
                ),
              },
              `${c.pct}%`,
              fmt(c.recs),
              c.assets === null ? '—' : fmt(c.assets),
              { node: <Badge tone={FLAG_TONE[c.flag]}>{c.flag}</Badge> },
              {
                node: bad ? (
                  <Btn
                    size="sm"
                    fill="outline"
                    tone={c.flag === '생성 부족' ? 'primary' : 'gray'}
                    onClick={() => go(c.flag === '생성 부족' ? '/flow/generate' : '/upload')}
                  >
                    {c.flag === '생성 부족' ? '생성하기' : '데이터 추가'}
                  </Btn>
                ) : (
                  <span />
                ),
              },
            ];
          })}
        />
      </div>

      <div className={style['analysis-grid']}>
        <div className={common.stack}>
          <SectionHead aside={<span className={[common.num, common['cell-mute']].join(' ')}>SigLIP-so400m · UMAP</span>}>
            분포
          </SectionHead>

          <div className={[common.card, style.scatter].join(' ')}>
            <svg viewBox="0 0 560 296" className={style['scatter-svg']} role="img" aria-label="유형별 유사도 분포">
              {POINTS.map((p, i) => (
                // eslint-disable-next-line react/no-array-index-key
                <circle key={i} cx={p.x.toFixed(1)} cy={p.y.toFixed(1)} r="2.7" fill={CAP_COLOR[p.k]} opacity="0.7" />
              ))}

              {Object.entries(UMAP_LABEL).map(([k, [x, y]]) => (
                <text
                  key={k} x={x} y={y} textAnchor="middle"
                  fontFamily="SpoqaM, sans-serif" fontSize="11" fontWeight="500"
                  fill={CAP_COLOR[k]} stroke="#ffffff" strokeWidth="4" style={{ paintOrder: 'stroke' }}
                >
                  {k}
                </text>
              ))}

              {/* 빈 영역을 점선으로 표시한다 — 점이 없는 곳이 곧 못 만든 유형이다. */}
              {UMAP_GAPS.map((g) => {
                const on = COVERAGE[selected].k === g.k;
                const cx = g.x + g.w / 2;
                const cy = g.y + g.h / 2;
                const col = on ? '#164abe' : '#d91a0c';
                return (
                  <g
                    key={g.k}
                    style={{ cursor: 'pointer' }}
                    onClick={() => setSelected(COVERAGE.findIndex((c) => c.k === g.k))}
                  >
                    <rect
                      x={g.x} y={g.y} width={g.w} height={g.h} rx="4"
                      fill={on ? 'rgba(45,118,248,0.10)' : 'rgba(250,78,87,0.05)'}
                      stroke={on ? '#2d76f8' : '#fa4e57'} strokeDasharray="4 3"
                    />
                    <text
                      x={cx} y={cy - 2} textAnchor="middle"
                      fontFamily="SpoqaM, sans-serif" fontSize="11" fontWeight="500"
                      fill={col} stroke="#ffffff" strokeWidth="4" style={{ paintOrder: 'stroke' }}
                    >
                      {g.lab}
                    </text>
                    <text
                      x={cx} y={cy + 13} textAnchor="middle"
                      fontFamily="SpoqaM, sans-serif" fontSize="10"
                      fill={col} opacity="0.85" stroke="#ffffff" strokeWidth="4" style={{ paintOrder: 'stroke' }}
                    >
                      {on ? '선택됨' : g.sub}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        </div>

        <div className={common.stack}>
          <SectionHead>선택 상세</SectionHead>
          <div className={[common['card-pad'], common.stack].join(' ')}>
            <span className={style['detail-shot']}>
              <Frame spec={SHOTS[rec.shot]} ariaLabel={rec.id} />
              <span className={style['detail-shot-id']}>{rec.id}</span>
            </span>
            <span className={style['qa-block']}>
              <span className={common.eyebrow}>Q</span>
              <span className={common.prose} style={{ color: '#121619' }}>{rec.q}</span>
            </span>
            <span className={style['qa-block']}>
              <span className={common.eyebrow}>A</span>
              <span className={common.prose}>{rec.a}</span>
            </span>
            <GateRibbon axes={AXES} scores={rec.s} thresholds={THRESHOLDS} />
            <Btn size="md" block fill="outline" tone="gray" onClick={() => go(`/record/${rec.id}`)}>
              상세 보기 →
            </Btn>
          </div>
        </div>
      </div>
    </div>
  );
}
