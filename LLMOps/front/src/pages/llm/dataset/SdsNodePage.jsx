import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { getFlow, getStage, runStage } from '@src/apis/llm/dataset';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import {
  Badge,
  Btn,
  MetricTile,
  PageHeader,
  SectionHead,
  dsBase,
  useDatasetNav,
} from './components';
import RunPanel from './components/RunPanel';
import { stageOfNode, upstreamRunOf } from './lib/stage';
import { fmt } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

/**
 * 노드 상세 — 전용 설정 화면이 없는 노드(해양 COLREG 원천 · 조인 · 계산 등)가 온다.
 *
 * 노드마다 화면을 따로 만들지 않는다. 무엇을 하는 노드든 사람이 확인하려는 것은 같다 —
 * 어떤 설정으로, 몇 건이 들어와, 몇 건이 남고, 무엇이 왜 빠졌는가.
 *
 * 그래서 지표 · 설정은 저장된 노드에서 읽고, 결과는 파이프라인 드로어 · 단계 설정
 * 화면과 **같은 `RunPanel`** 을 쓴다. 노드별로 다른 표를 그리면 노드가 늘 때마다
 * 화면을 새로 만들어야 하고, 그 표들이 서로 다른 숫자를 보여주게 된다.
 */
export default function SdsNodePage() {
  const { wsId, dsId } = useDatasetNav();
  const { idx } = useParams();

  const [flow, setFlow] = useState(null);
  const [config, setConfig] = useState(null);
  const [busy, setBusy] = useState(false);

  const index = Math.max(0, parseInt(idx, 10) || 0);

  const load = useCallback(async () => {
    const res = await getFlow(dsId);
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return;
    }
    setFlow(res.result);
    const nodes = res.result?.nodes || [];
    const stage = stageOfNode(nodes[index], nodes);
    if (stage) {
      const st = await getStage(dsId, stage);
      if (st.status === STATUS_SUCCESS) setConfig(st.result?.config || {});
    }
  }, [dsId, index]);

  useEffect(() => {
    load();
  }, [load]);

  const nodes = flow?.nodes || [];
  const node = nodes[index] || null;
  const stage = node ? stageOfNode(node, nodes) : null;
  const run = node?.latest_run || null;
  const running = run?.status === 'running';

  const start = async (dryRun) => {
    if (!stage) return;
    setBusy(true);
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

  if (!node) {
    return (
      <div className={style.page}>
        <PageHeader
          title='노드'
          back={{ to: `${dsBase(wsId, dsId)}/flow`, label: '파이프라인' }}
        />
        <div className={common['card-pad']}>
          <span className={common.prose}>
            {flow ? '이 번호의 노드가 없습니다.' : '불러오는 중…'}
          </span>
        </div>
      </div>
    );
  }

  const isSource = node.kind === 'src';

  // 설정은 노드에 붙어 있는 steps 와 저장된 params 를 같이 보여준다.
  // 둘 다 없으면 "설정할 항목이 없다"고 적는다 — 빈 카드는 고장으로 읽힌다.
  const cfgSteps = (node.steps || []).map(([k, v]) => [k, String(v)]);
  const cfgParams = Object.entries(config?.params || {}).map(([k, v]) => [
    k,
    String(v),
  ]);
  const cfgRows = [...cfgSteps, ...cfgParams];

  const runTone =
    run?.status === 'failed'
      ? 'fail'
      : run?.status === 'running'
        ? 'warn'
        : 'pass';

  return (
    <div className={style.page}>
      <PageHeader
        title={node.name}
        back={{ to: `${dsBase(wsId, dsId)}/flow`, label: '파이프라인' }}
        meta={
          isSource
            ? `산출 · ${node.output_type}`
            : `${node.input_type} → ${node.output_type}`
        }
        actions={
          stage ? (
            <span className={style.toolbar}>
              <Btn
                size='md'
                fill='outline'
                tone='gray'
                onClick={() => start(true)}
                disabled={busy || running}
              >
                미리보기
              </Btn>
              <Btn
                size='md'
                onClick={() => start(false)}
                disabled={busy || running}
              >
                {running ? '실행중…' : '실행'}
              </Btn>
            </span>
          ) : null
        }
      />

      {node.warning && (
        <span className={[common.note, common['note-fail']].join(' ')}>
          <span className={common['note-title']}>경고</span>
          <span className={common['note-body']}>{node.warning}</span>
        </span>
      )}

      <div className={common.tiles}>
        {/* 소스 노드는 상류가 없어 in 이 out 과 같은 값으로 채워진다. 그대로 쓰면
            '입력 100' 과 실행 패널의 '상류 노드를 먼저 실행하세요' 가 한 화면에서
            서로를 부정한다. 상류가 있는 노드에서만 입력을 말한다. */}
        <MetricTile
          value={!isSource && run ? fmt(run.in ?? 0) : '—'}
          label='입력'
        />
        {/* 통과는 passed. 심사 노드는 미달을 버리지 않아 out 은 산출 건수다. */}
        <MetricTile value={run ? fmt(run.passed ?? run.out ?? 0) : '—'} label='통과' />
        <MetricTile value={run ? fmt(run.dropped ?? 0) : '—'} label='제외' />
        <MetricTile
          // 값이 문자열이 아니면(.slice 부재) 타일 하나가 아니라 페이지 전체가
          // 렌더 예외로 빈 화면이 된다 — String() 한 겹이 그 부류를 통째로 막는다.
          value={
            run?.started_at
              ? String(run.started_at).replace('T', ' ').slice(5, 16)
              : '없음'
          }
          label={run?.dry_run ? '최근 실행 · 미리보기' : '최근 실행'}
        />
      </div>

      <div className={style['sds-grid']}>
        <div className={common.stack}>
          <SectionHead
            aside={
              run?.status ? <Badge tone={runTone}>{run.status}</Badge> : null
            }
          >
            설정
          </SectionHead>
          <div
            className={common['card-pad']}
            style={{ paddingTop: 8, paddingBottom: 16 }}
          >
            {cfgSteps.map(([k, v]) => (
              <span key={`s-${k}`} className={style['cfg-row']}>
                <span className={common.label} style={{ flexShrink: 0 }}>
                  {k}
                </span>
                <span className={style['cfg-value']}>{v}</span>
              </span>
            ))}
            {/* params 는 steps 와 같은 설정을 원시 키로 한 번 더 보여준다. 구분 없이
                이어 붙이면 같은 값이 두 줄로 적힌 것처럼 읽힌다. */}
            {cfgParams.length > 0 && (
              <span
                className={common.label}
                style={{ display: 'block', marginTop: 12, marginBottom: 4 }}
              >
                저장된 파라미터
              </span>
            )}
            {cfgParams.map(([k, v]) => (
              <span key={`p-${k}`} className={style['cfg-row']}>
                <span
                  className={[common.label, common.mute].join(' ')}
                  style={{ flexShrink: 0 }}
                >
                  {k}
                </span>
                <span className={style['cfg-value']}>{v}</span>
              </span>
            ))}
            {cfgRows.length === 0 && (
              <span className={common.prose}>
                이 노드에는 설정할 항목이 없습니다.
              </span>
            )}
          </div>
        </div>

        <div className={common.stack}>
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
