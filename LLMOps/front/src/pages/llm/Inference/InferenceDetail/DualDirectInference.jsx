import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, ButtonV2, Textarea } from '@jonathan/ui-react';

import { postPlaygroundTestChat } from '@src/apis/llm/playground';
import {
  ImageUploadField,
  AISRowsForm,
  OutputTypeSelect,
} from '@src/components/MultiModalInput';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './DualDirectInference.module.scss';

const cx = classNames.bind(style);

// partner schema(RunParams.AISRow) 기본 자선 행 — ExternalTestCom 과 동일.
const MY_SHIP_DEFAULT = {
  ship_id: 1,
  my_ship: 1,
  latitude: 35.1,
  longitude: 129.0,
  knot: 5,
  heading: 90,
  length: 100,
  width: 20,
  draft: 5,
};

// 조나단 Textarea 는 rest props 를 wrapper div 로 보내므로 aria-label 은 options 로 넘겨야
//   내부 <textarea> 에 붙는다(접근성 이름 유지).
const taOptions = (label, rows) => ({ 'aria-label': label, rows });

// 이중모델 직접 입력 추론(WBS 4.3).
//   시스템 프롬프트 + 도메인 최적화(예시기반) + 사용자 입력 → BE playground_dual_test
//   (LLM1 재작성 → LLM2 추론). prompt_gen 은 세션 링크에서 서버 자동 파생.
//   isExternal=true → LLM2 가 외부 SDS(VLM): 이미지+AIS+출력유형 입력을 추가로 받아
//   external_payload 로 전달(BE 가 LLM1 출력을 custom_prompt 로 연결). text→SDS.
//   UI 는 플랫폼 조나단 규약 — 섹션=카드(padding 24/radius 16), 입력=Textarea, 버튼=ButtonV2,
//   모델/단계 표기=Badge(이모지 미사용).
const DualDirectInference = ({
  playgroundId,
  promptModelName,
  inferenceModelName,
  isExternal = false,
}) => {
  const { t } = useTranslation();
  const [systemPrompt, setSystemPrompt] = useState('');
  const [userInput, setUserInput] = useState('');
  const [domainOpen, setDomainOpen] = useState(false);
  const [examples, setExamples] = useState([{ id: 0, query: '', answer: '' }]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null); // { optimized_prompt, output }
  const runningRef = useRef(false);
  const exampleIdRef = useRef(1); // 안정 key 용 증가 id(index-key 재정렬 버그 방지)

  // 외부 SDS(VLM) 입력 — isExternal 일 때만 사용.
  const [imageB64, setImageB64] = useState('');
  const [aisRows, setAisRows] = useState([{ ...MY_SHIP_DEFAULT }]);
  const [outputType, setOutputType] = useState('한글 해상상황묘사');

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

  const externalReady =
    !isExternal || (!!imageB64 && aisRows.some((r) => Number(r.my_ship) === 1));
  const canRun = !!userInput.trim() && !running && externalReady;

  const handleRun = async () => {
    if (!canRun || runningRef.current) return;
    if (isExternal && !imageB64) {
      errorToastMessage(null, t('inference.dual.imageRequired'));
      return;
    }
    if (isExternal && !aisRows.some((r) => Number(r.my_ship) === 1)) {
      errorToastMessage(null, t('inference.dual.myShipRequired'));
      return;
    }
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
        // LLM2 가 외부 SDS 면 VLM 입력 동봉(custom_prompt 는 BE 가 LLM1 출력으로 채움).
        external_payload: isExternal
          ? {
              image_base64: imageB64,
              ais_rows: aisRows,
              output_type: outputType,
              max_new_tokens: 256,
              repetition_penalty: 1.1,
              do_sample: false,
            }
          : undefined,
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
      errorToastMessage(null, t('inference.dual.runError'));
    } finally {
      runningRef.current = false;
      setRunning(false);
    }
  };

  return (
    <div className={cx('panel')}>
      <section className={cx('card')}>
        <div className={cx('card-head')}>
          <h3 className={cx('card-title')}>
            {t('inference.dual.systemPrompt')}
          </h3>
          {promptModelName && (
            <Badge type='gray' size='sm' label={`LLM1 · ${promptModelName}`} />
          )}
          <div className={cx('head-actions')}>
            <ButtonV2
              type={domainOpen ? 'solid' : 'outline'}
              colorType='blue'
              size='s'
              label={t('inference.dual.domainOptimize')}
              onClick={() => setDomainOpen((v) => !v)}
            />
          </div>
        </div>
        <Textarea
          size='large'
          placeholder={t('inference.dual.systemPromptPlaceholder')}
          value={systemPrompt}
          name='system-prompt'
          maxLength={4000}
          options={taOptions(t('inference.dual.systemPrompt'), 3)}
          customStyle={{ fontSize: '14px', height: '96px' }}
          onChange={(e) => setSystemPrompt(e.target.value)}
        />
        {domainOpen && (
          <div className={cx('domain-panel')}>
            {examples.map((ex, i) => (
              <div key={ex.id} className={cx('qa-set')}>
                <div className={cx('qa-header')}>
                  <span className={cx('qa-index')}>
                    {t('inference.dual.exampleIndex', { n: i + 1 })}
                  </span>
                  {examples.length > 1 && (
                    <ButtonV2
                      type='clear'
                      colorType='red'
                      size='s'
                      label={t('delete.label')}
                      onClick={() => handleExampleRemove(i)}
                    />
                  )}
                </div>
                <Textarea
                  size='large'
                  placeholder={t('inference.dual.exampleQueryPlaceholder')}
                  value={ex.query}
                  name={`example-query-${ex.id}`}
                  maxLength={2000}
                  options={taOptions(
                    t('inference.dual.exampleQueryAria', { n: i + 1 }),
                    2,
                  )}
                  customStyle={{ fontSize: '14px', height: '72px' }}
                  onChange={(e) =>
                    handleExampleChange(i, 'query', e.target.value)
                  }
                />
                <Textarea
                  size='large'
                  placeholder={t('inference.dual.exampleAnswerPlaceholder')}
                  value={ex.answer}
                  name={`example-answer-${ex.id}`}
                  maxLength={2000}
                  options={taOptions(
                    t('inference.dual.exampleAnswerAria', { n: i + 1 }),
                    2,
                  )}
                  customStyle={{ fontSize: '14px', height: '72px' }}
                  onChange={(e) =>
                    handleExampleChange(i, 'answer', e.target.value)
                  }
                />
              </div>
            ))}
            {examples.length < EXAMPLES_MAX && (
              <div className={cx('qa-add')}>
                <ButtonV2
                  type='outline'
                  colorType='blue'
                  size='s'
                  label={t('inference.dual.exampleAdd')}
                  onClick={handleExampleAdd}
                />
              </div>
            )}
          </div>
        )}
      </section>

      <section className={cx('card')}>
        <div className={cx('card-head')}>
          <h3 className={cx('card-title')}>{t('inputUser.label')}</h3>
          {inferenceModelName && (
            <Badge
              type='blue'
              size='sm'
              label={`LLM2 · ${inferenceModelName}`}
            />
          )}
        </div>
        <Textarea
          size='large'
          placeholder={t('inference.dual.userInputPlaceholder')}
          value={userInput}
          name='user-input'
          maxLength={4000}
          options={taOptions(t('inputUser.label'), 5)}
          customStyle={{ fontSize: '14px', height: '148px' }}
          onChange={(e) => setUserInput(e.target.value)}
        />
      </section>

      {isExternal && (
        <section className={cx('card')}>
          <div className={cx('card-head')}>
            <h3 className={cx('card-title')}>{t('inference.dual.sdsInput')}</h3>
            <Badge
              type='gray'
              size='sm'
              label={t('inference.dual.sdsInputBadge')}
            />
          </div>
          <ImageUploadField value={imageB64} onChange={setImageB64} />
          <OutputTypeSelect value={outputType} onChange={setOutputType} />
          <AISRowsForm value={aisRows} onChange={setAisRows} />
        </section>
      )}

      <div className={cx('run-row')}>
        <ButtonV2
          type='solid'
          colorType='blue'
          size='l'
          label={
            running ? t('inference.dual.running') : t('inference.dual.run')
          }
          isLoading={running}
          disabled={!canRun}
          onClick={handleRun}
        />
      </div>

      {result && (
        <div className={cx('result')}>
          {result.optimized_prompt && (
            <section className={cx('card')}>
              <div className={cx('card-head')}>
                <h3 className={cx('card-title')}>
                  {t('inference.dual.optimizedPrompt')}
                </h3>
                <Badge type='gray' size='sm' label='LLM1' />
              </div>
              <div className={cx('result-body')}>{result.optimized_prompt}</div>
            </section>
          )}
          <section className={cx('card')}>
            <div className={cx('card-head')}>
              <h3 className={cx('card-title')}>
                {t('inference.result.title')}
              </h3>
              <Badge
                type='blue'
                size='sm'
                label={isExternal ? 'LLM2 · SDS' : 'LLM2'}
              />
            </div>
            <div className={cx('result-body')}>{result.output || '-'}</div>
          </section>
        </div>
      )}
    </div>
  );
};

export default DualDirectInference;
