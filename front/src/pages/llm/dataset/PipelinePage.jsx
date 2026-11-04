import React, { useCallback, useEffect, useRef, useState } from 'react';

import {
  getFlow,
  listRecords,
  listSourceDatasets,
  listSourceFolders,
  runStage,
  saveStageConfig,
} from '@src/apis/llm/dataset';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import {
  Btn,
  DatasetTabs,
  PageHeader,
  Select,
  listBase,
  useDatasetName,
  useDatasetNav,
} from './components';
import NodeCanvas, { NodeDrawer } from './components/NodeCanvas';
import RunPanel from './components/RunPanel';
import { GENERIC_HOME, SDS_FLOW, SDS_HOME, STAGE } from './mock';
import { fmt } from './lib/format';
import {
  NOT_RUNNABLE,
  configStageOfNode,
  isStaleRun,
  stageOfNode,
  upstreamRunOf,
} from './lib/stage';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

// 파이프라인 캔버스.
//
// 노드 체인·카운트·상태·최근 실행은 전부 BE(`GET /flow`)에서 온다. 예전에는 mock 체인을
// 그렸는데, mock 범용 체인(7노드)과 BE 기본 체인(5노드)이 서로 달라 실제 실행 결과를
// 얹으면 노드가 한 칸씩 밀려 엉뚱한 노드의 결과가 표시된다.
//
// mock 에서 계속 가져오는 것은 **표현 정보뿐**이다 — 노드 설명 문구, 캔버스 기본 좌표.
// 숫자·상태·소스 목록은 하나도 없다(소스는 `GET /source-datasets`)。

// 상태별 색 — 점 · 후광 · 왼쪽 강조선 · 숫자 잉크가 한 벌로 움직인다.
const TONE = {
  정상: {
    dot: '#00c775',
    halo: null,
    accent: 'transparent',
    ink: '#121619',
    tone: 'pass',
  },
  주의: {
    dot: '#ffab31',
    halo: '#fff0e4',
    accent: '#ffab31',
    ink: '#b35500',
    tone: 'warn',
  },
  위험: {
    dot: '#fa4e57',
    halo: '#ffe6e5',
    accent: '#fa4e57',
    ink: '#d91a0c',
    tone: 'fail',
  },
};

// BE `_node_warning` 이 돌려주는 값과 짝. 여기서 갈라지면 경고가 조용히 사라진다.
const STATE_BY_WARN = { normal: '정상', warn: '주의', danger: '위험' };

// 노드 종류 → 전용 화면 경로. 생성 · 심사는 화면 구성이 달라 따로 있다.
const ROUTE_BY_KIND = {
  data: '/flow',
  synth: '/flow/generate',
  gen: '/flow/generate',
  gate: '/flow/gate',
};

// 기능 목록(library)으로 그리는 공용 설정 화면(StageConfigPage)을 쓰는 단계.
// kind 로 고르면 안 된다 — 해양 프리셋은 'AIS 행 정제'(filter) · 'AIS 씬 구조화'(prep) 가
// 영상 갈래와 kind 가 같아, 영상 필터 · 전처리 화면이 열리고 거기서 저장하면 영상 노드
// 설정이 덮인다. 전처리 · 필터는 기존 경로를 유지한다.
const ROUTE_BY_STAGE = {
  preprocess: '/flow/preprocess',
  filter: '/flow/filter',
};
const LIBRARY_STAGES = new Set([
  'sds_video',
  'sds_ais',
  'sds_ais_clean',
  'sds_ais_scene',
  'sds_join',
  'sds_colreg',
]);

/** 노드 상세 화면 경로. 설정 화면이 없는 노드(조립 등)는 노드 화면으로 보낸다. */
function routeOfNode(node, idx, nodes) {
  if (ROUTE_BY_KIND[node.kind]) return ROUTE_BY_KIND[node.kind];
  const stage = configStageOfNode(node, nodes);
  if (ROUTE_BY_STAGE[stage]) return ROUTE_BY_STAGE[stage];
  if (LIBRARY_STAGES.has(stage)) return `/flow/stage/${stage}`;
  return `/flow/node/${idx}`;
}

/** 실행 시각 한 줄. 아직 안 돌았으면 그 사실을 적는다(빈칸이면 고장으로 읽힌다). */
function runLabel(run) {
  if (!run) return '실행 기록 없음';
  // DATETIME('YYYY-MM-DD HH:MM:SS') 에서 'MM-DD HH:MM' 만 남긴다.
  const when = (run.ended_at || run.started_at || '').toString().slice(5, 16);
  const kindTxt = run.dry_run ? '미리보기' : '실행';
  if (run.status === 'running') return `${kindTxt} 중…`;
  if (run.status === 'failed') return `${kindTxt} 실패 ${when}`;
  return `최근 ${kindTxt} ${when}`;
}

/**
 * 캔버스 좌표. 프리셋 기본 배치를 쓰되, 노드를 추가해 기본 배치보다 길어지면
 * 뒤쪽을 이어서 깐다 — 좌표가 모자라면 NodeCanvas 가 undefined 를 읽고 죽는다.
 */
function layoutFor(count, isDomain) {
  const base = isDomain ? SDS_HOME : GENERIC_HOME;
  if (count <= base.length) return base;
  const out = base.slice();
  for (let i = base.length; i < count; i += 1) {
    out.push([30 + (i % 5) * 248, 40 + Math.floor(i / 5) * 260]);
  }
  return out;
}

/**
 * 데이터 노드의 마운트 편집기 — 드로어 안에서만 쓴다.
 *
 * 캔버스 위가 아니라 드로어에 두는 이유: 데이터 노드가 여러 개일 수 있어서 화면 상단에
 * 하나만 놓으면 어느 노드를 가리키는지 알 수 없다. 노드를 고른 다음 그 노드의 소스를 바꾼다.
 */
function SourceEditor({ value, datasets, folders, saving, onChange }) {
  // 고를 것이 없을 때 빈 셀렉트를 보여주면 사용자는 목록을 못 불러온 것과 구분할 수
  // 없다. 무엇을 해야 하는지 말한다.
  if (!datasets.length)
    return (
      <span className={style['drawer-source']}>
        <span className={common.eyebrow}>데이터 소스</span>
        <span className={common.label}>
          고를 수 있는 데이터셋이 없습니다 — 데이터 메뉴에서 원본을 먼저 올리세요.
        </span>
      </span>
    );

  // 저장된 경로가 목록에 없는 경우(데이터셋이 지워졌거나 권한이 사라졌다).
  // Select 는 값이 목록에 없으면 **첫 항목을 고른 것처럼** 보여주므로, 그대로 두면
  // 사용자는 엉뚱한 데이터셋이 설정된 줄 안다. 원문을 글자로 보여준다.
  const orphan = value?.unknown;

  return (
    <span className={style['drawer-source']}>
      <span className={common.eyebrow}>데이터 소스</span>
      {orphan ? (
        <span className={common.label}>
          저장된 소스 `{orphan}` 를 목록에서 찾을 수 없습니다 — 다시 고르세요.
        </span>
      ) : null}
      <span className={common.label}>데이터셋</span>
      <Select
        value={value?.datasetId}
        options={datasets.map((d) => ({ v: d.id, n: d.name }))}
        disabled={saving}
        // 데이터셋이 바뀌면 폴더 목록이 통째로 달라지므로 전체(루트)로 되돌린다.
        onChange={(v) => onChange({ datasetId: v, folder: '/' })}
      />
      <span className={common.label}>폴더</span>
      <Select
        value={value?.folder || '/'}
        options={folders.map((f) => ({ v: f.path, n: f.name }))}
        disabled={saving || !value?.datasetId}
        onChange={(v) => onChange({ datasetId: value?.datasetId, folder: v })}
      />
    </span>
  );
}

/** 저장된 경로("{access}/{이름}{서브폴더}")를 선택기 값으로 되돌린다. */
function parseSourcePath(raw, datasets) {
  if (!raw) return undefined;
  const hit = datasets.find((d) => raw === d.path || raw.startsWith(`${d.path}/`));
  if (!hit) return { folder: '/', unknown: raw };
  const rest = raw.slice(hit.path.length);
  return { datasetId: hit.id, folder: rest || '/' };
}

export default function PipelinePage() {
  const { wsId, dsId, go, goList } = useDatasetNav();
  const dsName = useDatasetName(dsId);
  const [flow, setFlow] = useState(null);
  const [failed, setFailed] = useState('');
  const [selected, setSelected] = useState(0);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editable, setEditable] = useState(false);
  const [starting, setStarting] = useState(false);
  const [sources, setSources] = useState({});
  const [sourceDatasets, setSourceDatasets] = useState([]);
  const [folderCache, setFolderCache] = useState({});
  const [savingSource, setSavingSource] = useState(false);
  const [reviewStats, setReviewStats] = useState(null);
  const pollRef = useRef(null);

  const load = useCallback(
    async (quiet = false) => {
      const res = await getFlow(dsId);
      if (res.status === STATUS_SUCCESS) {
        setFlow(res.result);
        setFailed('');
        return;
      }
      // 조용한 폴링 실패로 화면을 비우면 사용자는 실행이 사라진 줄 안다 — 직전 상태를 남긴다.
      if (!quiet) {
        // 서버 문구는 영문 원문("dataset not found: 5")이라 그대로 띄우면
        // 사용자 화면에 개발자 메시지가 노출된다. 없는 데이터셋만 따로 말한다.
        //
        // 앵커를 붙여 좁힌다 — BE 에는 `record not found:` 도 있어서 /not found/i 로
        // 잡으면 멀쩡한 데이터셋을 "삭제됐다" 고 단정하게 된다(사용자가 재생성이라는
        // 되돌릴 수 없는 대응을 한다).
        const gone = /^dataset not found/i.test(res.message || '');
        setFailed(
          gone ? 'notfound' : res.message || '파이프라인을 불러오지 못했습니다',
        );
        // 배너를 한글로 바꿔 놓고 토스트로 원문을 띄우면 노출량은 그대로고 화면만
        // 두 목소리로 갈린다. 이 경우 message 를 넘기지 않아 공용 폴백 문구를 태운다.
        errorToastMessage(res.error, gone ? null : res.message);
      }
    },
    [dsId],
  );

  useEffect(() => {
    load();
  }, [load]);

  // 고를 수 있는 소스 데이터셋. 경로 규칙과 작업 데이터셋 제외는 BE 가 처리한다.
  useEffect(() => {
    (async () => {
      const res = await listSourceDatasets(wsId);
      if (res.status === STATUS_SUCCESS) setSourceDatasets(res.result || []);
      else errorToastMessage(res.error, res.message);
    })();
  }, [wsId]);

  // 저장된 소스를 선택기 값으로 되돌린다. 이게 없으면 화면을 다시 열 때마다 빈 값이
  // 보여서, 사용자는 저장이 안 된 줄 알고 다시 고른다.
  useEffect(() => {
    const list = flow?.nodes || [];
    if (!list.length || !sourceDatasets.length) return;
    const next = {};
    list.forEach((n, i) => {
      const raw = (n.config?.sources || [])[0];
      const parsed = parseSourcePath(raw, sourceDatasets);
      if (parsed) next[i] = parsed;
    });
    setSources(next);
  }, [flow, sourceDatasets]);

  // 고른 데이터셋의 폴더 목록. 한 번 받으면 캐시한다 — 노드를 옮겨 다닐 때마다
  // 같은 트리를 다시 받으면 실행 산출물이 쌓인 데이터셋에서 눈에 띄게 느려진다.
  useEffect(() => {
    const id = sources[selected]?.datasetId;
    if (!id || folderCache[id]) return;
    (async () => {
      const res = await listSourceFolders(id, wsId);
      if (res.status === STATUS_SUCCESS)
        setFolderCache((prev) => ({ ...prev, [id]: res.result?.folders || [] }));
      else errorToastMessage(res.error, res.message);
    })();
  }, [selected, sources, folderCache, wsId]);

  // 상단 배너의 '검수 대기'. 캔버스와 무관해 실패해도 화면을 막지 않는다.
  useEffect(() => {
    (async () => {
      const res = await listRecords(dsId, { limit: 1 });
      if (res.status === STATUS_SUCCESS)
        setReviewStats(res.result?.stats || null);
    })();
  }, [dsId]);

  const nodes = flow?.nodes || [];
  const anyRunning = nodes.some((n) => n.latest_run?.status === 'running');

  // 노드 잡은 비동기다. BE 리콘사일러가 20초 주기로 산출물을 확인해 done/failed 로
  // 마감하므로, 도는 동안만 그 절반 주기로 따라간다. 다 끝나면 폴링을 세운다 —
  // 안 세우면 아무도 안 보는 화면이 계속 요청을 보낸다.
  useEffect(() => {
    if (!anyRunning) return undefined;
    pollRef.current = setInterval(() => load(true), 10000);
    return () => clearInterval(pollRef.current);
  }, [anyRunning, load]);

  const isDomain = flow?.preset === 'sds_colreg';
  const canEdit = flow?.editable !== false;

  // 간선은 view 보다 먼저 필요하다 — 노드마다 상류 실행 시각을 봐야 하기 때문이다.
  // BE 가 간선을 안 주면 선형(0→1→2…)이다. 해양 프리셋만은 갈래가 있는 그래프라
  // 선형으로 그리면 조인이 두 갈래를 받는다는 사실이 화면에서 사라진다.
  let flowEdges;
  if (flow?.flow?.length) flowEdges = flow.flow;
  else if (isDomain) flowEdges = SDS_FLOW;
  else flowEdges = nodes.map((_, i) => [i, i + 1]).slice(0, -1);

  const view = nodes.map((n, i) => {
    const state = STATE_BY_WARN[n.state] || '정상';
    const t = TONE[state];
    const run = n.latest_run;
    const meta = STAGE[n.kind] || {};
    return {
      ...n,
      code: meta.code || '',
      desc: meta.desc || '',
      // 카운트는 실행 결과다. 아직 안 돌았으면 숫자를 지어내지 않고 —로 둔다.
      // 통과는 out 이 아니라 passed 를 본다 — 심사 노드는 미달 레코드를 버리지 않아
      // out(=산출 건수)이 곧 통과가 아니고, out 을 쓰면 통과가 늘 100% 로 보인다.
      count:
        run?.passed === null || run?.passed === undefined ? '—' : fmt(run.passed),
      stats: run
        ? [
            ['입력', fmt(run.in ?? 0)],
            ['통과', fmt(run.passed ?? run.out ?? 0)],
            ['제외', fmt(run.dropped ?? 0)],
          ]
        : null,
      run: runLabel(run),
      // 상류가 나보다 나중에 돌았으면 이 숫자는 옛 입력의 결과다.
      stale: isStaleRun(nodes, flowEdges, i),
      steps: n.steps && n.steps.length ? n.steps : undefined,
      isSource: n.kind === 'data' || n.kind === 'src',
      source: sources[i],
      inT: n.input_type,
      outT: n.output_type,
      to: routeOfNode(n, i, nodes),
      state,
      warn: n.warning || '',
      dot: t.dot,
      halo: t.halo,
      accent: t.accent,
      countColor: t.ink,
      tone: t.tone,
      warnInk: t.ink,
    };
  });

  const home = layoutFor(view.length, isDomain);
  const width = isDomain ? 288 : 216;
  const nodeHeight = (i) =>
    view[i]?.steps ? 96 + view[i].steps.length * 38 : 100;

  const cur = view[selected];
  const curStage = cur ? stageOfNode(nodes[selected], nodes) : null;

  // 소스는 고르는 즉시 저장한다. useState 에만 담으면 화면을 떠나는 순간 사라지고,
  // 노드를 실행해도 그 선택이 반영되지 않는다(노드는 sources 가 비면 /datasets 전체를 훑는다).
  const setSource = async (idx, next) => {
    setSources((prev) => ({ ...prev, [idx]: { ...prev[idx], ...next, unknown: undefined } }));
    const node = nodes[idx];
    const stage = configStageOfNode(node, nodes);
    if (!stage) {
      errorToastMessage(null, '이 노드는 소스를 저장할 수 없습니다');
      return;
    }
    const ds = sourceDatasets.find((d) => d.id === next.datasetId);
    if (!ds) return;
    const folder = next.folder && next.folder !== '/' ? next.folder : '';
    // 기존 config(기능 on/off·파라미터)를 반드시 살린다 — sources 만 보내면
    // 항해 영상의 fps 나 조인 허용오차 같은 설정이 통째로 지워진다.
    const body = {
      enabled: node.config?.enabled || {},
      params: node.config?.params || {},
      sources: [`${ds.path}${folder}`],
    };
    setSavingSource(true);
    const res = await saveStageConfig(dsId, stage, body);
    setSavingSource(false);
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return;
    }
    await load(true);
  };

  const links = (idx) => {
    const out = [];
    flowEdges.forEach(([a, b]) => {
      if (b === idx && view[a])
        out.push({ dir: '← 입력', name: view[a].name, color: '#747474' });
      if (a === idx && view[b])
        out.push({ dir: '출력 →', name: view[b].name, color: '#2d76f8' });
    });
    return out;
  };

  const start = async (dryRun) => {
    if (!curStage) return;
    setStarting(true);
    const res = await runStage(dsId, curStage, {
      dry_run: dryRun,
      sample_size: 10,
    });
    setStarting(false);
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return;
    }
    // 잡은 비동기라 지금은 running 이다. 즉시 한 번 새로 읽어 상태를 running 으로
    // 바꿔 두면 위 폴링이 이어받는다.
    load();
  };

  if (failed) {
    const gone = failed === 'notfound';
    return (
      <div className={style.page}>
        <PageHeader
          // 없는 데이터셋에서 useDatasetName 은 이름을 못 찾아 원시 ID 를 돌려준다.
          title={gone ? '데이터셋을 찾을 수 없습니다' : dsName}
          back={{ to: listBase(wsId), label: '데이터셋' }}
        />
        {/* 데이터셋이 없으면 탭은 갈 곳이 없다 — 남겨 두면 죽은 화면을 계속 순회한다. */}
        {!gone && <DatasetTabs active='파이프라인' />}
        <div className={style['pending-banner']}>
          <span className={common.prose}>
            {gone
              ? `${dsId}번 데이터셋을 찾을 수 없습니다. 삭제되었거나 주소가 잘못됐습니다.`
              : failed}
          </span>
          {gone ? (
            <Btn size='md' onClick={goList}>
              데이터셋 목록으로
            </Btn>
          ) : (
            <Btn size='md' onClick={() => load()}>
              다시 시도
            </Btn>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={style.page}>
      <PageHeader
        title={dsName}
        back={{ to: listBase(wsId), label: '데이터셋' }}
      />
      <DatasetTabs active='파이프라인' />

      <div className={style['pending-banner']}>
        <span className={style['pending-left']}>
          <span className={style['pending-left']}>
            <span className={style['pending-count']}>
              {fmt(reviewStats?.pending ?? 0)}
            </span>
            <span className={style['pending-unit']}>건 검수 대기</span>
          </span>
          <span className={common.prose}>
            전체 {fmt(reviewStats?.total ?? 0)}건
          </span>
        </span>
        <span className={style.toolbar}>
          <Btn
            size='md'
            fill='outline'
            tone='gray'
            onClick={() => go('/compose')}
          >
            데이터셋
          </Btn>
          <Btn size='md' onClick={() => go('/review')}>
            검수 시작 →
          </Btn>
        </span>
      </div>

      <div className={style.toolbar}>
        <span className={common.prose}>
          {flow ? (isDomain ? '해양 COLREG' : '범용') : '불러오는 중…'}
        </span>
        <span className={common.vline} />
        {canEdit ? (
          <Btn
            size='sm'
            fill='outline'
            tone={editable ? 'primary' : 'gray'}
            onClick={() => setEditable((v) => !v)}
          >
            {editable ? '편집 종료' : '편집'}
          </Btn>
        ) : (
          <span className={common.prose}>
            도메인 프리셋은 구성이 고정입니다
          </span>
        )}
        {/* 노드를 하나씩 실행한다. 체인 전체를 순서대로 도는 오케스트레이션은 아직
            BE 에 없다(설계문서 Phase 5) — 있는 척하면 눌러도 한 노드만 돈다. */}
        <Btn
          size='sm'
          fill='outline'
          tone='gray'
          onClick={() => start(true)}
          disabled={!curStage || starting || anyRunning}
        >
          미리보기 (표본 10)
        </Btn>
        <Btn
          size='sm'
          onClick={() => start(false)}
          disabled={!curStage || starting || anyRunning}
        >
          {anyRunning ? '실행중…' : cur ? `${cur.name} 실행` : '실행'}
        </Btn>
      </div>

      {view.length > 0 && (
        <NodeCanvas
          nodes={view}
          flow={flowEdges}
          home={home}
          width={width}
          nodeHeight={nodeHeight}
          selected={selected}
          onSelect={(i) => {
            setSelected(i);
            setDrawerOpen(true);
          }}
          onOpen={(i) => go(view[i].to)}
          editable={editable && canEdit}
          running={anyRunning}
          runningIdx={nodes.findIndex(
            (n) => n.latest_run?.status === 'running',
          )}
        />
      )}

      <NodeDrawer
        node={drawerOpen && cur ? { ...cur, links: links(selected) } : null}
        onClose={() => setDrawerOpen(false)}
        onOpen={() => go(cur.to)}
        sourceEditor={
          drawerOpen && cur?.isSource ? (
            <SourceEditor
              value={cur.source}
              datasets={sourceDatasets}
              folders={folderCache[cur.source?.datasetId] || [{ path: '/', name: '/ (전체)' }]}
              saving={savingSource}
              onChange={(next) => setSource(selected, next)}
            />
          ) : null
        }
        runPanel={
          drawerOpen && cur && !NOT_RUNNABLE.has(cur.kind) ? (
            <RunPanel
              datasetId={dsId}
              node={nodes[selected]}
              upstreamRun={upstreamRunOf(nodes, flowEdges, selected)}
              onCompare={() => go(`/flow/compare?node=${selected}`)}
            />
          ) : null
        }
      />
    </div>
  );
}
