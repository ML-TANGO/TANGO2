import React, { useState } from 'react';

import {
  Badge, Btn, Checkbox, Frame, GateRibbon, PageHeader, ProgressBar, SectionHead,
  Segmented, Select, Slider, Textarea, Textfield, dsBase, useDatasetNav,
} from './components';
import {
  BASE_PROMPT, CHIPS, GENERATE_BY_CAP, GENERATE_RESULT, MODELS, TEMPLATES,
} from './mock';
import { SHOTS } from './lib/frames';
import { AXES, THRESHOLDS, fmt } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

/**
 * 생성.
 *
 * 핵심은 두 가지다.
 * 1. 생성 모델과 심사 모델이 같으면 실행을 막는다. 자기 결과를 자기가 채점하면
 *    맹점이 그대로 통과해 게이트가 통과율만 올릴 뿐 걸러내지 못한다.
 * 2. 프롬프트 제약을 칩으로 넣고 빼면 미리보기 점수가 실제로 움직인다. 문장 하나가
 *    어느 축을 올리는지 눈으로 보게 해야 사용자가 프롬프트를 고칠 수 있다.
 */
export default function GeneratePage() {
  const { wsId, dsId } = useDatasetNav();
  const [phase, setPhase] = useState('실행 전');
  const [templates, setTemplates] = useState({ ocr_document: true, chart_table: true });
  const [genModel, setGenModel] = useState('qwen8b');
  const [judgeModel, setJudgeModel] = useState('intern3');
  const [hardNegative, setHardNegative] = useState(6);
  const [perImage, setPerImage] = useState('3');
  const [prompt, setPrompt] = useState(BASE_PROMPT);

  const g = MODELS.find((m) => m.id === genModel);
  const j = MODELS.find((m) => m.id === judgeModel);
  const sameModel = genModel === judgeModel;
  const sameFamily = !sameModel && g.fam === j.fam;

  // 칩의 on/off 는 별도 상태가 아니라 프롬프트 본문에서 읽는다. 사용자가 문장을 직접
  // 고쳐도 칩 상태가 어긋나지 않게 하기 위해서다.
  const active = CHIPS.filter((c) => {
    if (c.lock) return true;
    if (c.id === 'GROUNDED') return /명시적|도출/.test(prompt);
    if (c.id === 'NOTEXT') return /보지 않고|이미지 없이/.test(prompt);
    if (c.id === 'UNIQUE') return /유일|하나로 확정/.test(prompt);
    return false;
  }).map((c) => c.id);

  const scores = (() => {
    const s = { align: 0.82, imgdep: 0.91, answer: 0.74, unique: 0.88 };
    if (active.includes('GROUNDED')) { s.answer = 0.89; s.align = 0.86; }
    if (active.includes('NOTEXT')) s.imgdep = 0.94;
    if (active.includes('UNIQUE')) { s.unique = 0.93; s.answer = Math.min(0.93, s.answer + 0.02); }
    return s;
  })();

  const failing = AXES.filter((a) => scores[a.k] < THRESHOLDS[a.k]);
  const estimate = failing.length === 0 ? 9 : Math.max(3, 10 - 3 * failing.length);
  const tplCount = Object.values(templates).filter(Boolean).length || 1;
  const expected = Math.round(741 * (parseInt(perImage, 10) || 1) * tplCount * 0.343);

  const toggleChip = (c) => {
    if (c.lock) return;
    const on = active.includes(c.id);
    setPrompt(on
      ? prompt.split('\n').filter((l) => l.trim() !== c.text).join('\n')
      : `${prompt.replace(/\s*$/, '')}\n${c.text}`);
  };

  const nextPhase = () => {
    if (phase === '실행 전') setPhase('소규모 생성');
    else setPhase('전체 생성');
  };

  return (
    <div className={style.page}>
      <PageHeader
        title="생성"
        back={{ to: `${dsBase(wsId, dsId)}/flow`, label: '파이프라인' }}
        actions={(
          <span className={style.toolbar}>
            <Segmented options={['실행 전', '소규모 생성', '전체 생성']} value={phase} onChange={setPhase} />
            <Btn size="md" disabled={sameModel} onClick={nextPhase}>
              {phase === '실행 전' ? '소규모 생성 10건'
                : phase === '소규모 생성' ? `전체 생성 ${fmt(expected)}건` : '다시 생성'}
            </Btn>
          </span>
        )}
      />

      <div className={style['generate-grid']}>
        {/* 좌: 템플릿 · 함정 데이터 */}
        <div className={common['stack-lg']}>
          <div className={common.stack}>
            <SectionHead>템플릿</SectionHead>
            <div className={[common['card-pad'], common.stack].join(' ')}>
              {TEMPLATES.map((t) => (
                <Checkbox
                  key={t.k}
                  checked={!!templates[t.k]}
                  onChange={(v) => setTemplates({ ...templates, [t.k]: v })}
                  label={t.n}
                />
              ))}
            </div>
          </div>

          <div className={common.stack}>
            <SectionHead>함정 데이터</SectionHead>
            <div className={common['card-pad']}>
              {/* 답할 수 없는 질문을 일부러 섞어 "모른다"고 답하는 법을 학습시킨다. */}
              <span className={style['cap-row']} style={{ gridTemplateColumns: 'minmax(0,1fr) 48px' }}>
                <Slider min={0} max={15} value={hardNegative} onChange={setHardNegative} />
                <span className={[common['cell-num']].join(' ')}>{hardNegative}%</span>
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
                    <span className={common.label} style={{ display: 'block', marginBottom: 10 }}>{label}</span>
                    <Select
                      value={value}
                      onChange={setValue}
                      options={MODELS.map((m) => ({ v: m.id, n: m.n }))}
                    />
                    <span style={{ display: 'block', marginTop: 10 }}>
                      <Badge tone={model.fam === 'gemma' ? 'warn' : 'pass'}>{model.lic}</Badge>
                    </span>
                  </span>
                ))}
              </span>

              {(sameModel || sameFamily) && (
                <span className={[common.note, sameModel ? common['note-fail'] : common['note-warn']].join(' ')}>
                  <span className={common['note-title']}>
                    {sameModel ? '선택 불가 — 생성 모델과 심사 모델이 같습니다' : `경고 — 같은 계열 모델입니다 (${g.fam})`}
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
              <span className={style['model-pair']} style={{ gridTemplateColumns: 'repeat(3,minmax(0,1fr))' }}>
                <span>
                  <span className={common.label} style={{ display: 'block', marginBottom: 10 }}>이미지당 생성 수</span>
                  <Textfield value={perImage} onChange={setPerImage} />
                </span>
                <span>
                  <span className={common.label} style={{ display: 'block', marginBottom: 10 }}>답변 길이</span>
                  <Select options={['짧게', '중간', '설명형']} value="중간" onChange={() => {}} />
                </span>
                <span>
                  <span className={common.label} style={{ display: 'block', marginBottom: 10 }}>언어</span>
                  <Select options={['ko', 'en', 'ko + en']} value="ko" onChange={() => {}} />
                </span>
              </span>
            </div>
          </div>

          <div className={common.stack}>
            <SectionHead aside={<span className={[common.num, common['cell-mute']].join(' ')}>docqa_v4</span>}>
              프롬프트
            </SectionHead>
            <div className={[common['card-pad'], common.stack].join(' ')}>
              <Textarea value={prompt} onChange={setPrompt} height={120} />
              <span className={style.chips}>
                {CHIPS.map((c) => {
                  const on = active.includes(c.id);
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => toggleChip(c)}
                      className={[style.chip, c.lock ? style['chip-lock'] : on ? style['chip-on'] : ''].join(' ')}
                    >
                      {(c.lock ? '🔒 ' : on ? '✓ ' : '＋ ') + c.label}
                    </button>
                  );
                })}
              </span>
            </div>
          </div>
        </div>

        {/* 우: 미리보기 / 결과 — 세 단계가 같은 폭을 쓴다 */}
        <div className={common.stack}>
          <SectionHead>{phase === '전체 생성' ? '생성 결과' : '미리보기'}</SectionHead>
          <div className={[common['card-pad'], common.stack].join(' ')}>
            {phase === '실행 전' && (
              <span className={style['review-done']} style={{ padding: '40px 0', gridColumn: 'auto' }}>
                <span className={common.prose}>소규모 생성을 실행하면 표시됩니다</span>
                <Btn size="md" disabled={sameModel} onClick={() => setPhase('소규모 생성')}>소규모 생성 10건</Btn>
              </span>
            )}

            {phase === '소규모 생성' && (
              <>
                <span className={common.thumb}>
                  <Frame spec={SHOTS[0]} />
                </span>
                <span className={style['qa-block']}>
                  <span className={common.eyebrow}>Q</span>
                  <span className={style['qa-text']}>이 표의 합계는 얼마인가?</span>
                </span>
                <span className={style['qa-block']}>
                  <span className={common.eyebrow}>A</span>
                  <span className={[style['qa-text'], common.mute].join(' ')}>133,500원입니다.</span>
                </span>

                <GateRibbon axes={AXES} scores={scores} thresholds={THRESHOLDS} />

                <span className={[common.note, failing.length ? common['note-fail'] : common['note-pass']].join(' ')}>
                  <span className={common['note-title']}>심사 · {j.n}</span>
                  <span className={common['note-body']}>
                    {failing.length
                      ? `${failing.map((a) => a.label).join(' · ')} 축이 기준값에 못 미칩니다.`
                      : '4축 전부 기준값을 넘었습니다. 재생성 불필요.'}
                  </span>
                </span>

                <span className={style['estimate-row']}>
                  <span className={common.label}>통과 추정</span>
                  <span className={[style['estimate-value'], failing.length ? common.warn : common.pass].join(' ')}>
                    {estimate} / 10
                  </span>
                </span>
              </>
            )}

            {phase === '전체 생성' && (
              <>
                <span className={style['result-grid']}>
                  {GENERATE_RESULT.map(([k, v]) => (
                    <span key={k} className={style['result-cell']}>
                      <span className={style['result-value']}>{v}</span>
                      <span className={common['tile-label']}>{k}</span>
                    </span>
                  ))}
                </span>
                <span className={common.stack} style={{ paddingTop: 16, borderTop: '1px solid #f0f0f0' }}>
                  <span className={common.eyebrow}>유형별 생성량</span>
                  {GENERATE_BY_CAP.map(([k, v]) => (
                    <span key={k} className={style['cap-row']}>
                      <span className={[common.num, common['cell-mute']].join(' ')}>{k}</span>
                      <ProgressBar value={Math.round((v / 612) * 100)} height={8} />
                      <span className={common['cell-num']}>{v}</span>
                    </span>
                  ))}
                </span>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
