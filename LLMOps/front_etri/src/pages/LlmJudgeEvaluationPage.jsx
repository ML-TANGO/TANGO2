import { useState, useEffect } from 'react';
import { useHistory, useLocation } from 'react-router-dom';
import classNames from 'classnames/bind';
import style from './LlmJudgeEvaluationPage.module.scss';
import ModelSelector from '@src/components/ModelSelector/ModelSelector';
import { callApi, STATUS_SUCCESS } from '@src/network';
import { convertBinaryByte } from '@src/utils';
import { convertLocalTime } from '@src/datetimeUtils';

const cx = classNames.bind(style);

const COMMERCIAL_JUDGES = [
  { id: 'chatgpt',  label: 'ChatGPT',  model: 'gpt-4o',              icon: '🟢' },
  { id: 'claude',   label: 'Claude',   model: 'claude-opus-4-8',     icon: '🟠' },
  { id: 'gemini',   label: 'Gemini',   model: 'gemini-2.0-flash',    icon: '🔵' },
];

const CRITERIA = [
  { id: 'accuracy',    label: '정확성',  desc: '사실 오류 없이 올바른 답변인가?' },
  { id: 'relevance',   label: '관련성',  desc: '질문과 관련된 내용을 담고 있는가?' },
  { id: 'fluency',     label: '유창성',  desc: '자연스럽고 읽기 쉬운 문장인가?' },
  { id: 'safety',      label: '안전성',  desc: '유해하거나 편향된 내용이 없는가?' },
];

const METRICS = [
  { id: 'meteor', label: 'METEOR',  desc: '번역/생성 품질 — 단어 정렬 기반' },
  { id: 'cider',  label: 'CIDEr',   desc: '이미지 캡셔닝 품질 — TF-IDF 가중치' },
  { id: 'spice',  label: 'SPICE',   desc: '장면 그래프 기반 의미 유사도' },
  { id: 'bleu',   label: 'BLEU',    desc: 'N-gram 정밀도 기반 번역 품질' },
  { id: 'rouge',  label: 'ROUGE-L', desc: '최장 공통 부분 수열 기반 요약 품질' },
];

function DatasetSelector({ datasets, selectedDataset, onSelect, keyword, onKeywordChange }) {
  const filtered = datasets.filter((d) => d.dataset_name.includes(keyword));
  return (
    <div className={cx('ds-block')}>
      <div className={cx('ds-header')}>
        <span className={cx('ds-title')}>데이터셋 선택</span>
        <span className={cx('ds-count')}>{datasets.length}개</span>
        <div className={cx('ds-spacer')} />
        {selectedDataset && (
          <span className={cx('ds-selected-label')}>
            선택됨: <strong>{selectedDataset.dataset_name}</strong>
          </span>
        )}
      </div>
      <div className={cx('ds-search-wrap')}>
        <input
          className={cx('ds-search-input')}
          placeholder="데이터셋 이름 검색..."
          value={keyword}
          onChange={(e) => onKeywordChange(e.target.value)}
        />
        {keyword && (
          <button className={cx('ds-search-clear')} onClick={() => onKeywordChange('')}>✕</button>
        )}
      </div>
      {filtered.length === 0 ? (
        <div className={cx('ds-empty')}>등록된 데이터셋이 없습니다.</div>
      ) : (
        <div className={cx('ds-list')}>
          {filtered.map((item) => {
            const isSel = selectedDataset?.id === item.id;
            return (
              <div
                key={item.id}
                className={cx('ds-card', isSel && 'ds-card--on')}
                onClick={() => onSelect(isSel ? null : item)}
              >
                <div className={cx('ds-check', isSel && 'ds-check--on')}>{isSel && '✓'}</div>
                <div className={cx('ds-card-body')}>
                  <div className={cx('ds-card-name-row')}>
                    <span className={cx('ds-card-name')}>{item.dataset_name}</span>
                    {item.format && <span className={cx('ds-format-badge')}>{item.format}</span>}
                    <span className={cx('ds-access-badge', Number(item.access) === 0 ? 'ds-ro' : 'ds-rw')}>
                      {Number(item.access) === 0 ? '읽기전용' : '읽기/쓰기'}
                    </span>
                  </div>
                  <div className={cx('ds-card-meta')}>
                    {item.owner && <><span>{item.owner}</span><span className={cx('dot')}>·</span></>}
                    <span>{item.size ? convertBinaryByte(item.size) : '0 Bytes'}</span>
                    {item.file_count != null && (
                      <><span className={cx('dot')}>·</span><span>{item.file_count.toLocaleString()}개 파일</span></>
                    )}
                    {item.create_datetime && (
                      <><span className={cx('dot')}>·</span><span>{convertLocalTime(item.create_datetime)}</span></>
                    )}
                  </div>
                  {item.description && <div className={cx('ds-card-desc')}>{item.description}</div>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function MetricSelector({ selectedMetrics, onToggle }) {
  return (
    <div className={cx('metric-block')}>
      <div className={cx('metric-header')}>
        <span className={cx('ds-title')}>평가 메트릭 선택</span>
        {selectedMetrics.length > 0 && (
          <span className={cx('ds-count')}>{selectedMetrics.length}개 선택됨</span>
        )}
      </div>
      <div className={cx('option-grid')}>
        {METRICS.map((m) => (
          <div
            key={m.id}
            className={cx('option-card', selectedMetrics.includes(m.id) && 'selected')}
            onClick={() => onToggle(m.id)}
          >
            <div className={cx('option-name')}>{m.label}</div>
            <div className={cx('option-desc')}>{m.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function LlmJudgeEvaluationPage() {
  const history = useHistory();
  const location = useLocation();
  const wid = location.pathname.split('/')[3];

  const [selectedModel, setSelectedModel] = useState(null);
  const [judgeType, setJudgeType] = useState('commercial');
  const [selectedJudge, setSelectedJudge] = useState('chatgpt');
  const [apiKey, setApiKey] = useState('');
  const [localEndpoint, setLocalEndpoint] = useState('http://localhost:8000/v1');
  const [localModel, setLocalModel] = useState('');
  const [selectedCriteria, setSelectedCriteria] = useState(['accuracy', 'relevance']);
  const [judgePrompt, setJudgePrompt] = useState(
    '아래 모델 출력이 주어진 입력에 대해 얼마나 적절한지 1~5점으로 평가하고, 이유를 설명하세요.',
  );
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);

  const [datasets, setDatasets] = useState([]);
  const [datasetKeyword, setDatasetKeyword] = useState('');
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [selectedMetrics, setSelectedMetrics] = useState([]);

  useEffect(() => {
    callApi({ url: `datasets?workspace_id=${wid}`, method: 'GET' }).then((res) => {
      if (res.status === STATUS_SUCCESS) setDatasets(res.result?.list || []);
    });
  }, [wid]);

  const toggleCriteria = (id) =>
    setSelectedCriteria((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  const toggleMetric = (id) =>
    setSelectedMetrics((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  const canRun =
    !!selectedModel &&
    !!selectedDataset &&
    selectedMetrics.length > 0 &&
    selectedCriteria.length > 0 &&
    (judgeType === 'commercial' ? apiKey.trim().length > 0 : localEndpoint.trim().length > 0);

  const handleRun = () => {
    if (!canRun) return;
    setRunning(true);
    setResults(null);
    setTimeout(() => {
      const judge =
        judgeType === 'commercial'
          ? COMMERCIAL_JUDGES.find((j) => j.id === selectedJudge)?.label
          : `로컬 LLM (${localModel || localEndpoint})`;
      const mockResults = Array.from({ length: 5 }, (_, i) => ({
        sample: `Sample #${i + 1}`,
        judge,
        dataset: selectedDataset?.dataset_name,
        metricScores: Object.fromEntries(
          selectedMetrics.map((m) => [m, (Math.random() * 0.35 + 0.55).toFixed(4)])
        ),
        precision: (Math.random() * 0.15 + 0.75).toFixed(4),
        recall:    (Math.random() * 0.15 + 0.70).toFixed(4),
        f1:        (Math.random() * 0.15 + 0.72).toFixed(4),
        criteria: selectedCriteria.map((c) => CRITERIA.find((x) => x.id === c)?.label).join(', '),
        score: (Math.random() * 2 + 3).toFixed(1),
        reason: '모델 출력이 전반적으로 질문에 부합하며 정확한 정보를 제공합니다.',
      }));
      setResults(mockResults);
      setRunning(false);
    }, 3000);
  };

  return (
    <div className={cx('page')}>
      <div className={cx('header')}>
        <button className={cx('back-btn')} onClick={() => history.push(`/user/workspace/${wid}/services`)}>
          ← 목록으로
        </button>
        <h1 className={cx('title')}>LLM-as-a-Judge 평가</h1>
      </div>

      <div className={cx('body')}>
        <section className={cx('section')}>
          <h2 className={cx('section-title')}>평가 대상 모델</h2>
          <ModelSelector wid={wid} selected={selectedModel} onSelect={(id) => setSelectedModel(id)} />
        </section>

        {/* 심사 LLM 선택 */}
        <section className={cx('section')}>
          <h2 className={cx('section-title')}>심사 LLM 선택</h2>
          <div className={cx('type-tabs')}>
            <button className={cx('tab', judgeType === 'commercial' && 'active')} onClick={() => setJudgeType('commercial')}>
              상용 LLM API
            </button>
            <button className={cx('tab', judgeType === 'local' && 'active')} onClick={() => setJudgeType('local')}>
              로컬 LLM
            </button>
          </div>

          {judgeType === 'commercial' ? (
            <div className={cx('judge-area')}>
              <div className={cx('judge-cards')}>
                {COMMERCIAL_JUDGES.map((j) => (
                  <div
                    key={j.id}
                    className={cx('judge-card', selectedJudge === j.id && 'selected')}
                    onClick={() => setSelectedJudge(j.id)}
                  >
                    <span className={cx('judge-icon')}>{j.icon}</span>
                    <span className={cx('judge-label')}>{j.label}</span>
                    <span className={cx('judge-model')}>{j.model}</span>
                  </div>
                ))}
              </div>
              <div className={cx('field')}>
                <label className={cx('field-label')}>API Key</label>
                <input
                  className={cx('field-input')}
                  type='password'
                  placeholder='sk-...'
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
              </div>
              {/* 데이터셋 선택기 */}
              <DatasetSelector
                datasets={datasets}
                selectedDataset={selectedDataset}
                onSelect={setSelectedDataset}
                keyword={datasetKeyword}
                onKeywordChange={setDatasetKeyword}
              />
              {/* 평가 메트릭 선택 */}
              <MetricSelector selectedMetrics={selectedMetrics} onToggle={toggleMetric} />
            </div>
          ) : (
            <div className={cx('judge-area')}>
              <div className={cx('field')}>
                <label className={cx('field-label')}>Endpoint URL</label>
                <input
                  className={cx('field-input')}
                  type='text'
                  placeholder='http://localhost:8000/v1'
                  value={localEndpoint}
                  onChange={(e) => setLocalEndpoint(e.target.value)}
                />
              </div>
              <div className={cx('field')}>
                <label className={cx('field-label')}>Model Name</label>
                <input
                  className={cx('field-input')}
                  type='text'
                  placeholder='예: llama3-8b-instruct'
                  value={localModel}
                  onChange={(e) => setLocalModel(e.target.value)}
                />
              </div>
              {/* 데이터셋 선택기 */}
              <DatasetSelector
                datasets={datasets}
                selectedDataset={selectedDataset}
                onSelect={setSelectedDataset}
                keyword={datasetKeyword}
                onKeywordChange={setDatasetKeyword}
              />
              {/* 평가 메트릭 선택 */}
              <MetricSelector selectedMetrics={selectedMetrics} onToggle={toggleMetric} />
            </div>
          )}
        </section>

        {/* 평가 기준 */}
        <section className={cx('section')}>
          <h2 className={cx('section-title')}>평가 기준</h2>
          <div className={cx('criteria-grid')}>
            {CRITERIA.map((c) => (
              <div
                key={c.id}
                className={cx('criteria-card', selectedCriteria.includes(c.id) && 'selected')}
                onClick={() => toggleCriteria(c.id)}
              >
                <div className={cx('criteria-label')}>{c.label}</div>
                <div className={cx('criteria-desc')}>{c.desc}</div>
              </div>
            ))}
          </div>
        </section>

        {/* 심사 프롬프트 */}
        <section className={cx('section')}>
          <h2 className={cx('section-title')}>심사 프롬프트</h2>
          <textarea
            className={cx('prompt-textarea')}
            value={judgePrompt}
            onChange={(e) => setJudgePrompt(e.target.value)}
            rows={4}
          />
        </section>

        <div className={cx('run-row')}>
          <button
            className={cx('run-btn', !canRun && 'disabled')}
            disabled={!canRun || running}
            onClick={handleRun}
          >
            {running ? '평가 실행 중...' : '평가 시작'}
          </button>
        </div>

        {results && (
          <section className={cx('section')}>
            <h2 className={cx('section-title')}>평가 결과</h2>
            <table className={cx('result-table')}>
              <thead>
                <tr>
                  <th>샘플</th>
                  <th>심사 LLM</th>
                  <th>데이터셋</th>
                  {selectedMetrics.map((m) => (
                    <th key={m}>{METRICS.find((x) => x.id === m)?.label}</th>
                  ))}
                  <th>Precision</th>
                  <th>Recall</th>
                  <th>F1-Score</th>
                  <th>평가 기준</th>
                  <th>점수 (1–5)</th>
                  <th>이유</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, i) => (
                  <tr key={i}>
                    <td>{r.sample}</td>
                    <td>{r.judge}</td>
                    <td>{r.dataset}</td>
                    {selectedMetrics.map((m) => (
                      <td key={m} className={cx('score')}>{r.metricScores[m]}</td>
                    ))}
                    <td className={cx('score')}>{r.precision}</td>
                    <td className={cx('score')}>{r.recall}</td>
                    <td className={cx('score')}>{r.f1}</td>
                    <td>{r.criteria}</td>
                    <td className={cx('score')}>{r.score}</td>
                    <td className={cx('reason')}>{r.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </div>
    </div>
  );
}
