import React, { useCallback, useEffect, useState } from 'react';

import {
  createVersion,
  getCoverage,
  verifyTrainFormat,
} from '@src/apis/llm/dataset';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import {
  Badge,
  Btn,
  Checkbox,
  DatasetTabs,
  PageHeader,
  ProgressBar,
  SectionHead,
  Select,
  Slider,
  Textfield,
  listBase,
  useDatasetName,
  useDatasetNav,
} from './components';
import { allocate, fmt } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

const SPLIT_COLOR = ['#2d76f8', '#93baff', '#dee9ff'];
const SPLIT_KEYS = ['train', 'validation', 'test'];
// 서버 SPLIT_BY 와 문자 단위로 같아야 한다 — 다르면 저장 시 거부된다.
const SPLIT_BY = ['문서 ID', '이미지', '무작위'];
const FORMATS = ['Qwen3-VL', 'Gemma 3', 'HuggingFace messages'];

/**
 * 구성 · 분할.
 *
 * 분리 기준이 '문서 ID' 가 기본인 이유: 같은 문서의 다른 페이지가 train 과 test 로
 * 갈리면 사실상 정답을 미리 본 셈이라 평가 점수가 부풀려진다.
 *
 * 학습 형식 검사를 통과해야 데이터셋을 만들 수 있게 막는다. 형식 오류는 학습을
 * 시작하고 한참 뒤에 터지는데, 그때는 GPU 시간을 이미 버린 뒤다.
 *
 * 유형 목록과 풀 크기는 분포 분석과 같은 곳(`coverage`)에서 온다 — 두 화면이 서로
 * 다른 유형을 보여주면 어느 쪽을 믿어야 할지 알 수 없다.
 */
export default function ComposePage() {
  const { wsId, dsId, go } = useDatasetNav();
  const dsName = useDatasetName(dsId);

  const [cov, setCov] = useState(null);
  const [weights, setWeights] = useState({});
  const [split, setSplit] = useState({ train: 80, validation: 10, test: 10 });
  const [splitBy, setSplitBy] = useState(SPLIT_BY[0]);
  const [formats, setFormats] = useState(
    Object.fromEntries(FORMATS.map((f) => [f, true])),
  );
  const [verify, setVerify] = useState('idle');
  const [verifyRows, setVerifyRows] = useState([]);
  const [failOpen, setFailOpen] = useState(false);
  const [version, setVersion] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const res = await getCoverage(dsId);
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return;
    }
    setCov(res.result);
    // 기본 가중치는 현재 분포 그대로 — 사용자가 손대기 전에는 지금 구성을 재현한다.
    setWeights(
      Object.fromEntries(
        (res.result?.coverage || []).map((c) => [c.capability, c.pct || 0]),
      ),
    );
  }, [dsId]);

  useEffect(() => {
    load();
  }, [load]);

  const caps = cov?.coverage || [];
  const pool = cov?.total_records || 0;
  const splitSum = SPLIT_KEYS.reduce((acc, k) => acc + split[k], 0) || 1;
  const weightSum = Object.values(weights).reduce((a, b) => a + b, 0) || 1;

  // 화면의 미리보기 배분. 실제 배분은 릴리스 시 서버가 같은 방식(최대잉여법)으로 다시 한다.
  const { counts } = allocate(
    caps.map((c) => ({ k: c.capability })),
    weights,
    pool,
  );
  const totalRecs = Object.values(counts).reduce((a, b) => a + b, 0);

  const runVerify = async () => {
    const picked = FORMATS.filter((f) => formats[f]);
    if (picked.length === 0) {
      errorToastMessage(null, '검사할 형식을 하나 이상 고르세요');
      return;
    }
    setVerify('busy');
    const res = await verifyTrainFormat(dsId, { formats: picked });
    if (res.status !== STATUS_SUCCESS) {
      setVerify('idle');
      errorToastMessage(res.error, res.message);
      return;
    }
    const rows = Array.isArray(res.result)
      ? res.result
      : res.result?.formats || [];
    setVerifyRows(rows);
    setVerify('done');
  };

  const create = async () => {
    if (!version.trim()) {
      errorToastMessage(null, '버전 이름을 입력하세요 (예: v0.4.0)');
      return;
    }
    setBusy(true);
    const res = await createVersion(dsId, {
      version: version.trim(),
      mix: weights,
      split,
      split_by: splitBy,
    });
    setBusy(false);
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return;
    }
    go('/compose/history');
  };

  const fails = verifyRows.flatMap((r) => r.bad || []);

  return (
    <div className={style.page}>
      <PageHeader
        title={dsName}
        back={{ to: listBase(wsId), label: '데이터셋' }}
      />
      <DatasetTabs active='구성 · 분할' />

      <div className={style['compose-grid']}>
        <div className={common['stack-lg']}>
          <div className={common.stack}>
            <SectionHead
              aside={
                <span className={[common.num, common['cell-mute']].join(' ')}>
                  풀 {fmt(pool)}
                </span>
              }
            >
              구성
            </SectionHead>
            <div className={common['card-pad']} style={{ paddingTop: 8 }}>
              {caps.map((c) => (
                <span key={c.capability} className={style['mix-row']}>
                  <span
                    className={[
                      common.num,
                      common['cell-mute'],
                      common.truncate,
                    ].join(' ')}
                  >
                    {c.capability}
                  </span>
                  <Slider
                    min={0}
                    max={50}
                    value={weights[c.capability] ?? 0}
                    onChange={(v) =>
                      setWeights({ ...weights, [c.capability]: v })
                    }
                  />
                  <span className={common['cell-num']}>
                    {Math.round(
                      ((weights[c.capability] ?? 0) / weightSum) * 100,
                    )}
                    %
                  </span>
                  <span className={[common['cell-num'], common.mute].join(' ')}>
                    {fmt(counts[c.capability] || 0)}
                  </span>
                </span>
              ))}
              {caps.length === 0 && (
                <span className={common.prose}>
                  아직 구성할 레코드가 없습니다.
                </span>
              )}

              {/* 합계가 항상 풀과 정확히 맞는다 — 잔여분을 소수부가 큰 순서로 나눈 결과다. */}
              <span className={style.totals}>
                <span className={style['total-cell']}>
                  <span className={style['total-value']}>{fmt(totalRecs)}</span>
                  <span className={common['tile-label']}>건수</span>
                </span>
              </span>
            </div>
          </div>

          <div className={common.stack}>
            <SectionHead
              aside={
                <span className={[common.num, common['cell-mute']].join(' ')}>
                  {split.train} : {split.validation} : {split.test}
                </span>
              }
            >
              분할
            </SectionHead>

            <div className={[common['card-pad'], common.stack].join(' ')}>
              {SPLIT_KEYS.map((k) => (
                <span key={k} className={style['split-row']}>
                  <span className={[common.num, common['cell-mute']].join(' ')}>
                    {k}
                  </span>
                  <Slider
                    min={0}
                    max={100}
                    value={split[k]}
                    onChange={(v) => setSplit({ ...split, [k]: v })}
                  />
                  <span className={common['cell-num']}>
                    {Math.round((split[k] / splitSum) * 100)}%
                  </span>
                  <span className={[common['cell-num'], common.mute].join(' ')}>
                    {fmt(Math.round((totalRecs * split[k]) / splitSum))}
                  </span>
                </span>
              ))}

              <span className={style['split-bar']}>
                {SPLIT_KEYS.map((k, i) => (
                  <i
                    key={k}
                    style={{
                      width: `${(split[k] / splitSum) * 100}%`,
                      background: SPLIT_COLOR[i],
                    }}
                  />
                ))}
              </span>

              <span
                className={[style['split-row'], common.divider].join(' ')}
                style={{
                  gridTemplateColumns: '110px minmax(0,1fr)',
                  paddingTop: 16,
                }}
              >
                <span className={common.label}>분리 기준</span>
                <span style={{ maxWidth: 220 }}>
                  <Select
                    value={splitBy}
                    onChange={setSplitBy}
                    options={SPLIT_BY}
                  />
                </span>
              </span>
            </div>
          </div>
        </div>

        <div className={common.stack}>
          <SectionHead>학습 형식 검사</SectionHead>
          <div className={[common['card-pad'], common.stack].join(' ')}>
            {verify === 'idle' && (
              <>
                {FORMATS.map((k) => (
                  <Checkbox
                    key={k}
                    checked={!!formats[k]}
                    onChange={(v) => setFormats({ ...formats, [k]: v })}
                    label={k}
                  />
                ))}
                <span className={common.prose}>
                  실제 모델이 읽을 수 있는지 미리 확인합니다.
                </span>
              </>
            )}

            {verify === 'busy' && <ProgressBar value={64} height={8} />}

            {verify === 'done' && (
              <>
                {verifyRows.map((v) => (
                  <span key={v.format} className={style['check-line']}>
                    <span className={common.label}>{v.format}</span>
                    <Badge tone={v.tone === 'green' ? 'pass' : 'warn'}>
                      {fmt(v.passed)} / {fmt(v.total)}
                    </Badge>
                  </span>
                ))}

                {fails.length > 0 && !failOpen && (
                  <button
                    type='button'
                    className={style['link-btn']}
                    onClick={() => setFailOpen(true)}
                  >
                    실패 {fails.length}건 보기 →
                  </button>
                )}
                {fails.length > 0 && failOpen && (
                  <span className={common.stack}>
                    {fails.map((v) => (
                      <button
                        key={`${v.format}-${v.record_key}`}
                        type='button'
                        className={style['fail-link']}
                        onClick={() => go(`/record/${v.record_key}`)}
                      >
                        {v.record_key} — {v.reason}
                      </button>
                    ))}
                  </span>
                )}
              </>
            )}

            <Btn
              block
              fill='outline'
              disabled={verify === 'busy'}
              onClick={runVerify}
            >
              {verify === 'busy' ? '검사 중…' : '학습 형식 미리 검사'}
            </Btn>
          </div>

          <div className={[common['card-pad'], common.stack].join(' ')}>
            <span className={common.label}>버전 이름</span>
            <Textfield
              value={version}
              onChange={setVersion}
              placeholder='v0.4.0'
            />
            <span className={common.prose}>
              {verify === 'done'
                ? `검사 완료 · ${fmt(totalRecs)}건`
                : '학습 형식 검사를 마쳐야 만들 수 있습니다'}
            </span>
            <Btn
              size='md'
              block
              disabled={verify !== 'done' || busy || totalRecs === 0}
              onClick={create}
            >
              {busy ? '만드는 중…' : '데이터셋 만들기'}
            </Btn>
          </div>
        </div>
      </div>
    </div>
  );
}
