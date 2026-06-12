import { useState, useEffect } from 'react';
import { useHistory, useLocation, useParams } from 'react-router-dom';
import { callApi, STATUS_SUCCESS } from '@src/network';
import classNames from 'classnames/bind';
import style from './InferenceDetailPage.module.scss';

const cx = classNames.bind(style);

const METRICS = [
  { id: 'spice',  label: 'SPICE' },
  { id: 'bleu',   label: 'BLEU' },
  { id: 'meteor', label: 'METEOR' },
  { id: 'rouge',  label: 'ROUGE-L' },
  { id: 'cider',  label: 'CIDEr' },
];

const SAMPLE_COUNTS = [10, 50, 100, 500];

export default function InferenceDetailPage() {
  const history  = useHistory();
  const location = useLocation();
  const { sid }  = useParams();
  const wid      = location.pathname.split('/')[3];

  const [session, setSession]   = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [mode, setMode]         = useState('direct');

  // direct inference state
  const [systemPrompt, setSystemPrompt] = useState('');
  const [userPrompt, setUserPrompt]     = useState('');
  const [directRunning, setDirectRunning] = useState(false);
  const [directResult, setDirectResult]   = useState(null);

  // batch inference state
  const [selectedDataset, setSelectedDataset]   = useState(null);
  const [sampleCount, setSampleCount]           = useState(10);
  const [selectedMetrics, setSelectedMetrics]   = useState(['spice', 'bleu']);
  const [batchRunning, setBatchRunning]         = useState(false);
  const [batchResults, setBatchResults]         = useState(null);

  useEffect(() => {
    callApi({ url: `inference/sessions?workspace_id=${wid}`, method: 'GET' }).then((res) => {
      if (res.status === STATUS_SUCCESS) {
        const list = Array.isArray(res.result) ? res.result : [];
        setSession(list.find((s) => s.id === sid) ?? null);
      }
    });
    callApi({ url: `datasets?workspace_id=${wid}`, method: 'GET' }).then((res) => {
      if (res.status === STATUS_SUCCESS) {
        const raw = res.result;
        const list = Array.isArray(raw) ? raw : (raw?.list ?? []);
        setDatasets(list);
      }
    });
  }, [wid, sid]);

  const toggleMetric = (id) =>
    setSelectedMetrics((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );

  const handleDirectRun = () => {
    if (!userPrompt.trim()) return;
    setDirectRunning(true);
    setDirectResult(null);
    const infModel = session?.models?.find((m) => m.role === 'inference');
    setTimeout(() => {
      setDirectResult({
        response: `[${infModel?.name ?? '모델'} 응답]\n입력 "${userPrompt.slice(0, 60)}${userPrompt.length > 60 ? '…' : ''}"에 대한 추론 결과입니다. 모델이 컨텍스트를 분석하여 가장 적절한 응답을 생성하였습니다.`,
        latency: (Math.random() * 1.5 + 0.4).toFixed(2),
        tokens:  Math.floor(Math.random() * 220 + 40),
      });
      setDirectRunning(false);
    }, 2000);
  };

  const handleBatchRun = () => {
    if (!selectedDataset) return;
    setBatchRunning(true);
    setBatchResults(null);
    setTimeout(() => {
      const samples = Array.from({ length: sampleCount }, (_, i) => ({
        idx: i + 1,
        input:  `샘플 #${i + 1} 입력 텍스트`,
        output: `샘플 #${i + 1} 추론 결과`,
        scores: Object.fromEntries(
          selectedMetrics.map((m) => [m, (Math.random() * 0.35 + 0.55).toFixed(4)]),
        ),
      }));
      const summary = Object.fromEntries(
        selectedMetrics.map((m) => [
          m,
          (
            samples.reduce((acc, s) => acc + parseFloat(s.scores[m] ?? 0), 0) /
            samples.length
          ).toFixed(4),
        ]),
      );
      setBatchResults({ samples, summary });
      setBatchRunning(false);
    }, 3500);
  };

  if (!session) {
    return <div className={cx('loading')}>세션 정보를 불러오는 중...</div>;
  }

  const infModel    = session.models?.find((m) => m.role === 'inference');
  const promptModel = session.models?.find((m) => m.role === 'prompt');

  return (
    <div className={cx('page')}>
      {/* Header */}
      <div className={cx('header')}>
        <button
          className={cx('back-btn')}
          onClick={() => history.push(`/user/workspace/${wid}/inference`)}
        >
          ← 목록으로
        </button>
        <div className={cx('header-info')}>
          <h1 className={cx('title')}>{session.name}</h1>
          <div className={cx('meta-row')}>
            {promptModel && (
              <span className={cx('meta-tag', 'prompt')}>📝 프롬프트: {promptModel.name}</span>
            )}
            {infModel && (
              <span className={cx('meta-tag', 'inference')}>🤖 추론: {infModel.name}</span>
            )}
            <span className={cx('meta-tag', 'res')}>{session.resources?.gpu}</span>
            <span className={cx('meta-tag', 'res')}>CPU {session.resources?.cpu}코어</span>
            <span className={cx('meta-tag', 'res')}>{session.resources?.memory}</span>
            <span className={cx('meta-tag', 'res')}>레플리카 {session.resources?.replicas}</span>
          </div>
        </div>
      </div>

      {/* Mode tabs */}
      <div className={cx('mode-tabs')}>
        <button
          className={cx('tab', mode === 'direct' && 'active')}
          onClick={() => setMode('direct')}
        >
          직접 입력 추론
        </button>
        <button
          className={cx('tab', mode === 'batch' && 'active')}
          onClick={() => setMode('batch')}
        >
          데이터셋 일괄 추론
        </button>
      </div>

      {/* ── 직접 입력 추론 ── */}
      {mode === 'direct' && (
        <div className={cx('panel')}>
          {promptModel && (
            <div className={cx('field')}>
              <label className={cx('field-label')}>
                시스템 프롬프트
                <span className={cx('model-hint')}>→ {promptModel.name}</span>
              </label>
              <textarea
                className={cx('textarea')}
                rows={3}
                placeholder='시스템 역할이나 컨텍스트를 입력하세요 (선택)'
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
              />
            </div>
          )}
          <div className={cx('field')}>
            <label className={cx('field-label')}>
              사용자 입력
              <span className={cx('model-hint')}>→ {infModel?.name}</span>
            </label>
            <textarea
              className={cx('textarea')}
              rows={6}
              placeholder='추론할 내용을 입력하세요...'
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
            />
          </div>
          <div className={cx('run-row')}>
            <button
              className={cx('run-btn', (!userPrompt.trim() || directRunning) && 'disabled')}
              disabled={!userPrompt.trim() || directRunning}
              onClick={handleDirectRun}
            >
              {directRunning ? '추론 중...' : '추론 실행'}
            </button>
          </div>

          {directResult && (
            <div className={cx('result-box')}>
              <div className={cx('result-header')}>
                <span>추론 결과</span>
                <span className={cx('result-meta')}>
                  응답 시간 {directResult.latency}s · 토큰 {directResult.tokens}
                </span>
              </div>
              <div className={cx('result-body')}>{directResult.response}</div>
            </div>
          )}
        </div>
      )}

      {/* ── 데이터셋 일괄 추론 ── */}
      {mode === 'batch' && (
        <div className={cx('panel')}>
          <div className={cx('batch-config')}>
            {/* 데이터셋 */}
            <section className={cx('section')}>
              <h3 className={cx('section-title')}>데이터셋 선택</h3>
              {datasets.length === 0 ? (
                <div className={cx('empty')}>업로드된 데이터셋이 없습니다.</div>
              ) : (
                <div className={cx('ds-grid')}>
                  {datasets.map((d) => (
                    <div
                      key={d.id ?? d.name}
                      className={cx('ds-card', selectedDataset === (d.id ?? d.name) && 'selected')}
                      onClick={() => setSelectedDataset(d.id ?? d.name)}
                    >
                      <div className={cx('ds-name')}>{d.name}</div>
                      <div className={cx('ds-desc')}>{d.description || '-'}</div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* 샘플 수 */}
            <section className={cx('section')}>
              <h3 className={cx('section-title')}>샘플 수</h3>
              <div className={cx('chip-row')}>
                {SAMPLE_COUNTS.map((n) => (
                  <div
                    key={n}
                    className={cx('chip', sampleCount === n && 'selected')}
                    onClick={() => setSampleCount(n)}
                  >
                    {n}개
                  </div>
                ))}
              </div>
            </section>

            {/* 정량 메트릭 */}
            <section className={cx('section')}>
              <h3 className={cx('section-title')}>정량 메트릭 (선택)</h3>
              <div className={cx('chip-row')}>
                {METRICS.map((m) => (
                  <div
                    key={m.id}
                    className={cx('chip', selectedMetrics.includes(m.id) && 'selected')}
                    onClick={() => toggleMetric(m.id)}
                  >
                    {m.label}
                  </div>
                ))}
              </div>
            </section>
          </div>

          <div className={cx('run-row')}>
            <button
              className={cx('run-btn', (!selectedDataset || batchRunning) && 'disabled')}
              disabled={!selectedDataset || batchRunning}
              onClick={handleBatchRun}
            >
              {batchRunning ? '일괄 추론 실행 중...' : '일괄 추론 실행'}
            </button>
          </div>

          {batchResults && (
            <div className={cx('batch-results')}>
              {/* 종합 요약 */}
              {selectedMetrics.length > 0 && (
                <div className={cx('summary-box')}>
                  <h3 className={cx('summary-title')}>종합 결과 (평균)</h3>
                  <div className={cx('summary-metrics')}>
                    {selectedMetrics.map((m) => (
                      <div key={m} className={cx('summary-metric')}>
                        <span className={cx('sm-label')}>
                          {METRICS.find((x) => x.id === m)?.label}
                        </span>
                        <span className={cx('sm-value')}>{batchResults.summary[m]}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 샘플별 결과 테이블 */}
              <div className={cx('table-wrap')}>
                <table className={cx('result-table')}>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>입력</th>
                      <th>출력</th>
                      {selectedMetrics.map((m) => (
                        <th key={m}>{METRICS.find((x) => x.id === m)?.label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {batchResults.samples.map((s) => (
                      <tr key={s.idx}>
                        <td>{s.idx}</td>
                        <td>{s.input}</td>
                        <td>{s.output}</td>
                        {selectedMetrics.map((m) => (
                          <td key={m} className={cx('score')}>{s.scores[m]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
