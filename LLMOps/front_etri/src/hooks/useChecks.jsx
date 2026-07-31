import { useState, useMemo } from 'react';

// Components
import SwitchFilterMenu from '@src/components/molecules/DropMenu/SwitchFilterMenu';

/**
 * 체크박스 로직과 컴포넌트를 함께 분리한 커스텀 훅
 * @param {[ { name: 'Activated', iconPath: 'image-url', value: any } ]} checks
 *
 * @returns { [[ { name: 'Activated', iconPath: 'image-url', checked: true } ], () => JSX.Element] }
 * @component
 * @example
 *
 * const checkList = [
 *  { name: 'Activated', iconPath: '/images/icon/00-ic-basic-filter.svg' },
 *  { name: 'Show hiddens', iconPath: '/images/icon/00-ic-basic-filter.svg' },
 *  { name: 'Built-in only', iconPath: '/images/icon/00-ic-basic-filter.svg' },
 * ];
 *
 * // checkedFilter: 체크된 옵션 목록을 반환
 * // renderChecks: 초기 옵션 목록
 * const [checkedFilter, renderChecks] = useChecks(checkList);
 *
 * return (
 *  <>
 *    {renderChecks()}
 *  </>
 * )
 *
 *
 * -
 */
const useChecks = (checks) => {
  const [checkList, setCheckList] = useState(
    checks.map((check) => ({ ...check, checked: false })),
  );

  // 체크박스 클릭 이벤트
  const handleCheckList = (index, prevChecked) => {
    const tmpCheckList = [...checkList];
    tmpCheckList[index].checked = !prevChecked;
    setCheckList(tmpCheckList);
  };

  const renderChecks = () => (
    <SwitchFilterMenu filterList={checkList} onChange={handleCheckList} />
  );

  const checkedList = useMemo(
    () => checkList.filter(({ checked }) => checked),
    [checks, checkList],
  );

  return [checkedList, renderChecks];
};

export default useChecks;
