import React, { useState } from 'react';
import { useHistory, useParams } from 'react-router-dom';

import BorderTable from '@src/components/molecules/BorderTable';

import { Badge, Btn, PageHeader, SearchField, dsBase } from './components';
import { DATASETS, STATE_TONE } from './mock';
import { PASS_RANGE, fmt, isPassRateOut } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

/**
 * 데이터셋 목록.
 *
 * 통과율을 숫자만 보여주지 않고 정상 범위(40–85%) 막대 위에 찍는다. 82% 가 좋은
 * 값인지 나쁜 값인지는 범위를 봐야 알 수 있고, 85% 를 넘으면 게이트가 헐거워
 * 걸러지지 않는 상태라 오히려 나쁜 신호다.
 */
export default function DatasetListPage() {
  const history = useHistory();
  const { id: wsId } = useParams();
  const [query, setQuery] = useState('');
  const [lo, hi] = PASS_RANGE;
  const unreviewed = DATASETS.reduce((acc, d) => acc + d.unrev, 0);
  const rows = query
    ? DATASETS.filter((d) => d.id.toLowerCase().includes(query.toLowerCase()))
    : DATASETS;

  const columns = [
    {
      name: '데이터셋',
      selector: 'id',
      sortable: true,
      grow: 2,
      cell: (d) => (
        <span className={style['list-name']}>
          <span className={style['list-name-text']}>{d.id}</span>
          <span className={style['list-badges']}>
            <Badge tone={STATE_TONE[d.state]}>{d.state}</Badge>
            {d.recs === 0 && (
              <span className={style['list-hint']}>데이터 소스를 연결해 시작하세요</span>
            )}
          </span>
        </span>
      ),
    },
    {
      name: '레코드',
      selector: 'recs',
      sortable: true,
      right: true,
      cell: (d) => (
        <span className={common['cell-num']}>{d.recs ? fmt(d.recs) : '—'}</span>
      ),
    },
    {
      name: '이미지 토큰',
      selector: 'imgTok',
      sortable: true,
      right: true,
      cell: (d) => (
        <span className={[common['cell-num'], common.mute].join(' ')}>
          {d.recs ? `${d.imgTok.toFixed(1)}M` : '—'}
        </span>
      ),
    },
    {
      // 숫자만으로는 82% 가 좋은지 알 수 없어 정상 범위 막대 위에 값을 찍는다.
      name: `통과율 ${lo}–${hi}%`,
      selector: 'pass',
      sortable: true,
      cell: (d) => {
        if (!d.recs) return <span className={common['cell-num']}>—</span>;
        const out = isPassRateOut(d.pass);
        return (
          <span className={style['list-pass-row']}>
            <span
              className={[
                style['list-pass-value'],
                out ? style['list-pass-out'] : '',
              ].join(' ')}
            >
              {d.pass}%
            </span>
            {out && <Badge tone="fail">범위 밖</Badge>}
          </span>
        );
      },
    },
    {
      name: '미검수',
      selector: 'unrev',
      sortable: true,
      right: true,
      cell: (d) => (
        <span
          className={[common['cell-num'], d.unrev ? common.warn : common.mute].join(' ')}
        >
          {d.unrev ? fmt(d.unrev) : '0'}
        </span>
      ),
    },
    {
      name: '버전',
      selector: 'ver',
      sortable: true,
      right: true,
      cell: (d) => (
        <span className={[common['cell-num'], common.mute].join(' ')}>{d.ver}</span>
      ),
    },
    {
      name: '갱신',
      selector: 'upd',
      sortable: true,
      right: true,
      cell: (d) => (
        <span className={[common['cell-num'], common.mute].join(' ')}>{d.upd}</span>
      ),
    },
    {
      name: '',
      selector: 'open',
      sortable: false,
      right: true,
      cell: (d) => (
        <Btn
          size="sm"
          fill="outline"
          tone="gray"
          onClick={() => history.push(`${dsBase(wsId, d.id)}/flow`)}
        >
          열기
        </Btn>
      ),
    },
  ];

  return (
    <div className={style.page}>
      <PageHeader
        title="데이터셋 목록"
        meta={`${DATASETS.length}개 데이터셋 · 미검수 합계 ${fmt(unreviewed)}건`}
        actions={<Btn size="md">＋ 새 데이터셋</Btn>}
      />

      {/* 검색은 플랫폼 입력으로 표 위에 둔다 — 다른 LLM 화면의 표도 자체 검색 상자를
          끄고(hideSearchBox) 바깥에서 거르는 방식을 쓴다. */}
      <div className={common['row-between']}>
        <SearchField
          placeholder="데이터셋 이름으로 검색"
          value={query}
          onChange={setQuery}
        />
      </div>

      <BorderTable
        columns={columns}
        data={rows}
        loading={false}
        selectableRows={false}
        hideSearchBox
        hideButtons
        onRowClick={(row) => history.push(`${dsBase(wsId, row.id)}/flow`)}
      />
    </div>
  );
}
