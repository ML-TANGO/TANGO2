import { useCallback } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { connect, useDispatch } from 'react-redux';

import { openModal } from '@src/store/modules/modal';

// Components
import Card from './Card';

import classNames from 'classnames/bind';
// CSS module
import style from './UserDashboardContent.module.scss';

const cx = classNames.bind(style);

function UserDashboardContent({
  data,
  onRefresh,
  moveWorkspace,
  nav: { isExpand },
  serverError,
  auth: { userName, jpUserName },
  getDashboardData,
}) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const onClickWorkspaceBtn = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'CREATE_WORKSPACE',
        modalData: {
          submit: {
            text: 'create.label',
            func: () => {
              getDashboardData();
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
          workspaceListData: data,
          createRequest: true,
        },
      }),
    );
  }, [t, dispatch, getDashboardData, data]);

  const onClickWorkspaceEditBtn = useCallback(
    (id) => {
      dispatch(
        openModal({
          modalType: 'EDIT_WORKSPACE',
          modalData: {
            submit: {
              text: 'edit.label',
              func: () => {
                getDashboardData();
              },
            },
            cancel: {
              text: 'cancel.label',
            },
            data: data.filter((info) => info.id === Number(id))[0],
            workspaceListData: data,
          },
        }),
      );
    },
    [dispatch, data, getDashboardData],
  );

  const workspaceList = data.map((list, index) => {
    return (
      <Card
        key={index}
        data={list}
        edit={true}
        moveWorkspace={moveWorkspace}
        onRefresh={onRefresh}
        onClickWorkspaceEditBtn={() => onClickWorkspaceEditBtn(list.id)}
        getDashboardData={getDashboardData}
      />
    );
  });

  return (
    <div id='UserDashboardContent' className={cx('dashboard')}>
      <div className={cx('header', isExpand && 'expand')}>
        <h1 className={cx('welcome')}>
          {t('welcomeBack.message')} {jpUserName || userName}
          {t('sir.label')}!
        </h1>
      </div>
      <div className={cx('content')}>
        {serverError ? (
          <div className={cx('no-response')}>{t('noResponse.message')}</div>
        ) : (
          <div className={cx('card-box')} data-testid='user-dashboard-ws-list'>
            <div
              className={cx('create-card-btn')}
              onClick={onClickWorkspaceBtn}
            >
              <div className={cx('flex-cont')}>
                <svg
                  xmlns='http://www.w3.org/2000/svg'
                  width='80'
                  height='80'
                  viewBox='0 0 80 80'
                  fill='none'
                >
                  <rect x='39' width='2' height='80' rx='1' fill='#2D76F8' />
                  <rect
                    y='41'
                    width='2'
                    height='80'
                    rx='1'
                    transform='rotate(-90 0 41)'
                    fill='#2D76F8'
                  />
                </svg>
                <span>
                  {t('workspace')}
                  <br />
                  {t('create.request.btn')}
                </span>
              </div>
            </div>
            {workspaceList}
          </div>
        )}
      </div>
    </div>
  );
}

export default connect(({ nav, auth }) => ({ nav, auth }))(
  UserDashboardContent,
);
