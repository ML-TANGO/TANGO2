import { useCallback, useEffect, useRef, useState } from 'react';
import { shallowEqual, useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import { ButtonV2, Textarea } from '@jonathan/ui-react';

import {
  getPromptOptimization,
  getPromptOptimizations,
  postPromptOptimization,
  putPromptOptimizationActive,
} from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';

import PlaygroundFrame from '../PlaygroundFrame';
import { calIsCompleteRunning } from '../PlaygroundHeader/PlaygroundButtonCont/util';

import classNames from 'classnames/bind';
import style from './PlaygroundPromptOptimization.module.scss';

const cx = classNames.bind(style);

const EXAMPLES_MAX = 10; // BE cap 과 동일(초과분은 서버가 잘라낸다)
const FIELD_MAX = 2000;
const POLL_MS = 10000; // 최적화는 2~10분 — 과한 폴링은 무의미
const TERMINAL = ['completed', 'failed', 'cancelled'];

let exampleSeq = 0;
const emptyExample = () => {
  exampleSeq += 1;
  return { key: `ex-${exampleSeq}`, query: '', response: '' };
};

// [프롬프트 최적화] 카드 — Playground 상세.
//   few-shot 예시로 시스템 프롬프트를 최적화(external job)하고, 완료본을 활성으로 지정하면
//   이후 "직접 추론"에 서버가 주입한다. 컨테이너는 학습을 하지 않고 배포된 모델을 수백 회
//   호출해 프롬프트만 탐색하므로, 실행 중에는 해당 모델 추론이 느려질 수 있다.
//   ⚠️ 일괄(데이터셋) 추론에는 적용되지 않는다 — 서빙 래퍼가 데이터셋을 직접 읽어
//      샘플별로 추론하므로 플랫폼이 프롬프트를 조립할 지점이 없다.
export default function PlaygroundPromptOptimization({ playgroundId }) {
  const status = useSelector(
    (state) => state.llmPlayground.status,
    shallowEqual,
  );
  const isCompleteRunning = calIsCompleteRunning(status);

  const [rows, setRows] = useState([]); // 최적화 이력
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [examples, setExamples] = useState([emptyExample(), emptyExample()]);
  const [detail, setDetail] = useState(null); // 펼친 산출물
  const pollRef = useRef(null);
  // 응답 순서 보장용 시퀀스. 폴링·수동 갱신·배포 전환이 겹치면 먼저 보낸 요청이
  // 나중에 도착해 최신 상태를 과거로 덮어쓴다.
  const listSeq = useRef(0);
  const detailSeq = useRef(0);

  const activeRow = rows.find((r) => r.is_active) || null;
  const hasRunning = rows.some((r) => !TERMINAL.includes(r.status));

  const fetchList = useCallback(async () => {
    if (!playgroundId) return;
    const seq = listSeq.current + 1;
    listSeq.current = seq;
    const res = await getPromptOptimizations(playgroundId);
    if (seq !== listSeq.current) return; // 더 새 요청이 이미 떴다 — 이 응답은 버린다
    // callApi 는 {status, result, message} 를 **최상위로** 돌려준다(res.data 없음).
    if (res?.status === STATUS_SUCCESS && Array.isArray(res?.result)) {
      setRows(res.result);
    }
    setLoading(false);
  }, [playgroundId]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  // 진행 중 항목이 있을 때만 폴링한다(BE 가 조회 시점에 external job 을 당겨와 갱신).
  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (!hasRunning) return undefined;
    pollRef.current = setInterval(fetchList, POLL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [hasRunning, fetchList]);

  const updateExample = (key, field, value) =>
    setExamples((prev) =>
      prev.map((ex) =>
        ex.key === key ? { ...ex, [field]: value.slice(0, FIELD_MAX) } : ex,
      ),
    );

  const handleRun = async () => {
    const prepared = examples
      .map((ex) => ({ query: ex.query.trim(), response: ex.response.trim() }))
      .filter((ex) => ex.query && ex.response);
    // 컨테이너 계약: seed 1 + holdout 1 → 최소 2건.
    if (prepared.length < 2) {
      toast.error('질의·응답이 모두 채워진 예시가 최소 2건 필요합니다.');
      return;
    }
    setBusy(true);
    try {
      const res = await postPromptOptimization({
        playground_id: playgroundId,
        examples: prepared,
      });
      // callApi 가 이미 서버 봉투의 status===1 을 STATUS_SUCCESS 로 접어 넣으므로
      // 여기서 다시 status===1 을 볼 필요가 없다(중복 조건이자 오답이었다).
      if (res?.status === STATUS_SUCCESS) {
        toast.success('최적화를 시작했습니다. 수 분 걸릴 수 있습니다.');
        await fetchList();
      } else {
        toast.error(res?.message || '최적화 시작에 실패했습니다.');
      }
    } finally {
      setBusy(false);
    }
  };

  const handleActivate = async (optimizationId) => {
    setBusy(true);
    try {
      const res = await putPromptOptimizationActive({
        playground_id: playgroundId,
        optimization_id: optimizationId,
      });
      if (res?.status === STATUS_SUCCESS) {
        toast.success(
          optimizationId ? '추론에 적용했습니다.' : '적용을 해제했습니다.',
        );
        await fetchList();
      } else {
        toast.error(res?.message || '적용 변경에 실패했습니다.');
      }
    } finally {
      setBusy(false);
    }
  };

  const handleShowDetail = async (optimizationId) => {
    if (detail?.id === optimizationId) {
      setDetail(null);
      return;
    }
    const seq = detailSeq.current + 1;
    detailSeq.current = seq;
    const res = await getPromptOptimization({
      playground_id: playgroundId,
      optimization_id: optimizationId,
    });
    // 다른 행을 이미 눌렀다면 이 응답은 버린다 — 안 그러면 B 를 열었는데 A 가 뜬다.
    if (seq !== detailSeq.current) return;
    if (res?.status === STATUS_SUCCESS && res?.result) {
      setDetail(res.result);
    } else {
      toast.error(res?.message || '산출물을 불러오지 못했습니다.');
    }
  };

  return (
    <PlaygroundFrame>
      <div className={cx('head')}>
        {/* 형제 카드(PlaygroundInfo/Model/Rag/ExternalApi …)가 전부 h3 를 쓴다.
            div 로 두면 스크린리더 heading 목록에서 이 카드만 사라진다. */}
        <h3 className={cx('title')}>프롬프트 최적화</h3>
        <div className={cx('desc')}>
          예시(질의·응답)로 시스템 프롬프트를 최적화합니다. 완료본을 적용하면
          이후
          <strong> 직접 추론</strong>에 자동으로 반영됩니다.
          <span className={cx('warn')}>
            일괄(데이터셋) 추론에는 적용되지 않습니다.
          </span>
        </div>
      </div>

      {!isCompleteRunning && (
        <div className={cx('notice')}>
          배포가 실행 중일 때만 최적화할 수 있습니다 — 최적화는 배포된 모델을
          호출합니다.
        </div>
      )}

      <div className={cx('examples')}>
        {examples.map((ex, idx) => (
          <div className={cx('example-row')} key={ex.key}>
            <div className={cx('example-index')}>{idx + 1}</div>
            {/* isDisabled 가 실제 prop 이다 — disabled 는 미지원이라 rest 로 빠져
                바깥 div 에 붙고 아무 효과가 없다. aria-label 도 마찬가지라
                options 로 내부 textarea 에 직접 전달해야 한다(placeholder 는
                값이 채워지면 사라져 접근 가능한 이름이 되지 못한다). */}
            <Textarea
              placeholder='질의'
              options={{ 'aria-label': `예시 ${idx + 1} 질의` }}
              value={ex.query}
              maxLength={FIELD_MAX}
              onChange={(e) => updateExample(ex.key, 'query', e.target.value)}
              isDisabled={busy}
            />
            <Textarea
              placeholder='기대 응답'
              options={{ 'aria-label': `예시 ${idx + 1} 기대 응답` }}
              value={ex.response}
              maxLength={FIELD_MAX}
              onChange={(e) =>
                updateExample(ex.key, 'response', e.target.value)
              }
              isDisabled={busy}
            />
            <ButtonV2
              colorType='white'
              size='s'
              disabled={busy || examples.length <= 2}
              onClick={() =>
                setExamples((prev) => prev.filter((p) => p.key !== ex.key))
              }
            >
              삭제
            </ButtonV2>
          </div>
        ))}
      </div>

      <div className={cx('actions')}>
        <ButtonV2
          colorType='white'
          size='s'
          disabled={busy || examples.length >= EXAMPLES_MAX}
          onClick={() => setExamples((prev) => [...prev, emptyExample()])}
        >
          예시 추가
        </ButtonV2>
        <ButtonV2
          colorType='blue'
          size='s'
          isLoading={busy}
          disabled={busy || !isCompleteRunning || hasRunning}
          onClick={handleRun}
        >
          {hasRunning ? '최적화 진행 중…' : '최적화 실행'}
        </ButtonV2>
      </div>

      <div className={cx('history')}>
        <div className={cx('history-head')}>
          <span>최적화 이력</span>
          {activeRow && (
            <ButtonV2
              colorType='white'
              size='s'
              disabled={busy}
              onClick={() => handleActivate(null)}
            >
              적용 해제
            </ButtonV2>
          )}
        </div>
        {loading && <div className={cx('empty')}>불러오는 중…</div>}
        {!loading && rows.length === 0 && (
          <div className={cx('empty')}>아직 최적화 이력이 없습니다.</div>
        )}
        {rows.map((row) => (
          <div className={cx('history-row')} key={row.id}>
            <div className={cx('cell', 'status', row.status)}>{row.status}</div>
            <div className={cx('cell')}>
              {row.metric || '-'} / {row.model || '-'}
            </div>
            <div className={cx('cell')}>
              {row.base_score != null && row.final_score != null
                ? `${row.base_score} → ${row.final_score}`
                : '-'}
            </div>
            <div className={cx('cell', 'time')}>
              {row.create_datetime || '-'}
            </div>
            <div className={cx('cell', 'right')}>
              {row.status === 'completed' && (
                <>
                  <ButtonV2
                    colorType='white'
                    size='s'
                    onClick={() => handleShowDetail(row.id)}
                  >
                    {detail?.id === row.id ? '접기' : '프롬프트'}
                  </ButtonV2>
                  <ButtonV2
                    colorType={row.is_active ? 'gray' : 'blue'}
                    size='s'
                    disabled={busy || !!row.is_active}
                    onClick={() => handleActivate(row.id)}
                  >
                    {row.is_active ? '적용 중' : '적용'}
                  </ButtonV2>
                </>
              )}
            </div>
            {/* 실패 원인 — 어댑터가 컨테이너의 code/message 를 복원해 BE 가 저장한다.
                없으면 사용자는 원인 없는 'failed' 만 보게 된다. */}
            {row.status === 'failed' && row.error_message && (
              <div className={cx('error-message')}>{row.error_message}</div>
            )}
            {detail?.id === row.id && (
              <pre className={cx('prompt-view')}>{detail.system_prompt}</pre>
            )}
          </div>
        ))}
      </div>
    </PlaygroundFrame>
  );
}
