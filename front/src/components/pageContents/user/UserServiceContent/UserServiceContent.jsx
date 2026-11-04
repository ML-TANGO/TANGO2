// i18n

// Components
import { Selectbox } from '@jonathan/ui-react';

import { useTranslation } from 'react-i18next';

import PageTitle from '@src/components/atoms/PageTitle';
import FBLoading from '@src/components/organisms/FBLoading';

import DeferredComponent from '@src/hooks/useDeferredComponent';

import Card from './Card';

import classNames from 'classnames/bind';
// CSS module
import style from './UserServiceContent.module.scss';

const cx = classNames.bind(style);

const deploymentTypeOptions = [
  { label: 'all.label', value: 'all' },
  {
    label: 'Built-in',
    value: 'built-in',
    icon: [
      '/images/icon/00-ic-data-built-in-yellow.svg',
      '/images/icon/00-ic-data-built-in-white.svg',
    ],
  },
  {
    label: 'Custom',
    value: 'custom',
    icon: [
      '/images/icon/00-ic-data-custom-yellow.svg',
      '/images/icon/00-ic-data-custom-white.svg',
    ],
  },
];

function UserServiceContent({
  originData,
  cardData,
  openTest,
  selectInputHandler,
  serviceType,
  deploymentType,
  status,
  moveToDeploymentPage,
  loading,
  serverError,
  workspaceId,
}) {
  const { t } = useTranslation();

  const statusOptions = [
    { label: t('allStatus.label'), value: 'all' },
    { label: t('serviceActive'), value: 'running' },
    { label: t('stop'), value: 'stop' },
    { label: t('installing'), value: 'installing' },
    { label: t('error'), value: 'error' },
  ];

  const serviceList = cardData.map((serviceData, index) => (
    <Card
      key={index}
      data={serviceData}
      openTest={openTest}
      wid={workspaceId}
    />
  ));
  return (
    <div
      id='UserServiceContent'
      className={cx('content', loading && 'loading-wrapper')}
    >
      <div className={cx('title-fliter')}>
        <PageTitle>{t('Test')}</PageTitle>
        {(originData.length > 0 || serverError) && (
          <div>
            {/* <div className={cx('btn-box')}>
              <SubMenu
                option={deploymentTypeOptions}
                select={deploymentType}
                onChangeHandler={(value) => {
                  selectInputHandler('deploymentType', value);
                }}
              />
            </div> */}
            <div className={cx('search-box')}>
              <div className={cx('filter-sort')}>
                <Selectbox
                  list={statusOptions}
                  selectedItem={status}
                  onChange={(value) => {
                    selectInputHandler('status', value);
                  }}
                  customStyle={{
                    fontStyle: {
                      selectbox: {
                        fontSize: '13px',
                      },
                    },
                  }}
                />
              </div>
            </div>
          </div>
        )}
      </div>
      {loading ? (
        // <div className={cx('card-box')}>
        //   {loadingList.map((_, key) => (
        //     <CardLoading key={key} />
        //   ))}
        // </div>
        <div className={cx('loading-box')}>
          <DeferredComponent>
            <FBLoading />
          </DeferredComponent>
        </div>
      ) : serverError ? (
        <div className={cx('no-response')}>{t('noResponse.message')}</div>
      ) : originData.length > 0 ? (
        cardData.length > 0 ? (
          <div className={cx('card-box')}>{serviceList}</div>
        ) : (
          <div className={cx('no-data')}>
            <div className={cx('message')}>
              <span>{t('noResultOf.message')}</span>
              {serviceType.value !== 'all' && (
                <span>
                  {t('serviceType.label')} :{' '}
                  <span className={cx('highlight')}>
                    {t(serviceType.label)}
                  </span>
                </span>
              )}
              {status.value !== 'all' && serviceType.value !== 'all' && (
                <span>&amp;</span>
              )}
              {status.value !== 'all' && (
                <span>
                  {t('status.label')} :{' '}
                  <span className={cx('highlight')}>{t(status.label)}</span>
                </span>
              )}
              {deploymentType.value !== 'all' &&
                (serviceType.value !== 'all' || status.value !== 'all') && (
                  <span>&amp;</span>
                )}
              {deploymentType.value !== 'all' && (
                <span>
                  {t('modelType.label')} :{' '}
                  <span className={cx('highlight')}>
                    {deploymentType.label}
                  </span>
                </span>
              )}
            </div>
          </div>
        )
      ) : (
        <div className={cx('no-data')}>
          <div className={cx('message')}>{t('noService.message')}</div>
          <button
            className={cx('go-to-btn')}
            onClick={() => {
              moveToDeploymentPage();
            }}
          >
            {t('goToCreateDeployment.label')}
            <img src='/images/icon/ic-right-blue.svg' alt='>' />
          </button>
        </div>
      )}
    </div>
  );
}

export default UserServiceContent;
