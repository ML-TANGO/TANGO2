import { useState, useMemo } from 'react';

// Components
import RadioBtnMenu from '@src/components/molecules/DropMenu/RadioBtnMenu';

/**
 * 라디오 버튼 로직과 컴포넌트를 함께 분리한 커스텀 훅
 * @param {Array<
 *    {
 *      name: string,
 *      options: Array<
 *        { label: string, value: any }
 *      >,
 *      checked: null | number,
 *    }
 *  >
 * } options
 *
 * @returns { [ Array<{ label: 'Activated', value: any }>, () => JSX.Element] }
 * @component
 * @example
 *
 * // 학습 목록 필터 옵션
 * const radioFilterList = useMemo(() => ([
 *   { name: 'activation.label', options: [ { label: '사용중', value: 'ACTIVATED' }, { label: '대기중', value: 'DEACTIVATED' } ], checked: null },
 *   { name: 'type.label', options: [ { label: 'Built-in', value: 'BUILT_IN' }, { label: 'Custom', value: 'CUSTOM' } ], checked: null },
 *   { name: 'Access.label', options: [ { label: '접근 가능', value: 'ACCESSIBLE' }, { label: '접근 불가능', value: 'INACCESSIBLE' } ], checked: null },
 * ]), []);
 *
 * // checkedFilter: 체크된 옵션 목록을 반환
 * // renderChecks: 초기 옵션 목록
 * const [checkedFilter, renderRadioBtn] = useRadioBtn(radioFilterList);
 *
 * return (
 *  <>
 *    {renderRadioBtn()}
 *  </>
 * )
 *
 *
 * -
 */
const useRadioBtn = (options) => {
  const [radioBtnList, setRadioBtnList] = useState(options);

  /**
   * 라디오 버튼 클릭 이벤트
   *
   * 클릭한 옵션의 인덱스 값을 해당 그룹 데이터의 checked에 설정
   *
   * @param {number} groupIndex 라디오 버튼 그룹 인덱스
   * @param {number} checkedIndex 라디오 버튼 그룹 안에 옵션 인덱스
   */
  const handleCheckList = (groupIndex, checkedIndex) => {
    const tmpList = [...radioBtnList];
    const prevCheckIndex = tmpList[groupIndex].checked;
    tmpList[groupIndex].checked =
      checkedIndex === prevCheckIndex ? null : checkedIndex;
    setRadioBtnList(tmpList);
  };

  /**
   * 라디오 버튼에 선택된 모든 값을 초기화 (checked 값을 초기화)
   */
  const clearAll = () => {
    const clearList = [...radioBtnList];

    for (let i = 0; i < clearList.length; i += 1) {
      clearList[i].checked = null;
    }
    setRadioBtnList(clearList);
  };

  /**
   * 라디오 버튼 메뉴 렌더링 함수
   * @returns {JSX.Element}
   */
  const renderRadioBtn = () => (
    <RadioBtnMenu
      options={radioBtnList}
      onChange={handleCheckList}
      clearAll={clearAll}
    />
  );

  /**
   * 라디오 버튼 옵션 중 선택된 값만 배열로 리턴
   * @returns {Array<{ label: string, value: any }>}
   */
  const checkedList = useMemo(() => {
    const list = [];
    for (let i = 0; i < radioBtnList.length; i += 1) {
      const { checked, options: opts } = radioBtnList[i];
      if (checked !== null) {
        const target = opts[checked];
        list.push(target);
      }
    }
    return list;
  }, [radioBtnList]);

  return [checkedList, renderRadioBtn];
};

export default useRadioBtn;
