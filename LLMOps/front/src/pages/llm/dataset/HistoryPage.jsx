import React, { useState } from 'react';

import {
  Badge, Btn, DataTable, DatasetTabs, PageHeader, listBase, useDatasetNav,
} from './components';
import { RECORDS, VERSIONS } from './mock';
import { delta, fmt } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

const SPLIT_TONE = { train: 'primary', validation: 'gray', test: 'gray' };

/**
 * 버전 이력 → 버전별 레코드.
 *
 * 버전 목록은 "무엇이 나아졌나"를 보는 화면이라 절대값보다 직전 대비 증감이 중요하다.
 * 생성 모델과 심사 모델이 같은 채로 만들어진 버전은 자가심사라 통과율을 믿을 수 없으므로
 * 따로 표시한다.
 */
export default function HistoryPage() {
  const { wsId, dsId, go } = useDatasetNav();
  const [openVersion, setOpenVersion] = useState(null);

  if (openVersion !== null) {
    const v = VERSIONS[openVersion];
    return (
      <div className={style.page}>
        <PageHeader
          title={`${v.v} 레코드`}
          meta={`${fmt(v.recs)}건 · 통과율 ${v.pass}% · ${v.prompt}`}
          actions={<Btn size="md" fill="outline" tone="gray" onClick={() => setOpenVersion(null)}>← 버전 목록</Btn>}
        />

        <DataTable
          cols={['레코드', '데이터 유형', '질문', '최저 축 · 점수', '분할', '']}
          onRowClick={(i) => go(`/record/${RECORDS[i].id}`)}
          rows={RECORDS.map((r) => {
            // 최저 축이 그 레코드의 실질 품질이다 — 나머지가 높아도 하나가 낮으면 쓸 수 없다.
            const worst = Object.entries(r.s).sort((a, b) => a[1] - b[1])[0];
            return [
              r.id,
              r.cap,
              { node: <span className={[common['cell-mute'], common.truncate].join(' ')}>{r.q}</span> },
              worst[1].toFixed(2),
              { node: <Badge tone={SPLIT_TONE[r.split]}>{r.split}</Badge> },
              { node: <span className={common['cell-mute']}>열기 →</span> },
            ];
          })}
        />
      </div>
    );
  }

  return (
    <div className={style.page}>
      <PageHeader
        title={dsId}
        back={{ to: listBase(wsId), label: '데이터셋 목록' }}
        meta={`${VERSIONS.length}개 버전 · 최신 ${VERSIONS[VERSIONS.length - 1].v}`}
      />
      <DatasetTabs active="이력" />

      <DataTable
        cols={['버전', '생성', '레코드', '통과율', '사람 검수', '심사 모델', '']}
        onRowClick={(i) => setOpenVersion(VERSIONS.length - 1 - i)}
        rows={VERSIONS.slice()
          .reverse()
          .map((v) => {
            const i = VERSIONS.indexOf(v);
            const prev = VERSIONS[i - 1];
            const sameModel = v.gen === v.jud;
            const deltaCell = (value, d) => ({
              node: (
                <span className={style['delta-cell']}>
                  <span className={style['delta-value']}>{value}</span>
                  {d && (
                    <span
                      className={[
                        style['delta-diff'],
                        d.up ? style['delta-up'] : style['delta-down'],
                      ].join(' ')}
                    >
                      {d.txt}
                    </span>
                  )}
                </span>
              ),
            });
            return [
              {
                node: (
                  <span className={common['row-flex']}>
                    <span
                      className={[common.num, common.cell].join(' ')}
                      style={{ fontFamily: 'SpoqaB' }}
                    >
                      {v.v}
                    </span>
                    {v.isNew && <Badge tone="primary">신규</Badge>}
                  </span>
                ),
              },
              v.d,
              deltaCell(fmt(v.recs), delta(prev, v, 'recs')),
              deltaCell(`${v.pass}%`, delta(prev, v, 'pass', '%')),
              deltaCell(fmt(v.hum), delta(prev, v, 'hum')),
              {
                node: (
                  <span className={common['row-flex']}>
                    <span className={[common.num, common['cell-mute'], common.truncate].join(' ')}>
                      {v.jud}
                    </span>
                    {/* 자기 결과를 자기가 채점한 버전 — 통과율을 그대로 믿으면 안 된다. */}
                    {sameModel && <Badge tone="fail">동일 모델</Badge>}
                  </span>
                ),
              },
              { node: <span className={common['cell-mute']}>열기 →</span> },
            ];
          })}
      />
    </div>
  );
}
