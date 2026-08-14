import React, { useEffect, useRef, useState } from 'react';

import { Badge, Btn } from './index';
import common from '../styles/common.module.scss';
import style from './NodeCanvas.module.scss';

// 파이프라인 노드 캔버스 + 노드 상세 드로어.
//
// @xyflow/react 를 쓰지 않는 이유: 이 캔버스는 노드 안에 기능 목록·수량·상태 점이
// 들어가는 전용 카드이고 연결도 고정(분기 포함)이라, 범용 플로우 라이브러리를 쓰면
// 노드 렌더링을 통째로 커스터마이즈하면서 라이브러리 기능은 거의 쓰지 않게 된다.

/**
 * 두 노드를 잇는 베지어 경로.
 * 가로/세로 중 더 벌어진 축을 골라 앵커를 정한다 — 해양 프리셋처럼 위아래로 갈라지는
 * 분기 구조에서 선이 노드를 관통하지 않게 하기 위해서.
 */
function edgePath(a, b, w, hA, hB) {
  const horizontal = Math.abs(a[0] - b[0]) >= Math.abs(a[1] - b[1]);
  if (horizontal) {
    const right = b[0] > a[0];
    const x1 = a[0] + (right ? w : 0);
    const y1 = a[1] + Math.min(hA, hB) / 2;
    const x2 = b[0] + (right ? 0 : w);
    const y2 = b[1] + Math.min(hA, hB) / 2;
    const d = Math.max(30, Math.abs(x2 - x1) * 0.45) * (right ? 1 : -1);
    return `M${x1} ${y1} C${x1 + d} ${y1},${x2 - d} ${y2},${x2} ${y2}`;
  }
  const down = b[1] > a[1];
  const x1 = a[0] + w / 2;
  const y1 = a[1] + (down ? hA : 0);
  const x2 = b[0] + w / 2;
  const y2 = b[1] + (down ? 0 : hB);
  const d = Math.max(40, Math.abs(y2 - y1) * 0.5) * (down ? 1 : -1);
  return `M${x1} ${y1} C${x1} ${y1 + d},${x2} ${y2 - d},${x2} ${y2}`;
}

export default function NodeCanvas({
  nodes, flow, home, width, nodeHeight,
  selected, onSelect, onOpen, editable, running, runningIdx,
}) {
  const [pos, setPos] = useState(null);
  const [zoom, setZoom] = useState(1);
  const boxRef = useRef(null);
  // 드래그 중에 붙인 document 리스너. 드래그 도중 언마운트되면 mouseup 이 오지 않아
  // 스스로 걷히지 못하므로, 정리할 수 있게 참조를 들고 있는다.
  const dragCleanupRef = useRef(null);
  const P = pos || home;

  const bounds = nodes.reduce(
    (acc, _, i) => ({
      w: Math.max(acc.w, P[i][0] + width),
      h: Math.max(acc.h, P[i][1] + nodeHeight(i)),
    }),
    { w: 0, h: 0 },
  );
  const canvas = { w: bounds.w + 30, h: bounds.h + 30 };

  const fit = () => {
    const el = boxRef.current;
    if (!el) return;
    setZoom(Math.min(1, Math.max(0.5, Math.min(el.clientWidth / canvas.w, el.clientHeight / canvas.h))));
  };

  // 프리셋이 바뀌면 노드 수와 배치가 통째로 달라지므로 드래그로 옮긴 위치는 버린다.
  useEffect(() => {
    setPos(null);
    fit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes.length]);

  // 드래그 도중 화면을 벗어나면(라우팅·탭 전환) mouseup 이 오지 않는다.
  useEffect(() => () => {
    if (dragCleanupRef.current) dragCleanupRef.current();
  }, []);

  const startDrag = (i, e) => {
    if (!editable) return;
    e.preventDefault();
    const next = P.map((q) => q.slice());
    const originX = e.clientX;
    const originY = e.clientY;
    const base = next[i].slice();
    onSelect(i);

    const move = (ev) => {
      next[i] = [
        Math.max(0, base[0] + (ev.clientX - originX) / zoom),
        Math.max(0, base[1] + (ev.clientY - originY) / zoom),
      ];
      setPos(next.map((q) => q.slice()));
    };
    const up = () => {
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      dragCleanupRef.current = null;
    };
    dragCleanupRef.current = up;
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  };

  return (
    <div className={style.wrap}>
      <div className={style.toolbar}>
        <span className={style['toolbar-info']}>{nodes.length}개 노드</span>
        <span className={style['toolbar-actions']}>
          <span className={style['toolbar-info']}>{Math.round(zoom * 100)}%</span>
          <button type="button" className={style['zoom-btn']} onClick={() => setZoom((z) => Math.max(0.5, Math.round((z - 0.1) * 10) / 10))}>−</button>
          <button type="button" className={style['zoom-btn']} onClick={() => setZoom((z) => Math.min(1.4, Math.round((z + 0.1) * 10) / 10))}>＋</button>
          <button type="button" className={style['zoom-btn']} onClick={fit}>맞춤</button>
        </span>
      </div>

      <div ref={boxRef} className={style.canvas}>
        <div className={style.plane} style={{ width: canvas.w, height: canvas.h, transform: `scale(${zoom})` }}>
          <svg width={canvas.w} height={canvas.h} className={style.edges}>
            <defs>
              <marker id="dp-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0 0 L8 4 L0 8 z" fill="#93baff" />
              </marker>
            </defs>
            {flow.map(([a, b]) => (
              <path
                key={`${a}-${b}`}
                d={edgePath(P[a], P[b], width, nodeHeight(a), nodeHeight(b))}
                fill="none"
                stroke="#93baff"
                strokeWidth="2"
                markerEnd="url(#dp-arrow)"
              />
            ))}
          </svg>

          {nodes.map((n, i) => (
            <div
              key={n.name + i}
              role="button"
              tabIndex={0}
              onMouseDown={(e) => startDrag(i, e)}
              onClick={() => onSelect(i)}
              onDoubleClick={() => onOpen(i)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') onOpen(i);
              }}
              style={{ left: P[i][0], top: P[i][1], width, height: nodeHeight(i), borderLeft: `3px solid ${n.accent}` }}
              className={[
                style.node,
                editable ? style['node-drag'] : '',
                selected === i ? style['node-on'] : '',
              ].join(' ')}
            >
              <span className={style['node-head']}>
                <span className={style['node-name']}>{n.name}</span>
                {running && runningIdx === i && <span className={style['node-live']}>실행중</span>}
                <span
                  className={style['node-dot']}
                  style={{ background: n.dot, boxShadow: n.halo ? `0 0 0 3px ${n.halo}` : 'none' }}
                />
              </span>

              {n.steps && (
                <span className={style['node-steps']}>
                  {n.steps.map(([k, v]) => (
                    <span key={k} className={style['node-step']}>
                      {editable && <span className={style['node-grip']}>⠿</span>}
                      <span className={style['node-step-name']}>{k}</span>
                      <span className={style['node-step-val']}>{v}</span>
                    </span>
                  ))}
                </span>
              )}

              <span className={style['node-count']} style={{ color: n.countColor }}>
                {n.count}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * 노드 상세 드로어.
 * 캔버스는 한눈에 보는 곳이고, 문장으로 된 설명과 다음 조치는 여기서만 다룬다.
 */
export function NodeDrawer({ node, onClose, onOpen, sourceEditor = null }) {
  if (!node) return null;
  return (
    <>
      <div className={style.dim} onClick={onClose} role="presentation" />
      <aside className={style.drawer}>
        <div className={style['drawer-head']}>
          <span className={style['drawer-title-row']}>
            <span className={style['drawer-title-box']}>
              <span className={style['drawer-title']}>{node.name}</span>
              {node.code && <span className={[common.eyebrow, style['drawer-code']].join(' ')}>{node.code}</span>}
            </span>
            <button type="button" onClick={onClose} className={style['drawer-close']} aria-label="닫기">✕</button>
          </span>
          {node.warn && (
            <span className={style['drawer-warn']}>
              <span className={style['drawer-warn-dot']} style={{ background: node.warnInk }} />
              <span className={style['drawer-warn-text']}>{node.warn}</span>
            </span>
          )}
        </div>

        <div className={style['drawer-body']}>
          <span className={style['drawer-meta']}>
            <Badge tone={node.tone} size="lg">{node.state}</Badge>
            <span className={style['drawer-run']}>{node.run}</span>
          </span>

          <span className={style['drawer-io']}>
            <span className={common.eyebrow}>I/O</span>
            <span className={style['drawer-io-val']}>{node.inT} → {node.outT}</span>
          </span>

          <span className={style['drawer-desc']}>{node.desc}</span>

          {/* 데이터 노드라면 여기서 마운트를 바꾼다 — 노드가 여러 개라 캔버스 밖에 두면
              어느 노드의 소스인지 알 수 없다. */}
          {sourceEditor}

          {node.stats && (
            <span className={style['drawer-stats']}>
              {node.stats.map(([k, v]) => (
                <span key={k} className={style['drawer-stat']}>
                  <span className={style['drawer-stat-value']}>{v}</span>
                  <span className={style['drawer-stat-label']}>{k}</span>
                </span>
              ))}
            </span>
          )}

          {node.steps && (
            <span className={style['drawer-block']}>
              <span className={common.eyebrow}>기능</span>
              {node.steps.map(([k, v], i) => (
                <span key={k} className={style['drawer-step']}>
                  <span className={style['drawer-step-idx']}>{i + 1}</span>
                  <span className={style['drawer-step-name']}>{k}</span>
                  <span className={style['drawer-step-val']}>{v}</span>
                </span>
              ))}
            </span>
          )}

          {node.links && node.links.length > 0 && (
            <span className={style['drawer-block']}>
              <span className={common.eyebrow}>연결</span>
              {node.links.map((l) => (
                <span key={l.dir + l.name} className={style['drawer-link']}>
                  <span className={style['drawer-link-dir']} style={{ color: l.color }}>{l.dir}</span>
                  <span className={style['drawer-link-name']}>{l.name}</span>
                </span>
              ))}
            </span>
          )}

          <span className={style['drawer-foot']}>
            <Btn block onClick={onOpen}>{node.cta || '열기'} →</Btn>
          </span>
        </div>
      </aside>
    </>
  );
}
