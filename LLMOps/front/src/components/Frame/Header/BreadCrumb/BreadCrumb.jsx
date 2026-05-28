import ArrowIcon from '@src/static/images/icon/00-ic-basic-arrow-02-up-white.svg';
import PathIcon from '@src/static/images/icon/00-path-icon.svg';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSelector } from 'react-redux';
import { useHistory, useLocation, useRouteMatch } from 'react-router-dom';

import useOutsideClick from '@src/hooks/useOutsideClick';

// CSS Module
import classNames from 'classnames/bind';
import style from './BreadCrumb.module.scss';

const cx = classNames.bind(style);

const calHomePath = (pathname) => {
  if (pathname.includes('selected')) return null;
  const isLLM = pathname.includes('llm');
  return isLLM ? 'llm' : 'flightbase';
};

function BreadCrumb() {
  const { t } = useTranslation();

  const history = useHistory();
  const match = useRouteMatch();
  const location = useLocation();
  const homePathValue = calHomePath(location.pathname);

  const [isOpen, setIsOpen] = useState(false);

  // Redux hooks
  let breadCrumbState = useSelector((state) => state.breadCrumb);
  // 워크스페이스 이름 표시용
  const { workspaceState } = useSelector((state) => ({
    workspaceState: state.workspace,
  }));

  const workspaces = workspaceState?.workspaces || [];
  const { id: workspaceId } = match.params;
  let selectedWs;
  workspaces.map(({ name: label, id: value, favorites, status }) => {
    const wItem = { label, value, favorites, status };
    if (Number(workspaceId) === value) {
      selectedWs = wItem;
    }
    return wItem;
  });

  const workspaceList = workspaces.map(
    ({ name: label, id: value, favorites, status, manager }) => {
      const wItem = { label, value, favorites, status, manager };
      if (Number(workspaceId) === value) {
        selectedWs = wItem;
      }
      return wItem;
    },
  );

  if (!Array.isArray(breadCrumbState)) {
    breadCrumbState = [];
  }

  const handleDropdown = (value) => {
    const newPath = `/user/workspace/${value}/home`;
    history.push(newPath);
    setIsOpen(false);
  };

  const { ref } = useOutsideClick(() => {
    setIsOpen(false);
  });

  return (
    <>
      <div
        className={cx(
          'path-wrap',
          breadCrumbState.length < 3 ? 'short' : 'long',
        )}
      >
        {selectedWs && (
          <div className={cx('path-wrapper')}>
            <div className={cx('dropdown-wrapper')}>
              <img src={PathIcon} alt='path-icon' />
              <span>현재 워크스페이스</span>
              <div className={cx('dropdown-cont')} ref={ref}>
                <div className={cx('select-cont')}>{selectedWs.label}</div>
                <button
                  className={cx('dropdown-btn')}
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsOpen((prev) => !prev);
                  }}
                >
                  <img
                    className={cx('arrow-img', isOpen && 'reverse')}
                    src={ArrowIcon}
                    alt='arrow'
                  />
                </button>
                {isOpen && (
                  <ul className={cx('workspace-list')}>
                    {workspaceList.map((info) => {
                      const { label, manager, value } = info;
                      return (
                        <li
                          key={value}
                          className={cx('workspace-item')}
                          onClick={() => handleDropdown(value)}
                        >
                          <span>{label}</span>
                          <span>{manager}</span>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export default BreadCrumb;
