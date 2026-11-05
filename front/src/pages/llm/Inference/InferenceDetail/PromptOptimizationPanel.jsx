import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'react-toastify';

import { Badge, ButtonV2, InputText, Textarea } from '@jonathan/ui-react';

import IconArrow from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';
import SwitchBtn from '@src/components/atoms/checkbox/SwitchBtn';
import Tab from '@src/components/molecules/Tab';
import BorderTable from '@src/components/molecules/BorderTable';
import {
  getPlayground,
  getPromptOptimizationState,
  postPromptOptimization,
  putPromptOptimizationActive,
} from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './PromptOptimizationPanel.module.scss';

const cx = classNames.bind(style);

const EXAMPLES_MAX = 10; // BE cap 과 동일(초과분은 서버가 잘라낸다)
const EXAMPLES_MIN = 2; // 컨테이너 계약: seed 1 + holdout 1
const FIELD_MAX = 2000; // BE _PROMPT_OPT_FIELD_MAX 와 동일
const POLL_MS = 10000; // 최적화는 2~10분 — 과한 폴링은 무의미
// 예시 이미지 원본 크기 상한. BE _PROMPT_OPT_IMAGE_MAX(base64 6,000,000자)의 짝 —
//   base64 는 원본보다 약 33% 커지므로 4MB 원본이 대략 그 한도에 대응한다.
const IMAGE_MAX_BYTES = 4 * 1024 * 1024;

// 입력 방식 탭 — Tab 이 내부에서 t(label) 하므로 형제 화면과 같은 규약으로 넘긴다.
const SOURCE_TABS = [
  { label: '직접 입력', value: 'manual' },
  { label: '파일로 가져오기', value: 'file' },
];

// 최적화 상태 → 조나단 Badge type. 플랫폼 상태 어휘를 그대로 쓰고,
//   Badge 가 모르는 값만 중립(gray)으로 떨어뜨린다.
const STATUS_BADGE = {
  completed: 'green',
  running: 'running',
  pending: 'pending',
  failed: 'error',
  cancelled: 'gray',
};

let exampleSeq = 0;
const emptyExample = () => {
  exampleSeq += 1;
  // image/ais 는 SDS(external) 배포에서만 쓴다 — 내부 배포에서는 계속 비어 있고
  //   전송 페이로드에도 실리지 않는다.
  return {
    key: `ex-${exampleSeq}`,
    query: '',
    response: '',
    image_base64: '',
    image_name: '',
    ais: '',
  };
};

// data URL(`data:image/png;base64,AAA…`) → 순수 base64. SDS 는 접두 없는 값을 받는다.
const stripDataUrl = (dataUrl) =>
  String(dataUrl || '').replace(/^data:[^;]+;base64,/, '');

// AIS 입력 파싱 — SDS 계약상 my_ship=1 행이 최소 1건 필요하다.
//   빈 문자열은 "미입력"으로 구분해 호출자가 다른 메시지를 낼 수 있게 null 을 준다.
const parseAisRows = (text) => {
  const raw = String(text || '').trim();
  if (!raw) return null;
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed)) throw new Error('AIS 는 배열이어야 합니다');
  if (!parsed.some((r) => Number(r?.my_ship) === 1))
    throw new Error('my_ship=1 인 행이 최소 1건 필요합니다');
  return parsed;
};

// 파일 가져오기 파서 — CSV/TSV 는 query,response 헤더, JSON 은 같은 키의 배열.
//   서버로는 결국 examples[{query,response}] 만 나가므로 BE 계약 변화는 없다.
const parseExampleFile = (text, fileName) => {
  if (fileName.endsWith('.json')) {
    const parsed = JSON.parse(text);
    if (!Array.isArray(parsed))
      throw new Error('JSON 최상위는 배열이어야 합니다');
    return parsed.map((o) => ({
      query: String(o?.query ?? ''),
      response: String(o?.response ?? ''),
    }));
  }
  const sep = fileName.endsWith('.tsv') ? '\t' : ',';
  const lines = text.split(/\r?\n/).filter((l) => l.trim());
  if (!lines.length) throw new Error('내용이 비어 있습니다');
  const head = lines[0].split(sep).map((h) => h.trim().toLowerCase());
  const qi = head.indexOf('query');
  const ri = head.indexOf('response');
  if (qi < 0 || ri < 0) throw new Error('query/response 헤더가 없습니다');
  return lines.slice(1).map((line) => {
    const cols = line.split(sep);
    return {
      query: (cols[qi] || '').trim(),
      response: (cols[ri] || '').trim(),
    };
  });
};

// [프롬프트 최적화] — 추론 입력 화면 상단의 ON/OFF 토글 + few-shot 패널.
//   토글은 곧 "적용" 이다: ON 이면 최신 완료본을 활성으로 지정해 서버가 추론에 주입하고,
//   OFF 면 활성을 해제한다. 이력 표에서 과거 산출물을 골라 적용할 수도 있다.
//   ⚠️ 노출 조건은 호출자(InferenceDetail)가 판단한다 — 이중은 LLM1 이 프롬프트를
//      생성하므로 역할이 충돌한다.
export default function PromptOptimizationPanel({ playgroundId }) {
  const [state, setState] = useState(null);
  const [on, setOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [examples, setExamples] = useState([emptyExample(), emptyExample()]);
  const [source, setSource] = useState('manual'); // manual | file
  const [imported, setImported] = useState([]);
  const [importError, setImportError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [rounds, setRounds] = useState(1);
  // 채점 metric — 컨테이너 _METRICS 레지스트리 키와 정확히 일치해야 한다.
  //   모르는 값을 보내면 컨테이너가 _METRICS.get(name, token_f1) 로 조용히 떨어뜨려
  //   "bert_score 를 골랐는데 실제로는 token_f1" 인 상태를 알 수 없게 된다.
  const [metric, setMetric] = useState('token_f1');
  // 제안자(메타) LM — instruction 제안·reflection·예시생성을 맡을 **텍스트** 배포.
  //   대상이 VLM(SDS)이면 그 모델이 구조화 출력을 못 내 필수다(BE 가 강제).
  const [proposerId, setProposerId] = useState('');
  const [proposerOptions, setProposerOptions] = useState([]);
  const [advOpen, setAdvOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const pollRef = useRef(null);
  // 응답 순서 보장 — 폴링과 수동 갱신이 겹치면 먼저 보낸 응답이 나중에 도착해
  // 최신 상태를 과거로 덮어쓴다.
  const seqRef = useRef(0);
  // 토글이 ON 인 채 완료된 실행을 자동 적용할 때, 같은 id 를 반복 적용하지 않도록.
  const autoAppliedRef = useRef(null);
  // 사용자가 토글을 만진 뒤에는 서버 상태로 on 을 되돌리지 않는다(초기 1회만 동기화).
  const syncedRef = useRef(false);

  const refresh = useCallback(async () => {
    if (!playgroundId) return null;
    const seq = seqRef.current + 1;
    seqRef.current = seq;
    const res = await getPromptOptimizationState(playgroundId);
    if (seq !== seqRef.current) return null; // 더 새 요청이 떴다 — 이 응답은 버린다
    if (res?.status !== STATUS_SUCCESS || !res?.result) return null;
    setState(res.result);
    if (!syncedRef.current) {
      syncedRef.current = true;
      setOn(!!res.result.enabled);
    }
    return res.result;
  }, [playgroundId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // 제안자 후보 — 같은 워크스페이스의 **실행 중인 내부(비 external·비 dual)** 배포.
  //   BE 가 같은 조건으로 다시 검증하므로 여기서는 고르기 좋은 목록만 만든다.
  //   VLM 대상일 때만 필요하니 requires_media 인 경우에만 가져온다.
  useEffect(() => {
    if (!state?.requires_media) return;
    const workspaceId =
      window.location.pathname.match(/\/workspace\/(\d+)/)?.[1];
    if (!workspaceId) return;
    let cancelled = false;
    (async () => {
      const res = await getPlayground(workspaceId);
      if (cancelled || res?.status !== STATUS_SUCCESS) return;
      const raw = Array.isArray(res.result)
        ? res.result
        : (res.result?.list ?? []);
      setProposerOptions(
        raw
          .filter(
            (p) =>
              String(p.id) !== String(playgroundId) &&
              p.status === 'running' &&
              p.mode !== 'dual',
          )
          .map((p) => ({ id: p.id, name: p.name })),
      );
    })();
    return () => {
      cancelled = true;
    };
  }, [state?.requires_media, playgroundId]);

  // 진행 중일 때만 폴링한다(BE 가 조회 시점에 external job 을 당겨와 갱신).
  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (!state?.running) return undefined;
    pollRef.current = setInterval(refresh, POLL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [state?.running, refresh]);

  const applyActive = useCallback(
    async (optimizationId) => {
      const res = await putPromptOptimizationActive({
        playground_id: playgroundId,
        optimization_id: optimizationId,
      });
      if (res?.status !== STATUS_SUCCESS) {
        toast.error(res?.message || '적용 변경에 실패했습니다.');
        return false;
      }
      await refresh();
      return true;
    },
    [playgroundId, refresh],
  );

  // 토글이 ON 인데 방금 끝난 완료본이 아직 적용 전이면 자동으로 적용한다.
  //   ON = "적용" 이라는 약속을 지키기 위한 것 — 안 하면 토글은 ON 인데 추론에는
  //   아무 것도 안 먹는 상태가 되어 UI 가 거짓말을 한다.
  useEffect(() => {
    if (!on || !state) return;
    const id = state.latest_completed_id;
    if (!id || state.enabled || autoAppliedRef.current === id) return;
    autoAppliedRef.current = id;
    applyActive(id).then((ok) => {
      if (ok) toast.success('최적화한 프롬프트를 추론에 적용했습니다.');
    });
  }, [on, state, applyActive]);

  const handleToggle = async () => {
    const next = !on;
    setOn(next);
    setBusy(true);
    try {
      if (!next) {
        // OFF = 적용 해제. 실행 이력은 남기고 주입만 멈춘다.
        await applyActive(null);
      } else if (state?.latest_completed_id && !state?.enabled) {
        // ON = 최신 완료본 적용. 완료본이 없으면 패널만 열어 실행을 유도한다.
        autoAppliedRef.current = state.latest_completed_id;
        await applyActive(state.latest_completed_id);
      }
    } finally {
      setBusy(false);
    }
  };

  const updateExample = (key, field, value) =>
    setExamples((prev) =>
      prev.map((ex) =>
        ex.key === key
          ? {
              ...ex,
              // FIELD_MAX 는 BE 의 query/response cap 이다. AIS(JSON 배열)는 그 cap
              // 대상이 아니라 잘라내면 파싱이 깨진다.
              [field]: field === 'ais' ? value : value.slice(0, FIELD_MAX),
            }
          : ex,
      ),
    );

  // SDS(external)는 이미지 없이는 추론 자체가 불가하므로 "채워진 예시" 기준이 다르다.
  const requiresMedia = !!state?.requires_media;
  const isFilled = (ex) =>
    ex.query.trim() &&
    ex.response.trim() &&
    (!requiresMedia || !!ex.image_base64);
  const filledCount = examples.filter(isFilled).length;

  const readExampleImage = (key, file) => {
    if (!file) return;
    // accept='image/*' 는 파일 선택기 힌트일 뿐 강제력이 없다. 인코딩하면 base64 로
    //   원본 대비 +33% 가 되어 state·전송·DB 를 동시에 압박하므로 여기서 먼저 막는다
    //   (BE _PROMPT_OPT_IMAGE_MAX 와 짝 — 서버까지 보내고 거부당하지 않게).
    if (file.size > IMAGE_MAX_BYTES) {
      toast.error(
        `이미지가 너무 큽니다(${Math.round(file.size / 1024 / 1024)}MB) — ` +
          `${IMAGE_MAX_BYTES / 1024 / 1024}MB 이하로 줄여 주세요.`,
      );
      return;
    }
    const reader = new FileReader();
    reader.onload = () =>
      setExamples((prev) =>
        prev.map((ex) =>
          ex.key === key
            ? {
                ...ex,
                image_base64: stripDataUrl(reader.result),
                image_name: file.name,
              }
            : ex,
        ),
      );
    reader.onerror = () => toast.error('이미지를 읽지 못했습니다.');
    reader.readAsDataURL(file);
  };

  const readFile = (file) => {
    if (!file) return;
    setImportError('');
    setImported([]);
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const rows = parseExampleFile(String(reader.result), file.name).filter(
          (r) => r.query && r.response,
        );
        if (!rows.length) throw new Error('가져올 예시가 없습니다');
        setImported(rows);
      } catch (err) {
        setImportError(`읽기 실패: ${err.message}`);
      }
    };
    reader.onerror = () => setImportError('파일을 읽지 못했습니다');
    reader.readAsText(file);
  };

  const applyImported = () => {
    setExamples((prev) => {
      // 빈 행은 가져온 예시로 대체한다 — 초기 2개 빈 행이 그대로 남으면
      // "등록 N개" 와 실제 유효 건수가 어긋나 보인다.
      const kept = prev.filter((ex) => ex.query.trim() || ex.response.trim());
      const added = imported.map((r) => ({
        ...emptyExample(),
        query: r.query.slice(0, FIELD_MAX),
        response: r.response.slice(0, FIELD_MAX),
      }));
      return [...kept, ...added].slice(0, EXAMPLES_MAX);
    });
    setImported([]);
    setImportError('');
    setSource('manual');
  };

  const handleRun = async () => {
    let prepared;
    try {
      prepared = examples.filter(isFilled).map((ex) => {
        const base = { query: ex.query.trim(), response: ex.response.trim() };
        if (!requiresMedia) return base;
        // AIS 파싱 실패는 여기서 잡아 어떤 예시가 문제인지 알린다 —
        //   서버로 보내면 컨테이너 로그 안쪽에서 실패해 원인을 못 찾는다.
        const ais = parseAisRows(ex.ais);
        if (!ais)
          throw new Error(
            `"${base.query.slice(0, 20)}…" 예시의 AIS 가 비었습니다`,
          );
        return { ...base, image_base64: ex.image_base64, ais_rows: ais };
      });
    } catch (err) {
      toast.error(`AIS 입력 오류: ${err.message}`);
      return;
    }
    if (prepared.length < EXAMPLES_MIN) {
      toast.error(
        requiresMedia
          ? `질의·응답·이미지가 모두 채워진 예시가 최소 ${EXAMPLES_MIN}건 필요합니다.`
          : `질의·응답이 모두 채워진 예시가 최소 ${EXAMPLES_MIN}건 필요합니다.`,
      );
      return;
    }
    setBusy(true);
    try {
      const res = await postPromptOptimization({
        playground_id: playgroundId,
        examples: prepared,
        rounds,
        metric,
        // VLM 대상일 때만 의미가 있다. BE 가 워크스페이스·유형·실행상태를 재검증한다.
        proposer_playground_id: proposerId ? Number(proposerId) : null,
      });
      if (res?.status === STATUS_SUCCESS) {
        toast.success('최적화를 시작했습니다. 수 분 걸릴 수 있습니다.');
        await refresh();
      } else {
        toast.error(res?.message || '최적화 시작에 실패했습니다.');
      }
    } finally {
      setBusy(false);
    }
  };

  const handleCopy = () => {
    const text = state?.active_system_prompt || '';
    if (!text || !navigator.clipboard) return;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  // 상태를 못 읽었거나(state=null) 외부 컨테이너 배포면 아무것도 그리지 않는다.
  //   첫 조회 전에 미리 그리면 미지원 배포에서 토글이 깜빡였다 사라진다 → fail-closed.
  if (!state || !state.supported) return null;

  const history = state.history || [];
  const latest = history[0] || null;
  const running = !!state.running;
  const canRun =
    !busy &&
    !running &&
    state.deployment_running &&
    filledCount >= EXAMPLES_MIN;

  const historyColumns = [
    {
      name: '상태',
      width: '110px',
      cell: (row) => (
        <Badge
          type={STATUS_BADGE[row.status] || 'gray'}
          label={row.status}
          size='sm'
        />
      ),
    },
    {
      name: '실행 시각',
      selector: (row) => row.create_datetime || '-',
      width: '170px',
    },
    {
      name: 'metric / model',
      selector: (row) => `${row.metric || '-'} / ${row.model || '-'}`,
      wrap: true,
    },
    {
      name: '점수',
      width: '130px',
      selector: (row) =>
        row.base_score != null && row.final_score != null
          ? `${row.base_score} → ${row.final_score}`
          : '-',
    },
    {
      name: '',
      width: '92px',
      cell: (row) =>
        row.status === 'completed' ? (
          <ButtonV2
            colorType={row.is_active ? 'gray' : 'blue'}
            size='s'
            disabled={busy || !!row.is_active}
            onClick={() => {
              // 과거 산출물을 고르면 그것이 활성이 된다 — 토글도 켜진 상태로 맞춘다.
              autoAppliedRef.current = row.id;
              setOn(true);
              applyActive(row.id);
            }}
          >
            {row.is_active ? '적용 중' : '적용'}
          </ButtonV2>
        ) : null,
    },
  ];

  const previewColumns = [
    { name: '#', width: '48px', selector: (_r, i) => i + 1 },
    { name: 'query', selector: (r) => r.query, wrap: true },
    { name: 'response', selector: (r) => r.response, wrap: true },
  ];

  return (
    <div className={cx('panel')}>
      <div className={cx('head')}>
        <div className={cx('head-main')}>
          <SwitchBtn checked={on} onChange={handleToggle} disabled={busy} />
          <span className={cx('title')}>프롬프트 최적화</span>
          {on && state.enabled && (
            <Badge
              type={state.effective ? 'green' : 'yellow'}
              label={state.effective ? '적용 중' : '적용됨 · 미반영'}
              size='sm'
            />
          )}
          {running && <Badge type='running' label='최적화 진행 중' size='sm' />}
        </div>
        <p className={cx('caption')}>
          few-shot 예시로 시스템 프롬프트를 자동 최적화해 주입합니다 — 실시간
          질문과 데이터셋 일괄 추론 모두에 적용됩니다.
        </p>
        {/* 활성인데 주입은 생략되는 상태 — 서버만 아는 사실이라 반드시 드러낸다. */}
        {on && state.stale_reason === 'model_changed' && (
          <p className={cx('alert')}>
            배포 모델이 최적화 당시와 달라 이 프롬프트는 추론에 반영되지
            않습니다 — 현재 모델로 다시 실행하세요.
          </p>
        )}
        {on && !state.deployment_running && (
          <p className={cx('alert')}>
            배포가 실행 중일 때만 최적화를 실행할 수 있습니다 — 최적화는 배포된
            모델을 호출합니다.
          </p>
        )}
      </div>

      {on && (
        <div className={cx('body')}>
          {/* ── Few-Shot 예시 ── */}
          <section className={cx('sec')}>
            <div className={cx('sec-h')}>
              <h4>Few-Shot 예시</h4>
              <span className={cx('count')}>
                등록 <b>{filledCount}</b>개
                {filledCount < EXAMPLES_MIN && (
                  <em className={cx('need')}>· 최소 {EXAMPLES_MIN}개 필요</em>
                )}
              </span>
            </div>

            {/* SDS(external)는 예시마다 이미지가 필요해 CSV/JSON 가져오기로는 구성할 수
                없다 → 그 배포에서는 입력 방식 탭 자체를 숨기고 직접 입력만 남긴다. */}
            {!requiresMedia && (
              <Tab
                type='b'
                sidePaddingNone
                option={SOURCE_TABS}
                select={{ value: source }}
                tabHandler={({ value }) => setSource(value)}
              />
            )}

            {(requiresMedia || source === 'manual') && (
              <>
                <div className={cx('qa-stack')}>
                  {examples.map((ex, idx) => (
                    <div className={cx('qa')} key={ex.key}>
                      <div className={cx('qa-top')}>
                        <span className={cx('idx')}>예시 #{idx + 1}</span>
                        <ButtonV2
                          colorType='white'
                          size='s'
                          disabled={busy || examples.length <= EXAMPLES_MIN}
                          onClick={() =>
                            setExamples((prev) =>
                              prev.filter((p) => p.key !== ex.key),
                            )
                          }
                        >
                          삭제
                        </ButtonV2>
                      </div>
                      <label className={cx('qa-label')}>
                        Query — 사용자 입력
                      </label>
                      <InputText
                        placeholder='예: 배송이 언제 오나요?'
                        value={ex.query}
                        maxLength={FIELD_MAX}
                        onChange={(e) =>
                          updateExample(ex.key, 'query', e.target.value)
                        }
                        isDisabled={busy}
                      />
                      <label className={cx('qa-label')}>
                        Response — 기대 응답
                      </label>
                      {/* isDisabled 가 실제 prop 이다 — disabled 는 미지원이라 rest 로
                          빠져 아무 효과가 없다. aria-label 도 options 로 내부 textarea
                          에 직접 전달해야 한다(placeholder 는 값이 채워지면 사라져
                          접근 가능한 이름이 되지 못한다). */}
                      <Textarea
                        placeholder='예: 영업일 기준 2~3일 내 도착합니다.'
                        options={{ 'aria-label': `예시 ${idx + 1} 기대 응답` }}
                        value={ex.response}
                        maxLength={FIELD_MAX}
                        onChange={(e) =>
                          updateExample(ex.key, 'response', e.target.value)
                        }
                        isDisabled={busy}
                      />

                      {/* SDS(VLM) 전용 — 이미지·AIS 없이는 추론 호출 자체가 실패한다.
                          shim 이 최적화 중 이 예시의 이미지를 query 로 되찾아 붙인다. */}
                      {requiresMedia && (
                        <>
                          <label className={cx('qa-label')}>
                            이미지 — SDS 추론 대상
                          </label>
                          <label className={cx('file-line')}>
                            <span className={cx('file-name')}>
                              {ex.image_name || '이미지를 선택하세요'}
                            </span>
                            <span className={cx('file-btn')}>파일 선택</span>
                            <input
                              type='file'
                              accept='image/*'
                              hidden
                              disabled={busy}
                              onChange={(e) => {
                                readExampleImage(ex.key, e.target.files[0]);
                                e.target.value = '';
                              }}
                            />
                          </label>
                          <label className={cx('qa-label')}>
                            AIS — my_ship=1 행 포함 JSON 배열
                          </label>
                          <Textarea
                            placeholder='[{"my_ship": 1, "lat": 35.1, "lon": 129.0}]'
                            options={{ 'aria-label': `예시 ${idx + 1} AIS` }}
                            value={ex.ais}
                            onChange={(e) =>
                              updateExample(ex.key, 'ais', e.target.value)
                            }
                            isDisabled={busy}
                          />
                        </>
                      )}
                    </div>
                  ))}
                </div>

                <div className={cx('row-end')}>
                  <ButtonV2
                    colorType='white'
                    size='s'
                    disabled={busy || examples.length >= EXAMPLES_MAX}
                    onClick={() =>
                      setExamples((prev) => [...prev, emptyExample()])
                    }
                  >
                    예시 추가
                  </ButtonV2>
                </div>
              </>
            )}

            {!requiresMedia && source === 'file' && (
              <>
                <label
                  className={cx('drop', { over: dragOver })}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragOver(true);
                  }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragOver(false);
                    readFile(e.dataTransfer.files[0]);
                  }}
                >
                  <b>파일을 끌어다 놓거나 클릭하여 선택</b>
                  <span className={cx('fmt')}>.csv · .tsv · .json</span>
                  <input
                    type='file'
                    accept='.csv,.tsv,.json'
                    hidden
                    onChange={(e) => {
                      readFile(e.target.files[0]);
                      // 같은 파일을 다시 고를 수 있게 값을 비운다.
                      e.target.value = '';
                    }}
                  />
                </label>
                <p className={cx('hint')}>
                  CSV/TSV: <code>query,response</code> 헤더 필요 · JSON:{' '}
                  <code>{'[{"query": "...", "response": "..."}]'}</code> 배열
                </p>

                {importError && <p className={cx('alert')}>{importError}</p>}

                {imported.length > 0 && (
                  <>
                    <div className={cx('row-between')}>
                      <span className={cx('ok-msg')}>
                        {imported.length}개 예시를 읽었습니다
                      </span>
                      <ButtonV2
                        colorType='blue'
                        size='s'
                        onClick={applyImported}
                      >
                        목록에 추가
                      </ButtonV2>
                    </div>
                    <BorderTable
                      columns={previewColumns}
                      data={imported.slice(0, 5)}
                      loading={false}
                      selectableRows={false}
                      hideSearchBox
                      hideButtons
                    />
                  </>
                )}
              </>
            )}
          </section>

          {/* ── 고급 설정 ── */}
          <section className={cx('acc')}>
            <button
              type='button'
              className={cx('acc-h', { open: advOpen })}
              onClick={() => setAdvOpen((v) => !v)}
            >
              <span>고급 설정</span>
              <img
                className={cx('arrow', { open: advOpen })}
                src={IconArrow}
                alt='arrow'
              />
            </button>
            {advOpen && (
              <div className={cx('acc-b')}>
                <div className={cx('opt-row')}>
                  <span className={cx('lab')}>
                    최적화 모드
                    <span className={cx('sub')}>
                      빠른 모드는 예시 증강 없이 더 짧게 끝납니다
                    </span>
                  </span>
                  <div className={cx('opt-actions')}>
                    {[
                      { v: 0, label: '빠른 (rounds 0)' },
                      { v: 1, label: '기본 (rounds 1)' },
                    ].map((c) => (
                      <ButtonV2
                        key={c.v}
                        colorType={rounds === c.v ? 'blue' : 'white'}
                        size='s'
                        disabled={busy}
                        onClick={() => setRounds(c.v)}
                      >
                        {c.label}
                      </ButtonV2>
                    ))}
                  </div>
                </div>

                <div className={cx('opt-row')}>
                  <span className={cx('lab')}>
                    채점 metric
                    <span className={cx('sub')}>
                      token_f1 = 토큰 겹침(의존성 없음) · bert_score = 의미
                      유사도
                    </span>
                  </span>
                  <div className={cx('opt-actions')}>
                    {[
                      { v: 'token_f1', label: 'token_f1' },
                      { v: 'bert_score', label: 'bert_score' },
                    ].map((m) => (
                      <ButtonV2
                        key={m.v}
                        colorType={metric === m.v ? 'blue' : 'white'}
                        size='s'
                        disabled={busy}
                        onClick={() => setMetric(m.v)}
                      >
                        {m.label}
                      </ButtonV2>
                    ))}
                  </div>
                </div>

                {/* bert_score 는 첫 사용 때 채점 모델(roberta-large, 약 1.4GB)을
                    내려받는다. 잡 파드는 매번 새로 뜨므로 실행마다 반복된다.
                    ⚠️ 받지 못하면 _bert_f1 이 token_f1 로 폴백하는데, 컨테이너는
                       결과에 **요청한** metric 을 그대로 실어 보낸다(service.py:172)
                       → 이력의 metric 열로는 폴백 여부를 알 수 없다. 잡 로그의
                       "[fewshot_task] BERTScore unavailable" 만이 유일한 단서다. */}
                {/* 제안자(메타) LM — VLM 대상에서만. 대상 모델은 이미지에 답할 뿐
                    instruction 을 JSON 으로 제안하지 못해 dspy 가 죽는다(실측). */}
                {requiresMedia && (
                  <div className={cx('opt-row')}>
                    <span className={cx('lab')}>
                      프롬프트 제안 LLM
                      <span className={cx('sub')}>
                        instruction 제안·예시 생성을 맡을 텍스트 배포 (필수)
                      </span>
                    </span>
                    <select
                      className={cx('select')}
                      value={proposerId}
                      disabled={busy}
                      onChange={(e) => setProposerId(e.target.value)}
                    >
                      <option value=''>선택하세요</option>
                      {proposerOptions.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {requiresMedia && proposerOptions.length === 0 && (
                  <p className={cx('alert')}>
                    실행 중인 내부 텍스트 배포가 없습니다 — 제안 LLM으로 쓸
                    배포를 먼저 시작하세요.
                  </p>
                )}

                {metric === 'bert_score' && (
                  <p className={cx('hint')}>
                    bert_score 는 첫 채점 때 모델(약 1.4GB)을 내려받아 실행이 수
                    분 길어집니다. 내려받지 못하면 자동으로 token_f1 로
                    채점되지만, 이력의 metric 열에는 요청값 그대로{' '}
                    <code>bert_score</code> 가 남습니다 — 폴백 여부는 잡
                    로그로만 확인됩니다.
                  </p>
                )}
              </div>
            )}
          </section>

          {/* ── 최적화 이력 ── */}
          <section className={cx('acc')}>
            <button
              type='button'
              className={cx('acc-h', { open: historyOpen })}
              onClick={() => setHistoryOpen((v) => !v)}
            >
              <span>최적화 이력 ({history.length})</span>
              <img
                className={cx('arrow', { open: historyOpen })}
                src={IconArrow}
                alt='arrow'
              />
            </button>
            {historyOpen && (
              <div className={cx('acc-b')}>
                {/* 조회 실패를 "이력 없음"으로 보여주지 않는다 — 원인이 화면에서 사라진다. */}
                {state.history_error && (
                  <p className={cx('alert')}>
                    이력을 불러오지 못했습니다 — {state.history_error}
                  </p>
                )}
                <BorderTable
                  columns={historyColumns}
                  data={history}
                  loading={false}
                  selectableRows={false}
                  hideSearchBox
                  hideButtons
                  fixedHeader
                  fixedHeaderScrollHeight='320px'
                />
                {/* 실패 원인 — 어댑터가 컨테이너의 code/message 를 복원해 BE 가 저장한다.
                    표 칸에 넣으면 잘려서 원인을 못 읽으므로 아래에 펼쳐 둔다. */}
                {history
                  .filter((r) => r.status === 'failed' && r.error_message)
                  .slice(0, 3)
                  .map((r) => (
                    <p className={cx('job-error')} key={r.id}>
                      #{r.id} · {r.error_message}
                    </p>
                  ))}
              </div>
            )}
          </section>

          {/* ── 실행 / 결과 ── */}
          <div className={cx('foot')}>
            {latest && (
              <div className={cx('row-between')}>
                <span className={cx('latest-label')}>
                  최근 실행 · {latest.create_datetime || '-'}
                </span>
                <Badge
                  type={STATUS_BADGE[latest.status] || 'gray'}
                  label={latest.status}
                  size='sm'
                />
              </div>
            )}

            {state.active_system_prompt && (
              <div className={cx('result')}>
                <div className={cx('row-between')}>
                  <h5>적용 중인 시스템 프롬프트</h5>
                  <ButtonV2 colorType='white' size='s' onClick={handleCopy}>
                    {copied ? '복사됨' : '복사'}
                  </ButtonV2>
                </div>
                {/* 개행/공백이 프롬프트 의미의 일부이므로 pre 로 보존한다. */}
                <pre className={cx('sp-box')}>{state.active_system_prompt}</pre>
              </div>
            )}

            <ButtonV2
              colorType='blue'
              size='m'
              isLoading={busy}
              disabled={!canRun}
              onClick={handleRun}
            >
              {running ? '최적화 진행 중' : '최적화 시작'}
            </ButtonV2>
            <span className={cx('foot-note')}>
              {running
                ? '진행 중에는 화면을 벗어나도 계속 실행됩니다.'
                : `예시 ${EXAMPLES_MIN}개 이상 · 배포 실행 중일 때 시작할 수 있습니다.`}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
