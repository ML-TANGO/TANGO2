import React, { useCallback, useEffect, useState } from 'react';

import { listVersions } from '@src/apis/llm/dataset';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import {
  Badge,
  Btn,
  DataTable,
  DatasetTabs,
  PageHeader,
  SectionHead,
  listBase,
  useDatasetName,
  useDatasetNav,
} from './components';
import { fmt } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

/**
 * 버전 이력.
 *
 * "무엇이 나아졌나"를 보는 화면이라 절대값보다 직전 대비 증감이 중요하다. 증감은
 * 서버가 계산해 준다(`delta`) — FE 가 다시 빼면 목록 정렬이 바뀔 때 기준 행이 달라져
 * 서로 다른 값이 나온다.
 *
 * 생성 모델과 심사 모델이 같은 채로 만들어진 버전은 자가심사라 통과율을 믿을 수 없으므로
 * 따로 표시한다.
 *
 * 버전 상세는 **그 버전의 구성**(혼합비 · 분할 · 임계값 · 모델)을 보여준다. 버전에 담긴
 * 레코드만 골라 오는 API 는 아직 없다 — 전체 레코드를 보여주면서 "이 버전의 레코드"라고
 * 하면 거짓이 된다. 검수 화면으로 보내는 링크만 둔다.
 */
export default function HistoryPage() {
  const { wsId, dsId, go } = useDatasetNav();
  const dsName = useDatasetName(dsId);
  const [versions, setVersions] = useState([]);
  const [openId, setOpenId] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await listVersions(dsId);
    setLoading(false);
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return;
    }
    setVersions(res.result?.versions || []);
  }, [dsId]);

  useEffect(() => {
    load();
  }, [load]);

  const cur = versions.find((v) => v.id === openId) || null;

  if (cur) {
    const rows = (obj) =>
      Object.entries(obj || {}).map(([k, v]) => [k, String(v)]);
    return (
      <div className={style.page}>
        <PageHeader
          title={`${cur.version} 구성`}
          meta={`${fmt(cur.record_count || 0)}건 · 통과율 ${cur.pass_rate ?? '—'}% · 사람 검수 ${fmt(cur.human_reviewed || 0)}건`}
          actions={
            <Btn
              size='md'
              fill='outline'
              tone='gray'
              onClick={() => setOpenId(null)}
            >
              ← 버전 목록
            </Btn>
          }
        />

        <div className={common.stack}>
          <SectionHead>만들 때 쓴 것</SectionHead>
          <DataTable
            cols={['항목', '값']}
            rows={[
              ['생성 모델', cur.gen_model || '—'],
              ['심사 모델', cur.judge_model || '—'],
              ['프롬프트', cur.prompt_name || '—'],
              ['분할 기준', cur.split_by || '—'],
              ['릴리스', cur.create_datetime || '—'],
            ]}
          />
        </div>

        <div className={common.stack}>
          <SectionHead>데이터 유형 혼합비</SectionHead>
          <DataTable cols={['유형', '가중치']} rows={rows(cur.mix)} />
        </div>

        <div className={common.stack}>
          <SectionHead>분할</SectionHead>
          <DataTable cols={['분할', '비율']} rows={rows(cur.split)} />
        </div>

        <div className={common.stack}>
          <SectionHead>심사 임계값</SectionHead>
          <DataTable cols={['축', '기준값']} rows={rows(cur.thresholds)} />
        </div>

        <div className={[common['card-pad'], common['row-between']].join(' ')}>
          <span className={common.prose}>
            이 버전에 담긴 레코드만 골라 보는 기능은 아직 없습니다.
          </span>
          <Btn size='md' onClick={() => go('/review')}>
            검수 화면으로 →
          </Btn>
        </div>
      </div>
    );
  }

  const latest = versions.length ? versions[versions.length - 1] : null;

  const deltaCell = (value, d, unit = '') => ({
    node: (
      <span className={style['delta-cell']}>
        <span className={style['delta-value']}>{value}</span>
        {!!d && (
          <span
            className={[
              style['delta-diff'],
              d > 0 ? style['delta-up'] : style['delta-down'],
            ].join(' ')}
          >
            {d > 0 ? `+${fmt(d)}${unit}` : `−${fmt(Math.abs(d))}${unit}`}
          </span>
        )}
      </span>
    ),
  });

  return (
    <div className={style.page}>
      <PageHeader
        title={dsName}
        back={{ to: listBase(wsId), label: '데이터셋 목록' }}
        meta={
          latest
            ? `${versions.length}개 버전 · 최신 ${latest.version}`
            : '아직 릴리스한 버전이 없습니다'
        }
      />
      <DatasetTabs active='이력' />

      <DataTable
        cols={[
          '버전',
          '생성',
          '레코드',
          '통과율',
          '사람 검수',
          '심사 모델',
          '',
        ]}
        loading={loading}
        // 최신이 위로 오게 뒤집어 보여주되, 클릭한 행은 id 로 되짚는다
        // (인덱스로 되짚으면 뒤집기·정렬이 바뀔 때 다른 버전이 열린다).
        onRowClick={(i) => {
          const list = versions.slice().reverse();
          setOpenId(list[i]?.id ?? null);
        }}
        rows={versions
          .slice()
          .reverse()
          .map((v) => {
            const sameModel = !!v.gen_model && v.gen_model === v.judge_model;
            const isLatest = latest && v.id === latest.id;
            return [
              {
                node: (
                  <span className={common['row-flex']}>
                    <span
                      className={[common.num, common.cell].join(' ')}
                      style={{ fontFamily: 'SpoqaB' }}
                    >
                      {v.version}
                    </span>
                    {isLatest && <Badge tone='primary'>최신</Badge>}
                  </span>
                ),
              },
              (v.create_datetime || '').slice(0, 10) || '—',
              deltaCell(fmt(v.record_count || 0), v.delta?.record_count),
              deltaCell(`${v.pass_rate ?? '—'}%`, v.delta?.pass_rate, '%'),
              deltaCell(fmt(v.human_reviewed || 0), v.delta?.human_reviewed),
              {
                node: (
                  <span className={common['row-flex']}>
                    <span
                      className={[
                        common.num,
                        common['cell-mute'],
                        common.truncate,
                      ].join(' ')}
                    >
                      {v.judge_model || '—'}
                    </span>
                    {/* 자기 결과를 자기가 채점한 버전 — 통과율을 그대로 믿으면 안 된다. */}
                    {sameModel && <Badge tone='fail'>동일 모델</Badge>}
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
