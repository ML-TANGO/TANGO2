import React, { useCallback, useEffect, useState } from 'react';
import { useLocation, useParams } from 'react-router-dom';

import {
  getFlow,
  getStage,
  runStage,
  saveStageConfig,
} from '@src/apis/llm/dataset';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import {
  Btn,
  Checkbox,
  PageHeader,
  SectionHead,
  Slider,
  dsBase,
  useDatasetNav,
} from './components';
import RunPanel from './components/RunPanel';
import { findStageNode, upstreamRunOf } from './lib/stage';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

// 단계 → 화면 제목 · 기능 배지(이 기능이 무엇을 하는가). 모르는 단계는 노드 이름으로 그린다.
const STAGE_VIEW = {
  preprocess: { title: '전처리', tag: '변환' },
  filter: { title: '필터', tag: '제외' },
  sds_video: { title: '항해 영상', tag: '추출' },
  sds_ais: { title: 'AIS 로그', tag: '변환' },
  sds_ais_clean: { title: 'AIS 행 정제', tag: '제외' },
  sds_ais_scene: { title: 'AIS 씬 구조화', tag: '변환' },
  sds_join: { title: '조인', tag: '결합' },
  sds_colreg: { title: 'COLREG 계산', tag: '계산' },
};

/**
 * 전처리 · 필터 · 해양 COLREG 단계 공용 화면.
 *
 * 단계들은 레이아웃이 같고 기능 목록과 결과만 다르다. 화면을 단계마다 나누면 같은 코드를
 * 여러 벌 고치게 되므로 하나로 두고 stage 로 갈라 쓴다.
 *
 * 기능 목록(무엇을 켤 수 있는지)과 파라미터 범위는 **서버가 정본**이다(`library`).
 * FE 가 목록을 들고 있으면 노드 스크립트에 기능이 추가돼도 화면에 안 나타난다.
 *
 * 실행 결과는 파이프라인 드로어와 같은 것을 본다 — `RunPanel` 을 그대로 쓴다.
 * 같은 화면을 두 벌 만들면 한쪽만 고쳐져 서로 다른 숫자를 보여주게 된다.
 */
export default function StageConfigPage({ stage: stageProp }) {
  const { wsId, dsId } = useDatasetNav();
  const location = useLocation();
  const { stage: stageParam } = useParams();
  const stage =
    stageProp ||
    stageParam ||
    (location.pathname.endsWith('/filter') ? 'filter' : 'preprocess');

  const [library, setLibrary] = useState([]);
  const [enabled, setEnabled] = useState({});
  const [params, setParams] = useState({});
  const [sources, setSources] = useState([]);
  const [flow, setFlow] = useState(null);
  const [selected, setSelected] = useState(0);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState('');

  const load = useCallback(async () => {
    const [st, fl] = await Promise.all([getStage(dsId, stage), getFlow(dsId)]);
    if (st.status !== STATUS_SUCCESS) {
      setFailed(st.message || '단계 설정을 불러오지 못했습니다');
      errorToastMessage(st.error, st.message);
      return;
    }
    setFailed('');
    const lib = st.result?.library || [];
    const cfg = st.result?.config || {};
    setLibrary(lib);
    setSources(cfg.sources || []);
    // 저장된 값이 없는 기능은 라이브러리 기본값으로 채운다. 빈 칸으로 두면 슬라이더가
    // 0 에서 시작해 사용자가 만진 적 없는 값이 저장된다.
    // on/off 를 한 번도 저장하지 않은 노드는 BE `_runnable_steps` 와 같은 규칙으로 표시
    // 이름(steps)에서 되짚는다 — 전부 꺼진 채로 보여주면 실제로는 켜져 도는 기능이 화면에서
    // 사라지고, 그 상태로 저장하면 실행이 바뀐다(조인 · 영상 노드는 기본 config 가 없다).
    const savedOn = cfg.enabled || {};
    const hasSaved = Object.keys(savedOn).length > 0;
    const shown = new Set(
      (st.result?.steps || []).map((s) => (Array.isArray(s) ? s[0] : s)),
    );
    setEnabled(
      Object.fromEntries(
        lib.map((s) => [s.key, hasSaved ? !!savedOn[s.key] : shown.has(s.key)]),
      ),
    );
    setParams(
      Object.fromEntries(
        lib
          .filter((s) => s.param)
          .map((s) => [
            s.param.key,
            cfg.params?.[s.param.key] ?? s.param.default,
          ]),
      ),
    );
    if (fl.status === STATUS_SUCCESS) setFlow(fl.result);
  }, [dsId, stage]);

  useEffect(() => {
    load();
  }, [load]);

  const nodes = flow?.nodes || [];
  const { node, index } = findStageNode(nodes, stage);
  const view = STAGE_VIEW[stage] || { title: node?.name || stage, tag: '변환' };
  const running = node?.latest_run?.status === 'running';

  const cur = library[selected] || null;
  const onCount = Object.values(enabled).filter(Boolean).length;

  const persist = async () => {
    const res = await saveStageConfig(dsId, stage, {
      sources,
      enabled,
      params,
    });
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

  /**
   * 저장하고 바로 실행한다.
   *
   * 잡은 **저장된** 노드 설정을 읽어 params.json 을 만든다(run_stage → get_flow).
   * 저장하지 않고 실행하면 방금 바꾼 슬라이더가 반영되지 않은 채 돌아, 사용자는
   * "기능을 바꿨는데 결과가 같다"를 보게 된다 — 이 화면의 목적이 정확히 그 비교다.
   */
  const run = async (dryRun) => {
    setBusy(true);
    if (!(await persist())) {
      setBusy(false);
      return;
    }
    const res = await runStage(dsId, stage, {
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

  /** 라이브러리 기본값으로 되돌린다(저장은 사용자가 누를 때). */
  const reset = () => {
    setParams(
      Object.fromEntries(
        library
          .filter((s) => s.param)
          .map((s) => [s.param.key, s.param.default]),
      ),
    );
  };

  if (failed) {
    return (
      <div className={style.page}>
        <PageHeader
          title={view.title}
          back={{ to: `${dsBase(wsId, dsId)}/flow`, label: '파이프라인' }}
        />
        <div className={common['card-pad']}>
          <span className={common.prose}>{failed}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={style.page}>
      <PageHeader
        title={view.title}
        back={{ to: `${dsBase(wsId, dsId)}/flow`, label: '파이프라인' }}
      />

      <div className={style['stage-grid']}>
        {/* 좌: 기능 목록 + 선택한 기능의 파라미터 */}
        <div className={common['stack-lg']}>
          <div className={common.stack}>
            <SectionHead
              aside={
                <span className={[common.num, common['cell-mute']].join(' ')}>
                  {library.length}개 중 {onCount}개 켜짐
                </span>
              }
            >
              기능
            </SectionHead>
            <div className={common['card-clip']}>
              {library.map((s, i) => (
                <div
                  key={s.key}
                  role='button'
                  tabIndex={0}
                  onClick={() => setSelected(i)}
                  onKeyDown={(e) => e.key === 'Enter' && setSelected(i)}
                  className={[
                    style['step-item'],
                    selected === i ? style['step-item-on'] : '',
                  ].join(' ')}
                >
                  <span className={style['step-head']}>
                    <Checkbox
                      checked={!!enabled[s.key]}
                      onChange={(v) => setEnabled({ ...enabled, [s.key]: v })}
                      label={s.key}
                    />
                    <span
                      className={[
                        style['step-tag'],
                        view.tag === '제외' ? style['step-tag-del'] : '',
                      ].join(' ')}
                    >
                      {/* 배지는 이 기능이 무엇을 하는지(제외 / 변환)를 말한다.
                          켜짐 여부는 바로 옆 체크박스가 이미 말하고 있다. */}
                      {view.tag}
                    </span>
                  </span>
                  <span className={style['step-desc']}>{s.desc}</span>
                </div>
              ))}
              {library.length === 0 && (
                <div className={style['step-desc']}>
                  이 단계에 쓸 수 있는 기능이 없습니다.
                </div>
              )}
              <div className={style['step-actions']}>
                <Btn
                  size='md'
                  fill='outline'
                  tone='gray'
                  onClick={reset}
                  disabled={busy}
                >
                  기본값
                </Btn>
                <Btn
                  size='md'
                  fill='outline'
                  tone='gray'
                  onClick={save}
                  disabled={busy}
                >
                  저장
                </Btn>
              </div>
              <div className={style['step-actions']}>
                {/* 표본만 돌려 이력에 남기지 않는다 — 껐다 켜며 비교하는 경로. */}
                <Btn
                  size='md'
                  fill='outline'
                  tone='gray'
                  onClick={() => run(true)}
                  disabled={busy || running}
                >
                  미리보기
                </Btn>
                <Btn
                  size='md'
                  block
                  onClick={() => run(false)}
                  disabled={busy || running}
                >
                  {running ? '실행중…' : '실행'}
                </Btn>
              </div>
            </div>
          </div>

          {cur?.param && (
            <div className={common.stack}>
              <SectionHead>{cur.key} 설정</SectionHead>
              <div className={[common['card-pad'], common.stack].join(' ')}>
                <span>
                  <span className={style['param-head']}>
                    <span className={common.label}>{cur.param.name}</span>
                    <span className={style['param-value']}>
                      {/* 서버가 unit 을 준다. ratio 는 0.95 처럼 소수로 읽는 값이다. */}
                      {cur.param.unit === 'ratio'
                        ? `0.${params[cur.param.key]}`
                        : `${params[cur.param.key]}${cur.param.unit ? ` ${cur.param.unit}` : ''}`}
                    </span>
                  </span>
                  <Slider
                    min={cur.param.min}
                    max={cur.param.max}
                    value={params[cur.param.key]}
                    onChange={(v) =>
                      setParams({ ...params, [cur.param.key]: v })
                    }
                  />
                </span>
              </div>
            </div>
          )}
        </div>

        {/* 우: 실행 결과 — 입력 / 통과 / 제외. 파이프라인 드로어와 같은 컴포넌트다. */}
        <div className={common['stack-lg']}>
          <SectionHead>실행 결과</SectionHead>
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
