import { useState } from 'react';
import { useHistory, useLocation } from 'react-router-dom';
import classNames from 'classnames/bind';
import style from './LlmJudgeEvaluationPage.module.scss';
import ModelSelector from '@src/components/ModelSelector/ModelSelector';

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

export default function LlmJudgeEvaluationPage() {
  const history = useHistory();
  const location = useLocation();
  const wid = location.pathname.split('/')[3];

  const [selectedModel, setSelectedModel] = useState(null);
  const [judgeType, setJudgeType] = useState('commercial'); // 'commercial' | 'local'
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

  const toggleCriteria = (id) => {
    setSelectedCriteria((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const canRun =
    !!selectedModel &&
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
          <ModelSelector
            wid={wid}
            selected={selectedModel}
            onSelect={(id) => setSelectedModel(id)}
          />
        </section>

        {/* Judge 유형 선택 */}
        <section className={cx('section')}>
          <h2 className={cx('section-title')}>심사 LLM 선택</h2>
          <div className={cx('type-tabs')}>
            <button
              className={cx('tab', judgeType === 'commercial' && 'active')}
              onClick={() => setJudgeType('commercial')}
            >
              상용 LLM API
            </button>
            <button
              className={cx('tab', judgeType === 'local' && 'active')}
              onClick={() => setJudgeType('local')}
            >
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
