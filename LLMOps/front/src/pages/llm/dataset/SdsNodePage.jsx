import React from 'react';
import { useParams } from 'react-router-dom';

import {
  DataTable, Frame, MetricTile, PageHeader, SectionHead, dsBase, useDatasetNav,
} from './components';
import { SDS_CHAIN, SDS_DETAIL, SDS_SAMPLE } from './mock';
import { seaFrame } from './lib/frames';
import { gateState } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

/**
 * 해양 COLREG 노드 상세 (11종).
 *
 * 노드마다 화면을 따로 만들지 않는다. 지표 · 설정 · 표는 모든 노드가 같은 골격이고,
 * 노드 성격에 따라 시각 블록(프레임 썸네일 · 생성 표본 · 심사 표본)만 갈아 끼운다.
 */
export default function SdsNodePage() {
  const { wsId, dsId } = useDatasetNav();
  const { idx } = useParams();

  const i = Math.max(0, Math.min(SDS_CHAIN.length - 1, parseInt(idx, 10) || 0));
  const node = SDS_CHAIN[i];
  const d = SDS_DETAIL[i];

  return (
    <div className={style.page}>
      <PageHeader
        title={node.name}
        back={{ to: `${dsBase(wsId, dsId)}/flow`, label: '파이프라인' }}
        meta={d.sub}
      />

      <div className={common.tiles}>
        {d.m.map(([value, label]) => (
          <MetricTile key={label} value={value} label={label} />
        ))}
      </div>

      <div className={style['sds-grid']}>
        <div className={common.stack}>
          <SectionHead>설정</SectionHead>
          <div className={common['card-pad']} style={{ paddingTop: 8, paddingBottom: 16 }}>
            {d.cfg.map(([k, v]) => (
              <span key={k} className={style['cfg-row']}>
                <span className={common.label} style={{ flexShrink: 0 }}>{k}</span>
                <span className={style['cfg-value']}>{v}</span>
              </span>
            ))}
          </div>
        </div>

        <div className={common.stack}>
          {d.thumbs && (
            <>
              <SectionHead>프레임</SectionHead>
              <div className={[common.card, common['thumb-grid']].join(' ')}>
                {[0, 1, 2, 3, 4, 5].map((k) => (
                  <span key={k} className={common.thumb}>
                    <Frame spec={seaFrame(k)} ariaLabel={`frame_${String(k).padStart(3, '0')}`} />
                    <span className={common['thumb-cap']}>frame_{String(k).padStart(3, '0')}</span>
                  </span>
                ))}
              </div>
            </>
          )}

          {d.text && (
            <>
              <SectionHead aside={<span className={[common.num, common['cell-mute']].join(' ')}>sc_0002 · 마주침 · 14조</span>}>
                생성 표본
              </SectionHead>
              <div className={[common.card, style['sample-grid']].join(' ')}>
                <span className={common.thumb}>
                  <Frame spec={seaFrame(1)} />
                </span>
                <span className={style['sample-text']}>
                  <span className={style['sample-block']}>
                    <span className={common.eyebrow}>DESCRIBE</span>
                    <span className={style['sample-body']}>{SDS_SAMPLE.describe}</span>
                  </span>
                  {/* 조언은 계산된 조항에 묶여 있어야 한다 — 모델이 지어내면 심사에서 걸린다. */}
                  <span className={[style['sample-block'], style['sample-block-strong']].join(' ')}>
                    <span className={common.eyebrow}>ADVICE</span>
                    <span className={style['sample-body']}>{SDS_SAMPLE.advice}</span>
                  </span>
                </span>
              </div>
            </>
          )}

          {d.gate && (
            <>
              <SectionHead aside={<span className={[common.num, common['cell-mute']].join(' ')}>sc_0002 · 통과</span>}>
                심사 표본
              </SectionHead>
              <div className={common['card-pad']}>
                <span className={common.tiles} style={{ gap: 12 }}>
                  {SDS_SAMPLE.gate.map(([k, v, th]) => {
                    const st = gateState(v, th);
                    return (
                      <span key={k} className={common.tile} style={{ flex: 1 }}>
                        <span className={common['tile-value']} style={{ color: st.hex }}>{v.toFixed(2)}</span>
                        <span className={common['tile-label']}>{k}</span>
                        <span className={common.prose} style={{ color: st.hex }}>
                          {st.label} · 기준 {th.toFixed(2)}
                        </span>
                      </span>
                    );
                  })}
                </span>
              </div>
            </>
          )}

          <SectionHead>{d.tTitle}</SectionHead>
          <DataTable
            cols={d.cols}
            rows={d.rows}
            cellTone={(cell) => (cell === '미달' ? 'danger' : cell === '통과' ? 'pass' : null)}
          />
        </div>
      </div>
    </div>
  );
}
