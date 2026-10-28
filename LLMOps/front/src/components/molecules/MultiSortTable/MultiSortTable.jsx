import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import Table from '@src/components/molecules/Table';

import classNames from 'classnames/bind';
import style from './MultiSortTable.module.scss';

const cx = classNames.bind(style);

// 그룹 경계선 — 행 사이 헤어라인($mono203 #dbdbdb)보다 한 단계 진해야 "경계"로 읽힌다.
// conditionalRowStyles 는 인라인 스타일이라 SCSS 변수를 쓸 수 없어 값($mono204)을 그대로 적는다.
const GROUP_BORDER_TOP = '1px solid #c1c1c1';

// 헤더를 누른 "순서"가 곧 정렬 레벨인 표.
//   - 처음 누른 열 = 1차, 그다음 = 2차 … 이미 잡힌 열을 다시 누르면 방향만 뒤집는다.
//   - 표 위 칩이 현재 레벨을 그대로 보여주고, 칩의 ✕ 로 레벨 하나만 뺄 수 있다.
//   - 선두 레벨이 범주형(categorical)이면 값이 바뀌는 자리에 그룹 경계선을 긋는다.
//
// ── 무엇을 위임하고 무엇을 소유하는가 ────────────────────────────────────────
// 위임(= 공용 molecules/Table 이 한다): 표 렌더(머리글·행·셀), 페이지네이션, 빈 상태,
//   로딩, 행 클릭. **표의 픽셀은 여기서 한 줄도 그리지 않는다** — 예전엔 자체 <table> 을
//   그려서 모델·배포의 하우스 표와 시각이 갈렸고, 페이지네이션도 없었다.
// 소유(= 이 컴포넌트가 한다): 정렬 레벨 스택, 열별 비교 함수, 정렬 칩, 그룹 경계.
//
// react-data-table-component 는 정렬 축이 하나뿐이라(sortColumn 한 개) 다중 레벨을 담을 수
// 없다. 그래서 공용 Table 의 `sortServer` 를 켜서 **DataTable 의 자체 정렬을 끄고**(헤더
// 클릭만 `onChangeSort(column, dir)` 로 통지받는다) 정렬은 우리가 해서 `data` 로 넘긴다.
// 클릭한 열은 `column.selector` 로 식별되므로 selector 에 우리 `key` 를 싣는다.
//
// columns: [{ key, label, align?: 'right', sortable?: boolean, categorical?: boolean,
//             defaultDir?: 'asc'|'desc', compare?: (a, b) => number, render?: (row) => node,
//             groupValue?: (row) => any }]
// baseCompare: 정렬 레벨이 하나도 없을 때(레벨 0)의 비교 함수 — 기본 정렬.
const MultiSortTable = ({
  columns,
  rows,
  rowKey,
  baseCompare,
  baseSortLabel,
  onRowClick,
  emptyText,
  minWidth = '760px',
}) => {
  const { t } = useTranslation();
  const [sort, setSort] = useState([]); // [{ key, dir }] — 배열 순서 = 정렬 레벨

  const columnMap = useMemo(
    () => Object.fromEntries(columns.map((c) => [c.key, c])),
    [columns],
  );

  const toggleSort = useCallback(
    (key) => {
      setSort((prev) => {
        const at = prev.findIndex((level) => level.key === key);
        if (at < 0) {
          return [...prev, { key, dir: columnMap[key]?.defaultDir || 'asc' }];
        }
        return prev.map((level, i) =>
          i === at ? { key, dir: level.dir === 'asc' ? 'desc' : 'asc' } : level,
        );
      });
    },
    [columnMap],
  );

  const dropSort = useCallback((key) => {
    setSort((prev) => prev.filter((level) => level.key !== key));
  }, []);

  const resetSort = useCallback(() => setSort([]), []);

  // ── 행 키보드 활성화 ──────────────────────────────────────────────────────
  // 위임 대상인 react-data-table-component 는 행에 tabIndex 도 onKeyDown 도 달지 않는다
  // (라이브러리 소스 확인 — 유일한 tabIndex 는 정렬 헤더에 있다). 그런데 이 표는 행 클릭이
  // 결과 화면으로 들어가는 **유일한 길**이라(actions 열엔 중지·삭제뿐) 그대로 두면 키보드
  // 사용자가 결과에 닿을 수 없다. 자체 <table> 을 그리던 시절 tr 에 직접 달았던 것을,
  // 위임 구조에서는 렌더된 행 노드에 tabIndex 를 얹고 래퍼에서 키를 위임받아 되살린다.
  //
  // role 은 덮지 않는다 — 행의 암묵적 role='row' 를 유지해야 표 시맨틱(행·열 관계)이 남고,
  // role='button' 은 인터랙티브 자손을 가질 수 없는데 이 행 안에는 중지·삭제 버튼이 들어간다.
  // 포커스와 Enter/Space 활성화는 tabIndex + 키 위임으로 충분하다.
  const wrapRef = useRef(null);

  useEffect(() => {
    const root = wrapRef.current;
    if (!root || !onRowClick) return undefined;
    const mark = () => {
      root.querySelectorAll('.rdt_TableRow').forEach((el) => {
        if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '0');
      });
    };
    mark();
    // 정렬·페이지 이동은 행 노드를 통째로 갈아 끼우는데 그 시점을 이 컴포넌트가 알 수 없다
    // (페이지네이션은 공용 Table 안 DataTable 의 내부 상태다) → 관찰로 따라간다.
    const observer = new MutationObserver(mark);
    observer.observe(root, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [onRowClick]);

  const handleRowKeyDown = useCallback(
    (event) => {
      if (!onRowClick) return;
      if (event.key !== 'Enter' && event.key !== ' ') return;
      const row = event.target;
      // 행 자신에 포커스가 있을 때만 연다 — 행 안의 버튼(중지·삭제)에서 올라온 키는
      // 그 버튼의 것이지 행의 것이 아니다.
      if (!row?.classList?.contains('rdt_TableRow')) return;
      event.preventDefault(); // Space 의 기본 스크롤을 막는다
      // 데이터 인덱스를 되매핑하지 않고 마우스와 **같은 경로**를 태운다
      // (expandOnRowClicked → onRowExpandToggled → onRowClick).
      // ⚠️ 클릭 핸들러는 행이 아니라 **셀**에 달려 있다(실측: row.click() 은 아무 일도
      //    일어나지 않고 cell.click() 만 동작한다). 그래서 첫 셀에 합성한다 — 마지막
      //    actions 셀은 중지·삭제 버튼을 감싼 래퍼가 stopPropagation 을 걸어 두어 무효다.
      row.querySelector('.rdt_TableCell')?.click();
    },
    [onRowClick],
  );

  // DataTable 이 알려 주는 것은 "어느 열을 눌렀나"뿐이다 — 방향은 우리 레벨 스택이 정한다
  // (RDTC 의 sortDirection 은 축이 하나라 레벨 2 이상의 방향을 담지 못한다).
  const handleHeaderSort = useCallback(
    (column) => {
      const key = column?.selector;
      if (!key || !columnMap[key]) return;
      toggleSort(key);
    },
    [columnMap, toggleSort],
  );

  const sorted = useMemo(() => {
    const base = baseCompare || (() => 0);
    // 원본 배열을 건드리지 않는다 — 상위가 같은 배열을 다른 곳에서도 읽는다.
    return [...rows].sort((a, b) => {
      for (const { key, dir } of sort) {
        const compare = columnMap[key]?.compare;
        if (!compare) continue;
        const c = compare(a, b) * (dir === 'asc' ? 1 : -1);
        if (c) return c;
      }
      // 마지막 tiebreak — 레벨이 비었을 때의 기본 정렬이자, 레벨이 다 같을 때
      // 순서가 매 렌더 흔들리지 않게 하는 고정축이다.
      return base(a, b);
    });
  }, [rows, sort, columnMap, baseCompare]);

  // RDTC 는 행 키를 `row.id` 로 잡는다(keyField 기본값 'id'). 없으면 **배열 인덱스**로
  // 떨어져, 한 런이 여러 행이 되는 표에서 React 가 행을 잘못 재사용한다(다른 벤치마크의
  // 셀이 남는다). 공용 Table 이 keyField 를 열어 두지 않으므로 rowKey 를 id 로 실어 준다 —
  // 원본 행은 건드리지 않고 사본에 얹는다.
  const tableData = useMemo(
    () => sorted.map((row) => ({ ...row, id: rowKey(row) })),
    [sorted, rowKey],
  );

  // 선두의 범주형 레벨들이 그룹 경계를 만든다. 범주형이 아닌 레벨(점수·시각)을 만나면
  // 거기서 멈춘다 — 연속값은 값마다 경계가 생겨 선이 모든 행에 그어진다.
  const groupKeyOf = useCallback(
    (row) => {
      const lead = [];
      for (const { key } of sort) {
        const column = columnMap[key];
        if (!column?.categorical) break;
        lead.push(column);
      }
      if (!lead.length) return null;
      return lead
        .map((column) =>
          String(column.groupValue ? column.groupValue(row) : ''),
        )
        .join('|');
    },
    [sort, columnMap],
  );

  // 경계가 그어질 행(= 그룹의 첫 행)의 id 집합. 첫 행은 뺀다 — 머리글 헤어라인이
  // 이미 그 자리를 가르므로 선이 겹쳐 두 줄로 보인다.
  const groupStartIds = useMemo(() => {
    const ids = new Set();
    let prev = null;
    tableData.forEach((row, i) => {
      const key = groupKeyOf(row);
      if (key === null) return;
      if (i > 0 && key !== prev) ids.add(row.id);
      prev = key;
    });
    return ids;
  }, [tableData, groupKeyOf]);

  const conditionalRowStyles = useMemo(
    () =>
      groupStartIds.size
        ? [
            {
              when: (row) => groupStartIds.has(row.id),
              style: { borderTop: GROUP_BORDER_TOP },
            },
          ]
        : undefined,
    [groupStartIds],
  );

  // 열이 늘면 기본 폭에서 서로 붙는다. 표 자체의 최소 폭만 정하고 가로 스크롤은
  // DataTable 의 반응형 래퍼가 맡는다.
  const customStyles = useMemo(
    () => ({ table: { style: { minWidth } } }),
    [minWidth],
  );

  const tableColumns = useMemo(
    () =>
      columns.map((column) => {
        const at = sort.findIndex((level) => level.key === column.key);
        const on = at >= 0;
        return {
          // RDTC 가 "어느 열을 눌렀나"를 식별하는 키(sortColumn = column.selector)다.
          // 열마다 **유일한 문자열**이어야 한다 — 겹치면 서로 다른 열을 같은 열로 본다.
          selector: column.key,
          // 머리글 자체는 공용 Table 의 스타일을 그대로 쓴다. 여기에 얹는 것은 다중
          // 정렬에만 있는 표식(레벨 번호·방향)뿐이다.
          name: (
            <span className={cx('th-name', on && 'active')}>
              {column.label}
              {on && <span className={cx('level')}>{at + 1}</span>}
              {on && (
                <span className={cx('th-arrow')}>
                  {sort[at].dir === 'asc' ? '▲' : '▼'}
                </span>
              )}
            </span>
          ),
          // 비교 함수가 없는 열은 누를 수 있어도 정렬할 것이 없다.
          sortable: column.sortable !== false && !!column.compare,
          right: column.align === 'right',
          cell: (row) => (column.render ? column.render(row) : row[column.key]),
        };
      }),
    [columns, sort],
  );

  return (
    <div className={cx('multi-sort-table')}>
      {rows.length > 0 && (
        <div className={cx('sort-chips')}>
          <span className={cx('chips-label')}>{t('sort.label')}</span>
          {sort.length === 0 ? (
            <span className={cx('chip', 'chip-base')}>{baseSortLabel}</span>
          ) : (
            sort.map((level, i) => (
              <span key={level.key} className={cx('chip')}>
                <span className={cx('level')}>{i + 1}</span>
                {columnMap[level.key]?.label}
                <span className={cx('chip-dir')}>
                  {level.dir === 'asc' ? '▲' : '▼'}
                </span>
                <button
                  type='button'
                  className={cx('chip-x')}
                  title={t('sort.remove', {
                    column: columnMap[level.key]?.label,
                  })}
                  aria-label={t('sort.remove', {
                    column: columnMap[level.key]?.label,
                  })}
                  onClick={() => dropSort(level.key)}
                >
                  ✕
                </button>
              </span>
            ))
          )}
          {sort.length > 0 && (
            <button
              type='button'
              className={cx('chip-reset')}
              onClick={resetSort}
            >
              {t('sort.reset')}
            </button>
          )}
        </div>
      )}

      <div ref={wrapRef} onKeyDown={handleRowKeyDown}>
        <Table
          columns={tableColumns}
          data={tableData}
          // 공용 Table 은 loading 을 안 주면 "data 가 한 번 더 바뀔 때까지" 스피너를 띄우는
          // 자체 휴리스틱으로 떨어진다(모듈 전역 renderCount). 이 표는 상위가 프로젝트를
          // 다 받은 뒤에야 마운트되므로 그 조건이 영영 오지 않아 스피너에 갇힌다.
          loading={false}
          hideSearchBox
          selectableRows={false}
          onRowClick={onRowClick}
          noDataMessage={emptyText}
          customStyles={customStyles}
          conditionalRowStyles={conditionalRowStyles}
          // 자체 정렬을 끄고 헤더 클릭만 받는다(다중 레벨은 우리가 소유한다).
          sortServer
          onChangeSort={handleHeaderSort}
        />
      </div>
    </div>
  );
};

export default MultiSortTable;
