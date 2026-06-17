import { memo, useState, useEffect, useRef, Fragment } from 'react';
import { useHistory, useParams } from 'react-router-dom';
import { callApi, STATUS_SUCCESS } from '@src/network';
import classNames from 'classnames/bind';
import style from './ModelDetailPage.module.scss';

const cx = classNames.bind(style);

// ─── Static constants ──────────────────────────────────────────────────────────

const TABS = ['정보', '학습', '관리'];

const MOCK_DATASETS = [
  { id: 'ds-1', name: 'SDS Dataset',       desc: 'SDS Field Test Dataset (20260227)',              size: '158.3 MB', fmt: 'CSV',   samples: 12450 },
  { id: 'ds-2', name: 'SDS Dataset V1',    desc: 'VisionLanguageModel 학습용 변환 데이터셋',         size: '2.0 MB',   fmt: 'JSONL', samples: 1800  },
  { id: 'ds-3', name: 'KoAlpaca-v1.1a',   desc: '한국어 알파카 지시 데이터셋',                      size: '45.2 MB',  fmt: 'JSONL', samples: 52000 },
  { id: 'ds-4', name: 'Open-Platypus-ko', desc: '오픈 플래티퍼스 한국어 번역 명령 데이터',            size: '8.7 MB',   fmt: 'JSONL', samples: 25000 },
];

const GPU_OPTS = [
  { id: 'a100-1',  label: '1× A100 80GB' },
  { id: 'a100-2',  label: '2× A100 80GB' },
  { id: 'v100-1',  label: '1× V100 32GB' },
  { id: 'rtx4090', label: '1× RTX 4090'  },
];
const CPU_OPTS = [4, 8, 16, 32];
const MEM_OPTS = ['16GB', '32GB', '64GB', '128GB'];

const INIT_CKPTS = [
  { id: 'ckpt-500',  step: 500,  epoch: 1, loss: 2.3412, grad: 0.3421, size: '16.2 GB', saved_at: '2026-06-16T10:30:00Z', is_best: false },
  { id: 'ckpt-1000', step: 1000, epoch: 2, loss: 1.8761, grad: 0.2893, size: '16.2 GB', saved_at: '2026-06-16T11:15:00Z', is_best: false },
  { id: 'ckpt-1500', step: 1500, epoch: 3, loss: 1.5421, grad: 0.2611, size: '16.2 GB', saved_at: '2026-06-16T12:00:00Z', is_best: true  },
  { id: 'ckpt-2000', step: 2000, epoch: 4, loss: 1.3211, grad: 0.2452, size: '16.2 GB', saved_at: '2026-06-16T12:45:00Z', is_best: false },
];

// Deterministic pseudo-random training curve (no Math.random)
function genCurves(n = 80) {
  const loss = [], grad = [];
  for (let i = 0; i <= n; i++) {
    const t  = i / n;
    const s1 = ((i * 1637 + 42) % 97) / 97 - 0.5;
    const s2 = ((i * 3271 + 17) % 83) / 83 - 0.5;
    loss.push({ step: i * 25, val: Math.max(0.32, 2.75 * Math.exp(-3.2 * t) + 0.44 + s1 * 0.15) });
    grad.push({ step: i * 25, val: Math.max(0.04, 0.27 + Math.sin(t * Math.PI * 3.2) * 0.14 + s2 * 0.09) });
  }
  return { loss, grad };
}
const ALL_CURVES = genCurves(80);

// Faster convergence curve for projector pre-training (fewer steps)
function genProjCurves(n = 40) {
  const loss = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const s = ((i * 2341 + 77) % 89) / 89 - 0.5;
    loss.push({ step: i * 10, val: Math.max(0.18, 1.85 * Math.exp(-5.2 * t) + 0.21 + s * 0.07) });
  }
  return { loss };
}
const PROJ_CURVES = genProjCurves(40);

function fmtDate(iso) { return iso.slice(0, 16).replace('T', ' '); }

// ─── Sub-components ────────────────────────────────────────────────────────────

function SectionLabel({ children }) {
  return <div className={cx('section-label')}>{children}</div>;
}

function Chip({ label, selected, onClick }) {
  return (
    <button type="button" className={cx('chip', selected && 'chip--on')} onClick={onClick}>
      {label}
    </button>
  );
}

// SVG line chart (pure, no side effects)
function LineChart({ data, colorStroke, labelY }) {
  const W = 560, H = 180, PX = 50, PY = 14, PR = 12, PB = 28;
  const cW = W - PX - PR, cH = H - PY - PB;

  if (!data || data.length < 2) {
    return (
      <svg viewBox={`0 0 ${W} ${H}`} className={cx('chart-svg')}>
        <text x={W / 2} y={H / 2 + 4} textAnchor="middle" fontSize="12" fill="#c1c1c1" fontFamily="SpoqaM">
          학습 시작 후 표시됩니다
        </text>
      </svg>
    );
  }

  const vals  = data.map((d) => d.val);
  const steps = data.map((d) => d.step);
  const yMin  = Math.min(...vals) * 0.88;
  const yMax  = Math.max(...vals) * 1.12;
  const xMin  = steps[0];
  const xMax  = steps[steps.length - 1];
  const toX   = (s) => PX + ((s - xMin) / (xMax - xMin || 1)) * cW;
  const toY   = (v) => PY + cH - ((v - yMin) / (yMax - yMin || 0.001)) * cH;
  const pts   = data.map((d) => `${toX(d.step).toFixed(1)},${toY(d.val).toFixed(1)}`).join(' ');
  const lastX = toX(data[data.length - 1].step);
  const lastY = toY(data[data.length - 1].val);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={cx('chart-svg')}>
      {/* Y grid + labels */}
      {[0, 0.25, 0.5, 0.75, 1].map((f, i) => {
        const y = PY + f * cH;
        const v = yMax - f * (yMax - yMin);
        return (
          <g key={i}>
            <line x1={PX} y1={y} x2={W - PR} y2={y} stroke="#f0f0f0" strokeWidth="1" />
            <text x={PX - 4} y={y + 4} textAnchor="end" fontSize="9" fill="#c1c1c1" fontFamily="SpoqaM">{v.toFixed(3)}</text>
          </g>
        );
      })}
      {/* X labels */}
      {[0, 0.25, 0.5, 0.75, 1].map((f, i) => {
        const x = PX + f * cW;
        const s = Math.round(xMin + f * (xMax - xMin));
        return <text key={i} x={x} y={H - 5} textAnchor="middle" fontSize="9" fill="#c1c1c1" fontFamily="SpoqaM">{s}</text>;
      })}
      {/* Axes */}
      <line x1={PX} y1={PY} x2={PX} y2={PY + cH} stroke="#dbdbdb" strokeWidth="1" />
      <line x1={PX} y1={PY + cH} x2={W - PR} y2={PY + cH} stroke="#dbdbdb" strokeWidth="1" />
      {/* Y-axis label */}
      <text
        x={10} y={PY + cH / 2}
        textAnchor="middle" fontSize="9" fill="#747474" fontFamily="SpoqaM"
        transform={`rotate(-90,10,${PY + cH / 2})`}
      >
        {labelY}
      </text>
      {/* Area fill */}
      <polygon
        points={`${PX},${PY + cH} ${pts} ${lastX.toFixed(1)},${PY + cH}`}
        fill={colorStroke}
        opacity="0.07"
      />
      {/* Line */}
      <polyline points={pts} fill="none" stroke={colorStroke} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      {/* Last dot */}
      <circle cx={lastX.toFixed(1)} cy={lastY.toFixed(1)} r="3.5" fill={colorStroke} />
    </svg>
  );
}

// VLM architecture diagram: CLIP → Projector → LLM
function MultimodalArchDiagram({ projType, mlpHidden, xAttnHeads, qTokens }) {
  // ── Column geometry ──────────────────────────────────────────────────
  const CL_X = 5,   CL_W = 295, CL_CX = CL_X + CL_W / 2;   // CLIP   cx≈152
  const PR_X = 360, PR_W = 240, PR_CX = PR_X + PR_W / 2;    // Proj   cx=480
  const QW_X = 660, QW_W = 310, QW_CX = QW_X + QW_W / 2;   // Qwen   cx=815
  const SVG_W = QW_X + QW_W + 5;                             // 975

  // ── SVG helpers ──────────────────────────────────────────────────────
  const BBox = ({ x, cx, w, y, h = 28, label, s1, fill, stroke, tf = '#333' }) => (
    <g>
      <rect x={x ?? cx - w / 2} y={y} width={w} height={h} rx="5" fill={fill} stroke={stroke} strokeWidth="1.5" />
      <text x={cx} y={y + (s1 ? 11 : Math.round(h / 2) + 4)} textAnchor="middle" fontSize="10" fontFamily="SpoqaB" fill={tf}>{label}</text>
      {s1 && <text x={cx} y={y + 22} textAnchor="middle" fontSize="8.5" fontFamily="SpoqaM" fill={tf} opacity="0.75">{s1}</text>}
    </g>
  );
  const VArr = ({ cx, y1, y2 }) => (
    <g>
      <line x1={cx} y1={y1} x2={cx} y2={y2 - 7} stroke="#c0c0c0" strokeWidth="1.5" />
      <polygon points={`${cx - 4},${y2 - 10} ${cx + 4},${y2 - 10} ${cx},${y2 - 3}`} fill="#c0c0c0" />
    </g>
  );
  const HArr = ({ x1, y1, x2, y2 }) => {
    const mx = Math.round((x1 + x2) / 2);
    if (Math.abs(y1 - y2) < 2) {
      return <g>
        <line x1={x1} y1={y1} x2={x2 - 7} y2={y2} stroke="#b0b0b0" strokeWidth="1.5" />
        <polygon points={`${x2 - 10},${y2 - 4} ${x2 - 10},${y2 + 4} ${x2 - 3},${y2}`} fill="#b0b0b0" />
      </g>;
    }
    return <g>
      <polyline points={`${x1},${y1} ${mx},${y1} ${mx},${y2} ${x2 - 7},${y2}`} fill="none" stroke="#b0b0b0" strokeWidth="1.5" strokeDasharray="4 2" />
      <polygon points={`${x2 - 10},${y2 - 4} ${x2 - 10},${y2 + 4} ${x2 - 3},${y2}`} fill="#b0b0b0" />
    </g>;
  };
  const Plus = ({ cx, cy }) => (
    <g>
      <circle cx={cx} cy={cy} r={9} fill="#fff" stroke="#c0c0c0" strokeWidth="1.5" />
      <line x1={cx - 5} y1={cy} x2={cx + 5} y2={cy} stroke="#888" strokeWidth="1.5" />
      <line x1={cx} y1={cy - 5} x2={cx} y2={cy + 5} stroke="#888" strokeWidth="1.5" />
    </g>
  );
  const ColHdr = ({ x, w, cx, title, sub, fill, stroke, tf }) => (
    <g>
      <rect x={x} y={0} width={w} height={50} rx="8" fill={fill} stroke={stroke} strokeWidth="1.5" />
      <text x={cx} y={18} textAnchor="middle" fontSize="12" fontFamily="SpoqaB" fill={tf}>{title}</text>
      <text x={cx} y={34} textAnchor="middle" fontSize="9"  fontFamily="SpoqaM" fill={tf} opacity="0.75">{sub}</text>
    </g>
  );
  const BlockOutline = ({ x, w, y, h, label, stroke }) => (
    <g>
      <rect x={x} y={y} width={w} height={h} rx="6" fill="none" stroke={stroke} strokeWidth="1" strokeDasharray="5 3" opacity="0.6" />
      <rect x={x + w - 72} y={y + h - 16} width={68} height={13} rx="3" fill={stroke} opacity="0.12" />
      <text x={x + w - 36} y={y + h - 6} textAnchor="middle" fontSize="8" fontFamily="SpoqaB" fill={stroke} opacity="0.9">{label}</text>
    </g>
  );

  // ── CLIP ViT-L/14 Y layout ────────────────────────────────────────────
  const cl_bx = CL_X + 8, cl_bw = CL_W - 16;
  const cl_in   = 60;
  const cl_pe   = cl_in + 28 + 10;
  const cl_pos  = cl_pe + 28 + 10;
  const cl_blk  = cl_pos + 22 + 12;
  const cl_ln1  = cl_blk + 14;
  const cl_mhsa = cl_ln1 + 24 + 8;
  const cl_r1cy = cl_mhsa + 40 + 10;
  const cl_ln2  = cl_r1cy + 18 + 8;
  const cl_ffn  = cl_ln2 + 24 + 8;
  const cl_r2cy = cl_ffn + 40 + 10;
  const cl_blkH = cl_r2cy + 18 - cl_blk + 10;
  const cl_fln  = cl_blk + cl_blkH + 12;
  const cl_out  = cl_fln + 24 + 10;

  // ── Qwen3-8B Y layout ────────────────────────────────────────────────
  const qw_bx = QW_X + 8, qw_bw = QW_W - 16;
  const qw_in   = 60;
  const qw_emb  = qw_in + 22 + 10;
  const qw_blk  = qw_emb + 28 + 12;
  const qw_rn1  = qw_blk + 14;
  const qw_gqa  = qw_rn1 + 24 + 8;
  const qw_r1cy = qw_gqa + 40 + 10;
  const qw_rn2  = qw_r1cy + 18 + 8;
  const qw_mlp  = qw_rn2 + 24 + 8;
  const qw_r2cy = qw_mlp + 40 + 10;
  const qw_blkH = qw_r2cy + 18 - qw_blk + 10;
  const qw_fnm  = qw_blk + qw_blkH + 12;
  const qw_lmh  = qw_fnm + 24 + 10;
  const qw_out  = qw_lmh + 28 + 10;

  const COL_H = Math.max(cl_out + 28 + 20, qw_out + 22 + 20, 480);
  const SVG_H = COL_H;

  // ── Projector: build nodes centered in column ────────────────────────
  const pr_bx = PR_X + 8, pr_bw = PR_W - 16;
  const NK = { fill: '#e8f0fe', stroke: '#4285f4', tf: '#1a237e' };
  const GN = { fill: '#e8f5e9', stroke: '#43a047', tf: '#1b5e20' };
  const NH = 28, NG = 10;

  let prSeq;
  if (projType === 'linear') {
    prSeq = [
      { label: 'Linear', s1: `1024 → 4096`, ...NK },
    ];
  } else if (projType === 'mlp2') {
    prSeq = [
      { label: 'Linear (1)', s1: `1024 → ${mlpHidden}`, ...NK },
      { label: 'GELU', ...GN },
      { label: 'Linear (2)', s1: `${mlpHidden} → 4096`, ...NK },
    ];
  } else if (projType === 'mlp3') {
    prSeq = [
      { label: 'Linear (1)', s1: `1024 → ${mlpHidden}`, ...NK },
      { label: 'GELU', ...GN },
      { label: 'Linear (2)', s1: `${mlpHidden} → ${mlpHidden}`, ...NK },
      { label: 'GELU', ...GN },
      { label: 'Linear (3)', s1: `${mlpHidden} → 4096`, ...NK },
    ];
  } else if (projType === 'xattn') {
    prSeq = [
      { label: 'Cross-Attention', s1: `${xAttnHeads} heads`, ...NK, h: 40 },
      { label: 'Cross-Attention', s1: `(Layer 2)`, ...NK, h: 40 },
      { label: 'Linear', s1: `1024 → 4096`, ...NK },
    ];
  } else {
    prSeq = [
      { label: `×8 Q-Former Block`, s1: `Self + Cross Attn`, ...NK, h: 40 },
      { label: 'Linear', s1: `${qTokens}×1024 → ${qTokens}×4096`, ...NK },
    ];
  }

  const seqTotalH = prSeq.reduce((a, n) => a + (n.h || NH), 0) + NG * (prSeq.length - 1);
  // Input/output IO boxes + arrows above/below
  const ioH = 22, ioArr = 14, ioBox = 2;
  const blockTotal = ioH + ioArr + seqTotalH + ioArr + ioH;
  const pr_top = Math.round((COL_H - blockTotal) / 2);

  const pr_io_in_y = pr_top;
  let pr_y = pr_io_in_y + ioH + ioArr;
  const prNodePos = prSeq.map((n) => {
    const nh = n.h || NH;
    const y = pr_y;
    pr_y += nh + NG;
    return { ...n, y };
  });
  const pr_io_out_y = pr_y - NG + ioArr;

  // Horizontal connector Y mid-points
  const cl_out_cy = cl_out + 14;
  const pr_in_cy  = pr_io_in_y + 11;
  const pr_out_cy = pr_io_out_y + 11;
  const qw_in_cy  = qw_in + 11;

  return (
    <div className={cx('mg-wrapper')}>
      <svg viewBox={`0 0 ${SVG_W} ${SVG_H}`} className={cx('mg-svg')} xmlns="http://www.w3.org/2000/svg">

        {/* ── Column backgrounds ────────────────────────────────────── */}
        <rect x={CL_X} y={0} width={CL_W} height={SVG_H} rx="8" fill="#fffdf7" stroke="#fb8c00" strokeWidth="1.5" />
        <rect x={PR_X} y={0} width={PR_W} height={SVG_H} rx="8" fill="#f0f4ff" stroke="#4285f4" strokeWidth="1.5" />
        <rect x={QW_X} y={0} width={QW_W} height={SVG_H} rx="8" fill="#fdf5ff" stroke="#8e24aa" strokeWidth="1.5" />

        {/* ── Column headers ────────────────────────────────────────── */}
        <ColHdr x={CL_X} w={CL_W} cx={CL_CX} title="CLIP ViT-L/14" sub="Vision Encoder · L24 H16 D1024 · 256 patches" fill="#fff8e1" stroke="#fb8c00" tf="#e65100" />
        <ColHdr x={PR_X} w={PR_W} cx={PR_CX} title="Projector"      sub={{ linear:'Linear', mlp2:'MLP-2', mlp3:'MLP-3', xattn:'Cross-Attention', qformer:'Q-Former' }[projType] ?? ''} fill="#e8f0fe" stroke="#4285f4" tf="#1a237e" />
        <ColHdr x={QW_X} w={QW_W} cx={QW_CX} title="Qwen3-8B"       sub="Language Model · L36 H32 D4096 · 152K vocab" fill="#f3e5f5" stroke="#8e24aa" tf="#4a148c" />

        {/* ══ CLIP ViT-L/14 architecture ══════════════════════════════ */}

        {/* Image Input */}
        <BBox x={cl_bx} cx={CL_CX} w={cl_bw} y={cl_in}  h={28} label="Image Input" s1="[3 × 224 × 224]" fill="#f5f5f5" stroke="#bdbdbd" tf="#424242" />
        <VArr cx={CL_CX} y1={cl_in + 28} y2={cl_pe} />

        {/* Patch Embed */}
        <BBox x={cl_bx} cx={CL_CX} w={cl_bw} y={cl_pe}  h={28} label="Patch Embed (14×14)" s1="256 patches × 1024" fill="#fff8e1" stroke="#fb8c00" tf="#e65100" />
        <VArr cx={CL_CX} y1={cl_pe + 28} y2={cl_pos} />

        {/* Pos Encoding */}
        <BBox x={cl_bx} cx={CL_CX} w={cl_bw} y={cl_pos} h={22} label="+ Positional Encoding [257 tokens]" fill="#e8f5e9" stroke="#43a047" tf="#1b5e20" />
        <VArr cx={CL_CX} y1={cl_pos + 22} y2={cl_blk + 14} />

        {/* ×24 ViT Block */}
        <BlockOutline x={cl_bx} w={cl_bw} y={cl_blk} h={cl_blkH} label="× 24 ViT Block" stroke="#fb8c00" />

        <BBox x={cl_bx + 10} cx={CL_CX} w={cl_bw - 20} y={cl_ln1}  h={24} label="LayerNorm" fill="#e8f5e9" stroke="#43a047" tf="#1b5e20" />
        <VArr cx={CL_CX} y1={cl_ln1 + 24} y2={cl_mhsa} />

        <BBox x={cl_bx + 10} cx={CL_CX} w={cl_bw - 20} y={cl_mhsa} h={40} label="Multi-Head Self-Attention" s1="16 heads · head_dim=64" fill="#e8f0fe" stroke="#4285f4" tf="#1a237e" />
        <VArr cx={CL_CX} y1={cl_mhsa + 40} y2={cl_r1cy - 9} />
        <Plus cx={CL_CX} cy={cl_r1cy} />
        <VArr cx={CL_CX} y1={cl_r1cy + 9} y2={cl_ln2} />

        <BBox x={cl_bx + 10} cx={CL_CX} w={cl_bw - 20} y={cl_ln2}  h={24} label="LayerNorm" fill="#e8f5e9" stroke="#43a047" tf="#1b5e20" />
        <VArr cx={CL_CX} y1={cl_ln2 + 24} y2={cl_ffn} />

        <BBox x={cl_bx + 10} cx={CL_CX} w={cl_bw - 20} y={cl_ffn}  h={40} label="Feed-Forward Network" s1="FFN dim: 4096" fill="#f3e5f5" stroke="#8e24aa" tf="#4a148c" />
        <VArr cx={CL_CX} y1={cl_ffn + 40} y2={cl_r2cy - 9} />
        <Plus cx={CL_CX} cy={cl_r2cy} />

        <VArr cx={CL_CX} y1={cl_r2cy + 9} y2={cl_fln} />
        <BBox x={cl_bx} cx={CL_CX} w={cl_bw} y={cl_fln} h={24} label="LayerNorm" fill="#e8f5e9" stroke="#43a047" tf="#1b5e20" />
        <VArr cx={CL_CX} y1={cl_fln + 24} y2={cl_out} />

        {/* Visual Features output */}
        <BBox x={cl_bx} cx={CL_CX} w={cl_bw} y={cl_out} h={28} label="Visual Features" s1="[257 × 1024]" fill="#fff8e1" stroke="#fb8c00" tf="#e65100" />

        {/* ══ Projector architecture (dynamic) ═══════════════════════ */}

        {/* Input IO box */}
        <BBox x={pr_bx} cx={PR_CX} w={pr_bw} y={pr_io_in_y} h={ioH} label="Visual In [257 × 1024]" fill="#f5f5f5" stroke="#bdbdbd" tf="#555" />
        <VArr cx={PR_CX} y1={pr_io_in_y + ioH} y2={prNodePos[0]?.y ?? pr_io_in_y + ioH + ioArr} />

        {prNodePos.map((n, i) => {
          const nh = n.h || NH;
          return (
            <g key={i}>
              <BBox x={pr_bx} cx={PR_CX} w={pr_bw} y={n.y} h={nh} label={n.label} s1={n.s1} fill={n.fill} stroke={n.stroke} tf={n.tf} />
              {i < prNodePos.length - 1 && <VArr cx={PR_CX} y1={n.y + nh} y2={prNodePos[i + 1].y} />}
            </g>
          );
        })}

        {prNodePos.length > 0 && (
          <VArr cx={PR_CX} y1={(prNodePos[prNodePos.length - 1].y) + (prNodePos[prNodePos.length - 1].h || NH)} y2={pr_io_out_y} />
        )}

        {/* Output IO box */}
        <BBox x={pr_bx} cx={PR_CX} w={pr_bw} y={pr_io_out_y} h={ioH} label="Projected [257 × 4096]" fill="#f5f5f5" stroke="#bdbdbd" tf="#555" />

        {/* ══ Qwen3-8B architecture ════════════════════════════════════ */}

        <BBox x={qw_bx} cx={QW_CX} w={qw_bw} y={qw_in}  h={22} label="Input IDs [batch, seq_len]" fill="#f5f5f5" stroke="#bdbdbd" tf="#424242" />
        <VArr cx={QW_CX} y1={qw_in + 22} y2={qw_emb} />

        <BBox x={qw_bx} cx={QW_CX} w={qw_bw} y={qw_emb} h={28} label="Token Embedding + Vision Prefix" s1="152K × 4096" fill="#f3e5f5" stroke="#8e24aa" tf="#4a148c" />
        <VArr cx={QW_CX} y1={qw_emb + 28} y2={qw_blk + 14} />

        {/* ×36 Transformer Block */}
        <BlockOutline x={qw_bx} w={qw_bw} y={qw_blk} h={qw_blkH} label="× 36 Transformer Block" stroke="#8e24aa" />

        <BBox x={qw_bx + 10} cx={QW_CX} w={qw_bw - 20} y={qw_rn1}  h={24} label="RMSNorm" fill="#e8f5e9" stroke="#43a047" tf="#1b5e20" />
        <VArr cx={QW_CX} y1={qw_rn1 + 24} y2={qw_gqa} />

        <BBox x={qw_bx + 10} cx={QW_CX} w={qw_bw - 20} y={qw_gqa}  h={40} label="Grouped-Query Attention (GQA)" s1="32 Q heads · 8 KV heads" fill="#e8f0fe" stroke="#4285f4" tf="#1a237e" />
        <VArr cx={QW_CX} y1={qw_gqa + 40} y2={qw_r1cy - 9} />
        <Plus cx={QW_CX} cy={qw_r1cy} />
        <VArr cx={QW_CX} y1={qw_r1cy + 9} y2={qw_rn2} />

        <BBox x={qw_bx + 10} cx={QW_CX} w={qw_bw - 20} y={qw_rn2}  h={24} label="RMSNorm" fill="#e8f5e9" stroke="#43a047" tf="#1b5e20" />
        <VArr cx={QW_CX} y1={qw_rn2 + 24} y2={qw_mlp} />

        <BBox x={qw_bx + 10} cx={QW_CX} w={qw_bw - 20} y={qw_mlp}  h={40} label="SwiGLU Feed-Forward" s1="intermediate: 22016" fill="#f3e5f5" stroke="#8e24aa" tf="#4a148c" />
        <VArr cx={QW_CX} y1={qw_mlp + 40} y2={qw_r2cy - 9} />
        <Plus cx={QW_CX} cy={qw_r2cy} />

        <VArr cx={QW_CX} y1={qw_r2cy + 9} y2={qw_fnm} />
        <BBox x={qw_bx} cx={QW_CX} w={qw_bw} y={qw_fnm} h={24} label="RMSNorm" fill="#e8f5e9" stroke="#43a047" tf="#1b5e20" />
        <VArr cx={QW_CX} y1={qw_fnm + 24} y2={qw_lmh} />

        <BBox x={qw_bx} cx={QW_CX} w={qw_bw} y={qw_lmh} h={28} label="LM Head (Linear, no bias)" s1="4096 → 152K" fill="#fff8e1" stroke="#fb8c00" tf="#e65100" />
        <VArr cx={QW_CX} y1={qw_lmh + 28} y2={qw_out} />

        <BBox x={qw_bx} cx={QW_CX} w={qw_bw} y={qw_out} h={22} label="Logits [batch, seq, 152K]" fill="#f5f5f5" stroke="#bdbdbd" tf="#424242" />

        {/* ══ Cross-column connecting arrows ══════════════════════════ */}
        <HArr x1={CL_X + CL_W} y1={cl_out_cy} x2={PR_X} y2={pr_in_cy} />
        <HArr x1={PR_X + PR_W} y1={pr_out_cy} x2={QW_X} y2={qw_in + 11} />

      </svg>
    </div>
  );
}

// ── Multimodal tab content ─────────────────────────────────────────────────────

const PROJ_TYPES   = [
  { id: 'linear',  label: 'Linear' },
  { id: 'mlp2',    label: 'MLP-2' },
  { id: 'mlp3',    label: 'MLP-3' },
  { id: 'xattn',   label: 'Cross-Attention' },
  { id: 'qformer', label: 'Q-Former' },
];
const LORA_TARGETS = ['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'];
const MM_DATASETS  = [
  { id: 'llava-150k',  name: 'LLaVA-150K',      desc: '이미지-텍스트 지시 데이터',  size: '12.4 GB', fmt: 'JSON+JPEG', samples: 150000, dtype: 'multimodal' },
  { id: 'sharegpt4v',  name: 'ShareGPT4V-100K', desc: '고품질 이미지 캡셔닝',       size: '8.7 GB',  fmt: 'JSON+JPEG', samples: 100000, dtype: 'multimodal' },
  { id: 'alpaca-52k',  name: 'Alpaca-52K',       desc: '텍스트 지시 튜닝',           size: '120 MB',  fmt: 'JSON',     samples: 52000,  dtype: 'text' },
  { id: 'sharegpt-v4', name: 'ShareGPT v4',      desc: '다중 턴 대화 데이터',        size: '340 MB',  fmt: 'JSON',     samples: 90000,  dtype: 'text' },
];
const MM_INIT_CKPTS = [
  { id: 'mm-ck-1',  step:  500, epoch: 1, loss: 1.8203, grad: 1.1034, size: '18.3 GB', saved_at: '2025-03-10 09:10', is_best: false, mode: 'proj' },
  { id: 'mm-ck-2',  step: 1000, epoch: 1, loss: 1.4832, grad: 0.8411, size: '18.3 GB', saved_at: '2025-03-10 11:20', is_best: false, mode: 'proj' },
  { id: 'mm-ck-3',  step: 2000, epoch: 1, loss: 1.1204, grad: 0.6234, size: '18.3 GB', saved_at: '2025-03-10 14:05', is_best: false, mode: 'proj' },
  { id: 'mm-ck-4',  step: 3000, epoch: 2, loss: 0.9512, grad: 0.5801, size: '18.3 GB', saved_at: '2025-03-10 17:40', is_best: false, mode: 'proj' },
  { id: 'mm-ck-5',  step:  500, epoch: 1, loss: 1.2341, grad: 0.7023, size: '18.5 GB', saved_at: '2025-03-11 09:30', is_best: false, mode: 'llm'  },
  { id: 'mm-ck-6',  step: 1000, epoch: 1, loss: 0.9821, grad: 0.5102, size: '18.5 GB', saved_at: '2025-03-11 12:15', is_best: false, mode: 'llm'  },
  { id: 'mm-ck-7',  step: 1500, epoch: 2, loss: 0.8134, grad: 0.4430, size: '18.5 GB', saved_at: '2025-03-11 15:00', is_best: false, mode: 'llm'  },
  { id: 'mm-ck-8',  step: 2000, epoch: 2, loss: 0.7203, grad: 0.3912, size: '18.5 GB', saved_at: '2025-03-11 18:20', is_best: false, mode: 'llm'  },
  { id: 'mm-ck-9',  step: 2500, epoch: 3, loss: 0.6541, grad: 0.3401, size: '18.5 GB', saved_at: '2025-03-12 09:45', is_best: false, mode: 'llm'  },
  { id: 'mm-ck-10', step: 3000, epoch: 3, loss: 0.5987, grad: 0.2934, size: '18.5 GB', saved_at: '2025-03-12 13:00', is_best: true,  mode: 'llm'  },
];

function MultimodalTabContent({ tab }) {
  // ── 정보 tab state ──
  const [selGpu,  setSelGpu]  = useState('a100-2');
  const [selCpu,  setSelCpu]  = useState(16);
  const [selMem,  setSelMem]  = useState('64GB');

  // projector structure
  const [projType,   setProjType]   = useState('mlp2');
  const [mlpHidden,  setMlpHidden]  = useState(2048);
  const [xAttnHeads, setXAttnHeads] = useState(8);
  const [qTokens,    setQTokens]    = useState(32);

  // ── 학습 tab state ──
  const [trainProj, setTrainProj] = useState(true);
  const [trainLLM,  setTrainLLM]  = useState(true);
  const [dataMode,  setDataMode]  = useState('multimodal'); // 'multimodal' | 'text-only'
  const [selMmDs,   setSelMmDs]   = useState(new Set(['llava-150k', 'alpaca-52k']));
  const toggleMmDs = (id) => setSelMmDs((prev) => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });

  // projector hyperparams
  const [lr1, setLr1] = useState(0.001);
  const [ep1, setEp1] = useState(1);
  const [bs1, setBs1] = useState(16);
  const [wu1, setWu1] = useState(0.03);

  // LLM hyperparams
  const [lr2,      setLr2]      = useState(0.0002);
  const [ep2,      setEp2]      = useState(3);
  const [bs2,      setBs2]      = useState(4);
  const [wu2,      setWu2]      = useState(0.05);
  const [wd2,      setWd2]      = useState(0.01);
  const [loraR,    setLoraR]    = useState(16);
  const [loraA,    setLoraA]    = useState(32);
  const [loraD,    setLoraD]    = useState(0.05);
  const [loraTgts, setLoraTgts] = useState(new Set(['q_proj', 'v_proj']));

  // checkpoint config
  const [ckptEvery, setCkptEvery] = useState(500);
  const [maxCkpts,  setMaxCkpts]  = useState(5);

  // projector training simulation
  const [ts1, setTs1] = useState('idle');
  const [ti1, setTi1] = useState(0);
  const [ld1, setLd1] = useState([]);
  const ir1 = useRef(null);

  // LLM training simulation
  const [ts2, setTs2] = useState('idle');
  const [ti2, setTi2] = useState(0);
  const [ld2, setLd2] = useState([]);
  const [gd2, setGd2] = useState([]);
  const ir2 = useRef(null);

  // ── 관리 tab state ──
  const [mmCkpts, setMmCkpts] = useState(MM_INIT_CKPTS);

  useEffect(() => {
    if (ts1 === 'running') {
      ir1.current = setInterval(() => {
        setTi1((prev) => {
          const next = prev + 1;
          if (next >= PROJ_CURVES.loss.length) { clearInterval(ir1.current); setTs1('done'); return prev; }
          setLd1(PROJ_CURVES.loss.slice(0, next));
          return next;
        });
      }, 100);
    } else { clearInterval(ir1.current); }
    return () => clearInterval(ir1.current);
  }, [ts1]);

  useEffect(() => {
    if (ts2 === 'running') {
      ir2.current = setInterval(() => {
        setTi2((prev) => {
          const next = prev + 1;
          if (next >= ALL_CURVES.loss.length) { clearInterval(ir2.current); setTs2('done'); return prev; }
          setLd2(ALL_CURVES.loss.slice(0, next));
          setGd2(ALL_CURVES.grad.slice(0, next));
          return next;
        });
      }, 120);
    } else { clearInterval(ir2.current); }
    return () => clearInterval(ir2.current);
  }, [ts2]);

  const toggleLoraTgt  = (t) => setLoraTgts((prev) => { const s = new Set(prev); s.has(t) ? s.delete(t) : s.add(t); return s; });

  const handle1Toggle = () => {
    if (ts1 === 'idle' || ts1 === 'paused') { if (ts1 === 'idle') { setLd1([]); setTi1(0); } setTs1('running'); }
    else if (ts1 === 'running') setTs1('paused');
  };
  const reset1 = () => { clearInterval(ir1.current); setTs1('idle'); setTi1(0); setLd1([]); };

  const handle2Toggle = () => {
    if (ts2 === 'idle' || ts2 === 'paused') { if (ts2 === 'idle') { setLd2([]); setGd2([]); setTi2(0); } setTs2('running'); }
    else if (ts2 === 'running') setTs2('paused');
  };
  const reset2 = () => { clearInterval(ir2.current); setTs2('idle'); setTi2(0); setLd2([]); setGd2([]); };

  const prog1    = Math.round((ti1 / PROJ_CURVES.loss.length) * 100);
  const curLoss1 = ld1.length > 0 ? ld1[ld1.length - 1].val.toFixed(4) : '—';
  const curStep1 = ld1.length > 0 ? ld1[ld1.length - 1].step : 0;
  const prog2    = Math.round((ti2 / ALL_CURVES.loss.length) * 100);
  const curLoss2 = ld2.length > 0 ? ld2[ld2.length - 1].val.toFixed(4) : '—';
  const curStep2 = ld2.length > 0 ? ld2[ld2.length - 1].step : 0;
  const curGrad2 = gd2.length > 0 ? gd2[gd2.length - 1].val.toFixed(4) : '—';

  const combinedTs = trainProj && trainLLM
    ? (ts1 === 'running' || ts2 === 'running') ? 'running'
      : (ts1 === 'paused' || ts2 === 'paused') ? 'paused'
      : (ts1 === 'done' && ts2 === 'done') ? 'done' : 'idle'
    : trainProj ? ts1 : ts2;
  const combinedProg = trainProj && trainLLM ? Math.round((prog1 + prog2) / 2) : trainProj ? prog1 : prog2;
  const combinedBtnLabel = combinedTs === 'running' ? '⏸  일시 정지' : combinedTs === 'paused' ? '▶  재개' : combinedTs === 'done' ? '✓  완료' : '▶  학습 시작';
  const handleCombined = () => {
    if (combinedTs === 'idle' || combinedTs === 'paused') {
      if (trainProj && ts1 !== 'done') handle1Toggle();
      if (trainLLM  && ts2 !== 'done') handle2Toggle();
    } else {
      if (trainProj) handle1Toggle();
      if (trainLLM)  handle2Toggle();
    }
  };
  const resetAll = () => { if (trainProj) reset1(); if (trainLLM) reset2(); };

  // freeze banner layers — dynamic based on training selection
  const freezeLayers = [];
  if (dataMode === 'multimodal') {
    freezeLayers.push({ icon: '🔒', name: 'CLIP ViT-L/14', note: 'Vision Encoder (동결)', cls: 'frozen' });
  }
  freezeLayers.push(trainProj
    ? { icon: '⚙',  name: 'Projector', note: `${PROJ_TYPES.find((p) => p.id === projType)?.label} (학습)`, cls: 'trainable' }
    : { icon: '🔒', name: 'Projector', note: '동결', cls: 'frozen' }
  );
  freezeLayers.push(trainLLM
    ? { icon: '⚡', name: 'Qwen3-8B', note: 'LoRA 학습', cls: 'lora' }
    : { icon: '🔒', name: 'Qwen3-8B', note: 'Language Model (동결)', cls: 'frozen' }
  );

  const mmSetBest = (id) => setMmCkpts((prev) => prev.map((c) => ({ ...c, is_best: c.id === id })));
  const mmDelCkpt = (id) => setMmCkpts((prev) => prev.filter((c) => c.id !== id));

  // ── Tab 0: 정보 ──────────────────────────────────────────────────────────────
  if (tab === 0) return (
    <div className={cx('panel')}>

      {/* ── 정보 Tab 0: resources, projector structure ── */}

      {/* 학습 데이터셋 */}
      <section className={cx('section')}>
        <SectionLabel>학습 데이터셋 ({selMmDs.size}개 선택)</SectionLabel>
        <div className={cx('dataset-list')}>
          {MM_DATASETS.map((ds) => {
            const on = selMmDs.has(ds.id);
            return (
              <div key={ds.id} className={cx('dataset-item', on && 'dataset-item--on')} onClick={() => toggleMmDs(ds.id)}>
                <div className={cx('ds-check', on && 'ds-check--on')}>{on && '✓'}</div>
                <div className={cx('ds-body')}>
                  <div className={cx('ds-name-row')}>
                    <span className={cx('ds-name')}>{ds.name}</span>
                    <span className={cx('ds-dtype', ds.dtype === 'multimodal' ? 'ds-dtype--mm' : 'ds-dtype--text')}>
                      {ds.dtype === 'multimodal' ? '멀티모달' : '텍스트'}
                    </span>
                  </div>
                  <div className={cx('ds-desc')}>{ds.desc}</div>
                  <div className={cx('ds-meta')}>
                    <span>{ds.size}</span>
                    <span className={cx('dot')}>·</span>
                    <span>{ds.fmt}</span>
                    <span className={cx('dot')}>·</span>
                    <span>{ds.samples.toLocaleString()} 샘플</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 자원 할당 */}
      <section className={cx('section')}>
        <SectionLabel>자원 할당</SectionLabel>
        <div className={cx('res-block')}>
          <div className={cx('res-row')}>
            <span className={cx('res-label')}>GPU</span>
            <div className={cx('chip-row')}>
              {GPU_OPTS.map((g) => <Chip key={g.id} label={g.label} selected={selGpu === g.id} onClick={() => setSelGpu(g.id)} />)}
            </div>
          </div>
          <div className={cx('res-row')}>
            <span className={cx('res-label')}>CPU (코어)</span>
            <div className={cx('chip-row')}>
              {CPU_OPTS.map((c) => <Chip key={c} label={`${c}코어`} selected={selCpu === c} onClick={() => setSelCpu(c)} />)}
            </div>
          </div>
          <div className={cx('res-row')}>
            <span className={cx('res-label')}>메모리</span>
            <div className={cx('chip-row')}>
              {MEM_OPTS.map((m) => <Chip key={m} label={m} selected={selMem === m} onClick={() => setSelMem(m)} />)}
            </div>
          </div>
        </div>
      </section>

      {/* 모델 구조 (CLIP + Projector + Qwen) */}
      <section className={cx('section')}>
        <SectionLabel>모델 구조</SectionLabel>
        {/* Projector type selector — controls the middle column of the diagram */}
        <div className={cx('proj-type-block')}>
          <span className={cx('proj-type-title')}>프로젝터 구조 선택</span>
          <div className={cx('chip-row')}>
            {PROJ_TYPES.map((p) => <Chip key={p.id} label={p.label} selected={projType === p.id} onClick={() => setProjType(p.id)} />)}
          </div>
          <div className={cx('proj-cfg')}>
            {(projType === 'mlp2' || projType === 'mlp3') && (
              <div className={cx('proj-cfg-row')}>
                <span className={cx('proj-cfg-label')}>Hidden Dim</span>
                <div className={cx('chip-row')}>
                  {[1024, 2048, 4096].map((h) => <Chip key={h} label={String(h)} selected={mlpHidden === h} onClick={() => setMlpHidden(h)} />)}
                </div>
              </div>
            )}
            {projType === 'xattn' && (
              <div className={cx('proj-cfg-row')}>
                <span className={cx('proj-cfg-label')}>Attn Heads</span>
                <div className={cx('chip-row')}>
                  {[4, 8, 16].map((h) => <Chip key={h} label={`${h} heads`} selected={xAttnHeads === h} onClick={() => setXAttnHeads(h)} />)}
                </div>
              </div>
            )}
            {projType === 'qformer' && (
              <div className={cx('proj-cfg-row')}>
                <span className={cx('proj-cfg-label')}>Query Tokens</span>
                <div className={cx('chip-row')}>
                  {[16, 32, 64].map((q) => <Chip key={q} label={`${q} tokens`} selected={qTokens === q} onClick={() => setQTokens(q)} />)}
                </div>
              </div>
            )}
          </div>
        </div>
        <MultimodalArchDiagram projType={projType} mlpHidden={mlpHidden} xAttnHeads={xAttnHeads} qTokens={qTokens} />
      </section>
    </div>
  );

  // ── Tab 1: 학습 ──────────────────────────────────────────────────────────────
  if (tab === 1) return (
    <div className={cx('panel')}>

      {/* 학습 컴포넌트 선택 */}
      <section className={cx('section')}>
        <SectionLabel>학습 컴포넌트</SectionLabel>
        <div className={cx('train-mode-block')}>
          <div className={cx('train-mode-row')}>
            <span className={cx('train-mode-label')}>학습 대상</span>
            <div className={cx('chip-row')}>
              <Chip label="프로젝터" selected={trainProj} onClick={() => setTrainProj((v) => !v)} />
              <Chip label="LLM (LoRA)" selected={trainLLM} onClick={() => setTrainLLM((v) => !v)} />
            </div>
          </div>
          <div className={cx('train-mode-row')}>
            <span className={cx('train-mode-label')}>데이터 형식</span>
            <div className={cx('chip-row')}>
              <Chip label="멀티모달" selected={dataMode === 'multimodal'} onClick={() => setDataMode('multimodal')} />
              <Chip label="텍스트 전용" selected={dataMode === 'text-only'} onClick={() => setDataMode('text-only')} />
            </div>
          </div>
        </div>
        {!trainProj && !trainLLM && (
          <div className={cx('train-warn')}>학습 대상을 하나 이상 선택해야 합니다.</div>
        )}
      </section>

      {/* 레이어 동결 상태 */}
      {(trainProj || trainLLM) && (
        <div className={cx('freeze-banner')}>
          {freezeLayers.map(({ icon, name, note, cls }) => (
            <div key={name} className={cx('freeze-item', `freeze-item--${cls}`)}>
              <span className={cx('freeze-icon')}>{icon}</span>
              <div>
                <div className={cx('freeze-name')}>{name}</div>
                <div className={cx('freeze-note')}>{note}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Projector hyperparams */}
      {trainProj && (
        <section className={cx('section')}>
          <SectionLabel>하이퍼파라미터 — 프로젝터</SectionLabel>
          <div className={cx('params-grid')}>
            {[
              { label: 'Learning Rate', val: lr1.toExponential(1), min: 0.0001, max: 0.01, step: 0.0001, set: setLr1, curr: lr1 },
              { label: '에포크 수',      val: ep1,                   min: 1,     max: 5,    step: 1,      set: setEp1, curr: ep1 },
              { label: '배치 크기',       val: bs1,                   min: 4,     max: 64,   step: 4,      set: setBs1, curr: bs1 },
              { label: 'Warmup Ratio',  val: wu1.toFixed(2),        min: 0,     max: 0.1,  step: 0.01,   set: setWu1, curr: wu1 },
            ].map(({ label, val, min, max, step, set, curr }) => (
              <div key={label} className={cx('param-item')}>
                <div className={cx('param-header')}>
                  <span className={cx('param-name')}>{label}</span>
                  <span className={cx('param-val')}>{val}</span>
                </div>
                <input type="range" className={cx('slider')} min={min} max={max} step={step} value={curr} onChange={(e) => set(Number(e.target.value))} />
              </div>
            ))}
          </div>
        </section>
      )}

      {/* LoRA config + LLM hyperparams */}
      {trainLLM && (<>
        <section className={cx('section')}>
          <SectionLabel>LoRA 설정</SectionLabel>
          <div className={cx('lora-block')}>
            <div className={cx('params-grid')}>
              {[
                { label: 'LoRA Rank (r)', val: loraR,            min: 4,  max: 128, step: 4,    set: setLoraR, curr: loraR },
                { label: 'LoRA Alpha',    val: loraA,            min: 8,  max: 256, step: 8,    set: setLoraA, curr: loraA },
                { label: 'LoRA Dropout',  val: loraD.toFixed(2), min: 0,  max: 0.3, step: 0.01, set: setLoraD, curr: loraD },
              ].map(({ label, val, min, max, step, set, curr }) => (
                <div key={label} className={cx('param-item')}>
                  <div className={cx('param-header')}>
                    <span className={cx('param-name')}>{label}</span>
                    <span className={cx('param-val')}>{val}</span>
                  </div>
                  <input type="range" className={cx('slider')} min={min} max={max} step={step} value={curr} onChange={(e) => set(Number(e.target.value))} />
                </div>
              ))}
            </div>
            <div className={cx('lora-targets-row')}>
              <span className={cx('lora-targets-label')}>Target Modules</span>
              <div className={cx('chip-row')}>
                {LORA_TARGETS.map((t) => <Chip key={t} label={t} selected={loraTgts.has(t)} onClick={() => toggleLoraTgt(t)} />)}
              </div>
            </div>
          </div>
        </section>

        <section className={cx('section')}>
          <SectionLabel>하이퍼파라미터 — LLM</SectionLabel>
          <div className={cx('params-grid')}>
            {[
              { label: 'Learning Rate', val: lr2.toExponential(1), min: 0.00001, max: 0.001, step: 0.00001, set: setLr2, curr: lr2 },
              { label: '에포크 수',      val: ep2,                   min: 1,      max: 10,   step: 1,       set: setEp2, curr: ep2 },
              { label: '배치 크기',       val: bs2,                   min: 1,      max: 32,   step: 1,       set: setBs2, curr: bs2 },
              { label: 'Warmup Ratio',  val: wu2.toFixed(2),        min: 0,      max: 0.2,  step: 0.01,    set: setWu2, curr: wu2 },
              { label: 'Weight Decay',  val: wd2.toFixed(3),        min: 0,      max: 0.1,  step: 0.001,   set: setWd2, curr: wd2 },
            ].map(({ label, val, min, max, step, set, curr }) => (
              <div key={label} className={cx('param-item')}>
                <div className={cx('param-header')}>
                  <span className={cx('param-name')}>{label}</span>
                  <span className={cx('param-val')}>{val}</span>
                </div>
                <input type="range" className={cx('slider')} min={min} max={max} step={step} value={curr} onChange={(e) => set(Number(e.target.value))} />
              </div>
            ))}
          </div>
        </section>
      </>)}

      {/* Checkpoint config */}
      {(trainProj || trainLLM) && (
        <section className={cx('section')}>
          <SectionLabel>체크포인트 설정</SectionLabel>
          <div className={cx('ckpt-config')}>
            <div className={cx('ckpt-cfg-row')}>
              <label className={cx('ckpt-cfg-label')}>저장 간격 (스텝)</label>
              <input type="number" className={cx('ckpt-cfg-input')} value={ckptEvery} min={50} max={2000} step={50} onChange={(e) => setCkptEvery(Number(e.target.value))} />
              <span className={cx('ckpt-cfg-hint')}>스텝마다 체크포인트 저장</span>
            </div>
            <div className={cx('ckpt-cfg-row')}>
              <label className={cx('ckpt-cfg-label')}>최대 보관 개수</label>
              <input type="number" className={cx('ckpt-cfg-input')} value={maxCkpts} min={1} max={20} onChange={(e) => setMaxCkpts(Number(e.target.value))} />
              <span className={cx('ckpt-cfg-hint')}>초과 시 가장 오래된 체크포인트 자동 삭제</span>
            </div>
          </div>
        </section>
      )}

      {/* 통합 학습 제어 */}
      {(trainProj || trainLLM) && (
        <section className={cx('section')}>
          <SectionLabel>학습 제어</SectionLabel>
          <div className={cx('train-control')}>
            <div className={cx('train-stats')}>
              {trainProj && <div className={cx('stat-card')}><span className={cx('stat-label')}>프로젝터 Loss</span><span className={cx('stat-val')}>{curLoss1}</span></div>}
              {trainLLM  && <div className={cx('stat-card')}><span className={cx('stat-label')}>LLM Loss</span><span className={cx('stat-val')}>{curLoss2}</span></div>}
              {trainLLM  && <div className={cx('stat-card')}><span className={cx('stat-label')}>Grad Norm</span><span className={cx('stat-val')}>{curGrad2}</span></div>}
              <div className={cx('stat-card')}><span className={cx('stat-label')}>진행률</span><span className={cx('stat-val')}>{combinedProg}%</span></div>
            </div>
            <div className={cx('prog-track')}><div className={cx('prog-fill')} style={{ width: `${combinedProg}%` }} /></div>
            <div className={cx('train-btn-row')}>
              <button className={cx('train-btn', combinedTs === 'running' && 'train-btn--pause', combinedTs === 'done' && 'train-btn--done', (combinedTs === 'idle' || combinedTs === 'paused') && 'train-btn--start')} disabled={combinedTs === 'done'} onClick={handleCombined}>{combinedBtnLabel}</button>
              {combinedTs !== 'idle' && <button className={cx('reset-btn')} onClick={resetAll}>초기화</button>}
            </div>
          </div>
        </section>
      )}

      {/* 통합 학습 추이 */}
      {(trainProj || trainLLM) && (
        <section className={cx('section')}>
          <SectionLabel>학습 추이</SectionLabel>
          <div className={cx('charts-grid')}>
            {trainProj && (
              <div className={cx('chart-card')}>
                <div className={cx('chart-title')}>Projector Training Loss</div>
                <LineChart data={ld1} colorStroke="#fb8c00" labelY="Loss" />
              </div>
            )}
            {trainLLM && (
              <div className={cx('chart-card')}>
                <div className={cx('chart-title')}>LLM Training Loss</div>
                <LineChart data={ld2} colorStroke="#2d76f8" labelY="Loss" />
              </div>
            )}
            {trainLLM && (
              <div className={cx('chart-card')}>
                <div className={cx('chart-title')}>Gradient Norm</div>
                <LineChart data={gd2} colorStroke="#00c775" labelY="Grad Norm" />
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );

  // ── Tab 2: 관리 ──────────────────────────────────────────────────────────────
  return (
    <div className={cx('panel')}>
      <section className={cx('section')}>
        <SectionLabel>저장된 체크포인트 ({mmCkpts.length}개)</SectionLabel>
        {mmCkpts.length === 0 ? (
          <div className={cx('empty')}>저장된 체크포인트가 없습니다.</div>
        ) : (
          <div className={cx('ckpt-list')}>
            {mmCkpts.map((c) => (
              <div key={c.id} className={cx('ckpt-item', c.is_best && 'ckpt-item--best')}>
                <div className={cx('ckpt-top')}>
                  <div className={cx('ckpt-left')}>
                    <span className={cx('ckpt-step')}>Step {c.step.toLocaleString()}</span>
                    <span className={cx('ckpt-epoch')}>Epoch {c.epoch}</span>
                    {c.mode && <span className={cx('ckpt-mode')}>{c.mode === 'proj' ? '프로젝터' : 'LLM'}</span>}
                    {c.is_best && <span className={cx('best-badge')}>★ BEST</span>}
                  </div>
                  <div className={cx('ckpt-actions')}>
                    {!c.is_best && <button className={cx('best-btn')} onClick={() => mmSetBest(c.id)}>Best 지정</button>}
                    <button className={cx('del-btn')} onClick={() => mmDelCkpt(c.id)}>삭제</button>
                  </div>
                </div>
                <div className={cx('ckpt-metrics')}>
                  <span>Loss <b>{c.loss.toFixed(4)}</b></span>
                  <span>Grad Norm <b>{c.grad.toFixed(4)}</b></span>
                  <span>크기 <b>{c.size}</b></span>
                  <span>저장 시각 <b>{c.saved_at}</b></span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
      <section className={cx('section')}>
        <SectionLabel>스토리지 사용량</SectionLabel>
        <div className={cx('storage-box')}>
          <div className={cx('storage-row')}>
            <span className={cx('storage-label')}>체크포인트 사용량</span>
            <span className={cx('storage-val')}>{(mmCkpts.length * 18.3).toFixed(1)} GB</span>
          </div>
          <div className={cx('storage-track')}>
            <div className={cx('storage-fill')} style={{ width: `${Math.min(100, mmCkpts.length * 9.15)}%` }} />
          </div>
          <div className={cx('storage-total')}>총 할당: 200 GB</div>
        </div>
      </section>
    </div>
  );
}

// Pure-frontend model architecture graph — reads config.json via Vite middleware
function ModelGraphViewer({ modelId }) {
  const [status, setStatus] = useState('loading'); // loading|ready|error
  const [config, setConfig] = useState(null);
  const [errMsg, setErrMsg] = useState('');

  useEffect(() => {
    setStatus('loading');
    fetch(`/api/model-config?model_id=${encodeURIComponent(modelId)}`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((cfg) => { setConfig(cfg); setStatus('ready'); })
      .catch((e) => { setErrMsg(e.message); setStatus('error'); });
  }, [modelId]);

  if (status === 'loading') {
    return (
      <div className={cx('mg-loading')}>
        <span className={cx('mg-spinner')} />
        config.json 파싱 중...
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className={cx('mg-error')}>
        <div className={cx('mg-error-icon')}>⊘</div>
        <div className={cx('mg-error-title')}>config.json 로드 실패</div>
        <div className={cx('mg-error-desc')}>{errMsg}</div>
      </div>
    );
  }

  return <ArchDiagram config={config} />;
}

function ArchDiagram({ config }) {
  const nl    = config.num_hidden_layers        ?? 32;
  const hs    = config.hidden_size              ?? 4096;
  const vs    = config.vocab_size               ?? 128256;
  const iSize = config.intermediate_size        ?? 14336;
  const nh    = config.num_attention_heads      ?? 32;
  const nkv   = config.num_key_value_heads      ?? 8;
  const hd    = Math.floor(hs / nh);
  const arch  = (config.architectures           ?? ['LlamaForCausalLM'])[0];
  const dtype = config.torch_dtype              ?? 'bfloat16';
  const ctx   = config.max_position_embeddings  ?? 131072;
  const act   = config.hidden_act               ?? 'silu';
  const rmsEps = config.rms_norm_eps            ?? 1e-5;
  const ropeType = config.rope_scaling?.rope_type ?? config.rope_type ?? 'llama3';

  const fmt = (n) =>
    n >= 1e9 ? (n / 1e9).toFixed(1) + 'B'
    : n >= 1e6 ? (n / 1e6).toFixed(1) + 'M'
    : n >= 1e3 ? (n / 1e3).toFixed(0) + 'K'
    : String(n);
  const rmsStr = rmsEps < 1e-4 ? rmsEps.toExponential(1) : String(rmsEps);

  // Layout constants
  const SW = 760, IX = 480, IW = 260;
  const BX = 60,  BW = 340, CX = 230;
  const BLX = 40;

  // Y positions
  const Y_IN   = 20;
  const Y_EMB  = Y_IN  + 36 + 18;                    // 74
  const Y_BLK  = Y_EMB + 36 + 18;                    // 128
  const Y_ILN  = Y_BLK + 26;                         // 154
  const Y_GQA  = Y_ILN + 32 + 14;                    // 200
  const R1Y    = Y_GQA + 48 + 14;                    // 262
  const Y_PLN  = R1Y   + 11 + 12;                    // 285
  const Y_MLP  = Y_PLN + 32 + 14;                    // 331
  const R2Y    = Y_MLP + 48 + 14;                    // 393
  const Y_BEND = R2Y   + 11 + 16;                    // 420
  const Y_FLN  = Y_BEND + 22;                        // 442
  const Y_LMH  = Y_FLN + 32 + 14;                    // 488
  const Y_OUT  = Y_LMH + 36 + 14;                    // 538
  const SH     = Y_OUT + 32 + 22;                    // 592

  // ── Inner helpers (close over BX, BW, CX) ──
  const Box = ({ y, h = 32, label, s1, s2, fill, stroke, tf = '#333' }) => {
    const lines = 1 + (s1 ? 1 : 0) + (s2 ? 1 : 0);
    const lh    = 13;
    const top   = Math.floor((h - lines * lh) / 2) + 11;
    return (
      <g>
        <rect x={BX} y={y} width={BW} height={h} rx="6" fill={fill} stroke={stroke} strokeWidth="1.5" />
        <text x={CX} y={y + top} textAnchor="middle" fontSize="11" fontFamily="SpoqaB" fill={tf}>{label}</text>
        {s1 && <text x={CX} y={y + top + lh} textAnchor="middle" fontSize="9" fontFamily="SpoqaM" fill={tf} opacity="0.8">{s1}</text>}
        {s2 && <text x={CX} y={y + top + lh * 2} textAnchor="middle" fontSize="9" fontFamily="SpoqaM" fill={tf} opacity="0.7">{s2}</text>}
      </g>
    );
  };

  const Arr = ({ y1, y2 }) => (
    <g>
      <line x1={CX} y1={y1} x2={CX} y2={y2 - 8} stroke="#c0c0c0" strokeWidth="1.5" />
      <polygon points={`${CX - 4},${y2 - 11} ${CX + 4},${y2 - 11} ${CX},${y2 - 3}`} fill="#c0c0c0" />
    </g>
  );

  const Plus = ({ cy }) => (
    <g>
      <circle cx={CX} cy={cy} r={11} fill="#ffffff" stroke="#c0c0c0" strokeWidth="1.5" />
      <line x1={CX - 5} y1={cy} x2={CX + 5} y2={cy} stroke="#888" strokeWidth="1.5" />
      <line x1={CX} y1={cy - 5} x2={CX} y2={cy + 5} stroke="#888" strokeWidth="1.5" />
    </g>
  );

  const specs = [
    { l: 'Architecture', v: arch },
    { l: 'Layers',       v: nl },
    { l: 'Hidden Size',  v: fmt(hs) },
    { l: 'Attn Heads',   v: nh },
    { l: 'KV Heads',     v: nkv },
    { l: 'Head Dim',     v: hd },
    { l: 'Intermediate', v: fmt(iSize) },
    { l: 'Vocab Size',   v: fmt(vs) },
    { l: 'Max Context',  v: fmt(ctx) },
    { l: 'Activation',   v: act },
    { l: 'RoPE Type',    v: ropeType },
    { l: 'Data Type',    v: dtype },
    { l: 'RMS Norm ε',   v: rmsStr },
  ];

  const LEGEND = [
    { fill: '#e8f0fe', stroke: '#4285f4', label: 'Attention' },
    { fill: '#e8f5e9', stroke: '#43a047', label: 'Normalization' },
    { fill: '#f3e5f5', stroke: '#8e24aa', label: 'Feed-Forward' },
    { fill: '#fff8e1', stroke: '#fb8c00', label: 'Output' },
  ];

  return (
    <div className={cx('mg-wrapper')}>
      <svg viewBox={`0 0 ${SW} ${SH}`} className={cx('mg-svg')} xmlns="http://www.w3.org/2000/svg">

        {/* ── Config panel (right) ─────────────────────────────────── */}
        <rect x={IX} y={6} width={IW} height={SH - 12} rx="10" fill="#f8f9ff" stroke="#d8ddf0" strokeWidth="1" />
        <text x={IX + IW / 2} y={26} textAnchor="middle" fontSize="12" fontFamily="SpoqaB" fill="#1a237e">모델 구성</text>
        <line x1={IX + 12} y1={34} x2={IX + IW - 12} y2={34} stroke="#d8ddf0" strokeWidth="1" />
        {specs.map(({ l, v }, i) => {
          const ry = 42 + i * 30;
          return (
            <g key={l}>
              {i % 2 === 0 && <rect x={IX + 8} y={ry} width={IW - 16} height={26} rx="4" fill="rgba(66,133,244,0.05)" />}
              <text x={IX + 16} y={ry + 17} fontSize="10" fontFamily="SpoqaM" fill="#888">{l}</text>
              <text x={IX + IW - 14} y={ry + 17} textAnchor="end" fontSize="11" fontFamily="SpoqaB" fill="#1a237e">{String(v)}</text>
            </g>
          );
        })}
        <line x1={IX + 12} y1={42 + 13 * 30 + 4} x2={IX + IW - 12} y2={42 + 13 * 30 + 4} stroke="#d8ddf0" strokeWidth="1" />
        <text x={IX + 16} y={42 + 13 * 30 + 20} fontSize="10" fontFamily="SpoqaM" fill="#888">색상 범례</text>
        {LEGEND.map(({ fill, stroke, label }, i) => {
          const ly = 42 + 13 * 30 + 30 + i * 22;
          return (
            <g key={label}>
              <rect x={IX + 16} y={ly} width={12} height={12} rx="2" fill={fill} stroke={stroke} strokeWidth="1" />
              <text x={IX + 34} y={ly + 10} fontSize="10" fontFamily="SpoqaM" fill="#555">{label}</text>
            </g>
          );
        })}

        {/* ── Architecture diagram (left) ──────────────────────────── */}

        {/* Input IDs */}
        <Box y={Y_IN} h={36} label="Input IDs" s1="[batch, seq_len]" fill="#f5f5f5" stroke="#bdbdbd" tf="#424242" />

        <Arr y1={Y_IN + 36} y2={Y_EMB} />

        {/* Token Embedding */}
        <Box y={Y_EMB} h={36} label="Token Embedding" s1={`${fmt(vs)} × ${fmt(hs)}`} fill="#e8f0fe" stroke="#4285f4" tf="#1a237e" />

        <Arr y1={Y_EMB + 36} y2={Y_BLK + 4} />

        {/* Transformer block outline */}
        <rect x={BLX} y={Y_BLK} width={BW + (BX - BLX) * 2} height={Y_BEND - Y_BLK}
              rx="10" fill="none" stroke="#4285f4" strokeWidth="1.5" strokeDasharray="7 3" />
        <rect x={CX - 64} y={Y_BLK - 10} width={128} height={20} rx="5" fill="#fff" stroke="#4285f4" strokeWidth="1" />
        <text x={CX} y={Y_BLK + 5} textAnchor="middle" fontSize="11" fontFamily="SpoqaB" fill="#4285f4">
          × {nl} Transformer Layers
        </text>

        {/* Input RMSNorm */}
        <Box y={Y_ILN} h={32} label="RMSNorm  (Input LayerNorm)" s1={`ε = ${rmsStr}`} fill="#e8f5e9" stroke="#43a047" tf="#1b5e20" />

        <Arr y1={Y_ILN + 32} y2={Y_GQA} />

        {/* Grouped-Query Attention */}
        <Box y={Y_GQA} h={48}
          label="Grouped-Query Attention"
          s1={`${nh} Q-heads · ${nkv} KV-heads · head_dim=${hd}`}
          s2={`Q:${fmt(hs)}  K:${fmt(nkv * hd)}  V:${fmt(nkv * hd)}  +RoPE (${ropeType})`}
          fill="#e8f0fe" stroke="#4285f4" tf="#1a237e"
        />

        {/* line GQA → Residual 1 */}
        <line x1={CX} y1={Y_GQA + 48} x2={CX} y2={R1Y - 11} stroke="#c0c0c0" strokeWidth="1.5" />
        {/* Residual skip 1 */}
        <path d={`M ${BX} ${Y_ILN + 16} L ${BLX + 8} ${Y_ILN + 16} L ${BLX + 8} ${R1Y} L ${CX - 11} ${R1Y}`}
              fill="none" stroke="#c0c0c0" strokeWidth="1" strokeDasharray="4 3" />
        <Plus cy={R1Y} />

        {/* line Residual 1 → Post-Attn LN */}
        <line x1={CX} y1={R1Y + 11} x2={CX} y2={Y_PLN} stroke="#c0c0c0" strokeWidth="1.5" />

        {/* Post-Attention RMSNorm */}
        <Box y={Y_PLN} h={32} label="RMSNorm  (Post-Attn LayerNorm)" s1={`ε = ${rmsStr}`} fill="#e8f5e9" stroke="#43a047" tf="#1b5e20" />

        <Arr y1={Y_PLN + 32} y2={Y_MLP} />

        {/* SwiGLU MLP */}
        <Box y={Y_MLP} h={48}
          label="SwiGLU MLP"
          s1={`Gate × SiLU(Up) → Down`}
          s2={`${fmt(hs)} → ${fmt(iSize)} → ${fmt(hs)}`}
          fill="#f3e5f5" stroke="#8e24aa" tf="#4a148c"
        />

        {/* line MLP → Residual 2 */}
        <line x1={CX} y1={Y_MLP + 48} x2={CX} y2={R2Y - 11} stroke="#c0c0c0" strokeWidth="1.5" />
        {/* Residual skip 2 */}
        <path d={`M ${BX} ${Y_PLN + 16} L ${BLX + 8} ${Y_PLN + 16} L ${BLX + 8} ${R2Y} L ${CX - 11} ${R2Y}`}
              fill="none" stroke="#c0c0c0" strokeWidth="1" strokeDasharray="4 3" />
        <Plus cy={R2Y} />

        {/* line Residual 2 → block bottom */}
        <line x1={CX} y1={R2Y + 11} x2={CX} y2={Y_BEND - 4} stroke="#c0c0c0" strokeWidth="1.5" />

        <Arr y1={Y_BEND} y2={Y_FLN} />

        {/* Final RMSNorm */}
        <Box y={Y_FLN} h={32} label="Final RMSNorm" s1={`ε = ${rmsStr}`} fill="#e8f5e9" stroke="#43a047" tf="#1b5e20" />

        <Arr y1={Y_FLN + 32} y2={Y_LMH} />

        {/* LM Head */}
        <Box y={Y_LMH} h={36} label="LM Head  (Linear, no bias)" s1={`${fmt(hs)} → ${fmt(vs)}`} fill="#fff8e1" stroke="#fb8c00" tf="#e65100" />

        <Arr y1={Y_LMH + 36} y2={Y_OUT} />

        {/* Logits */}
        <Box y={Y_OUT} h={32} label="Logits" s1={`[batch, seq_len, ${fmt(vs)}]`} fill="#f5f5f5" stroke="#bdbdbd" tf="#424242" />

      </svg>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────────

const ModelDetailPage = memo(function ModelDetailPage({ trackingEvent, ...rest }) {
  const history  = useHistory();
  const { id: workspaceId, mId: modelId } = useParams();

  const [tab, setTab]     = useState(0);
  const [model, setModel] = useState(null);

  // ── 정보 tab state ──
  const [selDatasets, setSelDatasets] = useState(new Set(['ds-1']));
  const [selGpu, setSelGpu]           = useState('a100-1');
  const [selCpu, setSelCpu]           = useState(8);
  const [selMem, setSelMem]           = useState('32GB');

  // ── 학습 tab state ──
  const [lr,       setLr]       = useState(0.0002);
  const [epochs,   setEpochs]   = useState(3);
  const [batchSz,  setBatchSz]  = useState(4);
  const [loraR,    setLoraR]    = useState(16);
  const [loraAlpha,setLoraAlpha]= useState(32);
  const [warmup,   setWarmup]   = useState(0.05);
  const [wdecay,   setWdecay]   = useState(0.01);
  const [maxSeq,   setMaxSeq]   = useState(2048);
  const [ckptEvery,setCkptEvery]= useState(500);
  const [maxCkpts, setMaxCkpts] = useState(5);

  const [trainStatus, setTrainStatus] = useState('idle'); // idle | running | paused | done
  const [trainIdx,    setTrainIdx]    = useState(0);
  const [lossData,    setLossData]    = useState([]);
  const [gradData,    setGradData]    = useState([]);
  const intervalRef = useRef(null);

  // ── 관리 tab state ──
  const [checkpoints, setCheckpoints] = useState(INIT_CKPTS);

  useEffect(() => {
    callApi({ url: `models/fine-tuning/summary?model_id=${modelId}`, method: 'GET' }).then((res) => {
      if (res?.status === STATUS_SUCCESS) setModel(res.result);
    });
  }, [modelId]);

  // Training simulation
  useEffect(() => {
    if (trainStatus === 'running') {
      intervalRef.current = setInterval(() => {
        setTrainIdx((prev) => {
          const next = prev + 1;
          if (next >= ALL_CURVES.loss.length) {
            clearInterval(intervalRef.current);
            setTrainStatus('done');
            return prev;
          }
          setLossData(ALL_CURVES.loss.slice(0, next));
          setGradData(ALL_CURVES.grad.slice(0, next));
          return next;
        });
      }, 120);
    } else {
      clearInterval(intervalRef.current);
    }
    return () => clearInterval(intervalRef.current);
  }, [trainStatus]);



  const toggleDataset = (id) =>
    setSelDatasets((prev) => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });

  const handleTrainToggle = () => {
    if (trainStatus === 'idle' || trainStatus === 'paused') {
      if (trainStatus === 'idle') { setLossData([]); setGradData([]); setTrainIdx(0); }
      setTrainStatus('running');
    } else if (trainStatus === 'running') {
      setTrainStatus('paused');
    }
  };

  const handleReset = () => {
    clearInterval(intervalRef.current);
    setTrainStatus('idle');
    setTrainIdx(0);
    setLossData([]);
    setGradData([]);
  };

  const setBest  = (id) => setCheckpoints((prev) => prev.map((c) => ({ ...c, is_best: c.id === id })));
  const delCkpt  = (id) => setCheckpoints((prev) => prev.filter((c) => c.id !== id));

  const progress    = Math.round((trainIdx / ALL_CURVES.loss.length) * 100);
  const currentLoss = lossData.length > 0 ? lossData[lossData.length - 1].val.toFixed(4) : '—';
  const currentStep = lossData.length > 0 ? lossData[lossData.length - 1].step : 0;
  const currentGrad = gradData.length > 0 ? gradData[gradData.length - 1].val.toFixed(4) : '—';

  const trainBtnLabel =
    trainStatus === 'running' ? '⏸  일시 정지'
    : trainStatus === 'paused' ? '▶  재개'
    : trainStatus === 'done'   ? '✓  완료'
    : '▶  학습 시작';

  return (
    <div className={cx('page')}>

      {/* Back button */}
      <button className={cx('back-btn')} onClick={() => history.push(`/user/workspace/${workspaceId}/model`)}>
        ← 모델 목록
      </button>

      {/* Model header */}
      <div className={cx('model-header')}>
        <div className={cx('model-title-row')}>
          <h1 className={cx('model-title')}>{model?.name ?? '모델'}</h1>
          {model?.load_type === 'multimodal' ? (
            <span className={cx('model-status')}>● 준비</span>
          ) : (
            <span className={cx('model-status', trainStatus === 'running' && 'running', trainStatus === 'done' && 'done')}>
              {trainStatus === 'running' ? '● 학습 중' : trainStatus === 'done' ? '● 학습 완료' : '● 준비'}
            </span>
          )}
        </div>
        <div className={cx('model-badges')}>
          <span className={cx('badge', 'badge--hf')}>HuggingFace</span>
          {model?.load_type === 'multimodal' ? (
            <>
              <span className={cx('badge', 'badge--multi')}>Multimodal</span>
              <span className={cx('badge', 'badge--model')}>CLIP ViT-L/14</span>
              <span className={cx('badge', 'badge--model')}>Qwen3-8B</span>
              <span className={cx('badge', 'badge--size')}>8.4B params</span>
            </>
          ) : (
            <>
              <span className={cx('badge', 'badge--single')}>Single</span>
              <span className={cx('badge', 'badge--model')}>Llama 3.1 8B Instruct</span>
              <span className={cx('badge', 'badge--size')}>8.03B params</span>
            </>
          )}
        </div>
        <p className={cx('model-desc')}>{model?.description ?? ''}</p>
      </div>

      {/* Tab bar — all model types */}
      <div className={cx('tabs')}>
        {TABS.map((t, i) => (
          <button key={t} className={cx('tab', tab === i && 'tab--active')} onClick={() => setTab(i)}>
            {t}
          </button>
        ))}
      </div>

      {model?.load_type === 'multimodal' ? (
        <MultimodalTabContent tab={tab} />
      ) : (<>

      {/* ══════════════ Tab 0: 정보 ══════════════ */}
      {tab === 0 && (
        <div className={cx('panel')}>

          {/* 학습 데이터셋 */}
          <section className={cx('section')}>
            <SectionLabel>학습 데이터셋 ({selDatasets.size}개 선택)</SectionLabel>
            <div className={cx('dataset-list')}>
              {MOCK_DATASETS.map((ds) => {
                const on = selDatasets.has(ds.id);
                return (
                  <div key={ds.id} className={cx('dataset-item', on && 'dataset-item--on')} onClick={() => toggleDataset(ds.id)}>
                    <div className={cx('ds-check', on && 'ds-check--on')}>{on && '✓'}</div>
                    <div className={cx('ds-body')}>
                      <div className={cx('ds-name')}>{ds.name}</div>
                      <div className={cx('ds-desc')}>{ds.desc}</div>
                      <div className={cx('ds-meta')}>
                        <span>{ds.size}</span>
                        <span className={cx('dot')}>·</span>
                        <span>{ds.fmt}</span>
                        <span className={cx('dot')}>·</span>
                        <span>{ds.samples.toLocaleString()} 샘플</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* 자원 할당 */}
          <section className={cx('section')}>
            <SectionLabel>자원 할당</SectionLabel>
            <div className={cx('res-block')}>
              <div className={cx('res-row')}>
                <span className={cx('res-label')}>GPU</span>
                <div className={cx('chip-row')}>
                  {GPU_OPTS.map((g) => <Chip key={g.id} label={g.label} selected={selGpu === g.id} onClick={() => setSelGpu(g.id)} />)}
                </div>
              </div>
              <div className={cx('res-row')}>
                <span className={cx('res-label')}>CPU (코어)</span>
                <div className={cx('chip-row')}>
                  {CPU_OPTS.map((c) => <Chip key={c} label={`${c}코어`} selected={selCpu === c} onClick={() => setSelCpu(c)} />)}
                </div>
              </div>
              <div className={cx('res-row')}>
                <span className={cx('res-label')}>메모리</span>
                <div className={cx('chip-row')}>
                  {MEM_OPTS.map((m) => <Chip key={m} label={m} selected={selMem === m} onClick={() => setSelMem(m)} />)}
                </div>
              </div>
            </div>
          </section>

          {/* 모델 구조 */}
          <section className={cx('section')}>
            <SectionLabel>모델 구조</SectionLabel>
            <ModelGraphViewer modelId={modelId} />
          </section>
        </div>
      )}

      {/* ══════════════ Tab 1: 학습 ══════════════ */}
      {tab === 1 && (
        <div className={cx('panel')}>

          {/* 하이퍼파라미터 */}
          <section className={cx('section')}>
            <SectionLabel>하이퍼파라미터</SectionLabel>
            <div className={cx('params-grid')}>
              {[
                { label: 'Learning Rate',  val: lr.toExponential(1),    min: 0.00001, max: 0.001, step: 0.00001, set: setLr,        curr: lr       },
                { label: '에포크 수',        val: epochs,                 min: 1,       max: 10,   step: 1,       set: setEpochs,    curr: epochs   },
                { label: '배치 크기',         val: batchSz,                min: 1,       max: 32,   step: 1,       set: setBatchSz,   curr: batchSz  },
                { label: 'Max Seq Length', val: maxSeq,                 min: 512,     max: 4096, step: 128,     set: setMaxSeq,    curr: maxSeq   },
                { label: 'LoRA Rank (r)',  val: loraR,                  min: 4,       max: 128,  step: 4,       set: setLoraR,     curr: loraR    },
                { label: 'LoRA Alpha',     val: loraAlpha,              min: 8,       max: 256,  step: 8,       set: setLoraAlpha, curr: loraAlpha},
                { label: 'Warmup Ratio',   val: warmup.toFixed(2),      min: 0,       max: 0.2,  step: 0.01,    set: setWarmup,    curr: warmup   },
                { label: 'Weight Decay',   val: wdecay.toFixed(3),      min: 0,       max: 0.1,  step: 0.001,   set: setWdecay,    curr: wdecay   },
              ].map(({ label, val, min, max, step, set, curr }) => (
                <div key={label} className={cx('param-item')}>
                  <div className={cx('param-header')}>
                    <span className={cx('param-name')}>{label}</span>
                    <span className={cx('param-val')}>{val}</span>
                  </div>
                  <input
                    type="range"
                    className={cx('slider')}
                    min={min} max={max} step={step}
                    value={curr}
                    onChange={(e) => set(Number(e.target.value))}
                  />
                </div>
              ))}
            </div>
          </section>

          {/* 체크포인트 설정 */}
          <section className={cx('section')}>
            <SectionLabel>체크포인트 설정</SectionLabel>
            <div className={cx('ckpt-config')}>
              <div className={cx('ckpt-cfg-row')}>
                <label className={cx('ckpt-cfg-label')}>저장 간격 (스텝)</label>
                <input
                  type="number" className={cx('ckpt-cfg-input')}
                  value={ckptEvery} min={50} max={2000} step={50}
                  onChange={(e) => setCkptEvery(Number(e.target.value))}
                />
                <span className={cx('ckpt-cfg-hint')}>스텝마다 체크포인트 저장</span>
              </div>
              <div className={cx('ckpt-cfg-row')}>
                <label className={cx('ckpt-cfg-label')}>최대 보관 개수</label>
                <input
                  type="number" className={cx('ckpt-cfg-input')}
                  value={maxCkpts} min={1} max={20}
                  onChange={(e) => setMaxCkpts(Number(e.target.value))}
                />
                <span className={cx('ckpt-cfg-hint')}>초과 시 가장 오래된 체크포인트 자동 삭제</span>
              </div>
            </div>
          </section>

          {/* 학습 제어 */}
          <section className={cx('section')}>
            <SectionLabel>학습 제어</SectionLabel>
            <div className={cx('train-control')}>
              {/* 지표 카드 */}
              <div className={cx('train-stats')}>
                {[
                  ['현재 스텝', currentStep.toLocaleString()],
                  ['Train Loss', currentLoss],
                  ['Grad Norm',  currentGrad],
                  ['진행률',    `${progress}%`],
                ].map(([label, value]) => (
                  <div key={label} className={cx('stat-card')}>
                    <span className={cx('stat-label')}>{label}</span>
                    <span className={cx('stat-val')}>{value}</span>
                  </div>
                ))}
              </div>

              {/* 프로그레스 바 */}
              <div className={cx('prog-track')}>
                <div className={cx('prog-fill')} style={{ width: `${progress}%` }} />
              </div>

              {/* 버튼 */}
              <div className={cx('train-btn-row')}>
                <button
                  className={cx(
                    'train-btn',
                    trainStatus === 'running' && 'train-btn--pause',
                    trainStatus === 'done'    && 'train-btn--done',
                    (trainStatus === 'idle' || trainStatus === 'paused') && 'train-btn--start',
                  )}
                  disabled={trainStatus === 'done'}
                  onClick={handleTrainToggle}
                >
                  {trainBtnLabel}
                </button>
                {trainStatus !== 'idle' && (
                  <button className={cx('reset-btn')} onClick={handleReset}>초기화</button>
                )}
              </div>
            </div>
          </section>

          {/* 학습 추이 차트 */}
          <section className={cx('section')}>
            <SectionLabel>학습 추이</SectionLabel>
            <div className={cx('charts-grid')}>
              <div className={cx('chart-card')}>
                <div className={cx('chart-title')}>Training Loss</div>
                <LineChart data={lossData} colorStroke="#2d76f8" labelY="Loss" />
              </div>
              <div className={cx('chart-card')}>
                <div className={cx('chart-title')}>Gradient Norm</div>
                <LineChart data={gradData} colorStroke="#00c775" labelY="Grad Norm" />
              </div>
            </div>
          </section>
        </div>
      )}

      {/* ══════════════ Tab 2: 관리 ══════════════ */}
      {tab === 2 && (
        <div className={cx('panel')}>

          {/* 체크포인트 목록 */}
          <section className={cx('section')}>
            <SectionLabel>저장된 체크포인트 ({checkpoints.length}개)</SectionLabel>
            {checkpoints.length === 0 ? (
              <div className={cx('empty')}>저장된 체크포인트가 없습니다.</div>
            ) : (
              <div className={cx('ckpt-list')}>
                {checkpoints.map((c) => (
                  <div key={c.id} className={cx('ckpt-item', c.is_best && 'ckpt-item--best')}>
                    <div className={cx('ckpt-top')}>
                      <div className={cx('ckpt-left')}>
                        <span className={cx('ckpt-step')}>Step {c.step.toLocaleString()}</span>
                        <span className={cx('ckpt-epoch')}>Epoch {c.epoch}</span>
                        {c.is_best && <span className={cx('best-badge')}>★ BEST</span>}
                      </div>
                      <div className={cx('ckpt-actions')}>
                        {!c.is_best && (
                          <button className={cx('best-btn')} onClick={() => setBest(c.id)}>Best 지정</button>
                        )}
                        <button className={cx('del-btn')} onClick={() => delCkpt(c.id)}>삭제</button>
                      </div>
                    </div>
                    <div className={cx('ckpt-metrics')}>
                      <span>Loss <b>{c.loss.toFixed(4)}</b></span>
                      <span>Grad Norm <b>{c.grad.toFixed(4)}</b></span>
                      <span>크기 <b>{c.size}</b></span>
                      <span>저장 시각 <b>{fmtDate(c.saved_at)}</b></span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* 스토리지 */}
          <section className={cx('section')}>
            <SectionLabel>스토리지 사용량</SectionLabel>
            <div className={cx('storage-box')}>
              <div className={cx('storage-row')}>
                <span className={cx('storage-label')}>체크포인트 사용량</span>
                <span className={cx('storage-val')}>{(checkpoints.length * 16.2).toFixed(1)} GB</span>
              </div>
              <div className={cx('storage-track')}>
                <div
                  className={cx('storage-fill')}
                  style={{ width: `${Math.min(100, checkpoints.length * 8.1)}%` }}
                />
              </div>
              <div className={cx('storage-total')}>총 할당: 200 GB</div>
            </div>
          </section>
        </div>
      )}
      </>)}
    </div>
  );
});

export default ModelDetailPage;
