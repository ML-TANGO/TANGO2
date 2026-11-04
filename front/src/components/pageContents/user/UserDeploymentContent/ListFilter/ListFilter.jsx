// Icon
import DeploymentIcon from '@src/static/images/icon/icon-deployments-gray.svg';
import { useEffect, useMemo, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { useResizeDetector } from 'react-resize-detector';
import { useHistory /* useRouteMatch */ } from 'react-router-dom';

import Button from '@src/components/atoms/button/Button';
import TextInput from '@src/components/atoms/input/TextInput';
// Components
import PageTitle from '@src/components/atoms/PageTitle';
import DropMenu from '@src/components/molecules/DropMenu';

import { closePopup, openPopup } from '@src/store/modules/popup';
// Custom Hooks
import useRadioBtn from '@src/hooks/useRadioBtn';

// import TemplateIcon from '@src/static/images/icon/icon-template-gray.svg';

// CSS Module
import classNames from 'classnames/bind';
import style from './ListFilter.module.scss';

const cx = classNames.bind(style);

const LAPTOP = 'LAPTOP';
const TABLET = 'TABLET';
const MOBILE_L = 'MOBILE_L';
const MOBILE_M = 'MOBILE_M';
// const TEMPLATE_TAB = 'TEMPLATE_TAB';

let timer;
/**
 * 배포 목록 필터
 * @param {{
 *  watchFilterViewType: () => {},
 * }}
 * @component
 * @example
 *
 * return (
 *  <ListFilter />
 * )
 *
 *
 * -
 */
function ListFilter({ watchFilterViewType, openCreateApiCodeModal }) {
  const { t } = useTranslation();

  const dispatch = useDispatch();
  const isPopupOpen = useSelector(({ popup }) => popup);

  // Router Hooks
  const history = useHistory();
  const { action } = history;

  // Component State
  const [search, setSearch] = useState(
    (() => {
      const searchKeyword = sessionStorage.getItem('deployment-search');
      if (action === 'POP' && searchKeyword) {
        sessionStorage.removeItem('deployment-search');
        return searchKeyword;
      }
      return '';
    })(),
  ); // 검색 창 입력 값
  const [searchText, setSearchText] = useState(
    (() => {
      const searchKeyword = sessionStorage.getItem('deployment-search');
      if (action === 'POP' && searchKeyword) {
        sessionStorage.removeItem('deployment-search');
        return searchKeyword;
      }
      return '';
    })(),
  ); // 실제 목록 필터링을 위한 마지막에 최종 입력한 텍스트 값
  const [responsiveMode, setResponsiveMode] = useState(LAPTOP); // 넓이 사이즈를 감지하여 현재 넓이에 맞는 값 설정

  // 배포 목록 필터 옵션

  /**
   * 배포 상세 페이지에서 뒤로가기를 통해 접근할 때(action이 POP이면)
   *
   * 이전에 저장된 필터(sessionStorage에 deployment-filter가 존재하면)가 있으면
   *
   * 이전 필터 정보를 파싱하여 필터의 초기값으로 넘긴다.
   */
  const radioFilterList = useMemo(() => {
    // 이전 필터 정보
    let prevFilter = sessionStorage.getItem('deployment-filter');

    // 필터 초기값
    const originData = [
      {
        name: 'status.label',
        options: [
          { label: 'activated.label', value: 'ACTIVATED' },
          { label: 'deactivatedWaiting.label', value: 'DEACTIVATED' },
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

    // 이전 필터가 존재하면서 배포 상세 페이지에서 뒤로가기로 접근한 경우
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
      sessionStorage.removeItem('deployment-filter');
      return newRadioBtnList;
    }
    // 필터 정보가 없으면 초기값 그대로 설정
    return originData;
  }, [action]);

  // Custom Hooks
  const [checkedRadioFilter, renderRadioBtn] = useRadioBtn(radioFilterList);

  const filterPopupHandler = (e) => {
    if (e) e.stopPropagation();
    if (isPopupOpen['deployment/filter'] === true) {
      dispatch(closePopup('deployment/filter'));
    } else {
      dispatch(openPopup('deployment/filter'));
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

  // 검색 입력 Event
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

  // Lifecycle
  // 필터 감지
  useEffect(() => {
    watchFilterViewType({ filter: checkedRadioFilter });
  }, [checkedRadioFilter, watchFilterViewType]);

  // 키워드 검색 감지
  useEffect(() => {
    watchFilterViewType({ search: searchText });
  }, [searchText, watchFilterViewType]);

  useEffect(() => {
    return () => {
      // 배포 목록 페이지에서 상세 페이지로 이동할 때
      // 현재 필터 정보를 sessionStorage에 저장한다.
      if (action === 'POP') {
        sessionStorage.setItem(
          'deployment-filter',
          JSON.stringify(checkedRadioFilter),
        );
        sessionStorage.setItem('deployment-search', search);
      } else {
        sessionStorage.removeItem('deployment-filter');
        sessionStorage.removeItem('deployment-search');
        sessionStorage.removeItem('deployment-list-view');
      }
    };
  }, [checkedRadioFilter, search, action]);

  return (
    <div className={cx('list-filter')}>
      <PageTitle>{t('Deployment')}</PageTitle>
      <div className={cx('filter-wrap')} ref={ref}>
        {/* API code create */}
        <button
          onClick={openCreateApiCodeModal}
          className={cx('api-create-btn')}
        >
          {t('createDeploymentApiCode.label')}
        </button>
        {/* <div className={cx('divider')}></div> */}
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
          customStyle={{
            width: '310px',
          }}
        />
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
          menuRender={() => renderRadioBtn()}
          align='RIGHT'
        />
      </div>
    </div>
  );
}

export default ListFilter;
