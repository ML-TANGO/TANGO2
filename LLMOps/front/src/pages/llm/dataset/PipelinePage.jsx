import React, { useEffect, useRef, useState } from 'react';

import {
  Btn, DatasetTabs, PageHeader, Segmented, Select, listBase, useDatasetNav,
} from './components';
import NodeCanvas, { NodeDrawer } from './components/NodeCanvas';
import {
  DEFAULT_SOURCES, GENERIC_CHAIN, GENERIC_HOME, REVIEW_STATS, SDS_CHAIN, SDS_FLOW,
  SDS_HOME, SDS_IN, SDS_OUT, SOURCE_DATASETS, SOURCE_FOLDERS, STAGE,
  sourceInfo, sourceSteps,
} from './mock';
import { fmt, nodeWarning } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

// 상태별 색 — 점 · 후광 · 왼쪽 강조선 · 숫자 잉크가 한 벌로 움직인다.
const TONE = {
  정상: { dot: '#00c775', halo: null, accent: 'transparent', ink: '#121619', tone: 'pass' },
  주의: { dot: '#ffab31', halo: '#fff0e4', accent: '#ffab31', ink: '#b35500', tone: 'warn' },
  위험: { dot: '#fa4e57', halo: '#ffe6e5', accent: '#fa4e57', ink: '#d91a0c', tone: 'fail' },
};

const STATE_BY_WARN = { normal: '정상', warn: '주의', danger: '위험' };

/**
 * 범용 체인 → 노드.
 *
 * 타입이 '데이터'에서 '레코드'로 바뀌는 지점은 생성 노드다. 그 뒤에 오는 변형은
 * 원본이 아니라 이미 채점된 레코드를 건드리는 것이라 의미가 달라진다 — 그래서
 * 타입을 따라가며 경고를 판정한다.
 */
function genericNodes(sources) {
  let type = '—';
  return GENERIC_CHAIN.map((c, idx) => {
    const inType = type;

    if (c.t !== 'group') {
      const s = STAGE[c.t];
      type = s.out || inType;
      const alert = s.alert;
      const state = alert ? (alert[0] === 'err' ? '위험' : '주의') : '정상';
      const isSource = c.t === 'data';
      const src = isSource ? sources[idx] : null;
      const info = sourceInfo(src);
      return {
        name: s.name, code: s.code, desc: s.desc, stats: s.stats, run: s.run,
        // 데이터 노드는 무엇을 마운트했는지가 곧 그 노드의 내용이다.
        count: isSource && info ? fmt(info.files) : s.count,
        steps: isSource ? sourceSteps(src) : undefined,
        isSource, source: src,
        inT: isSource ? '—' : inType, outT: type, to: s.to,
        state, warn: alert ? alert[1] : '', cta: alert ? alert[2] : '',
      };
    }

    const { state: warnState, warn } = nodeWarning(c.steps, inType);
    const state = warn ? STATE_BY_WARN[warnState] : c.del ? '주의' : '정상';
    return {
      name: c.name, code: '', count: c.out, steps: c.steps,
      desc: c.kind === 'prep'
        ? (inType === '레코드'
          ? '레코드 안의 이미지를 변형합니다. 변형하면 좌표와 점수가 함께 영향을 받습니다.'
          : '원본 데이터의 형태를 바꿉니다. 아무것도 버리지 않습니다.')
        : '학습에 해로운 것을 걸러냅니다. 제거된 것은 보관되고 개별로 복구할 수 있습니다.',
      stats: [['기능', `${c.steps.length}개`], ['출력', c.out], ['제거', String(c.del)]],
      run: '최근 실행 07-28 15:20', inT: inType, outT: inType,
      to: c.kind === 'prep' ? '/flow/preprocess' : '/flow/filter',
      state, warn,
    };
  });
}

/** 해양 COLREG — 구성이 도메인 논리에 묶여 있어 편집하지 않는다. */
function sdsNodes(sources) {
  return SDS_CHAIN.map((c, i) => {
    const isSource = c.kind === 'src';
    const src = isSource ? sources[i] : null;
    const info = sourceInfo(src);
    return {
      name: c.name, code: '', desc: c.desc, stats: c.stats,
      count: isSource && info ? fmt(info.files) : c.out,
      steps: isSource ? sourceSteps(src) : c.steps,
      isSource, source: src,
      run: '최근 실행 08-11 16:20', inT: SDS_IN[i], outT: SDS_OUT[i],
      to: `/flow/node/${i}`,
      state: c.del ? '주의' : '정상', warn: '',
    };
  });
}

/**
 * 데이터 노드의 마운트 편집기 — 드로어 안에서만 쓴다.
 *
 * 캔버스 위가 아니라 드로어에 두는 이유: 데이터 노드가 여러 개일 수 있어서 화면 상단에
 * 하나만 놓으면 어느 노드를 가리키는지 알 수 없다. 노드를 고른 다음 그 노드의 소스를 바꾼다.
 */
function SourceEditor({ value, onChange }) {
  const folders = SOURCE_FOLDERS[value?.dataset] || [];
  return (
    <span className={style['drawer-source']}>
      <span className={common.eyebrow}>데이터 소스</span>
      <span className={common.label}>데이터셋</span>
      <Select
        value={value?.dataset}
        options={SOURCE_DATASETS}
        onChange={(v) =>
          // 데이터셋이 바뀌면 폴더 목록이 통째로 달라지므로 첫 폴더로 되돌린다.
          onChange({ dataset: v, folder: (SOURCE_FOLDERS[v] || [{ v: '/' }])[0].v })
        }
      />
      <span className={common.label}>폴더</span>
      <Select
        value={value?.folder}
        options={folders.map((f) => ({ v: f.v, n: f.n }))}
        onChange={(v) => onChange({ folder: v })}
      />
    </span>
  );
}

export default function PipelinePage() {
  const { wsId, dsId, go } = useDatasetNav();
  const [preset, setPreset] = useState('범용');
  const [selected, setSelected] = useState(0);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editable, setEditable] = useState(false);
  const [runningIdx, setRunningIdx] = useState(null);
  const timerRef = useRef(null);

  // 데이터 소스는 노드마다 붙는다 — 노드 index → { dataset, folder }.
  // 파이프라인 하나에 원본이 하나뿐이라고 가정하면 해양 프리셋(영상 + AIS)이 표현되지 않는다.
  const [sources, setSources] = useState(DEFAULT_SOURCES);

  const isDomain = preset === '해양 COLREG';
  const presetKey = isDomain ? 'sds_colreg' : 'generic';
  const raw = isDomain ? sdsNodes(sources[presetKey]) : genericNodes(sources[presetKey]);
  const nodes = raw.map((n) => {
    const t = TONE[n.state];
    return { ...n, dot: t.dot, halo: t.halo, accent: t.accent, countColor: t.ink, tone: t.tone, warnInk: t.ink };
  });

  const home = isDomain ? SDS_HOME : GENERIC_HOME;
  const flow = isDomain ? SDS_FLOW : nodes.map((_, i) => [i, i + 1]).slice(0, -1);
  const width = isDomain ? 288 : 216;
  const nodeHeight = (i) => (raw[i].steps ? 96 + raw[i].steps.length * 38 : 100);

  // 실행 애니메이션 타이머는 언마운트 시 반드시 정리한다 — 남으면 사라진 화면의
  // state 를 계속 건드린다.
  useEffect(() => () => clearInterval(timerRef.current), []);

  const startRun = () => {
    setRunningIdx(0);
    let i = 0;
    timerRef.current = setInterval(() => {
      i += 1;
      if (i >= nodes.length) {
        clearInterval(timerRef.current);
        setRunningIdx(null);
        return;
      }
      setRunningIdx(i);
    }, 700);
  };

  const setSource = (idx, next) =>
    setSources((prev) => ({
      ...prev,
      [presetKey]: { ...prev[presetKey], [idx]: { ...prev[presetKey][idx], ...next } },
    }));

  const links = (idx) => {
    const out = [];
    flow.forEach(([a, b]) => {
      if (b === idx) out.push({ dir: '← 입력', name: nodes[a].name, color: '#747474' });
      if (a === idx) out.push({ dir: '출력 →', name: nodes[b].name, color: '#2d76f8' });
    });
    return out;
  };

  return (
    <div className={style.page}>
      <PageHeader
        title={dsId}
        back={{ to: listBase(wsId), label: '데이터셋 목록' }}
      />
      <DatasetTabs active="파이프라인" />

      <div className={style['pending-banner']}>
        <span className={style['pending-left']}>
          <span className={style['pending-left']}>
            <span className={style['pending-count']}>{fmt(REVIEW_STATS.pending)}</span>
            <span className={style['pending-unit']}>건 검수 대기</span>
          </span>
          <span className={common.prose}>처리 {REVIEW_STATS.rate}건/시</span>
        </span>
        <span className={style.toolbar}>
          <Btn size="md" fill="outline" tone="gray" onClick={() => go('/compose')}>데이터셋</Btn>
          <Btn size="md" onClick={() => go('/review')}>검수 시작 →</Btn>
        </span>
      </div>

      <div className={style.toolbar}>
        <Segmented
          options={['범용', '해양 COLREG']}
          value={preset}
          onChange={(v) => {
            setPreset(v);
            setSelected(0);
            setDrawerOpen(false);
            setEditable(false);
          }}
        />
        <span className={common.vline} />
        {!isDomain && (
          <Btn size="sm" fill="outline" tone={editable ? 'primary' : 'gray'} onClick={() => setEditable((v) => !v)}>
            {editable ? '편집 종료' : '편집'}
          </Btn>
        )}
        {isDomain && <span className={common.prose}>도메인 프리셋은 구성이 고정입니다</span>}
        <Btn size="sm" onClick={startRun} disabled={runningIdx !== null}>
          {runningIdx !== null ? `${nodes[runningIdx].name} 실행중…` : '파이프라인 실행'}
        </Btn>
      </div>

      <NodeCanvas
        nodes={nodes}
        flow={flow}
        home={home}
        width={width}
        nodeHeight={nodeHeight}
        selected={selected}
        onSelect={(i) => {
          setSelected(i);
          setDrawerOpen(true);
        }}
        onOpen={(i) => go(nodes[i].to)}
        editable={editable && !isDomain}
        running={runningIdx !== null}
        runningIdx={runningIdx}
      />

      <NodeDrawer
        node={drawerOpen ? { ...nodes[selected], links: links(selected) } : null}
        onClose={() => setDrawerOpen(false)}
        onOpen={() => go(nodes[selected].to)}
        sourceEditor={
          drawerOpen && nodes[selected].isSource ? (
            <SourceEditor
              value={nodes[selected].source}
              onChange={(next) => setSource(selected, next)}
            />
          ) : null
        }
      />
    </div>
  );
}
