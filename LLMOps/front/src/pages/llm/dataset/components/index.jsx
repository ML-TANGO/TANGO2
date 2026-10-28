import React from 'react';
import { Link, useHistory, useParams } from 'react-router-dom';

import {
  Badge as JonathanBadge,
  ButtonV2,
  Checkbox as JonathanCheckbox,
  InputText,
  Radio as JonathanRadio,
  Selectbox,
  Textarea as JonathanTextarea,
} from '@jonathan/ui-react';

import { getDataset } from '@src/apis/llm/dataset';
import BorderTable from '@src/components/molecules/BorderTable';
// 탭은 ui-react 가 아니라 프로젝트 molecules 쪽이 정본이다.
// (@jonathan/ui-react 의 Tab 은 category/renderComponent 를 받는 다른 물건이라
//  option/select/tabHandler 를 넘기면 아무것도 그리지 않는다.)
import JonathanTab from '@src/components/molecules/Tab';

import { fmt, gateState } from '../lib/format';
import { VIEWBOX } from '../lib/frames';
import common from '../styles/common.module.scss';
import style from './components.module.scss';

// 데이터 파이프라인 화면 공용 컴포넌트.
//
// 여기 있는 것들은 **얇은 파사드**다. 실제 버튼·배지·입력·셀렉트·체크·라디오·탭은
// 플랫폼 디자인 시스템(@jonathan/ui-react)을 그대로 쓰고, 이 파일은 목업에서 쓰던
// prop 이름을 플랫폼 prop 으로 옮기는 일만 한다.
//
// 왜 직접 만들지 않는가: 처음엔 목업을 그대로 옮기느라 버튼·배지·입력을 자체 구현했는데,
// 그러면 같은 제품 안에서 이 화면들만 다른 규칙으로 그려져 이질적으로 보인다. 색·높이·
// 라운드·포커스 링·hover 는 플랫폼이 이미 정해 둔 것이 있다.
//
// 그대로 두는 것: 플랫폼에 대응물이 없는 것들 —
//   Frame(플레이스홀더 이미지) · Slider · ProgressBar · GateRibbon(4축 심사 리본) ·
//   Funnel(단계별 잔존) · NodeCanvas(파이프라인 캔버스) · 페이지 골격.

// ── 라우트 헬퍼 ─────────────────────────────────────────────────────────────
/** 데이터셋 하위 화면의 공통 경로. 라우트가 바뀌면 여기 한 곳만 고친다. */
export const dsBase = (wsId, dsId) =>
  `/user/workspace/${wsId}/datasets/pipeline/${dsId}`;

// 목록의 정본 경로는 LNB '데이터' 항목과 같은 `/datasets` 다.
// `/datasets/pipeline` 도 같은 화면을 그리지만 메뉴에 없는 하위 별칭이라, 뒤로 가기
// 링크는 사이드바에서 점등되는 쪽으로 보낸다.
export const listBase = (wsId) => `/user/workspace/${wsId}/datasets`;

/** 화면들이 반복해서 쓰는 이동 함수 — v5 라 useHistory 를 감싼다. */
export function useDatasetNav() {
  const history = useHistory();
  const { id: wsId, dsId } = useParams();
  return {
    wsId,
    dsId,
    go: (path) => history.push(`${dsBase(wsId, dsId)}${path}`),
    goList: () => history.push(listBase(wsId)),
    goPath: (path) => history.push(path),
  };
}

// 데이터셋 이름 캐시. 화면을 옮길 때마다 같은 데이터셋을 다시 물어보지 않게 모듈
// 수준에 둔다(이름은 한 세션 안에서 거의 바뀌지 않는다).
const dsNameCache = new Map();

/**
 * 화면 제목에 쓸 데이터셋 이름.
 *
 * 제목에 id 를 그대로 박으면 사용자는 자기가 만든 이름이 아니라 '5' 를 본다.
 * 이름을 아직 못 받았으면 id 로 대신한다 — 제목이 빈 채로 깜빡이는 것보다 낫다.
 */
export function useDatasetName(dsId) {
  const key = dsId == null ? '' : String(dsId);
  const [name, setName] = React.useState(() => dsNameCache.get(key) || '');

  React.useEffect(() => {
    if (!key) return undefined;
    if (dsNameCache.has(key)) {
      setName(dsNameCache.get(key));
      return undefined;
    }
    let alive = true;
    (async () => {
      const res = await getDataset(key);
      const found = res?.result?.name;
      if (!found) return;
      dsNameCache.set(key, found);
      if (alive) setName(found);
    })();
    return () => {
      alive = false;
    };
  }, [key]);

  return name || key;
}

// ── 플레이스홀더 이미지 ─────────────────────────────────────────────────────
/**
 * lib/frames 의 도형 명세를 SVG 로 그린다.
 * 마크업 문자열을 주입하지 않고 명세만 받아 JSX 로 만든다.
 */
export function Frame({ spec, ariaLabel = '표본 이미지' }) {
  return (
    <svg
      viewBox={VIEWBOX}
      className={style.frame}
      role='img'
      aria-label={ariaLabel}
    >
      {spec.map((e, i) => {
        if (e.t === 'rect') {
          return (
            <rect
              key={i}
              x={e.x}
              y={e.y}
              width={e.w}
              height={e.h}
              fill={e.fill}
              stroke={e.stroke}
              strokeDasharray={e.dash}
              opacity={e.opacity}
            />
          );
        }
        if (e.t === 'line') {
          return (
            <line
              key={i}
              x1={e.x1}
              y1={e.y1}
              x2={e.x2}
              y2={e.y2}
              stroke={e.stroke}
            />
          );
        }
        if (e.t === 'circle') {
          return (
            <circle
              key={i}
              cx={e.cx}
              cy={e.cy}
              r={e.r}
              fill={e.fill}
              opacity={e.opacity}
            />
          );
        }
        if (e.t === 'path') {
          return (
            <path
              key={i}
              d={e.d}
              fill={e.fill}
              stroke={e.stroke}
              strokeWidth={e.sw}
              opacity={e.opacity}
            />
          );
        }
        return (
          <text
            key={i}
            x={e.x}
            y={e.y}
            fontFamily={e.family}
            fontSize={e.fs}
            fill={e.fill}
            textAnchor={e.anchor}
            opacity={e.opacity}
            fontWeight={e.bold ? 'bold' : undefined}
          >
            {e.s}
          </text>
        );
      })}
    </svg>
  );
}

// ── 버튼 ────────────────────────────────────────────────────────────────────
// 목업 어휘(tone/fill/size) → 플랫폼 ButtonV2 어휘(colorType/type/size) 변환표.
// 화면 코드는 목업 어휘를 그대로 쓰고, 실제 모양은 플랫폼이 정한다.
const BTN_COLOR = {
  primary: 'blue',
  secondary: 'skyblue',
  gray: 'gray',
  danger: 'red',
};
const BTN_SIZE = { sm: 's', md: 'm', lg: 'l' };

/** tone: primary|secondary|gray|danger · fill: solid|outline · size: sm|md|lg */
export function Btn({
  tone = 'primary',
  fill = 'solid',
  size = 'md',
  block,
  disabled,
  onClick,
  children,
  className = '',
}) {
  const button = (
    <ButtonV2
      colorType={BTN_COLOR[tone] || 'blue'}
      type={fill === 'outline' ? 'outline' : 'solid'}
      size={BTN_SIZE[size] || 'm'}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </ButtonV2>
  );

  // ButtonV2 는 폭을 늘리는 prop 이 없다. 전체폭이 필요한 자리는 감싸서 늘린다.
  if (block) {
    return (
      <span className={[style['btn-block'], className].join(' ')}>
        {button}
      </span>
    );
  }
  return className ? <span className={className}>{button}</span> : button;
}

// ── 배지 ────────────────────────────────────────────────────────────────────
// 판정 어휘(pass/warn/fail) → 플랫폼 색 이름. 배경 틴트와 잉크 짝은 플랫폼이 쥔다.
const BADGE_TYPE = {
  pass: 'green',
  warn: 'orange',
  fail: 'red',
  gray: 'gray',
  primary: 'blue',
  yellow: 'yellow',
};

export function Badge({ tone = 'gray', size = 'md', children }) {
  return (
    <JonathanBadge
      label={children}
      type={BADGE_TYPE[tone] || 'gray'}
      size={size === 'lg' ? 'md' : 'sm'}
    />
  );
}

// ── 입력 ────────────────────────────────────────────────────────────────────
export function Textfield({ value, onChange, placeholder, disabled }) {
  return (
    <InputText
      size='medium'
      value={value}
      placeholder={placeholder}
      disabled={disabled}
      onChange={(e) => onChange && onChange(e.target.value)}
    />
  );
}

export function Textarea({ value, onChange, height = 84 }) {
  return (
    <JonathanTextarea
      size='large'
      value={value}
      onChange={(e) => onChange && onChange(e.target.value)}
      customStyle={{ width: '100%', minHeight: `${height}px` }}
    />
  );
}

/** options: string[] 또는 { v, n }[] */
export function Select({ value, onChange, options = [], disabled }) {
  // Selectbox 는 값이 아니라 항목 객체를 주고받는다.
  const list = options.map((o) =>
    typeof o === 'object' ? { label: o.n, value: o.v } : { label: o, value: o },
  );
  const selected = list.find((o) => o.value === value) || list[0];

  return (
    <Selectbox
      list={list}
      selectedItem={selected}
      disabled={disabled}
      onChange={(item) => onChange && onChange(item.value)}
      customStyle={{
        selectboxForm: { width: '100%' },
        listForm: { width: '100%' },
      }}
    />
  );
}

export function SearchField({ placeholder, value, onChange, width = 280 }) {
  return (
    <span style={{ display: 'inline-block', width }}>
      <InputText
        size='medium'
        value={value}
        placeholder={placeholder}
        leftIcon='/images/icon/ic-search.svg'
        disableLeftIcon={false}
        onChange={(e) => onChange && onChange(e.target.value)}
      />
    </span>
  );
}

export function Checkbox({ checked, onChange, label, disabled }) {
  return (
    <JonathanCheckbox
      checked={!!checked}
      label={label}
      disabled={disabled}
      onChange={() => onChange && onChange(!checked)}
    />
  );
}

/**
 * 낱개 라디오.
 * 플랫폼 Radio 는 그룹 단위(options + selectedValue)라, 항목 하나짜리 그룹으로 감싼다.
 */
export function RadioBtn({ checked, onChange, label, name = 'dp-radio' }) {
  return (
    <JonathanRadio
      name={name}
      options={[{ label, value: label }]}
      selectedValue={checked ? label : ''}
      onChange={() => onChange && onChange(true)}
    />
  );
}

export function Slider({ min = 0, max = 100, value, onChange, disabled }) {
  return (
    <input
      type='range'
      className={style.slider}
      min={min}
      max={max}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange && onChange(parseInt(e.target.value, 10))}
    />
  );
}

// ── 표시 ────────────────────────────────────────────────────────────────────
export function ProgressBar({ value = 0, tone = 'primary', height = 8 }) {
  return (
    <span className={style.bar} style={{ height }}>
      <i
        className={[style['bar-fill'], style[`bar-${tone}`]].join(' ')}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </span>
  );
}

export function MetricTile({ label, value }) {
  return (
    <span className={common.tile}>
      <span className={common['tile-value']}>{value}</span>
      <span className={common['tile-label']}>{label}</span>
    </span>
  );
}

export function SectionHead({ children, aside }) {
  return (
    <div className={common['section-head']}>
      <span className={common['section-title']}>{children}</span>
      {aside}
    </div>
  );
}

// ── 4축 게이트 리본 ─────────────────────────────────────────────────────────
/**
 * 점수 · 축 이름 · 막대 + 임계값 눈금 · 판정을 한 줄에 보여준다.
 * 막대 위의 세로선이 임계값이라 "얼마나 아슬아슬한지"가 눈에 보인다.
 */
export function GateRibbon({ axes, scores, thresholds, size = 'md' }) {
  return (
    <span className={style['ribbon-wrap']}>
      <span className={style.ribbon}>
        {axes.map((a) => {
          const v = scores[a.k];
          const th = thresholds[a.k];
          const st = gateState(v, th);
          return (
            <span
              key={a.k}
              className={[
                style['ribbon-cell'],
                style[`ribbon-${st.tone}`],
                size === 'lg' ? style['ribbon-lg'] : '',
              ].join(' ')}
            >
              <span className={style['ribbon-score']}>
                {Number(v).toFixed(2)}
              </span>
              <span className={style['ribbon-label']}>{a.label}</span>
              <span className={style['ribbon-bar']}>
                <i
                  className={style['ribbon-fill']}
                  style={{
                    width: `${Math.round(v * 100)}%`,
                    background: st.hex,
                  }}
                />
                <i
                  className={style['ribbon-tick']}
                  style={{ left: `${Math.round(th * 100)}%` }}
                />
              </span>
              <span className={style['ribbon-verdict']}>{st.label}</span>
            </span>
          );
        })}
      </span>
    </span>
  );
}

// ── 깔때기 ──────────────────────────────────────────────────────────────────
/** 단계별 잔존 수. 전처리는 숫자가 줄지 않고 필터에서만 줄어드는 것이 정상이다. */
export function Funnel({ rows, total }) {
  return (
    <div className={common.card}>
      <div className={style.funnel}>
        {rows.map((r) => {
          const edge = r.k === '입력' || r.k === '출력';
          return (
            <span key={r.k} className={style['funnel-row']}>
              <span
                className={[
                  style['funnel-name'],
                  edge ? style['funnel-edge'] : '',
                ].join(' ')}
              >
                {r.k}
              </span>
              <span className={style['funnel-track']}>
                <i
                  className={style['funnel-fill']}
                  style={{
                    width: `${Math.round((r.v / total) * 100)}%`,
                    background: edge ? '#042659' : '#2d76f8',
                  }}
                />
              </span>
              <span className={style['funnel-value']}>{fmt(r.v)}</span>
              <span
                className={[
                  style['funnel-del'],
                  r.del ? style['funnel-del-on'] : '',
                ].join(' ')}
              >
                {r.del === null || r.del === undefined
                  ? ''
                  : r.del === 0
                    ? '제거 없음'
                    : `−${r.del}`}
              </span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

// ── 공용 표 ─────────────────────────────────────────────────────────────────
/**
 * 표 — 플랫폼 BorderTable(react-data-table-component 래퍼)로 그린다.
 *
 * 예전에는 CSS grid 로 직접 그렸는데, 그러면 헤더 배경·행 구분선·정렬 화살표·hover 가
 * 플랫폼의 다른 목록과 미묘하게 어긋나 같은 제품이 아닌 것처럼 보였다.
 *
 * 화면 코드는 계속 `cols`(문자열 배열) + `rows`(셀 배열의 배열)로 넘긴다 —
 * 표 데이터가 대부분 이미 그 모양이라 여기서 열 정의로 바꿔 준다.
 *
 * @param cols 열 제목
 * @param rows 셀 배열의 배열. 셀이 `{ node }` 면 그 JSX 를 그대로 그린다.
 * @param cellTone (cell, colIndex) => 'danger'|'pass'|null — 값에 따른 잉크 강조
 */
export function DataTable({ cols, rows, onRowClick, cellTone, maxHeight }) {
  const columns = cols.map((label, ci) => ({
    name: label,
    selector: `c${ci}`,
    sortable: false,
    cell: (row) => {
      const cell = row.cells[ci];
      if (cell && typeof cell === 'object' && cell.node) return cell.node;
      const tone = cellTone ? cellTone(cell, ci) : null;
      return (
        <span
          className={[
            common.num,
            common.truncate,
            ci === 0 ? common.cell : common['cell-mute'],
            tone ? common[tone] : '',
          ].join(' ')}
          title={typeof cell === 'string' ? cell : undefined}
        >
          {cell}
        </span>
      );
    },
  }));

  const data = rows.map((cells, i) => ({ id: i, cells }));

  return (
    <BorderTable
      columns={columns}
      data={data}
      loading={false}
      selectableRows={false}
      hideSearchBox
      hideButtons
      onRowClick={onRowClick ? (row) => onRowClick(row.id) : undefined}
      fixedHeader={!!maxHeight}
      fixedHeaderScrollHeight={maxHeight}
    />
  );
}

// ── 페이지 헤더 ─────────────────────────────────────────────────────────────
/**
 * 상단 바 — 배포/모델 상세(DeployDetailHeader)와 같은 구성.
 *
 * 뒤로가기 줄 → 제목 24px → (오른쪽 액션). 예전에는 목업대로 eyebrow + 32px 네이비
 * 제목을 썼는데, 같은 제품의 다른 상세 화면과 글자 크기·색·간격이 달라 혼자 튀었다.
 */
export function PageHeader({ title, back, meta, actions }) {
  return (
    <div className={style['detail-header']}>
      {back && (
        <div className={style['detail-back-row']}>
          <Link to={back.to} className={style['detail-back']}>
            ← {back.label}
          </Link>
        </div>
      )}
      <div className={style['detail-title-row']}>
        <h2 className={style['detail-title']}>{title}</h2>
        {(meta || actions) && (
          <div className={style['detail-right']}>
            {meta && <span className={style['detail-meta']}>{meta}</span>}
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}

// ── 탭 · 세그먼트 ───────────────────────────────────────────────────────────
/**
 * 페이지 탭 — 화면을 갈아 끼우는 1차/2차 내비게이션. 플랫폼 Tab 을 그대로 쓴다.
 */
export function TabBar({ options, value, onChange, type = 'c' }) {
  return (
    <JonathanTab
      type={type}
      sidePaddingNone
      option={options.map((o) => ({ label: o, value: o }))}
      select={{ value }}
      tabHandler={(item) => onChange(item.value)}
    />
  );
}

/**
 * 인라인 세그먼트 토글 — '실행 전 / 실행 후' 처럼 같은 화면 안에서 보기를 바꾸는 것.
 *
 * 페이지 탭(TabBar)과 구분하는 이유: 화면을 옮기는 것이 아니라 한 화면의 상태를
 * 바꾸는 것이라 밑줄 탭을 쓰면 "여기서 다른 페이지로 간다"는 잘못된 신호를 준다.
 * 플랫폼이 같은 상황에서 쓰는 방식(선택된 것만 파란 ButtonV2)을 따른다.
 */
export function Segmented({ options, value, onChange, size = 's' }) {
  return (
    <span className={style.segmented}>
      {options.map((o) => (
        <ButtonV2
          key={o}
          colorType={o === value ? 'blue' : 'white'}
          type='solid'
          size={size}
          onClick={() => onChange(o)}
        >
          {o}
        </ButtonV2>
      ))}
    </span>
  );
}

// ── 데이터셋 탭 ─────────────────────────────────────────────────────────────
// 한 줄로 편다. 예전에는 1차(4개) + 2차(2개) 두 줄이었는데, 같은 제품의 다른 상세
// 화면(배포·모델)이 전부 한 줄이라 여기만 두 줄이면 깊이가 더 있는 것처럼 보인다.
const TABS = [
  { label: '파이프라인', seg: '/flow' },
  { label: '검수', seg: '/review' },
  { label: '분포 분석', seg: '/analysis' },
  { label: '구성 · 분할', seg: '/compose' },
  { label: '이력', seg: '/compose/history' },
];

/** @param active 현재 탭 라벨 */
export function DatasetTabs({ active }) {
  const { go } = useDatasetNav();
  return (
    <div className={style['tab-bar']}>
      <TabBar
        type="c"
        options={TABS.map((t) => t.label)}
        value={active}
        onChange={(v) => go(TABS.find((t) => t.label === v).seg)}
      />
    </div>
  );
}
