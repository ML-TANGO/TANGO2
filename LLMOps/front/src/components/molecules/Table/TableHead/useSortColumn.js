import { useEffect, useState } from 'react';
import _ from 'lodash';

function useSortColumn(count) {
  const [sortClickFlag, setSortClickFlag] = useState([]);
  const [clickedIdx, setClickedIdx] = useState();
  const onClickHandler = (num, sortDirection) => {
    const temp = _.cloneDeep(sortClickFlag);
    temp.forEach((item, idx) => {
      if (idx === num) {
        if (sortDirection === 'desc') {
          temp[idx] = false;
        } else temp[idx] = true;
      } else temp[idx] = undefined;
    });
    setSortClickFlag(temp);
  };

  const clickedIdxHandler = (idx) => {
    setClickedIdx(idx);
  };

  useEffect(() => {
    setSortClickFlag(Array.from(Array(count)).fill(undefined));
  }, [count]);

  return { onClickHandler, sortClickFlag, clickedIdx, clickedIdxHandler };
}
export default useSortColumn;
