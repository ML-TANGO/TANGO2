import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { getJudges } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './JudgeEvaluation.module.scss';

const cx = classNames.bind(style);

// 기준 4종(§14.3). 라벨은 i18n. BE judge_<id> 로 저장(벤치마크 메트릭과 컬럼 분리).
const CRITERIA = ['accuracy', 'relevance', 'fluency', 'safety'];

// LLM-as-a-Judge 실행 설정(프로젝트 상속) — 모델·데이터셋은 프로젝트에서 잠금이라
// 심판(상용 키 / 로컬 URL) + 기준 + 커스텀 프롬프트만 여기서 구성. onRun(body) 로 상위가
// runJudge({ project_id, ...body }) 호출. ⚠️ api_key/base_url = transient(화면 state, 영속 X).
const JudgeRunConfig = ({ running, onRun }) => {
  const { t } = useTranslation();
  const [judges, setJudges] = useState(null); // { commercial, local, criteria, mock }
  const [judgeType, setJudgeType] = useState('commercial'); // commercial | local
  const [provider, setProvider] = useState('chatgpt');
  const [apiKey, setApiKey] = useState(''); // transient
  const [baseUrl, setBaseUrl] = useState('');
  const [judgeModel, setJudgeModel] = useState('');
  const [selCriteria, setSelCriteria] = useState(['accuracy', 'relevance']);
  const [customPrompt, setCustomPrompt] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await getJudges();
      if (!cancelled && res.status === STATUS_SUCCESS) setJudges(res.result);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const toggle = (arr, setArr, v) =>
    setArr(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  const mock = !!judges?.mock;
  const commercial = judges?.commercial ?? [];
  // 상용=키 필요(mock 면 생략 가능) / 로컬=URL 필요(BE SSRF 검증).
  const providerOk =
    judgeType === 'commercial'
      ? mock || apiKey.trim().length > 0
      : baseUrl.trim().length > 0;
  const canRun = selCriteria.length > 0 && providerOk && !running;

  const handleRun = () => {
    if (!canRun) return;
    const body = {
      provider: judgeType === 'local' ? 'local' : provider,
      criteria: selCriteria,
      custom_prompt: customPrompt || undefined,
    };
    if (judgeType === 'commercial') {
      body.api_key = apiKey || undefined; // transient — 보내고 화면 state 외 보관 X
    } else {
      body.base_url = baseUrl;
      body.judge_model = judgeModel || undefined;
    }
    onRun(body);
  };

  return (
    <div className={cx('judge')}>
      <section className={cx('section')}>
        <h3 className={cx('section-title')}>
          {t('evaluation.judge.selectJudge')}
          {mock && <span className={cx('mock-badge')}>mock</span>}
        </h3>
        <div className={cx('tabs')}>
          <button
            type='button'
            className={cx('tab', judgeType === 'commercial' && 'active')}
            onClick={() => setJudgeType('commercial')}
          >
            {t('evaluation.judge.commercial')}
          </button>
          <button
            type='button'
            className={cx('tab', judgeType === 'local' && 'active')}
            onClick={() => setJudgeType('local')}
          >
            {t('evaluation.judge.local')}
          </button>
        </div>

        {judgeType === 'commercial' ? (
          <>
            <div className={cx('judge-cards')}>
              {commercial.map((j) => (
                <button
                  key={j.id}
                  type='button'
                  className={cx('judge-card', provider === j.id && 'selected')}
                  onClick={() => setProvider(j.id)}
                >
                  <span className={cx('judge-label')}>{j.label}</span>
                  <span className={cx('judge-model')}>{j.model}</span>
                </button>
              ))}
            </div>
            <div className={cx('field')}>
              <label className={cx('field-label')}>
                {t('evaluation.judge.apiKey')}
              </label>
              <input
                className={cx('field-input')}
                type='password'
                placeholder={mock ? t('evaluation.judge.apiKeyMock') : 'sk-...'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                autoComplete='off'
              />
              <p className={cx('field-hint')}>
                {t('evaluation.judge.keyHint')}
              </p>
            </div>
          </>
        ) : (
          <>
            <div className={cx('field')}>
              <label className={cx('field-label')}>
                {t('evaluation.judge.endpoint')}
              </label>
              <input
                className={cx('field-input')}
                type='text'
                placeholder='http://my-llm.example.com/v1'
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
              />
              <p className={cx('field-hint')}>
                {t('evaluation.judge.endpointHint')}
              </p>
            </div>
            <div className={cx('field')}>
              <label className={cx('field-label')}>
                {t('evaluation.judge.modelName')}
              </label>
              <input
                className={cx('field-input')}
                type='text'
                placeholder='llama3-8b-instruct'
                value={judgeModel}
                onChange={(e) => setJudgeModel(e.target.value)}
              />
            </div>
          </>
        )}
      </section>

      <section className={cx('section')}>
        <h3 className={cx('section-title')}>
          {t('evaluation.judge.criteriaTitle')}
        </h3>
        <div className={cx('chip-row')}>
          {CRITERIA.map((c) => (
            <button
              key={c}
              type='button'
              className={cx('chip', selCriteria.includes(c) && 'selected')}
              onClick={() => toggle(selCriteria, setSelCriteria, c)}
            >
              {t(`evaluation.judge.criteria.${c}`)}
            </button>
          ))}
        </div>
      </section>

      <section className={cx('section')}>
        <h3 className={cx('section-title')}>{t('evaluation.judge.prompt')}</h3>
        <textarea
          className={cx('prompt')}
          rows={3}
          placeholder={t('evaluation.judge.promptPlaceholder')}
          value={customPrompt}
          onChange={(e) => setCustomPrompt(e.target.value)}
        />
      </section>

      <div className={cx('run-row')}>
        <button
          type='button'
          className={cx('run-btn', !canRun && 'disabled')}
          disabled={!canRun}
          onClick={handleRun}
        >
          {running ? t('evaluation.running') : t('evaluation.judge.run')}
        </button>
      </div>
    </div>
  );
};

export default JudgeRunConfig;
