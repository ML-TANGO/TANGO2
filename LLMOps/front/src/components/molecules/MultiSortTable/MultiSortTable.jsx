import { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import EmptyBox from '@src/components/molecules/EmptyBox';

import classNames from 'classnames/bind';
import style from './MultiSortTable.module.scss';

const cx = classNames.bind(style);

// 헤더를 누른 "순서"가 곧 정렬 레벨인 표.
//   - 처음 누른 열 = 1차, 그다음 = 2차 … 이미 잡힌 열을 다시 누르면 방향만 뒤집는다.
//   - 표 위 칩이 현재 레벨을 그대로 보여주고, 칩의 ✕ 로 레벨 하나만 뺄 수 있다.
//   - 선두 레벨이 범주형(categorical)이면 값이 바뀌는 자리에 그룹 경계선을 긋는다.
// react-data-table-component(BorderTable) 는 정렬 축이 하나뿐이라(onSort(column,dir))
// 이 규약을 담을 수 없어 별도 컴포넌트로 둔다. 여러 화면이 같은 규약을 쓸 수 있게
// 열 정의(compare/render)만 주입받고 정렬 상태·머리글·칩은 이 컴포넌트가 소유한다.
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
          i === at
            ? { key, dir: level.dir === 'asc' ? 'desc' : 'asc' }
            : level,
        );
      });
    },
    [columnMap],
  );

  const dropSort = useCallback((key) => {
    setSort((prev) => prev.filter((level) => level.key !== key));
  }, []);

  const resetSort = useCallback(() => setSort([]), []);

  // 행 열기가 마우스 전용이면 키보드 사용자는 결과 화면에 들어갈 방법이 없다.
  // onRowClick 이 있는 행만 Tab 으로 닿게 하고 Enter/Space 로 연다.
  const handleRowKeyDown = useCallback(
    (event, row) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      // 행 안의 버튼(중지·삭제 등)에서 올라온 키는 그 버튼의 것이다 — 행까지 열지 않는다.
      if (event.target !== event.currentTarget) return;
      event.preventDefault(); // Space 의 기본 스크롤을 막는다
      onRowClick(row);
    },
    [onRowClick],
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

  if (!rows.length) {
    return (
      <EmptyBox text={emptyText} isBox customStyle={{ height: '120px' }} />
    );
  }

  return (
    <div className={cx('multi-sort-table')}>
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

      <div className={cx('table-scroll')}>
        <table className={cx('table')} style={{ minWidth }}>
          <thead>
            <tr>
              {columns.map((column) => {
                const at = sort.findIndex((level) => level.key === column.key);
                const on = at >= 0;
                if (column.sortable === false) {
                  return (
                    <th
                      key={column.key}
                      className={cx(column.align === 'right' && 'right')}
                    >
                      <span className={cx('th-static')}>{column.label}</span>
                    </th>
                  );
                }
                return (
                  <th
                    key={column.key}
                    className={cx(column.align === 'right' && 'right')}
                    aria-sort={
                      on
                        ? sort[at].dir === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                    }
                  >
                    <button
                      type='button'
                      className={cx('th-btn', on && 'active')}
                      aria-label={t('sort.by', { column: column.label })}
                      onClick={() => toggleSort(column.key)}
                    >
                      {column.label}
                      {on && <span className={cx('level')}>{at + 1}</span>}
                      <span className={cx('th-arrow')}>
                        {on && sort[at].dir === 'asc' ? '▲' : '▼'}
                      </span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => {
              const groupKey = groupKeyOf(row);
              const groupStart =
                groupKey !== null &&
                (i === 0 || groupKeyOf(sorted[i - 1]) !== groupKey);
              return (
                <tr
                  key={rowKey(row)}
                  className={cx(
                    groupStart && 'group-start',
                    onRowClick && 'clickable',
                  )}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  onKeyDown={
                    onRowClick
                      ? (event) => handleRowKeyDown(event, row)
                      : undefined
                  }
                  // role 을 덮지 않는다 — tr 의 암묵적 role='row' 를 유지해야 표
                  // 시맨틱(행·열 관계)이 남고, 무엇보다 role='button' 은 인터랙티브
                  // 자손을 가질 수 없는데 이 행 안에는 중지·삭제 버튼이 들어간다.
                  // 포커스와 Enter/Space 활성화는 tabIndex+onKeyDown 으로 충분하다.
                  tabIndex={onRowClick ? 0 : undefined}
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cx(column.align === 'right' && 'right')}
                    >
                      {column.render ? column.render(row) : row[column.key]}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default MultiSortTable;
