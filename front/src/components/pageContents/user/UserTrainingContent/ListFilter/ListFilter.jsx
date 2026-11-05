import { useEffect, useMemo, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { useResizeDetector } from 'react-resize-detector';
import { useHistory } from 'react-router-dom';

import Button from '@src/components/atoms/button/Button';
import TextInput from '@src/components/atoms/input/TextInput';
// Atoms
import PageTitle from '@src/components/atoms/PageTitle';
// Molecules
import DropMenu from '@src/components/molecules/DropMenu/DropMenu2';

import { closePopup, openPopup } from '@src/store/modules/popup';
import useRadioBtn from '@src/hooks/useRadioBtn';
// Custom Hooks
import useSelect from '@src/hooks/useSelect';

// CSS Module
import classNames from 'classnames/bind';
import style from './ListFilter.module.scss';

const cx = classNames.bind(style);

const LAPTOP = 'LAPTOP';
const TABLET = 'TABLET';
const MOBILE_L = 'MOBILE_L';
const MOBILE_M = 'MOBILE_M';

let timer;
/**
 * 학습 목록 필터
 * @param {{
 *  watchFilterViewType: () => {},
 *  selectedViewType: 'CARD_VIEW' | 'TABLE_VIEW',
 *  onCreate: function, // TABLE_VIEW 일때 생성 버튼 사용
 * }}
 * @component
 * @example
 *
 * return (
 *  <ListFilter />
 * )
 *
 * -
 */
function ListFilter({ watchFilterViewType, selectedViewType, onCreate }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  // Router Hooks
  const history = useHistory();
  const { action } = history;

  const isPopupOpen = useSelector(({ popup }) => popup);

  // Component State
  const [search, setSearch] = useState(
    (() => {
      const searchKeyword = sessionStorage.getItem('training-search');
      if (action === 'POP' && searchKeyword) {
        sessionStorage.removeItem('training-search');
        return searchKeyword;
      }
      return '';
    })(),
  ); // 검색 창 입력 값
  const [searchText, setSearchText] = useState(
    (() => {
      const searchKeyword = sessionStorage.getItem('training-search');
      if (action === 'POP' && searchKeyword) {
        sessionStorage.removeItem('training-search');
        return searchKeyword;
      }
      return '';
    })(),
  ); // 실제 목록 필터링을 위한 마지막에 최종 입력한 텍스트 값
  const [responsiveMode, setResponsiveMode] = useState(LAPTOP); // 너비 사이즈를 감지하여 현재 너비에 맞는 값 설정

  // 학습 목록 뷰타입 옵션
  const viewTypeList = useMemo(() => {
    let target = sessionStorage.getItem('training-list-view');

    const originData = [
      {
        name: 'gallery.label',
        value: 'CARD_VIEW',
        iconPath: '/images/icon/00-ic-basic-gallery.svg',
      },
      {
        name: 'table.label',
        value: 'TABLE_VIEW',
        iconPath: '/images/icon/00-ic-basic-list.svg',
      },
    ];

    if (target && (action === 'POP' || action === 'PUSH')) {
      target = JSON.parse(target);
      return originData.map((v) => ({
        ...v,
        selected: v.value === target.value,
      }));
    }
    return originData;
  }, [action]);

  // 학습 목록 필터 옵션

  /**
   * 학습 상세 페이지에서 뒤로가기를 통해 접근할 때(action이 POP이면)
   *
   * 이전에 저장된 필터(sessionStorage에 training-filter가 존재하면)가 있으면
   *
   * 이전 필터 정보를 파싱하여 필터의 초기값으로 넘긴다.
   */
  const radioFilterList = useMemo(() => {
    // 이전 필터 정보
    let prevFilter = sessionStorage.getItem('training-filter');

    // 필터 초기값
    const originData = [
      {
        name: 'status.label',
        options: [
          { label: 'activated.label', value: 'ACTIVATED' },
          { label: 'deactivated.label', value: 'DEACTIVATED' },
        ],
        checked: null,
      },
      // {
      //   name: 'type.label',
      //   options: [
      //     { label: 'Built-in', value: 'BUILT_IN' },
      //     { label: 'Custom', value: 'CUSTOM' },
      //   ],
      //   checked: null,
      // },
      {
        name: 'access.label',
        options: [
          { label: 'accessible.label', value: 'ACCESSIBLE' },
          { label: 'inaccessible.label', value: 'INACCESSIBLE' },
        ],
        checked: null,
      },
    ];

    // 이전 필터가 존재하면서 학습 상세 페이지에서 뒤로가기로 접근한 경우
    if (prevFilter && action === 'POP') {
      // 이전 필터 정보 파싱하여 초기값으로 설정
      prevFilter = JSON.parse(prevFilter);
      const newRadioBtnList = originData.map((g) => {
        const { options: opts } = g;
        let checkedTarget = null;
        for (let i = 0; i < opts.length; i += 1) {
          const opt = opts[i];
          for (let j = 0; j < prevFilter.length; j += 1) {
            if (opt.value === prevFilter[j].value) {
              checkedTarget = i;
              break;
            }
          }
          if (checkedTarget !== null) break;
        }
        return { ...g, checked: checkedTarget };
      });
      sessionStorage.removeItem('training-filter');
      return newRadioBtnList;
    }
    // 필터 정보가 없으면 초기값 그대로 설정
    return originData;
  }, [action]);

  // Custom Hooks
  const [selectedItem, renderSelectList] = useSelect(viewTypeList);
  const [checkedRadioFilter, renderRadioBtn] = useRadioBtn(radioFilterList);
  const [isFilterPopupOpen, setIsFilterPopupOpen] = useState(false);

  const filterPopupHandler = (e) => {
    if (e) e.stopPropagation();
    const prev = isFilterPopupOpen;
    setIsFilterPopupOpen((prev) => !prev);

    if (prev) {
      closePopup('training/filter');
    } else {
      openPopup('training/filter');
    }
  };

  const cardViewPopupHandler = (e) => {
    if (e) e.stopPropagation();
    if (isPopupOpen['training/cardView'] === true) {
      dispatch(closePopup('training/cardView'));
    } else {
      dispatch(openPopup('training/cardView'));
    }
  };

  // Resize Sensor Hooks
  const { ref } = useResizeDetector({
    onResize: (w) => {
      let mode = LAPTOP;
      if (w > 768) {
        mode = LAPTOP;
      } else if (w <= 768 && w > 425) {
        mode = TABLET;
      } else if (w <= 425 && w > 320) {
        mode = MOBILE_L;
      } else {
        mode = MOBILE_M;
      }
      setResponsiveMode(mode);
    },
  });

  // Event
  const inputHandler = (e) => {
    const { value } = e.target;
    if (timer) {
      clearTimeout(timer);
    }

    timer = setTimeout(() => {
      setSearchText(value);
    }, 500);

    setSearch(value);
  };

  // 필터 감지
  useEffect(() => {
    watchFilterViewType({ filter: checkedRadioFilter });
  }, [checkedRadioFilter, watchFilterViewType]);

  // 뷰타입 변경 감지
  useEffect(() => {
    watchFilterViewType({ viewType: selectedItem });
  }, [selectedItem, watchFilterViewType]);

  // 키워드 검색 감지
  useEffect(() => {
    watchFilterViewType({ search: searchText });
  }, [searchText, watchFilterViewType]);

  useEffect(() => {
    return () => {
      // 학습 목록 페이지에서 다른 페이지로 이동할 때
      // 현재 필터 정보를 sessionStorage에 저장한다.
      if (action === 'POP' || action === 'PUSH') {
        sessionStorage.setItem(
          'training-filter',
          JSON.stringify(checkedRadioFilter),
        );
        sessionStorage.setItem('training-search', search);
        sessionStorage.setItem(
          'training-list-view',
          JSON.stringify(selectedItem),
        );
      }
    };
  }, [selectedItem, checkedRadioFilter, search, action]);

  return (
    <div className={cx('list-filter')}>
      <PageTitle>{t('training.label')}</PageTitle>
      <div className={cx('filter-wrap')} ref={ref}>
        {selectedViewType === 'TABLE_VIEW' && (
          <>
            <Button type='primary' onClick={onCreate}>
              {t('createTraining.label')}
            </Button>
            <div className={cx('divider')}></div>
          </>
        )}
        {/* Search */}
        <TextInput
          value={search}
          onChange={inputHandler}
          leftIconPath='/images/icon/ic-search.svg'
          responsiveMode={
            responsiveMode === TABLET ||
            responsiveMode === MOBILE_L ||
            responsiveMode === MOBILE_M
          }
          placeholder={t('search.placeholder')}
        />
        {/* Filter */}
        <DropMenu
          btnRender={() => (
            <Button
              type={checkedRadioFilter.length > 0 ? 'primary' : 'gray'}
              size='medium'
              rightIcon={`/images/icon/00-ic-basic-filter${
                checkedRadioFilter.length > 0 ? '-white' : ''
              }.svg`}
              responsiveMode={
                responsiveMode === TABLET ||
                responsiveMode === MOBILE_L ||
                responsiveMode === MOBILE_M
              }
            >
              {t('filter.label')}
            </Button>
          )}
          isOpen={isFilterPopupOpen}
          popupHandler={filterPopupHandler}
          menuRender={() => renderRadioBtn()}
          align='RIGHT'
        />
        {/* ViewType */}
        {/* <DropMenu
          type='cardView'
          btnRender={() => (
            <Button
              type='gray'
              size='medium'
              rightIcon={
                selectedItem.value === 'CARD_VIEW'
                  ? '/images/icon/00-ic-basic-gallery.svg'
                  : '/images/icon/00-ic-basic-list.svg'
              }
              responsiveMode={
                responsiveMode === TABLET ||
                responsiveMode === MOBILE_L ||
                responsiveMode === MOBILE_M
              }
            >
              {selectedItem.value === 'CARD_VIEW'
                ? t('gallery.label')
                : t('table.label')}
            </Button>
          )}
          popupHandler={cardViewPopupHandler}
          menuRender={() => renderSelectList(cardViewPopupHandler)}
          isOpen={isPopupOpen['training/cardView']}
          align='RIGHT'
        /> */}
      </div>
    </div>
  );
}

export default ListFilter;
