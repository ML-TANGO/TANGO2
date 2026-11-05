import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';

import { compareRuns, listRuns } from '@src/apis/llm/dataset';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import {
  Badge,
  DataTable,
  PageHeader,
  SectionHead,
  Select,
  dsBase,
  useDatasetNav,
} from './components';
import { fmt } from './lib/format';
import common from './styles/common.module.scss';
import style from './ComparePage.module.scss';

// 두 실행 A/B 비교 — 설계문서 §5.4.
//
// 이 화면이 답하는 질문은 하나다: **기능을 껐다 켰더니 무엇이 달라졌는가.**
// 그래서 세 가지를 같이 놓는다 — 무엇을 바꿨나(설정 차이) · 어디서 갈렸나(단계별
// funnel 차이) · 얼마나 달라졌나(카운트 증감). 셋 중 하나만 있으면 원인과 결과가
// 이어지지 않는다.

const STATUS_TONE = { done: 'pass', running: 'warn', failed: 'fail' };

const CHANGE_LABEL = { added: '추가됨', removed: '제거됨', param: '값 변경' };

/** 증감 한 칸. 0 은 색을 주지 않는다 — 안 변한 것이 눈에 띄면 변한 걸 못 찾는다. */
function Delta({ n }) {
  if (n === null || n === undefined)
    return <span className={style['d-none']}>—</span>;
  if (n === 0) return <span className={style['d-zero']}>±0</span>;
  return (
    <span className={n > 0 ? style['d-up'] : style['d-down']}>
      {n > 0 ? `+${fmt(n)}` : `−${fmt(Math.abs(n))}`}
    </span>
  );
}

/** 실행 선택기의 한 줄 라벨. run_id 만 보이면 어느 게 어느 설정인지 못 고른다. */
function runOption(r) {
  const when = (r.end_datetime || r.create_datetime || '')
    .toString()
    .slice(5, 16);
  const tag = r.dry_run ? '미리보기' : '실행';
  return {
    v: r.run_id,
    n: `${tag} · ${when} · 통과 ${fmt(r.passed ?? r.out_count ?? 0)} / 제외 ${fmt(r.dropped_count ?? 0)}`,
  };
}

/** 설정값을 한 칸에 담을 문자열로. 없으면 그 실행엔 그 기능이 없었다는 뜻이다. */
function paramText(v) {
  if (v === null || v === undefined) return '없음';
  const entries = Object.entries(v);
  if (entries.length === 0) return '켜짐';
  return entries.map(([k, x]) => `${k}=${x}`).join(' · ');
}

export default function ComparePage() {
  const { wsId, dsId } = useDatasetNav();
  const location = useLocation();
  // 어느 노드의 실행을 비교할지. 드로어에서 ?node= 로 넘어온다.
  const nodeIndex = useMemo(() => {
    const raw = new URLSearchParams(location.search).get('node');
    const n = Number(raw);
    return Number.isInteger(n) && n >= 0 ? n : null;
  }, [location.search]);

  const [runs, setRuns] = useState([]);
  const [a, setA] = useState('');
  const [b, setB] = useState('');
  const [diff, setDiff] = useState(null);
  const [note, setNote] = useState('');

  useEffect(() => {
    (async () => {
      const res = await listRuns(dsId, {
        ...(nodeIndex === null ? {} : { node_index: nodeIndex }),
        limit: 50,
      });
      if (res.status !== STATUS_SUCCESS) {
        errorToastMessage(res.error, res.message);
        return;
      }
      const list = res.result?.runs || [];
      setRuns(list);
      // 가장 최근 둘을 기본으로 집는다 — 방금 껐다 켠 두 번이 대개 그 둘이다.
      if (list.length >= 2) {
        setA(list[1].run_id);
        setB(list[0].run_id);
      }
    })();
  }, [dsId, nodeIndex]);

  const compare = useCallback(async () => {
    if (!a || !b || a === b) {
      setDiff(null);
      return;
    }
    const res = await compareRuns(dsId, a, b);
    if (res.status === STATUS_SUCCESS) {
      setDiff(res.result);
      setNote('');
      return;
    }
    setDiff(null);
    // 서로 다른 노드의 실행을 고르면 서버가 거부한다. 그 사유를 그대로 보여준다 —
    // 화면이 조용히 비면 사용자는 비교 기능이 고장 난 줄 안다.
    setNote(res.message || '비교할 수 없습니다');
  }, [dsId, a, b]);

  useEffect(() => {
    compare();
  }, [compare]);

  const options = runs.map(runOption);

  return (
    <div className={style.page}>
      <PageHeader
        title='실행 비교'
        back={{ to: `${dsBase(wsId, dsId)}/flow`, label: '파이프라인' }}
      />

      <div className={style.picker}>
        <span className={style['picker-side']}>
          <span className={common.eyebrow}>기준 (A)</span>
          <Select value={a} options={options} onChange={setA} />
        </span>
        <span className={style['picker-vs']}>vs</span>
        <span className={style['picker-side']}>
          <span className={common.eyebrow}>비교 대상 (B)</span>
          <Select value={b} options={options} onChange={setB} />
        </span>
      </div>

      {runs.length < 2 && (
        <span className={common.prose}>
          비교하려면 실행이 두 번 이상 있어야 합니다. 기능을 바꿔 한 번 더
          실행하세요.
        </span>
      )}
      {note && <span className={style.note}>{note}</span>}

      {diff && (
        <>
          {/* 얼마나 달라졌나 */}
          <div className={style.totals}>
            {[
              // 라벨에 '증감'이 없으면 A·B 가 각각 100건이어도 요약이 0/0/0 이라
              // "결과가 0건" 으로 읽힌다. 아래 단계별 표의 '증감' 컬럼과 같은 값이다.
              ['입력 증감', diff.delta.in],
              ['통과 증감', diff.delta.passed ?? diff.delta.out],
              ['제외 증감', diff.delta.dropped],
            ].map(([label, n]) => (
              <span key={label} className={style.total}>
                <span className={style['total-label']}>{label}</span>
                <span className={style['total-delta']}>
                  <Delta n={n} />
                </span>
              </span>
            ))}
            <span className={style['total-meta']}>
              <Badge tone={STATUS_TONE[diff.a.status] || 'warn'}>
                A {diff.a.status}
              </Badge>
              <Badge tone={STATUS_TONE[diff.b.status] || 'warn'}>
                B {diff.b.status}
              </Badge>
              {(diff.a.dry_run || diff.b.dry_run) && (
                <Badge tone='warn'>미리보기 포함</Badge>
              )}
            </span>
          </div>

          {/* 무엇을 바꿨나 — 이게 없으면 아래 숫자 변화의 원인을 알 수 없다. */}
          <div className={common.stack}>
            <SectionHead>설정 차이</SectionHead>
            {diff.config_diff.length === 0 ? (
              <span className={common.prose}>
                설정이 같습니다. 카운트가 달라졌다면 입력 데이터가 바뀐
                것입니다.
              </span>
            ) : (
              <DataTable
                cols={['기능', '변화', 'A', 'B']}
                rows={diff.config_diff.map((c) => [
                  c.step,
                  CHANGE_LABEL[c.change] || c.change,
                  paramText(c.a),
                  paramText(c.b),
                ])}
              />
            )}
          </div>

          {/* 어디서 갈렸나 */}
          <div className={common.stack}>
            <SectionHead>단계별 차이</SectionHead>
            <DataTable
              cols={['단계', 'A 통과', 'B 통과', '증감']}
              rows={diff.funnel_diff.map((r) => [
                r.stage,
                r.a ? fmt(r.a.out ?? 0) : '—',
                r.b ? fmt(r.b.out ?? 0) : '—',
                { node: <Delta n={r.delta_out} /> },
              ])}
            />
          </div>
        </>
      )}
    </div>
  );
}
