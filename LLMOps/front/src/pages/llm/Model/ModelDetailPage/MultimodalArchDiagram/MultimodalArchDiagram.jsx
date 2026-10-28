// VLM 아키텍처 다이어그램: CLIP(비전) → Projector → LLM. 컬럼 헤더는 실제 모델명.
// projType 은 props 로 주입(기본 'mlp2' = 엔진 기본 2-layer MLP). 정보 탭 구조 탐색 버튼이 값을 바꿔 Projector 컬럼 그림만 재렌더.
// 모델 상세 '정보' 탭(멀티모달) 하단에 표시. props = { visionName, llmName, projType }.

import classNames from 'classnames/bind';
import style from './MultimodalArchDiagram.module.scss';

const lx = classNames.bind(style);

const shortName = (id) => {
  if (!id) return '-';
  const parts = String(id).split('/');
  return parts[parts.length - 1];
};

function MultimodalArchDiagram({ visionName, llmName, projType = 'mlp2' }) {
  // 다이어그램 표시 상수. projType 은 상위(정보 탭 구조 탐색 버튼)에서 주입, 기본 = 2-layer MLP.
  const mlpHidden = 2048;
  const xAttnHeads = 8;
  const qTokens = 32;

  const CL_X = 5;
  const CL_W = 295;
  const CL_CX = CL_X + CL_W / 2;
  const PR_X = 360;
  const PR_W = 240;
  const PR_CX = PR_X + PR_W / 2;
  const QW_X = 660;
  const QW_W = 310;
  const QW_CX = QW_X + QW_W / 2;
  const SVG_W = QW_X + QW_W + 5;

  const BBox = ({
    x,
    cx: bcx,
    w,
    y,
    h = 28,
    label,
    s1,
    fill,
    stroke,
    tf = '#333',
  }) => (
    <g>
      <rect
        x={x ?? bcx - w / 2}
        y={y}
        width={w}
        height={h}
        rx='5'
        fill={fill}
        stroke={stroke}
        strokeWidth='1.5'
      />
      <text
        x={bcx}
        y={y + (s1 ? 11 : Math.round(h / 2) + 4)}
        textAnchor='middle'
        fontSize='10'
        fontFamily='SpoqaB'
        fill={tf}
      >
        {label}
      </text>
      {s1 && (
        <text
          x={bcx}
          y={y + 22}
          textAnchor='middle'
          fontSize='8.5'
          fontFamily='SpoqaM'
          fill={tf}
          opacity='0.75'
        >
          {s1}
        </text>
      )}
    </g>
  );
  const VArr = ({ cx: vcx, y1, y2 }) => (
    <g>
      <line
        x1={vcx}
        y1={y1}
        x2={vcx}
        y2={y2 - 7}
        stroke='#c0c0c0'
        strokeWidth='1.5'
      />
      <polygon
        points={`${vcx - 4},${y2 - 10} ${vcx + 4},${y2 - 10} ${vcx},${y2 - 3}`}
        fill='#c0c0c0'
      />
    </g>
  );
  const HArr = ({ x1, y1, x2, y2 }) => {
    const mx = Math.round((x1 + x2) / 2);
    if (Math.abs(y1 - y2) < 2) {
      return (
        <g>
          <line
            x1={x1}
            y1={y1}
            x2={x2 - 7}
            y2={y2}
            stroke='#b0b0b0'
            strokeWidth='1.5'
          />
          <polygon
            points={`${x2 - 10},${y2 - 4} ${x2 - 10},${y2 + 4} ${x2 - 3},${y2}`}
            fill='#b0b0b0'
          />
        </g>
      );
    }
    return (
      <g>
        <polyline
          points={`${x1},${y1} ${mx},${y1} ${mx},${y2} ${x2 - 7},${y2}`}
          fill='none'
          stroke='#b0b0b0'
          strokeWidth='1.5'
          strokeDasharray='4 2'
        />
        <polygon
          points={`${x2 - 10},${y2 - 4} ${x2 - 10},${y2 + 4} ${x2 - 3},${y2}`}
          fill='#b0b0b0'
        />
      </g>
    );
  };
  const Plus = ({ cx: pcx, cy }) => (
    <g>
      <circle
        cx={pcx}
        cy={cy}
        r={9}
        fill='#fff'
        stroke='#c0c0c0'
        strokeWidth='1.5'
      />
      <line
        x1={pcx - 5}
        y1={cy}
        x2={pcx + 5}
        y2={cy}
        stroke='#888'
        strokeWidth='1.5'
      />
      <line
        x1={pcx}
        y1={cy - 5}
        x2={pcx}
        y2={cy + 5}
        stroke='#888'
        strokeWidth='1.5'
      />
    </g>
  );
  const ColHdr = ({ x, w, cx: hcx, title, sub, fill, stroke, tf }) => (
    <g>
      <rect
        x={x}
        y={0}
        width={w}
        height={50}
        rx='8'
        fill={fill}
        stroke={stroke}
        strokeWidth='1.5'
      />
      <text
        x={hcx}
        y={18}
        textAnchor='middle'
        fontSize='12'
        fontFamily='SpoqaB'
        fill={tf}
      >
        {title}
      </text>
      <text
        x={hcx}
        y={34}
        textAnchor='middle'
        fontSize='9'
        fontFamily='SpoqaM'
        fill={tf}
        opacity='0.75'
      >
        {sub}
      </text>
    </g>
  );
  const BlockOutline = ({ x, w, y, h, label, stroke }) => (
    <g>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx='6'
        fill='none'
        stroke={stroke}
        strokeWidth='1'
        strokeDasharray='5 3'
        opacity='0.6'
      />
      <rect
        x={x + w - 72}
        y={y + h - 16}
        width={68}
        height={13}
        rx='3'
        fill={stroke}
        opacity='0.12'
      />
      <text
        x={x + w - 36}
        y={y + h - 6}
        textAnchor='middle'
        fontSize='8'
        fontFamily='SpoqaB'
        fill={stroke}
        opacity='0.9'
      >
        {label}
      </text>
    </g>
  );

  const cl_bx = CL_X + 8;
  const cl_bw = CL_W - 16;
  const cl_in = 60;
  const cl_pe = cl_in + 28 + 10;
  const cl_pos = cl_pe + 28 + 10;
  const cl_blk = cl_pos + 22 + 12;
  const cl_ln1 = cl_blk + 14;
  const cl_mhsa = cl_ln1 + 24 + 8;
  const cl_r1cy = cl_mhsa + 40 + 10;
  const cl_ln2 = cl_r1cy + 18 + 8;
  const cl_ffn = cl_ln2 + 24 + 8;
  const cl_r2cy = cl_ffn + 40 + 10;
  const cl_blkH = cl_r2cy + 18 - cl_blk + 10;
  const cl_fln = cl_blk + cl_blkH + 12;
  const cl_out = cl_fln + 24 + 10;

  const qw_bx = QW_X + 8;
  const qw_bw = QW_W - 16;
  const qw_in = 60;
  const qw_emb = qw_in + 22 + 10;
  const qw_blk = qw_emb + 28 + 12;
  const qw_rn1 = qw_blk + 14;
  const qw_gqa = qw_rn1 + 24 + 8;
  const qw_r1cy = qw_gqa + 40 + 10;
  const qw_rn2 = qw_r1cy + 18 + 8;
  const qw_mlp = qw_rn2 + 24 + 8;
  const qw_r2cy = qw_mlp + 40 + 10;
  const qw_blkH = qw_r2cy + 18 - qw_blk + 10;
  const qw_fnm = qw_blk + qw_blkH + 12;
  const qw_lmh = qw_fnm + 24 + 10;
  const qw_out = qw_lmh + 28 + 10;

  const COL_H = Math.max(cl_out + 28 + 20, qw_out + 22 + 20, 480);
  const SVG_H = COL_H;

  const pr_bx = PR_X + 8;
  const pr_bw = PR_W - 16;
  const NK = { fill: '#e8f0fe', stroke: '#4285f4', tf: '#1a237e' };
  const GN = { fill: '#e8f5e9', stroke: '#43a047', tf: '#1b5e20' };
  const NH = 28;
  const NG = 10;

  let prSeq;
  if (projType === 'linear') {
    prSeq = [{ label: 'Linear', s1: '1024 → 4096', ...NK }];
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
      { label: 'Cross-Attention', s1: '(Layer 2)', ...NK, h: 40 },
      { label: 'Linear', s1: '1024 → 4096', ...NK },
    ];
  } else if (projType === 'llama3_2_vision') {
    prSeq = [
      { label: 'Cross-Attn Adapter', s1: 'Gated', ...NK, h: 40 },
      { label: 'Linear', s1: '1024 → 4096', ...NK },
    ];
  } else if (projType === 'resampler') {
    prSeq = [
      { label: 'Perceiver Resampler', s1: `${qTokens} latents`, ...NK, h: 40 },
      { label: 'Linear', s1: '1024 → 4096', ...NK },
    ];
  } else {
    prSeq = [
      { label: '×8 Q-Former Block', s1: 'Self + Cross Attn', ...NK, h: 40 },
      { label: 'Linear', s1: `${qTokens}×1024 → ${qTokens}×4096`, ...NK },
    ];
  }

  const seqTotalH =
    prSeq.reduce((a, n) => a + (n.h || NH), 0) + NG * (prSeq.length - 1);
  const ioH = 22;
  const ioArr = 14;
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

  const cl_out_cy = cl_out + 14;
  const pr_in_cy = pr_io_in_y + 11;
  const pr_out_cy = pr_io_out_y + 11;

  const projSub =
    {
      linear: 'Linear',
      mlp2: 'MLP-2',
      mlp3: 'MLP-3',
      xattn: 'Cross-Attention',
      qformer: 'Q-Former',
      llama3_2_vision: 'Llama3.2-Vision',
      resampler: 'Resampler',
    }[projType] ?? '';

  return (
    <div className={lx('mg-wrapper')}>
      {/* 내부 차원/블록 수는 대표 구성(CLIP-ViT-L/14 + Qwen 계열) 기준 예시 — 실제 조립 모델에 따라 다를 수 있음. */}
      <div className={lx('mg-note')}>
        ※ 구조 예시(대표 구성) — 비전/언어모델 명칭은 실제값, 내부 차원·블록
        수는 대표치입니다.
      </div>
      <svg
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        className={lx('mg-svg')}
        xmlns='http://www.w3.org/2000/svg'
      >
        <rect
          x={CL_X}
          y={0}
          width={CL_W}
          height={SVG_H}
          rx='8'
          fill='#fffdf7'
          stroke='#fb8c00'
          strokeWidth='1.5'
        />
        <rect
          x={PR_X}
          y={0}
          width={PR_W}
          height={SVG_H}
          rx='8'
          fill='#f0f4ff'
          stroke='#4285f4'
          strokeWidth='1.5'
        />
        <rect
          x={QW_X}
          y={0}
          width={QW_W}
          height={SVG_H}
          rx='8'
          fill='#fdf5ff'
          stroke='#8e24aa'
          strokeWidth='1.5'
        />

        <ColHdr
          x={CL_X}
          w={CL_W}
          cx={CL_CX}
          title={shortName(visionName)}
          sub='Vision Encoder'
          fill='#fff8e1'
          stroke='#fb8c00'
          tf='#e65100'
        />
        <ColHdr
          x={PR_X}
          w={PR_W}
          cx={PR_CX}
          title='Projector'
          sub={projSub}
          fill='#e8f0fe'
          stroke='#4285f4'
          tf='#1a237e'
        />
        <ColHdr
          x={QW_X}
          w={QW_W}
          cx={QW_CX}
          title={shortName(llmName)}
          sub='Language Model'
          fill='#f3e5f5'
          stroke='#8e24aa'
          tf='#4a148c'
        />

        <BBox
          x={cl_bx}
          cx={CL_CX}
          w={cl_bw}
          y={cl_in}
          h={28}
          label='Image Input'
          s1='[3 × 224 × 224]'
          fill='#f5f5f5'
          stroke='#bdbdbd'
          tf='#424242'
        />
        <VArr cx={CL_CX} y1={cl_in + 28} y2={cl_pe} />
        <BBox
          x={cl_bx}
          cx={CL_CX}
          w={cl_bw}
          y={cl_pe}
          h={28}
          label='Patch Embed (14×14)'
          s1='256 patches × 1024'
          fill='#fff8e1'
          stroke='#fb8c00'
          tf='#e65100'
        />
        <VArr cx={CL_CX} y1={cl_pe + 28} y2={cl_pos} />
        <BBox
          x={cl_bx}
          cx={CL_CX}
          w={cl_bw}
          y={cl_pos}
          h={22}
          label='+ Positional Encoding [257 tokens]'
          fill='#e8f5e9'
          stroke='#43a047'
          tf='#1b5e20'
        />
        <VArr cx={CL_CX} y1={cl_pos + 22} y2={cl_blk + 14} />
        <BlockOutline
          x={cl_bx}
          w={cl_bw}
          y={cl_blk}
          h={cl_blkH}
          label='× 24 ViT Block'
          stroke='#fb8c00'
        />
        <BBox
          x={cl_bx + 10}
          cx={CL_CX}
          w={cl_bw - 20}
          y={cl_ln1}
          h={24}
          label='LayerNorm'
          fill='#e8f5e9'
          stroke='#43a047'
          tf='#1b5e20'
        />
        <VArr cx={CL_CX} y1={cl_ln1 + 24} y2={cl_mhsa} />
        <BBox
          x={cl_bx + 10}
          cx={CL_CX}
          w={cl_bw - 20}
          y={cl_mhsa}
          h={40}
          label='Multi-Head Self-Attention'
          s1='16 heads · head_dim=64'
          fill='#e8f0fe'
          stroke='#4285f4'
          tf='#1a237e'
        />
        <VArr cx={CL_CX} y1={cl_mhsa + 40} y2={cl_r1cy - 9} />
        <Plus cx={CL_CX} cy={cl_r1cy} />
        <VArr cx={CL_CX} y1={cl_r1cy + 9} y2={cl_ln2} />
        <BBox
          x={cl_bx + 10}
          cx={CL_CX}
          w={cl_bw - 20}
          y={cl_ln2}
          h={24}
          label='LayerNorm'
          fill='#e8f5e9'
          stroke='#43a047'
          tf='#1b5e20'
        />
        <VArr cx={CL_CX} y1={cl_ln2 + 24} y2={cl_ffn} />
        <BBox
          x={cl_bx + 10}
          cx={CL_CX}
          w={cl_bw - 20}
          y={cl_ffn}
          h={40}
          label='Feed-Forward Network'
          s1='FFN dim: 4096'
          fill='#f3e5f5'
          stroke='#8e24aa'
          tf='#4a148c'
        />
        <VArr cx={CL_CX} y1={cl_ffn + 40} y2={cl_r2cy - 9} />
        <Plus cx={CL_CX} cy={cl_r2cy} />
        <VArr cx={CL_CX} y1={cl_r2cy + 9} y2={cl_fln} />
        <BBox
          x={cl_bx}
          cx={CL_CX}
          w={cl_bw}
          y={cl_fln}
          h={24}
          label='LayerNorm'
          fill='#e8f5e9'
          stroke='#43a047'
          tf='#1b5e20'
        />
        <VArr cx={CL_CX} y1={cl_fln + 24} y2={cl_out} />
        <BBox
          x={cl_bx}
          cx={CL_CX}
          w={cl_bw}
          y={cl_out}
          h={28}
          label='Visual Features'
          s1='[257 × 1024]'
          fill='#fff8e1'
          stroke='#fb8c00'
          tf='#e65100'
        />

        <BBox
          x={pr_bx}
          cx={PR_CX}
          w={pr_bw}
          y={pr_io_in_y}
          h={ioH}
          label='Visual In [257 × 1024]'
          fill='#f5f5f5'
          stroke='#bdbdbd'
          tf='#555'
        />
        <VArr
          cx={PR_CX}
          y1={pr_io_in_y + ioH}
          y2={prNodePos[0]?.y ?? pr_io_in_y + ioH + ioArr}
        />
        {prNodePos.map((n, i) => {
          const nh = n.h || NH;
          return (
            <g key={i}>
              <BBox
                x={pr_bx}
                cx={PR_CX}
                w={pr_bw}
                y={n.y}
                h={nh}
                label={n.label}
                s1={n.s1}
                fill={n.fill}
                stroke={n.stroke}
                tf={n.tf}
              />
              {i < prNodePos.length - 1 && (
                <VArr cx={PR_CX} y1={n.y + nh} y2={prNodePos[i + 1].y} />
              )}
            </g>
          );
        })}
        {prNodePos.length > 0 && (
          <VArr
            cx={PR_CX}
            y1={
              prNodePos[prNodePos.length - 1].y +
              (prNodePos[prNodePos.length - 1].h || NH)
            }
            y2={pr_io_out_y}
          />
        )}
        <BBox
          x={pr_bx}
          cx={PR_CX}
          w={pr_bw}
          y={pr_io_out_y}
          h={ioH}
          label='Projected [257 × 4096]'
          fill='#f5f5f5'
          stroke='#bdbdbd'
          tf='#555'
        />

        <BBox
          x={qw_bx}
          cx={QW_CX}
          w={qw_bw}
          y={qw_in}
          h={22}
          label='Input IDs [batch, seq_len]'
          fill='#f5f5f5'
          stroke='#bdbdbd'
          tf='#424242'
        />
        <VArr cx={QW_CX} y1={qw_in + 22} y2={qw_emb} />
        <BBox
          x={qw_bx}
          cx={QW_CX}
          w={qw_bw}
          y={qw_emb}
          h={28}
          label='Token Embedding + Vision Prefix'
          s1='152K × 4096'
          fill='#f3e5f5'
          stroke='#8e24aa'
          tf='#4a148c'
        />
        <VArr cx={QW_CX} y1={qw_emb + 28} y2={qw_blk + 14} />
        <BlockOutline
          x={qw_bx}
          w={qw_bw}
          y={qw_blk}
          h={qw_blkH}
          label='× 36 Transformer Block'
          stroke='#8e24aa'
        />
        <BBox
          x={qw_bx + 10}
          cx={QW_CX}
          w={qw_bw - 20}
          y={qw_rn1}
          h={24}
          label='RMSNorm'
          fill='#e8f5e9'
          stroke='#43a047'
          tf='#1b5e20'
        />
        <VArr cx={QW_CX} y1={qw_rn1 + 24} y2={qw_gqa} />
        <BBox
          x={qw_bx + 10}
          cx={QW_CX}
          w={qw_bw - 20}
          y={qw_gqa}
          h={40}
          label='Grouped-Query Attention (GQA)'
          s1='32 Q heads · 8 KV heads'
          fill='#e8f0fe'
          stroke='#4285f4'
          tf='#1a237e'
        />
        <VArr cx={QW_CX} y1={qw_gqa + 40} y2={qw_r1cy - 9} />
        <Plus cx={QW_CX} cy={qw_r1cy} />
        <VArr cx={QW_CX} y1={qw_r1cy + 9} y2={qw_rn2} />
        <BBox
          x={qw_bx + 10}
          cx={QW_CX}
          w={qw_bw - 20}
          y={qw_rn2}
          h={24}
          label='RMSNorm'
          fill='#e8f5e9'
          stroke='#43a047'
          tf='#1b5e20'
        />
        <VArr cx={QW_CX} y1={qw_rn2 + 24} y2={qw_mlp} />
        <BBox
          x={qw_bx + 10}
          cx={QW_CX}
          w={qw_bw - 20}
          y={qw_mlp}
          h={40}
          label='SwiGLU Feed-Forward'
          s1='intermediate: 22016'
          fill='#f3e5f5'
          stroke='#8e24aa'
          tf='#4a148c'
        />
        <VArr cx={QW_CX} y1={qw_mlp + 40} y2={qw_r2cy - 9} />
        <Plus cx={QW_CX} cy={qw_r2cy} />
        <VArr cx={QW_CX} y1={qw_r2cy + 9} y2={qw_fnm} />
        <BBox
          x={qw_bx}
          cx={QW_CX}
          w={qw_bw}
          y={qw_fnm}
          h={24}
          label='RMSNorm'
          fill='#e8f5e9'
          stroke='#43a047'
          tf='#1b5e20'
        />
        <VArr cx={QW_CX} y1={qw_fnm + 24} y2={qw_lmh} />
        <BBox
          x={qw_bx}
          cx={QW_CX}
          w={qw_bw}
          y={qw_lmh}
          h={28}
          label='LM Head (Linear, no bias)'
          s1='4096 → 152K'
          fill='#fff8e1'
          stroke='#fb8c00'
          tf='#e65100'
        />
        <VArr cx={QW_CX} y1={qw_lmh + 28} y2={qw_out} />
        <BBox
          x={qw_bx}
          cx={QW_CX}
          w={qw_bw}
          y={qw_out}
          h={22}
          label='Logits [batch, seq, 152K]'
          fill='#f5f5f5'
          stroke='#bdbdbd'
          tf='#424242'
        />

        <HArr x1={CL_X + CL_W} y1={cl_out_cy} x2={PR_X} y2={pr_in_cy} />
        <HArr x1={PR_X + PR_W} y1={pr_out_cy} x2={QW_X} y2={qw_in + 11} />
      </svg>
    </div>
  );
}

export default MultimodalArchDiagram;
