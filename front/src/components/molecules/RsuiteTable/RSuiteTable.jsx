import { useState } from 'react';

// Components
import { Table } from 'rsuite';

import 'rsuite-table/dist/css/rsuite-table.css';
import './RSuiteTable.scss';

const { Column, HeaderCell, Cell, Pagination } = Table;

function RSuiteTable({ data = [], columns = [] }) {
  const [displayLength, setDisplayLength] = useState(10);
  const [page, setPage] = useState(1);
  const [sortColumn, setSortColumn] = useState();
  const [sortType, setSortType] = useState();

  const handleChangePage = (p) => {
    setPage(p);
  };
  const handleChangeLength = (l) => {
    setPage(1);
    setDisplayLength(l);
  };

  const handleSortColumn = (sortColumn, sortType) => {
    setSortColumn(sortColumn);
    setSortType(sortType);
  };

  const filterByLength = (d) => {
    return d.filter((_, i) => {
      const start = displayLength * (page - 1);
      const end = start + displayLength;
      return i >= start && i < end;
    });
  };

  const sortByColumn = (d) => {
    if (sortColumn && sortType) {
      const collator = new Intl.Collator('en', {
        numeric: true,
        sensitivity: 'base',
      });
      return d.sort((a, b) => {
        let x = a[sortColumn];
        let y = b[sortColumn];
        if (sortType === 'asc') {
          return collator.compare(x, y);
        } else {
          return collator.compare(y, x);
        }
      });
    }
    return d;
  };

  const filteredList = sortByColumn(filterByLength(data));

  return (
    <div>
      <Table
        data={filteredList}
        virtualized
        autoHeight
        sortColumn={sortColumn}
        sortType={sortType}
        onSortColumn={handleSortColumn}
      >
        {columns.map(
          (
            { label, dataKey, sortable, fixed, resizable, width, render },
            key,
          ) => (
            <Column
              width={width}
              sortable={sortable}
              fixed={fixed}
              resizable={resizable}
              key={key}
            >
              <HeaderCell>{label}</HeaderCell>
              {render ? (
                <Cell dataKey={dataKey}>{(rowData) => render(rowData)}</Cell>
              ) : (
                <Cell dataKey={dataKey} />
              )}
            </Column>
          ),
        )}
      </Table>
      <Pagination
        lengthMenu={[
          {
            value: 5,
            label: 5,
          },
          {
            value: 10,
            label: 10,
          },
          {
            value: 20,
            label: 20,
          },
          {
            value: 50,
            label: 50,
          },
          {
            value: 100,
            label: 100,
          },
        ]}
        activePage={page}
        displayLength={displayLength}
        total={data.length}
        onChangePage={handleChangePage}
        onChangeLength={handleChangeLength}
      />
    </div>
  );
}

export default RSuiteTable;
