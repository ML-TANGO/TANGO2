import React, { useCallback, useEffect, useRef, useState } from 'react';

import {
  getPipelineMeta,
  listRecords,
  reviewRecord,
  recordImageUrl,
} from '@src/apis/llm/dataset';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import {
  Btn,
  DatasetTabs,
  GateRibbon,
  PageHeader,
  RadioBtn,
  SectionHead,
  Select,
  Textarea,
  listBase,
  useDatasetName,
  useDatasetNav,
} from './components';
import { fmt } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

// 정렬 라벨 ↔ 서버 order 값. 라벨만 바꾸고 값을 안 바꾸면 정렬이 조용히 무시된다.
const SORTS = [
  { label: '심사 점수 낮은 순', value: 'score_asc' },
  { label: '무작위', value: 'random' },
  { label: '오류 유형별', value: 'taxonomy' },
];

const KEYS = [
  ['J / K', '이동'],
  ['A', '승인'],
  ['E', '수정 후 승인'],
  ['R', '거절'],
];

// 한 번에 가져올 표본 수. 전수 검수가 목적이 아니라 나쁜 쪽부터 보는 화면이다.
const PAGE = 50;

/**
 * 사람 검수.
 *
 * 기본 정렬이 '심사 점수 낮은 순'인 이유: 사람의 시간이 가장 비싼 자원이라 위험한
 * 것부터 본다. 전부 볼 필요는 없고, 나쁜 쪽 표본만 확인해도 다음에 무엇을 고쳐야
 * 하는지 알 수 있다.
 *
 * 키보드가 처리량을 결정하므로 J/K/A/E/R 을 전역에 붙인다. 단축키도 버튼과 **같은
 * 저장 경로**를 탄다 — 인덱스만 넘기면 눌러도 아무것도 기록되지 않는다.
 */
export default function ReviewPage() {
  const { wsId, dsId, go } = useDatasetNav();
  const dsName = useDatasetName(dsId);

  const [data, setData] = useState(null);
  const [taxonomyList, setTaxonomyList] = useState([]);
  const [order, setOrder] = useState('score_asc');
  const [idx, setIdx] = useState(0);
  const [done, setDone] = useState(0);
  const [edits, setEdits] = useState({});
  const [taxonomy, setTaxonomy] = useState({});
  const [busy, setBusy] = useState(false);

  // 단축키 핸들러가 최신 상태를 보게 한다 — 등록 시점의 값을 가둬 두면(스테일 클로저)
  // 두 번째 레코드부터 첫 레코드를 계속 판정한다.
  const actionRef = useRef(null);

  const load = useCallback(async () => {
    const res = await listRecords(dsId, {
      order,
      limit: PAGE,
      review_state: 'pending',
    });
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return;
    }
    setData(res.result);
    setIdx(0);
  }, [dsId, order]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    (async () => {
      const res = await getPipelineMeta();
      if (res.status === STATUS_SUCCESS)
        setTaxonomyList(res.result?.taxonomy || []);
    })();
  }, []);

  const records = data?.records || [];
  const finished = idx >= records.length;
  const rec = finished ? null : records[idx];

  /** 판정을 서버에 남기고 다음으로 넘어간다. */
  const judge = useCallback(
    async (verdict) => {
      const cur = records[idx];
      if (!cur || busy) return;
      const edit = edits[cur.id] || {};
      const tax = taxonomy[cur.id] ?? cur.taxonomy ?? null;

      // 서버 규칙을 화면에서 먼저 막는다 — 422 로 돌려받으면 무엇이 빠졌는지 안 보인다.
      if (verdict === 'rejected' && !tax) {
        errorToastMessage(null, '거절하려면 오류 유형을 골라야 합니다');
        return;
      }
      if (verdict === 'edited' && !edit.q && !edit.a) {
        errorToastMessage(null, "'수정 후 승인'은 질문이나 답을 고쳐야 합니다");
        return;
      }

      setBusy(true);
      const res = await reviewRecord(cur.id, {
        verdict,
        taxonomy: tax || null,
        edited_question: edit.q ?? null,
        edited_answer: edit.a ?? null,
      });
      setBusy(false);
      if (res.status !== STATUS_SUCCESS) {
        errorToastMessage(res.error, res.message);
        return;
      }
      setDone((d) => d + 1);
      setIdx((i) => i + 1);
    },
    [records, idx, busy, edits, taxonomy],
  );

  actionRef.current = judge;

  useEffect(() => {
    const onKey = (e) => {
      // 입력 요소에 포커스가 있으면 단축키를 먹지 않는다 — 질문을 고치다가 'a' 를
      // 누르면 승인되는 사고를 막는다.
      const tag = e.target.tagName;
      if (tag === 'TEXTAREA' || tag === 'INPUT' || tag === 'SELECT') return;

      const k = e.key.toLowerCase();
      if (k === 'a') actionRef.current?.('approved');
      else if (k === 'e') actionRef.current?.('edited');
      else if (k === 'r') actionRef.current?.('rejected');
      else if (k === 'j') setIdx((i) => i + 1);
      else if (k === 'k') setIdx((i) => Math.max(0, i - 1));
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const axes = (data?.axes || []).map((a) => ({
    k: a.key,
    label: a.label,
    short: a.short,
  }));
  const pending = Math.max(0, (data?.stats?.pending ?? 0) - done);
  const taxDist = data?.taxonomy_distribution || [];
  // 비율만 두면 100건 전체 기준으로 읽힌다 — 실제 모수는 유형이 붙은(거절된) 몇 건뿐이다.
  const taxTotal = taxDist.reduce((n, t) => n + (t.count || 0), 0);
  // 원본 이미지는 서버가 레코드 id 로 찾아 준다. 화면이 run_id·경로를 조립하면
  // 검수 큐 응답에 계보를 실어야 하고(지금은 실리지 않아 이미지가 아예 안 떴다),
  // 썸네일은 일부만 만들어져 점수 낮은 레코드에서 오히려 비어 있다.
  const thumbOf = (r) => (r?.id && r?.asset_ref ? recordImageUrl(dsId, r.id) : null);

  return (
    <div className={style.page}>
      <PageHeader
        title={dsName}
        back={{ to: listBase(wsId), label: '데이터셋' }}
        meta={`미검수 ${fmt(pending)}건 · 이번 세션 ${fmt(done)}건 처리`}
      />
      <DatasetTabs active='검수' />

      <div className={style['review-grid']}>
        {/* 좌: 정렬 · 오류 유형 분포 */}
        <div className={[common['card-pad'], common['stack-lg']].join(' ')}>
          <span className={common.stack}>
            <span className={common.label}>정렬</span>
            {SORTS.map((s) => (
              <RadioBtn
                key={s.value}
                checked={order === s.value}
                onChange={() => setOrder(s.value)}
                label={s.label}
              />
            ))}
          </span>

          <span
            className={[common.stack, common.divider].join(' ')}
            style={{ paddingTop: 20 }}
          >
            <span className={common['row-flex']}>
              <span className={common.label}>오류 유형</span>
              {taxTotal > 0 && (
                <span className={common['cell-mute']}>
                  거절 {fmt(taxTotal)}건 기준
                </span>
              )}
            </span>
            {taxDist.map((t) => {
              // 25% 를 넘는 유형은 개별 레코드 문제가 아니라 생성 조건 문제다.
              const hot = t.pct > 25;
              return (
                <span key={t.taxonomy} className={style['tax-row']}>
                  <span
                    className={[
                      common['cell-mute'],
                      hot ? common.warn : '',
                    ].join(' ')}
                  >
                    {t.taxonomy}
                  </span>
                  <span
                    className={[
                      common['cell-num'],
                      hot ? common.warn : common.mute,
                    ].join(' ')}
                  >
                    {t.pct}%
                  </span>
                </span>
              );
            })}
            {taxDist.length === 0 && (
              <span className={common.prose}>
                아직 거절된 레코드가 없습니다.
              </span>
            )}
          </span>
        </div>

        {finished ? (
          <div className={[common.card, style['review-done']].join(' ')}>
            <span className={style['review-done-title']}>
              {records.length === 0
                ? '검수할 레코드가 없습니다'
                : `표본 검수 완료 · ${done}건`}
            </span>
            <span className={common.prose}>
              심사 점수가 낮은 순으로 위험한 것만 확인했습니다.
            </span>
            <span className={style.toolbar}>
              <Btn size='md' fill='outline' tone='gray' onClick={load}>
                더 가져오기
              </Btn>
              <Btn size='md' onClick={() => go('/compose')}>
                데이터셋 만들기 →
              </Btn>
            </span>
          </div>
        ) : (
          <>
            {/* 중: 검수 캔버스 */}
            <div className={[common.card, style['review-canvas']].join(' ')}>
              <span className={style['review-shot']}>
                {thumbOf(rec) ? (
                  <img
                    src={thumbOf(rec)}
                    alt={rec.record_key}
                    style={{ width: '100%', borderRadius: 8 }}
                  />
                ) : (
                  <span className={common.prose}>
                    원본 이미지를 찾을 수 없습니다.
                  </span>
                )}
              </span>

              <span className={style['review-edit']}>
                <span>
                  <span
                    className={common.label}
                    style={{ display: 'block', marginBottom: 10 }}
                  >
                    질문 · 편집 가능
                  </span>
                  <Textarea
                    height={96}
                    value={edits[rec.id]?.q ?? rec.question ?? ''}
                    onChange={(v) =>
                      setEdits({
                        ...edits,
                        [rec.id]: { ...edits[rec.id], q: v },
                      })
                    }
                  />
                </span>
                <span>
                  <span
                    className={common.label}
                    style={{ display: 'block', marginBottom: 10 }}
                  >
                    답 · 편집 가능
                  </span>
                  {/* 답은 CPA·TCPA 수치와 COLREG 조치까지 이어지는 긴 문단이다.
                      84px(약 3줄)로는 판정 근거가 보이지 않아 검수가 성립하지 않는다. */}
                  <Textarea
                    height={220}
                    value={edits[rec.id]?.a ?? rec.answer ?? ''}
                    onChange={(v) =>
                      setEdits({
                        ...edits,
                        [rec.id]: { ...edits[rec.id], a: v },
                      })
                    }
                  />
                </span>
              </span>
            </div>

            {/* 우: 판정 */}
            <div className={[common['card-pad'], common.stack].join(' ')}>
              <span
                className={[common.num, common.body].join(' ')}
                style={{ fontFamily: 'SpoqaB', fontSize: 16 }}
              >
                {rec.record_key}
              </span>

              <GateRibbon
                axes={axes}
                scores={rec.scores || {}}
                thresholds={data?.thresholds || {}}
              />

              {rec.judge_comment && (
                <span className={[common.note, common['note-fail']].join(' ')}>
                  <span className={common['note-title']}>심사 모델 지적</span>
                  <span className={common['note-body']}>
                    {rec.judge_comment}
                  </span>
                </span>
              )}

              <span>
                <span
                  className={common.label}
                  style={{ display: 'block', marginBottom: 10 }}
                >
                  오류 유형
                </span>
                <Select
                  value={taxonomy[rec.id] ?? rec.taxonomy ?? ''}
                  onChange={(v) => setTaxonomy({ ...taxonomy, [rec.id]: v })}
                  options={[
                    { v: '', n: '선택' },
                    ...taxonomyList.map((t) => ({ v: t, n: t })),
                  ]}
                />
              </span>

              <span className={style['review-verdicts']}>
                <Btn
                  size='lg'
                  block
                  disabled={busy}
                  onClick={() => judge('approved')}
                >
                  승인 · A
                </Btn>
                <Btn
                  size='lg'
                  block
                  tone='secondary'
                  disabled={busy}
                  onClick={() => judge('edited')}
                >
                  수정 후 승인 · E
                </Btn>
                <Btn
                  size='lg'
                  block
                  tone='danger'
                  disabled={busy}
                  onClick={() => judge('rejected')}
                >
                  거절 · R
                </Btn>
              </span>

              <Btn
                size='md'
                block
                fill='outline'
                tone='gray'
                onClick={() => go(`/record/${rec.record_key}`)}
              >
                레코드 상세 →
              </Btn>
            </div>
          </>
        )}
      </div>

      <div className={[common.card, style.keys].join(' ')}>
        {KEYS.map(([k, label]) => (
          <span key={k} className={common['row-flex']}>
            <span className={style['key-cap']}>{k}</span>
            <span className={common['cell-mute']}>{label}</span>
          </span>
        ))}
      </div>

      <SectionHead
        aside={
          <span className={common.prose}>
            표본만 봐도 됩니다 — 전수 검수가 목적이 아닙니다
          </span>
        }
      >
        검수 방침
      </SectionHead>
    </div>
  );
}
