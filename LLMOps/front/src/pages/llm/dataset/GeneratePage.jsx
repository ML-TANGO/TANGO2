import React, { useCallback, useEffect, useState } from 'react';

import {
  getFlow,
  getStage,
  runStage,
  saveGenerateConfig,
} from '@src/apis/llm/dataset';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import {
  Badge,
  Btn,
  Checkbox,
  PageHeader,
  SectionHead,
  Select,
  Slider,
  Textarea,
  Textfield,
  dsBase,
  useDatasetNav,
} from './components';
import RunPanel from './components/RunPanel';
import { findStageNode, upstreamRunOf } from './lib/stage';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

const ANSWER_LENGTHS = ['짧게', '중간', '설명형'];
const LANGUAGES = ['ko', 'en', 'ko + en'];

/**
 * 생성.
 *
 * 핵심은 두 가지다.
 * 1. 생성 모델과 심사 모델이 같으면 저장을 막는다. 자기 결과를 자기가 채점하면
 *    맹점이 그대로 통과해 게이트가 통과율만 올릴 뿐 걸러내지 못한다. 같은 계열이면
 *    경고만 한다 — 서버도 같은 기준으로 한 번 더 본다(judge_model_pairing).
 * 2. 프롬프트 제약을 칩으로 넣고 뺀다. 칩의 on/off 는 별도 상태가 아니라 프롬프트
 *    본문에서 읽는다 — 사용자가 문장을 직접 고쳐도 칩 상태가 어긋나지 않게.
 *
 * 결과는 지어내지 않는다. 예전 화면은 프롬프트에 특정 문구가 있으면 축 점수를 올려
 * 보여줬는데, 그건 실제 심사 결과가 아니라 화면이 만든 숫자였다. 지금은 실행한 것만
 * 보여준다(`RunPanel`).
 */
export default function GeneratePage() {
  const { wsId, dsId } = useDatasetNav();

  const [meta, setMeta] = useState(null);
  const [flow, setFlow] = useState(null);
  const [templates, setTemplates] = useState({});
  const [genModel, setGenModel] = useState('');
  const [judgeModel, setJudgeModel] = useState('');
  const [hardNegative, setHardNegative] = useState(0);
  const [perImage, setPerImage] = useState('3');
  const [answerLength, setAnswerLength] = useState(ANSWER_LENGTHS[1]);
  const [language, setLanguage] = useState(LANGUAGES[0]);
  const [prompt, setPrompt] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [st, fl] = await Promise.all([
      getStage(dsId, 'generate'),
      getFlow(dsId),
    ]);
    if (st.status !== STATUS_SUCCESS) {
      errorToastMessage(st.error, st.message);
      return;
    }
    const r = st.result || {};
    setMeta(r);
    const cfg = r.config || {};
    const models = r.models || [];
    setTemplates(
      Object.fromEntries(
        (r.templates || []).map((t) => [
          t.key,
          (cfg.templates || []).includes(t.key),
        ]),
      ),
    );
    // 저장값이 없으면 서로 다른 모델이 기본으로 잡히게 한다 — 같은 모델이 기본이면
    // 화면을 열자마자 차단 상태가 된다.
    const gen = cfg.generator_model || models[0]?.id || '';
    setGenModel(gen);
    // 심사 모델 기본값은 **다른 계열**에서 고른다. id 만 다르게 잡으면 같은 계열이
    // 걸려(qwen8b ↔ qwen4b) 화면을 열자마자 경고 상태로 시작한다.
    const genFam = models.find((m) => m.id === gen)?.family;
    setJudgeModel(
      cfg.judge_model
        || models.find((m) => m.family !== genFam)?.id
        || models.find((m) => m.id !== gen)?.id
        || '',
    );
    setHardNegative(cfg.hard_negative_pct ?? 0);
    setPerImage(String(cfg.per_image ?? 3));
    setAnswerLength(cfg.answer_length || ANSWER_LENGTHS[1]);
    setLanguage(cfg.language || LANGUAGES[0]);
    setPrompt(cfg.prompt || r.default_prompt || '');
    if (fl.status === STATUS_SUCCESS) setFlow(fl.result);
  }, [dsId]);

  useEffect(() => {
    load();
  }, [load]);

  const models = meta?.models || [];
  const chips = meta?.prompt_chips || [];
  const g = models.find((m) => m.id === genModel) || null;
  const j = models.find((m) => m.id === judgeModel) || null;
  const sameModel = !!genModel && genModel === judgeModel;
  const sameFamily = !sameModel && !!g && !!j && g.family === j.family;

  const nodes = flow?.nodes || [];
  const { node, index } = findStageNode(nodes, 'generate');
  const running = node?.latest_run?.status === 'running';

  // 칩이 켜졌는지는 프롬프트 본문에 그 문장이 들어 있는지로 본다.
  const isOn = (c) => c.locked || prompt.includes(c.text);

  const toggleChip = (c) => {
    if (c.locked) return;
    setPrompt(
      isOn(c)
        ? prompt
            .split('\n')
            .filter((l) => l.trim() !== c.text)
            .join('\n')
        : `${prompt.replace(/\s*$/, '')}\n${c.text}`,
    );
  };

  const body = () => ({
    generator_model: genModel,
    judge_model: judgeModel,
    templates: Object.entries(templates)
      .filter(([, v]) => v)
      .map(([k]) => k),
    prompt,
    per_image: Number(perImage) || 1,
    answer_length: answerLength,
    language,
    hard_negative_pct: hardNegative,
  });

  const persist = async () => {
    const res = await saveGenerateConfig(dsId, body());
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return false;
    }
    return true;
  };

  const save = async () => {
    setBusy(true);
    const ok = await persist();
    setBusy(false);
    if (ok) load();
  };

  // 잡은 저장된 설정을 읽는다 — 저장하지 않고 실행하면 방금 고친 프롬프트가 반영되지 않는다.
  const run = async (dryRun) => {
    setBusy(true);
    if (!(await persist())) {
      setBusy(false);
      return;
    }
    const res = await runStage(dsId, 'generate', {
      dry_run: dryRun,
      sample_size: 10,
    });
    setBusy(false);
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return;
    }
    load();
  };

  return (
    <div className={style.page}>
      <PageHeader
        title='생성'
        back={{ to: `${dsBase(wsId, dsId)}/flow`, label: '파이프라인' }}
        actions={
          <span className={style.toolbar}>
            <Btn
              size='md'
              fill='outline'
              tone='gray'
              onClick={save}
              disabled={busy || sameModel}
            >
              저장
            </Btn>
            <Btn
              size='md'
              fill='outline'
              tone='gray'
              onClick={() => run(true)}
              disabled={busy || sameModel || running}
            >
              소규모 생성 10건
            </Btn>
            <Btn
              size='md'
              onClick={() => run(false)}
              disabled={busy || sameModel || running}
            >
              {running ? '생성중…' : '전체 생성'}
            </Btn>
          </span>
        }
      />

      <div className={style['generate-grid']}>
        {/* 좌: 템플릿 · 함정 데이터 */}
        <div className={common['stack-lg']}>
          <div className={common.stack}>
            <SectionHead>템플릿</SectionHead>
            <div className={[common['card-pad'], common.stack].join(' ')}>
              {(meta?.templates || []).map((t) => (
                <Checkbox
                  key={t.key}
                  checked={!!templates[t.key]}
                  onChange={(v) => setTemplates({ ...templates, [t.key]: v })}
                  label={t.name}
                />
              ))}
            </div>
          </div>

          <div className={common.stack}>
            <SectionHead>함정 데이터</SectionHead>
            <div className={common['card-pad']}>
              {/* 답할 수 없는 질문을 일부러 섞어 "모른다"고 답하는 법을 학습시킨다. */}
              <span
                className={style['cap-row']}
                style={{ gridTemplateColumns: 'minmax(0,1fr) 48px' }}
              >
                <Slider
                  min={0}
                  max={15}
                  value={hardNegative}
                  onChange={setHardNegative}
                />
                <span className={common['cell-num']}>{hardNegative}%</span>
              </span>
            </div>
          </div>
        </div>

        {/* 중: 모델 · 설정 · 프롬프트 */}
        <div className={common['stack-lg']}>
          <div className={common.stack}>
            <SectionHead>모델</SectionHead>
            <div className={[common['card-pad'], common.stack].join(' ')}>
              <span className={style['model-pair']}>
                {[
                  ['생성 모델', genModel, setGenModel, g],
                  ['심사 모델', judgeModel, setJudgeModel, j],
                ].map(([label, value, setValue, model]) => (
                  <span key={label}>
                    <span
                      className={common.label}
                      style={{ display: 'block', marginBottom: 10 }}
                    >
                      {label}
                    </span>
                    <Select
                      value={value}
                      onChange={setValue}
                      options={models.map((m) => ({ v: m.id, n: m.name }))}
                    />
                    <span style={{ display: 'block', marginTop: 10 }}>
                      {model && (
                        <Badge
                          tone={model.family === 'gemma' ? 'warn' : 'pass'}
                        >
                          {model.license}
                        </Badge>
                      )}
                    </span>
                  </span>
                ))}
              </span>

              {(sameModel || sameFamily) && (
                <span
                  className={[
                    common.note,
                    sameModel ? common['note-fail'] : common['note-warn'],
                  ].join(' ')}
                >
                  <span className={common['note-title']}>
                    {sameModel
                      ? '선택 불가 — 생성 모델과 심사 모델이 같습니다'
                      : `경고 — 같은 계열 모델입니다 (${g?.family})`}
                  </span>
                  <span className={common['note-body']}>
                    {sameModel
                      ? '같은 모델이 자기 결과를 심사하면 맹점이 겹쳐 게이트가 무의미해집니다. 다른 계열의 모델을 고르세요.'
                      : '심사 독립성이 약합니다. 다른 계열의 모델을 권장합니다.'}
                  </span>
                </span>
              )}
            </div>
          </div>

          <div className={common.stack}>
            <SectionHead>생성 설정</SectionHead>
            <div className={common['card-pad']}>
              <span
                className={style['model-pair']}
                style={{ gridTemplateColumns: 'repeat(3,minmax(0,1fr))' }}
              >
                <span>
                  <span
                    className={common.label}
                    style={{ display: 'block', marginBottom: 10 }}
                  >
                    이미지당 생성 수
                  </span>
                  <Textfield value={perImage} onChange={setPerImage} />
                </span>
                <span>
                  <span
                    className={common.label}
                    style={{ display: 'block', marginBottom: 10 }}
                  >
                    답변 길이
                  </span>
                  <Select
                    options={ANSWER_LENGTHS}
                    value={answerLength}
                    onChange={setAnswerLength}
                  />
                </span>
                <span>
                  <span
                    className={common.label}
                    style={{ display: 'block', marginBottom: 10 }}
                  >
                    언어
                  </span>
                  <Select
                    options={LANGUAGES}
                    value={language}
                    onChange={setLanguage}
                  />
                </span>
              </span>
            </div>
          </div>

          <div className={common.stack}>
            <SectionHead>프롬프트</SectionHead>
            <div className={[common['card-pad'], common.stack].join(' ')}>
              <Textarea value={prompt} onChange={setPrompt} height={120} />
              <span className={style.chips}>
                {chips.map((c) => {
                  const on = isOn(c);
                  return (
                    <button
                      key={c.id}
                      type='button'
                      onClick={() => toggleChip(c)}
                      className={[
                        style.chip,
                        c.locked
                          ? style['chip-lock']
                          : on
                            ? style['chip-on']
                            : '',
                      ].join(' ')}
                    >
                      {(c.locked ? '🔒 ' : on ? '✓ ' : '＋ ') + c.label}
                    </button>
                  );
                })}
              </span>
            </div>
          </div>
        </div>

        {/* 우: 실행 결과 — 다른 노드 화면과 같은 것을 본다 */}
        <div className={common.stack}>
          <SectionHead>생성 결과</SectionHead>
          <RunPanel
            datasetId={dsId}
            node={node}
            upstreamRun={upstreamRunOf(nodes, flow?.flow, index)}
          />
        </div>
      </div>
    </div>
  );
}
