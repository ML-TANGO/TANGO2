import { useRef, useState } from 'react';

import { postPlaygroundTestChat } from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './DualDirectInference.module.scss';

const cx = classNames.bind(style);

// 이중모델 직접 입력 추론(WBS 4.3, 목업 InferenceDetailPage 직접모드 포팅).
//   시스템 프롬프트 + 도메인 최적화(예시기반, WBS 4.2) + 사용자 입력 →
//   BE playground_dual_test(LLM1 재작성 → LLM2 추론). prompt_gen 은 세션 링크에서
//   서버 자동 파생하므로 FE 는 prompt_gen_playground_id 미전달.
const DualDirectInference = ({ playgroundId, promptModelName, inferenceModelName }) => {
  const [systemPrompt, setSystemPrompt] = useState('');
  const [userInput, setUserInput] = useState('');
  const [domainOpen, setDomainOpen] = useState(false);
  const [examples, setExamples] = useState([{ id: 0, query: '', answer: '' }]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null); // { optimized_prompt, output }
  const runningRef = useRef(false);
  const exampleIdRef = useRef(1); // 안정 key 용 증가 id(index-key 재정렬 버그 방지)

  const EXAMPLES_MAX = 10; // BE _DUAL_EXAMPLES_MAX 와 정합

  const handleExampleChange = (idx, field, value) =>
    setExamples((prev) =>
      prev.map((ex, i) => (i === idx ? { ...ex, [field]: value } : ex)),
    );
  const handleExampleAdd = () =>
    setExamples((prev) =>
      prev.length >= EXAMPLES_MAX
        ? prev
        : [...prev, { id: exampleIdRef.current++, query: '', answer: '' }],
    );
  const handleExampleRemove = (idx) =>
    setExamples((prev) => prev.filter((_, i) => i !== idx));

  const handleRun = async () => {
    if (!userInput.trim() || runningRef.current) return;
    runningRef.current = true;
    setRunning(true);
    setResult(null);
    try {
      const cleanExamples = examples.filter(
        (ex) => ex.query.trim() || ex.answer.trim(),
      );
      const res = await postPlaygroundTestChat({
        playground_id: playgroundId,
        test_type: 'question',
        test_question: userInput,
        session_id: sessionStorage.getItem('loginedSession'),
        system_prompt: systemPrompt.trim() || undefined,
        dual_examples: cleanExamples.length ? cleanExamples : undefined,
      });
      if (res.status === STATUS_SUCCESS) {
        const item = Array.isArray(res.result) ? res.result[0] : res.result;
        setResult({
          optimized_prompt: item?.optimized_prompt ?? '',
          output: item?.output ?? '',
        });
        return;
      }
      errorToastMessage(res.error, res.message);
    } catch (err) {
      errorToastMessage(null, '추론 중 오류가 발생했습니다.');
    } finally {
      runningRef.current = false;
      setRunning(false);
    }
  };

  return (
    <div className={cx('panel')}>
      <div className={cx('field')}>
        <div className={cx('prompt-row')}>
          <label className={cx('field-label')}>
            시스템 프롬프트
            {promptModelName && (
              <span className={cx('model-hint')}>→ {promptModelName}</span>
            )}
          </label>
          <button
            type="button"
            className={cx('domain-btn', domainOpen && 'active')}
            onClick={() => setDomainOpen((v) => !v)}
          >
            도메인 최적화 {domainOpen ? '▲' : '▼'}
          </button>
        </div>
        <textarea
          className={cx('textarea')}
          rows={3}
          maxLength={4000}
          aria-label="시스템 프롬프트"
          placeholder="시스템 역할이나 컨텍스트를 입력하세요 (선택)"
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
        />
        {domainOpen && (
          <div className={cx('domain-panel')}>
            {examples.map((ex, i) => (
              <div key={ex.id} className={cx('qa-set')}>
                <div className={cx('qa-header')}>
                  <span className={cx('qa-index')}>예시 {i + 1}</span>
                  {examples.length > 1 && (
                    <button
                      type="button"
                      className={cx('qa-remove')}
                      onClick={() => handleExampleRemove(i)}
                    >
                      삭제
                    </button>
                  )}
                </div>
                <textarea
                  className={cx('textarea')}
                  rows={2}
                  maxLength={2000}
                  aria-label={`예시 ${i + 1} 질의`}
                  placeholder="예시 질의를 입력하세요"
                  value={ex.query}
                  onChange={(e) => handleExampleChange(i, 'query', e.target.value)}
                />
                <textarea
                  className={cx('textarea')}
                  rows={2}
                  maxLength={2000}
                  aria-label={`예시 ${i + 1} 답변`}
                  placeholder="예시 답변을 입력하세요"
                  value={ex.answer}
                  onChange={(e) =>
                    handleExampleChange(i, 'answer', e.target.value)
                  }
                />
              </div>
            ))}
            {examples.length < EXAMPLES_MAX && (
              <button
                type="button"
                className={cx('qa-add')}
                onClick={handleExampleAdd}
              >
                + 예시 추가
              </button>
            )}
          </div>
        )}
      </div>

      <div className={cx('field')}>
        <label className={cx('field-label')}>
          사용자 입력
          {inferenceModelName && (
            <span className={cx('model-hint')}>→ {inferenceModelName}</span>
          )}
        </label>
        <textarea
          className={cx('textarea')}
          rows={5}
          maxLength={4000}
          aria-label="사용자 입력"
          placeholder="추론할 내용을 입력하세요..."
          value={userInput}
          onChange={(e) => setUserInput(e.target.value)}
        />
      </div>

      <div className={cx('run-row')}>
        <button
          type="button"
          className={cx('run-btn', (!userInput.trim() || running) && 'disabled')}
          disabled={!userInput.trim() || running}
          onClick={handleRun}
        >
          {running ? '추론 중...' : '추론 실행'}
        </button>
      </div>

      {result && (
        <div className={cx('result')}>
          {result.optimized_prompt && (
            <div className={cx('result-box', 'optimized')}>
              <div className={cx('result-head')}>
                📝 최적화된 프롬프트 (LLM1)
              </div>
              <div className={cx('result-body')}>{result.optimized_prompt}</div>
            </div>
          )}
          <div className={cx('result-box', 'answer')}>
            <div className={cx('result-head')}>🤖 추론 결과 (LLM2)</div>
            <div className={cx('result-body')}>{result.output || '-'}</div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DualDirectInference;
