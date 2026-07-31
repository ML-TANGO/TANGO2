import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Badge,
  ButtonV2,
  Checkbox,
  InputPassword,
  InputText,
  Radio,
  Selectbox,
  Textarea,
} from '@jonathan/ui-react';

import GuideBox from '@src/components/molecules/GuideBox';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { getJudges } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './JudgeEvaluation.module.scss';

const cx = classNames.bind(style);

// 기준 4종(§14.3). 라벨은 i18n. BE judge_<id> 로 저장(벤치마크 메트릭과 컬럼 분리).
const CRITERIA = ['accuracy', 'relevance', 'fluency', 'safety'];

// 실행 환경 표시는 조나단 Badge type으로 매핑한다.
const MODE_BADGE_TYPE = {
  mock: 'gray',
};

// LLM-as-a-Judge 실행 설정(프로젝트 상속) — 모델·데이터셋은 프로젝트에서 잠금이라
// 심판(상용 키 / 로컬 URL) + 기준 + 커스텀 프롬프트만 여기서 구성. onRun(body) 로 상위가
// runJudge({ project_id, ...body }) 호출. api_key/base_url은 화면 state에서만 유지한다.
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
  const providerOptions = commercial.map((judge) => ({
    label: judge.model ? `${judge.label} · ${judge.model}` : judge.label,
    value: judge.id,
  }));
  const selectedProvider = providerOptions.find(
    (item) => item.value === provider,
  );
  const judgeTypeOptions = [
    {
      label: t('evaluation.judge.commercial'),
      value: 'commercial',
    },
    {
      label: t('evaluation.judge.local'),
      value: 'local',
    },
  ];

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
    <div className={cx('judge-config')}>
      <section className={cx('panel')}>
        <div className={cx('panel-head')}>
          <div>
            <h3 className={cx('panel-title')}>
              {t('evaluation.judge.selectJudge')}
            </h3>
          </div>
          {mock && (
            <Badge label='mock' type={MODE_BADGE_TYPE.mock} size='sm' />
          )}
        </div>

        <div className={cx('judge-type')}>
          <Radio
            name='judgeType'
            options={judgeTypeOptions}
            selectedValue={judgeType}
            onChange={(e) => setJudgeType(e.target.value)}
          />
        </div>

        {judgeType === 'commercial' ? (
          <div className={cx('form-stack')}>
            <InputBoxWithLabel
              labelText={t('evaluation.judge.selectJudge')}
              labelSize='medium'
              disableErrorMsg
            >
              <div className={cx('control')}>
                <Selectbox
                  size='medium'
                  list={providerOptions}
                  selectedItem={selectedProvider}
                  placeholder={t('evaluation.judge.selectJudge')}
                  onChange={(item) => setProvider(item.value)}
                  customStyle={{
                    selectboxForm: { width: '100%' },
                    listForm: { width: '100%' },
                  }}
                />
              </div>
            </InputBoxWithLabel>

            <InputBoxWithLabel
              labelText={t('evaluation.judge.apiKey')}
              labelSize='medium'
              disableErrorMsg
            >
              <div className={cx('control')}>
                <InputPassword
                  size='medium'
                  placeholder={
                    mock ? t('evaluation.judge.apiKeyMock') : 'sk-...'
                  }
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  options={{ autoComplete: 'off' }}
                  disableShowBtn
                  customStyle={{ width: '100%' }}
                />
              </div>
            </InputBoxWithLabel>

            <div className={cx('guide')}>
              <GuideBox
                title={t('evaluation.judge.apiKey')}
                isTitleIcon
                textList={[
                  t('evaluation.judge.keyHint'),
                  ...(mock ? [t('evaluation.judge.apiKeyMock')] : []),
                ]}
              />
            </div>
          </div>
        ) : (
          <div className={cx('form-stack')}>
            <InputBoxWithLabel
              labelText={t('evaluation.judge.endpoint')}
              labelSize='medium'
              disableErrorMsg
            >
              <div className={cx('control')}>
                <InputText
                  size='medium'
                  placeholder='http://my-llm.example.com/v1'
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  disableLeftIcon
                  disableClearBtn
                  options={{ autoComplete: 'off' }}
                  customStyle={{ width: '100%' }}
                />
              </div>
            </InputBoxWithLabel>

            <InputBoxWithLabel
              labelText={t('evaluation.judge.modelName')}
              labelSize='medium'
              disableErrorMsg
            >
              <div className={cx('control')}>
                <InputText
                  size='medium'
                  placeholder='llama3-8b-instruct'
                  value={judgeModel}
                  onChange={(e) => setJudgeModel(e.target.value)}
                  disableLeftIcon
                  disableClearBtn
                  customStyle={{ width: '100%' }}
                />
              </div>
            </InputBoxWithLabel>

            <div className={cx('guide')}>
              <GuideBox
                title={t('evaluation.judge.endpoint')}
                isTitleIcon
                textList={[t('evaluation.judge.endpointHint')]}
              />
            </div>
          </div>
        )}
      </section>

      <section className={cx('panel')}>
        <h3 className={cx('panel-title')}>
          {t('evaluation.judge.criteriaTitle')}
        </h3>
        <div className={cx('criteria-grid')}>
          {CRITERIA.map((c) => (
            <div key={c} className={cx('criterion-option')}>
              <Checkbox
                checked={selCriteria.includes(c)}
                label={t(`evaluation.judge.criteria.${c}`)}
                onChange={() => toggle(selCriteria, setSelCriteria, c)}
              />
            </div>
          ))}
        </div>
      </section>

      <section className={cx('panel')}>
        <h3 className={cx('panel-title')}>{t('evaluation.judge.prompt')}</h3>
        <Textarea
          size='large'
          placeholder={t('evaluation.judge.promptPlaceholder')}
          value={customPrompt}
          onChange={(e) => setCustomPrompt(e.target.value)}
          customStyle={{ width: '100%', minHeight: '112px' }}
        />
      </section>

      <div className={cx('actions')}>
        <ButtonV2
          type='solid'
          colorType='blue'
          size='l'
          label={
            running ? t('evaluation.running') : t('evaluation.judge.run')
          }
          disabled={!canRun}
          isLoading={running}
          onClick={handleRun}
        />
      </div>
    </div>
  );
};

export default JudgeRunConfig;
