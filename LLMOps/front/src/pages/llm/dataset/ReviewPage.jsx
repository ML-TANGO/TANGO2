import React, { useEffect, useState } from 'react';

import {
  Btn, Checkbox, DatasetTabs, Frame, GateRibbon, PageHeader, RadioBtn,
  SectionHead, Select, Textarea, listBase, useDatasetNav,
} from './components';
import { RECORDS, REVIEW_STATS, TAXONOMY, TAX_PCT } from './mock';
import { SHOTS } from './lib/frames';
import { AXES, THRESHOLDS, fmt } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

const SORTS = ['심사 점수 낮은 순', '무작위', '오류 유형별'];
const KEYS = [['J / K', '이동'], ['A', '승인'], ['E', '수정 후 승인'], ['R', '거절'], ['U', '취소']];

/**
 * 사람 검수.
 *
 * 기본 정렬이 '심사 점수 낮은 순'인 이유: 사람의 시간이 가장 비싼 자원이라 위험한
 * 것부터 본다. 전부 볼 필요는 없고, 나쁜 쪽 표본만 확인해도 다음에 무엇을 고쳐야
 * 하는지 알 수 있다.
 *
 * 키보드가 처리량을 결정하므로 J/K/A/E/R/U 를 전역에 붙인다.
 */
export default function ReviewPage() {
  const { wsId, dsId, go } = useDatasetNav();
  const [idx, setIdx] = useState(0);
  const [done, setDone] = useState(0);
  const [sort, setSort] = useState(SORTS[0]);
  const [edits, setEdits] = useState({});
  const [taxonomy, setTaxonomy] = useState({});

  const finished = idx >= RECORDS.length;
  const rec = finished ? null : RECORDS[idx];

  useEffect(() => {
    const onKey = (e) => {
      // 입력 요소에 포커스가 있으면 단축키를 먹지 않는다 — 질문을 고치다가 'a' 를
      // 누르면 승인되는 사고를 막는다.
      const tag = e.target.tagName;
      if (tag === 'TEXTAREA' || tag === 'INPUT' || tag === 'SELECT') return;

      const k = e.key.toLowerCase();
      if (k === 'a' || k === 'e' || k === 'r') {
        setDone((d) => d + 1);
        setIdx((i) => Math.min(RECORDS.length, i + 1));
      } else if (k === 'j') {
        setIdx((i) => Math.min(RECORDS.length, i + 1));
      } else if (k === 'k') {
        setIdx((i) => Math.max(0, i - 1));
      } else if (k === 'u') {
        setDone((d) => Math.max(0, d - 1));
        setIdx((i) => Math.max(0, i - 1));
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const judge = () => {
    setDone((d) => d + 1);
    setIdx((i) => i + 1);
  };

  return (
    <div className={style.page}>
      <PageHeader
        title={dsId}
        back={{ to: listBase(wsId), label: '데이터셋 목록' }}
        meta={`미검수 ${fmt(Math.max(0, REVIEW_STATS.pending - done))} · 처리 ${REVIEW_STATS.rate + done * 2}건/시`}
      />
      <DatasetTabs active="검수" />

      <div className={style['review-grid']}>
        {/* 좌: 정렬 · 오류 유형 분포 */}
        <div className={[common['card-pad'], common['stack-lg']].join(' ')}>
          <span className={common.stack}>
            <span className={common.label}>정렬</span>
            {SORTS.map((s) => (
              <RadioBtn key={s} checked={sort === s} onChange={() => setSort(s)} label={s} />
            ))}
          </span>

          <span className={[common.stack, common.divider].join(' ')} style={{ paddingTop: 20 }}>
            <span className={common.label}>오류 유형</span>
            {TAXONOMY.map((k) => {
              const pct = TAX_PCT[k];
              // 25% 를 넘는 유형은 개별 레코드 문제가 아니라 생성 조건 문제다.
              const hot = pct > 25;
              return (
                <span key={k} className={style['tax-row']}>
                  <span className={[common['cell-mute'], hot ? common.warn : ''].join(' ')}>{k}</span>
                  <span className={[common['cell-num'], hot ? common.warn : common.mute].join(' ')}>{pct}%</span>
                </span>
              );
            })}
          </span>
        </div>

        {finished ? (
          <div className={[common.card, style['review-done']].join(' ')}>
            <span className={style['review-done-title']}>표본 검수 완료 · {done}건</span>
            <span className={common.prose}>심사 점수가 낮은 순으로 위험한 것만 확인했습니다.</span>
            <Btn size="md" onClick={() => go('/compose')}>데이터셋 만들기 →</Btn>
          </div>
        ) : (
          <>
            {/* 중: 검수 캔버스 */}
            <div className={[common.card, style['review-canvas']].join(' ')}>
              <span className={style['review-shot']}>
                <Frame spec={SHOTS[rec.shot]} ariaLabel={rec.id} />
              </span>
              <span style={{ display: 'flex', justifyContent: 'center' }}>
                <Checkbox checked onChange={() => {}} label="영역 좌표 오버레이" />
              </span>

              <span className={style['review-edit']}>
                <span>
                  <span className={common.label} style={{ display: 'block', marginBottom: 10 }}>질문 · 편집 가능</span>
                  <Textarea
                    height={60}
                    value={edits[rec.id]?.q ?? rec.q}
                    onChange={(v) => setEdits({ ...edits, [rec.id]: { ...edits[rec.id], q: v } })}
                  />
                </span>
                <span>
                  <span className={common.label} style={{ display: 'block', marginBottom: 10 }}>답 · 편집 가능</span>
                  <Textarea
                    height={84}
                    value={edits[rec.id]?.a ?? rec.a}
                    onChange={(v) => setEdits({ ...edits, [rec.id]: { ...edits[rec.id], a: v } })}
                  />
                </span>
              </span>
            </div>

            {/* 우: 판정 */}
            <div className={[common['card-pad'], common.stack].join(' ')}>
              <span className={[common.num, common.body].join(' ')} style={{ fontFamily: 'SpoqaB', fontSize: 16 }}>
                {rec.id}
              </span>

              <GateRibbon axes={AXES} scores={rec.s} thresholds={THRESHOLDS} />

              <span className={[common.note, common['note-fail']].join(' ')}>
                <span className={common['note-title']}>심사 모델 지적</span>
                <span className={common['note-body']}>{rec.judge}</span>
              </span>

              <span>
                <span className={common.label} style={{ display: 'block', marginBottom: 10 }}>오류 유형</span>
                <Select
                  value={taxonomy[rec.id] ?? rec.tax ?? ''}
                  onChange={(v) => setTaxonomy({ ...taxonomy, [rec.id]: v })}
                  options={[{ v: '', n: '선택' }, ...TAXONOMY.map((t) => ({ v: t, n: t }))]}
                />
              </span>

              <span className={style['review-verdicts']}>
                <Btn size="lg" block onClick={judge}>승인 · A</Btn>
                <Btn size="lg" block tone="secondary" onClick={judge}>수정 후 승인 · E</Btn>
                <Btn size="lg" block tone="danger" onClick={judge}>거절 · R</Btn>
              </span>

              <Btn size="md" block fill="outline" tone="gray" onClick={() => go(`/record/${rec.id}`)}>
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

      <SectionHead aside={<span className={common.prose}>표본만 봐도 됩니다 — 전수 검수가 목적이 아닙니다</span>}>
        검수 방침
      </SectionHead>
    </div>
  );
}
