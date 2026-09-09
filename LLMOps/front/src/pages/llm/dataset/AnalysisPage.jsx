import React, { useCallback, useEffect, useState } from 'react';

import { getCoverage, listRecords, runThumbUrl } from '@src/apis/llm/dataset';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import {
  Badge,
  Btn,
  DataTable,
  DatasetTabs,
  PageHeader,
  ProgressBar,
  SectionHead,
  listBase,
  useDatasetName,
  useDatasetNav,
} from './components';
import {
  COVERAGE as SAMPLE_COVERAGE,
  UMAP_GAPS,
  UMAP_LABEL,
  UMAP_POS,
} from './mock';
import { CAP_COLOR, FLAG_TONE, fmt } from './lib/format';
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
  SAMPLE_COVERAGE.forEach((c) => {
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
 * 판정(`flag`)은 서버가 두 수를 같이 보고 내린다 — FE 가 다시 판정하면 기준이 갈린다.
 *
 * ⚠️ 아래 **유사도 분포(UMAP)** 섹션만은 아직 예시 데이터다. 임베딩·투영을 계산하는
 * BE 가 없어서(엔드포인트 자체가 없다) 화면에 그렇게 명시해 둔다 — 표시가 없으면
 * 사용자가 이 그림을 자기 데이터의 분포로 읽는다.
 */
export default function AnalysisPage() {
  const { wsId, dsId, go } = useDatasetNav();
  const dsName = useDatasetName(dsId);

  const [cov, setCov] = useState(null);
  const [records, setRecords] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [c, r] = await Promise.all([
      getCoverage(dsId),
      // 유형별 표본을 보여주려고 한 페이지만 받는다. 레코드를 유형으로 거르는
      // 파라미터가 없어 화면에서 고른다 — 이 페이지에 없으면 표본이 안 잡힌다.
      listRecords(dsId, { limit: 100 }),
    ]);
    setLoading(false);
    if (c.status !== STATUS_SUCCESS) {
      errorToastMessage(c.error, c.message);
      return;
    }
    setCov(c.result);
    if (r.status === STATUS_SUCCESS) setRecords(r.result?.records || []);
  }, [dsId]);

  useEffect(() => {
    load();
  }, [load]);

  const coverage = cov?.coverage || [];
  // 0 을 그대로 쓰면 대개 데이터가 없는 첫 유형이 잡혀 상세가 빈 채로 열린다.
  // 사용자가 아직 아무것도 고르지 않았을 때만 데이터가 있는 첫 유형으로 보낸다.
  const firstWithData = coverage.findIndex((c) => (c.record_count || 0) > 0);
  const shown =
    selected === null ? (firstWithData >= 0 ? firstWithData : 0) : selected;
  const cap = coverage[shown] || null;
  const rec = cap
    ? records.find((r) => r.capability === cap.capability) || null
    : null;
  // 막대는 가장 큰 유형을 기준으로 채운다 — 고정 분모를 쓰면 전체가 작을 때 다 비어 보인다.
  const maxPct = Math.max(1, ...coverage.map((c) => c.pct || 0));

  return (
    <div className={style.page}>
      <PageHeader
        title={dsName}
        back={{ to: listBase(wsId), label: '데이터셋' }}
        meta={
          cov
            ? `레코드 ${fmt(cov.total_records || 0)}건 · 원본 ${fmt(cov.dataset_assets || 0)}건`
            : ''
        }
      />
      <DatasetTabs active='분포 분석' />

      <div className={common.stack}>
        <SectionHead
          aside={
            <span className={common.prose}>
              데이터 수와 레코드 수를 함께 봐야 원인이 갈립니다
            </span>
          }
        >
          데이터 유형
        </SectionHead>

        <DataTable
          cols={[
            '데이터 유형',
            // 막대와 숫자가 같은 값이라 '비율'·'%' 로 두면 컬럼이 중복돼 보인다.
            '분포',
            '비율',
            '레코드',
            '데이터',
            '판정',
            '조치',
          ]}
          loading={loading}
          onRowClick={setSelected}
          rows={coverage.map((c) => {
            // 색과 조치는 다른 판단이다. 한 변수로 묶으면 '데이터 없음' 을 덜 강조하려다
            // 그 행의 '데이터 추가' 버튼까지 없애게 된다(빈 데이터셋에서는 전 유형이
            // '데이터 없음' 이라 업로드 진입로가 통째로 사라진다).
            // 조치: 충분하지 않으면 언제나 할 일이 있다.
            const actionable = c.flag !== '충분';
            // 색: 아직 안 만든 것까지 빨갛게 칠하면 전부 고장난 것처럼 보인다.
            //     손대야 할 것은 '있는데 모자란' 유형이다.
            const empty = c.flag === '데이터 없음';
            const bad = actionable && !empty;
            return [
              {
                node: (
                  <span
                    className={[
                      common.num,
                      bad ? common.danger : common['cell-mute'],
                    ].join(' ')}
                  >
                    {c.capability}
                  </span>
                ),
              },
              {
                node: (
                  <ProgressBar
                    value={Math.min(
                      100,
                      Math.round(((c.pct || 0) / maxPct) * 100),
                    )}
                    tone={
                      c.flag === '데이터 없음'
                        ? 'red'
                        : bad
                          ? 'orange'
                          : 'primary'
                    }
                  />
                ),
              },
              `${c.pct ?? 0}%`,
              fmt(c.record_count || 0),
              c.asset_count === null || c.asset_count === undefined
                ? '—'
                : fmt(c.asset_count),
              {
                node: (
                  <Badge tone={FLAG_TONE[c.flag] || 'gray'}>{c.flag}</Badge>
                ),
              },
              {
                node: actionable ? (
                  <Btn
                    size='sm'
                    fill='outline'
                    tone={c.flag === '생성 부족' ? 'primary' : 'gray'}
                    onClick={() =>
                      go(c.flag === '생성 부족' ? '/flow/generate' : '/upload')
                    }
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
        {!loading && coverage.length === 0 && (
          <span className={common.prose}>
            아직 유형을 판정할 레코드가 없습니다.
          </span>
        )}
      </div>

      <div className={style['analysis-grid']}>
        <div className={common.stack}>
          <SectionHead
            aside={
              <span className={[common.num, common['cell-mute']].join(' ')}>
                SigLIP-so400m · UMAP
              </span>
            }
          >
            분포
          </SectionHead>

          {/* 이 그림은 아직 이 데이터셋의 것이 아니다. 임베딩·투영 BE 가 생기기 전까지
              예시로 둔다 — 말없이 두면 자기 데이터의 분포로 읽힌다. */}
          <span className={[common.note, common['note-info']].join(' ')}>
            <span className={common['note-title']}>예시 데이터</span>
            <span className={common['note-body']}>
              유사도 분포는 아직 서버에서 계산하지 않습니다. 아래 그림은 화면
              구성을 보여주는 예시이며 이 데이터셋의 실제 분포가 아닙니다.
            </span>
          </span>

          <div className={[common.card, style.scatter].join(' ')}>
            <svg
              viewBox='0 0 560 296'
              className={style['scatter-svg']}
              role='img'
              aria-label='유형별 유사도 분포(예시)'
            >
              {POINTS.map((p, i) => (
                // eslint-disable-next-line react/no-array-index-key
                <circle
                  key={i}
                  cx={p.x.toFixed(1)}
                  cy={p.y.toFixed(1)}
                  r='2.7'
                  fill={CAP_COLOR[p.k]}
                  opacity='0.7'
                />
              ))}

              {Object.entries(UMAP_LABEL).map(([k, [x, y]]) => (
                <text
                  key={k}
                  x={x}
                  y={y}
                  textAnchor='middle'
                  fontFamily='SpoqaM, sans-serif'
                  fontSize='11'
                  fontWeight='500'
                  fill={CAP_COLOR[k]}
                  stroke='#ffffff'
                  strokeWidth='4'
                  style={{ paintOrder: 'stroke' }}
                >
                  {k}
                </text>
              ))}

              {/* 빈 영역을 점선으로 표시한다 — 점이 없는 곳이 곧 못 만든 유형이다. */}
              {UMAP_GAPS.map((g) => {
                const cx = g.x + g.w / 2;
                const cy = g.y + g.h / 2;
                return (
                  <g key={g.k}>
                    <rect
                      x={g.x}
                      y={g.y}
                      width={g.w}
                      height={g.h}
                      rx='4'
                      fill='rgba(250,78,87,0.05)'
                      stroke='#fa4e57'
                      strokeDasharray='4 3'
                    />
                    <text
                      x={cx}
                      y={cy - 2}
                      textAnchor='middle'
                      fontFamily='SpoqaM, sans-serif'
                      fontSize='11'
                      fontWeight='500'
                      fill='#d91a0c'
                      stroke='#ffffff'
                      strokeWidth='4'
                      style={{ paintOrder: 'stroke' }}
                    >
                      {g.lab}
                    </text>
                    <text
                      x={cx}
                      y={cy + 13}
                      textAnchor='middle'
                      fontFamily='SpoqaM, sans-serif'
                      fontSize='10'
                      fill='#d91a0c'
                      opacity='0.85'
                      stroke='#ffffff'
                      strokeWidth='4'
                      style={{ paintOrder: 'stroke' }}
                    >
                      {g.sub}
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
            {rec ? (
              <>
                {rec.lineage?.run_id && rec.asset_ref && (
                  <span className={style['detail-shot']}>
                    <img
                      src={runThumbUrl(dsId, rec.lineage.run_id, rec.asset_ref)}
                      alt={rec.record_key}
                      style={{ width: '100%', borderRadius: 8 }}
                    />
                    <span className={style['detail-shot-id']}>
                      {rec.record_key}
                    </span>
                  </span>
                )}
                <span className={style['qa-block']}>
                  <span className={common.eyebrow}>Q</span>
                  <span className={common.prose} style={{ color: '#121619' }}>
                    {rec.question}
                  </span>
                </span>
                <span className={style['qa-block']}>
                  <span className={common.eyebrow}>A</span>
                  <span className={common.prose}>{rec.answer}</span>
                </span>
                <Btn
                  size='md'
                  block
                  fill='outline'
                  tone='gray'
                  onClick={() => go(`/record/${rec.record_key}`)}
                >
                  상세 보기 →
                </Btn>
              </>
            ) : (
              <span className={common.prose}>
                {cap
                  ? `'${cap.capability}' 유형의 표본이 최근 레코드에 없습니다.`
                  : '유형을 선택하세요.'}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
