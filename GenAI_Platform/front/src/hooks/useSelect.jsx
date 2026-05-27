import { useState } from 'react';

// Molecules
import SelectMenu from '@src/components/molecules/DropMenu/SelectMenu';
/**
 * 아이템 선택 로직과 컴포넌트를 함께 분리한 커스텀 훅
 * @param {[ { name: 'Activated', iconPath: 'image-url' } ]} options
 *
 * @returns { [[ { name: 'Activated', iconPath: 'image-url', checked: true } ], () => JSX.Element] }
 * @component
 * @example
 *
 * const optionList = [
 *  { name: 'Gallery', iconPath: '/images/icon/00-ic-basic-filter.svg' },
 *  { name: 'Table', iconPath: '/images/icon/00-ic-basic-filter.svg' },
 * ];
 *
 * // selectedItem: 선택된 옵션 반환
 * // renderSelectList: 초기 옵션 목록
 * const [selectedItem, renderSelectList] = useSelect(optionList);
 *
 * return (
 *  <>
 *    {renderSelectList()}
 *  </>
 * )
 *
 *
 * -
 */
const useSelect = (options) => {
  const isSelected = options.filter(({ selected }) => selected).length > 0;
  const [optionList, setOptionList] = useState(
    !isSelected
      ? options.map((option, i) => ({ ...option, selected: i === 0 }))
      : options,
  );

  // 체크박스 클릭 이벤트
  const handleOptionList = (index) => {
    const tmpOptionList = optionList.map((option) => ({
      ...option,
      selected: false,
    }));
    tmpOptionList[index].selected = true;
    setOptionList(tmpOptionList);
  };

  const renderSelectList = (popupHandler) => (
    <SelectMenu
      optionList={optionList}
      onChange={(index) => {
        handleOptionList(index);
        popupHandler();
      }}
    />
  );

  return [optionList.filter(({ selected }) => selected)[0], renderSelectList];
};

export default useSelect;
