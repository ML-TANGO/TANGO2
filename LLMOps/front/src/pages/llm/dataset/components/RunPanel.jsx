import React, { useCallback, useEffect, useState } from 'react';

import { getRun, previewRun, runThumbUrl } from '@src/apis/llm/dataset';
import { STATUS_SUCCESS } from '@src/network';

import { Badge, Btn, Funnel } from './index';
import { fmt } from '../lib/format';
import common from '../styles/common.module.scss';
import style from './RunPanel.module.scss';

// 노드 드로어의 실행 결과 패널 — 설계문서 §5.5 "노드 전후 열람 UI".
//
// 입력 / 통과 / 제외 를 **한 화면에 나란히** 둔다. 탭으로 나누면 "무엇이 들어와서
// 무엇이 남고 무엇이 빠졌는지"를 동시에 볼 수 없어 이 화면의 목적이 사라진다.
//
// '입력' 열에 전용 API 는 없다. 입력은 곧 상류 노드 실행의 통과분이므로 같은
// preview 를 상류 run_id 로 한 번 더 부른다(BE 결정 C — 노드가 늘어도 API 가 안 는다).

// 한 열에 보여줄 건수. 전량을 내리면 제외 수천 건짜리 실행에서 드로어가 멈춘다.
const PAGE = 24;

const STATUS_TONE = { done: 'pass', running: 'warn', failed: 'fail' };
const STATUS_LABEL = { done: '완료', running: '실행중', failed: '실패' };

/** 실행 상태 배지 + 미리보기 여부. */
function RunBadge({ run }) {
  if (!run) return null;
  return (
    <span className={style['run-meta']}>
      <Badge tone={STATUS_TONE[run.status] || 'warn'} size='lg'>
        {STATUS_LABEL[run.status] || run.status}
      </Badge>
      {/* 미리보기 실행도 latest_run 으로 올라온다. 표시하지 않으면 표본만 돌린 결과를
          전량 실행 결과로 오해한다. */}
      {run.dry_run && <Badge tone='warn'>미리보기</Badge>}
      {run.error_reason && (
        <span className={style['run-error']}>{run.error_reason}</span>
      )}
    </span>
  );
}

/**
 * 자산 썸네일 한 장.
 *
 * 노드는 앞부분 일부만 썸네일로 만든다(전량이면 용량이 터진다). `has_thumb` 이
 * false 인데 걸면 깨진 이미지가 뜨므로, 그때는 파일명만 있는 자리를 그린다.
 */
function AssetTile({ datasetId, runId, item }) {
  const label = item.asset_id || item.scene_id || '—';
  return (
    <span className={style.tile}>
      {item.has_thumb ? (
        <img
          className={style['tile-img']}
          src={runThumbUrl(datasetId, runId, item.asset_id)}
          alt={label}
          loading='lazy'
        />
      ) : (
        <span className={style['tile-blank']}>썸네일 없음</span>
      )}
      <span className={style['tile-name']}>{label}</span>
    </span>
  );
}

/** 통과·입력 열 — 썸네일 그리드. */
function PassedColumn({ datasetId, data, empty, note, failed }) {
  // 요청 실패를 '0건'과 같은 문구로 그리면 사용자는 통과분이 정말 없는 줄 안다.
  if (failed)
    return <span className={style['col-fail']}>불러오지 못했습니다</span>;
  if (!data || !data.total) {
    return <span className={style['col-empty']}>{empty}</span>;
  }
  return (
    <>
      <span className={style['col-count']}>
        <b>{fmt(data.total)}</b>건
        {data.source_file && (
          <span className={style['col-file']}>{data.source_file}</span>
        )}
      </span>
      <span className={style.grid}>
        {data.items.map((it) => (
          <AssetTile
            key={it.asset_id || it.scene_id || it.src}
            datasetId={datasetId}
            runId={data.run_id}
            item={it}
          />
        ))}
      </span>
      {data.total > data.items.length && (
        <span className={style['col-more']}>
          앞 {data.items.length}건만 표시 · 전체 {fmt(data.total)}건
        </span>
      )}
      {note && <span className={style['col-note']}>{note}</span>}
    </>
  );
}

/**
 * 제외 열 — 사유별로 묶는다.
 *
 * 여기에 썸네일을 걸지 않는 이유: 노드가 제외 항목의 이미지를 **복사하지 않는다**
 * (원본이 RO 로 살아 있어 경로와 사유만 남긴다 — dp_prep 헤더 주석). 따라서
 * thumb 엔드포인트에 제외 자산을 물으면 전건 404 다. 사유·건수·단계를 보여준다.
 */
function DroppedColumn({ data, failed }) {
  if (failed)
    return <span className={style['col-fail']}>불러오지 못했습니다</span>;
  if (!data || !data.total) {
    return <span className={style['col-empty']}>제외된 항목이 없습니다</span>;
  }
  const reasons = Object.entries(data.reasons || {}).sort(
    (a, b) => b[1] - a[1],
  );
  return (
    <>
      <span className={style['col-count']}>
        <b>{fmt(data.total)}</b>건 제외
      </span>
      {reasons.length > 0 && (
        <span className={style.reasons}>
          {reasons.map(([reason, n]) => (
            <span key={reason} className={style['reason-chip']}>
              <span className={style['reason-name']}>{reason}</span>
              <span className={style['reason-n']}>{fmt(n)}</span>
            </span>
          ))}
        </span>
      )}
      <span className={style['drop-list']}>
        {data.items.map((it) => (
          <span key={`${it.asset_id}-${it.src}`} className={style['drop-row']}>
            <span className={style['drop-name']}>{it.asset_id}</span>
            <span className={style['drop-reason']}>{it.reason}</span>
            {/* 노드마다 키가 다르다 — dp_filter 는 `step`, 나머지는 `stage` 로 쓴다.
                하나만 읽으면 필터 노드의 제외 목록에서 이 칸이 통째로 빈다. */}
            <span className={style['drop-stage']}>{it.step || it.stage}</span>
          </span>
        ))}
      </span>
      {data.total > data.items.length && (
        <span className={style['col-more']}>
          앞 {data.items.length}건만 표시 · 전체 {fmt(data.total)}건
        </span>
      )}
    </>
  );
}

/**
 * funnel.json 의 단계 배열 → Funnel 컴포넌트 행.
 *
 * 노드가 남기는 funnel.json 은 요약 객체이고 단계 배열은 그 안의 `funnel` 키다
 * (`{in, out, dropped_total, funnel: [...]}`). 한 겹 더 들어가야 한다.
 */
function funnelRows(summary) {
  const stages = summary?.funnel;
  if (!Array.isArray(stages) || stages.length === 0) return null;
  const rows = stages.map((s) => ({
    k: s.stage,
    v: s.out ?? 0,
    // dropped 는 {사유:건수} 라 합계를 낸다. 빈 객체면 '제거 없음'으로 그려진다.
    del: Object.values(s.dropped || {}).reduce((a, b) => a + b, 0),
  }));
  // 막대 기준은 첫 단계의 입력 건수다. 0 으로 나누면 NaN% 가 style 에 들어간다.
  return { rows, total: stages[0]?.in || rows[0]?.v || 1 };
}

export default function RunPanel({ datasetId, node, upstreamRun, onCompare }) {
  const run = node?.latest_run || null;
  const runId = run?.run_id || null;
  const upstreamRunId = upstreamRun?.run_id || null;

  const [detail, setDetail] = useState(null);
  const [passed, setPassed] = useState(null);
  const [dropped, setDropped] = useState(null);
  const [input, setInput] = useState(null);
  const [loading, setLoading] = useState(false);
  // 어느 열이 '실패'인지 따로 기억한다 — null 하나로는 0건과 구분되지 않는다.
  const [failed, setFailed] = useState({});

  const load = useCallback(async () => {
    if (!datasetId || !runId) {
      setDetail(null);
      setPassed(null);
      setDropped(null);
      setInput(null);
      return;
    }
    setLoading(true);
    // 실행이 아직 도는 중이면 산출물이 없다 — 각 열이 빈 상태로 그려지는 게 맞다.
    const [d, p, dr] = await Promise.all([
      getRun(datasetId, runId),
      previewRun(datasetId, runId, { kind: 'passed', limit: PAGE }),
      previewRun(datasetId, runId, { kind: 'dropped', limit: PAGE }),
    ]);
    const ok = {
      passed: p.status === STATUS_SUCCESS,
      dropped: dr.status === STATUS_SUCCESS,
    };
    setDetail(d.status === STATUS_SUCCESS ? d.result : null);
    setPassed(ok.passed ? { ...p.result, run_id: runId } : null);
    setDropped(ok.dropped ? dr.result : null);

    // 입력 열 = 상류 실행의 통과분. 상류가 아직 안 돌았으면 비는 게 맞다.
    if (upstreamRunId) {
      const up = await previewRun(datasetId, upstreamRunId, {
        kind: 'passed',
        limit: PAGE,
      });
      setInput(
        up.status === STATUS_SUCCESS
          ? { ...up.result, run_id: upstreamRunId }
          : null,
      );
      setFailed({
        passed: !ok.passed,
        dropped: !ok.dropped,
        input: up.status !== STATUS_SUCCESS,
      });
    } else {
      setInput(null);
      setFailed({ passed: !ok.passed, dropped: !ok.dropped, input: false });
    }
    setLoading(false);
  }, [datasetId, runId, upstreamRunId]);

  useEffect(() => {
    load();
  }, [load]);

  if (!runId) {
    return (
      <span className={style.panel}>
        <span className={common.eyebrow}>실행 결과</span>
        <span className={style['col-empty']}>
          아직 실행 기록이 없습니다. 이 노드를 실행하면 통과·제외 결과가 여기
          나옵니다.
        </span>
      </span>
    );
  }

  const fn = funnelRows(detail?.funnel);

  return (
    <span className={style.panel}>
      <span className={style['panel-head']}>
        <span className={common.eyebrow}>실행 결과</span>
        <RunBadge run={run} />
        {onCompare && (
          <Btn size='sm' fill='outline' tone='gray' onClick={onCompare}>
            다른 실행과 비교
          </Btn>
        )}
      </span>

      {/* 단계별 잔존 — 어느 기능에서 얼마나 빠졌는지가 한 줄로 보인다. */}
      {fn && (
        <span className={style.block}>
          <span className={common.eyebrow}>단계별 잔존</span>
          <Funnel rows={fn.rows} total={fn.total} />
        </span>
      )}

      <span className={style.cols}>
        <span className={style.col}>
          <span className={style['col-head']}>입력</span>
          <PassedColumn
            datasetId={datasetId}
            data={input}
            failed={failed.input}
            note='상류 노드의 통과분입니다'
            empty={
              upstreamRunId
                ? '상류 실행에 통과분이 없습니다'
                : '상류 노드를 먼저 실행하세요'
            }
          />
        </span>
        <span className={style.col}>
          <span className={style['col-head']}>통과</span>
          <PassedColumn
            datasetId={datasetId}
            data={passed}
            failed={failed.passed}
            empty={
              run.status === 'running'
                ? '실행 중입니다'
                : '통과한 항목이 없습니다'
            }
          />
        </span>
        <span className={style.col}>
          <span className={style['col-head']}>제외</span>
          <DroppedColumn data={dropped} failed={failed.dropped} />
        </span>
      </span>

      {loading && <span className={style['col-more']}>불러오는 중…</span>}
    </span>
  );
}
