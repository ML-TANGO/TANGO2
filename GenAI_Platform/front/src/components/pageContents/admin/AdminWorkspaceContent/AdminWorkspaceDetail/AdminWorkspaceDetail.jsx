// i18n

// Components
import { Button, ButtonV2 } from '@jonathan/ui-react';

import { useTranslation } from 'react-i18next';

import NewPieChart from '@src/components/molecules/StorageNewPieChart/NewPieChart';
// import CircleProgressbar from '@src/components/atoms/loading/CircleProgressbar';
import CircleProgressbar from '@src/components/pageContents/user/UserDashboardContent/CircleProgressbar/CircleProgressbar';

import classNames from 'classnames/bind';
// CSS module
import style from './AdminWorkspaceDetail.module.scss';

const cx = classNames.bind(style);

const AdminWorkspaceDetail = ({ data, moreList }) => {
  const { t } = useTranslation();
  const {
    name,
    description,
    gpu,
    trainings,
    deployments,
    images,
    datasets,
    user: { list: userList, total: userTotal },
    resource,
  } = data;
  return (
    <div className={cx('detail')}>
      <div className={cx('header')}>
        {/* <h3 className={cx('title')}>{t('detailsOf.label', { name: name })}</h3> */}
        <div className={cx('title')}>
          {/* {t('detailsOf.label', { name: imageName })} */}
          <span>{name}</span>
          <span>{t('detailsOf')}</span>
        </div>
      </div>
      <div className={cx('usage-div')}>
        <div className={cx('desc-box')}>
          <div>
            <label className={cx('label')}>{t('description.label')}</label>
            <div className={cx('desc')}>
              {description === '' || !description ? '-' : description}
            </div>
          </div>
        </div>

        <div className={cx('users')}>
          <div>
            <label className={cx('label')}>
              {t('users.label')} ({userTotal})
            </label>
            <div className={cx('user-list')}>
              {userList &&
                userList.map(({ name: userName }, idx) =>
                  idx === userList.length - 1 ? userName : `${userName}, `,
                )}
            </div>
          </div>
        </div>
        <div className={cx('usage-chart')}>
          <div>
            <label className={cx('label')}>{t('totalGpuCount.label')}</label>
            <p className={cx('usage')}>
              {resource?.gpu?.used ?? '-'}/{resource?.gpu?.total ?? '-'}
            </p>
          </div>
          <div className={cx('graph')}>
            <CircleProgressbar
              total={resource?.gpu?.total ?? 100}
              used={resource?.gpu?.used ?? 0}
              toolTipStyle={{ left: '-18px', top: '24px', fontSize: '2px' }}
            />
          </div>
        </div>
        <div className={cx('usage-chart')}>
          <div>
            <label className={cx('label')}>{t('totalCpuCount.label')}</label>
            <p className={cx('usage')}>
              {resource?.cpu?.used ?? '-'}/{resource?.cpu?.total ?? '-'}
            </p>
          </div>
          <div className={cx('graph')}>
            <CircleProgressbar
              total={resource?.cpu?.total ?? 100}
              used={resource?.cpu?.used ?? 0}
            />
          </div>
        </div>
      </div>
      <div className={cx('block')}>
        <div className={cx('more-info')}>
          <div className={cx('border')}>
            <label
              className={cx('label')}
              name={t('goToTargetList.label', {
                target: t('training'),
              })}
            >
              <ButtonV2
                type='outline'
                size='l'
                label={t('trainings.label')}
                onClick={() => moreList(name, 'trainings')}
              />
            </label>
          </div>
          <div className={cx('count')}>
            {t('ea.label', { count: trainings })}
          </div>
        </div>
        <div className={cx('more-info')}>
          <div className={cx('border')}>
            <label
              className={cx('label')}
              name={t('goToTargetList.label', {
                target: t('deployment'),
              })}
            >
              <ButtonV2
                type='outline'
                size='l'
                label={t('deployments.label')}
                onClick={() => moreList(name, 'deployments')}
              />
            </label>
          </div>
          <div className={cx('count')}>
            {t('ea.label', { count: deployments })}
          </div>
        </div>
        <div className={cx('more-info')}>
          <div className={cx('border')}>
            <label
              className={cx('label')}
              name={t('goToTargetList.label', {
                target: t('docker image'),
              })}
            >
              <ButtonV2
                type='outline'
                size='l'
                label={t('dockerImages.label')}
                onClick={() => moreList(name, 'docker_images')}
              />
            </label>
          </div>
          <div className={cx('count')}>{t('ea.label', { count: images })}</div>
        </div>
        <div className={cx('more-info')}>
          <div className={cx('border')}>
            <label
              className={cx('label')}
              name={t('goToTargetList.label', {
                target: t('dataset'),
              })}
            >
              <ButtonV2
                type='outline'
                size='l'
                label={t('datasets.label')}
                onClick={() => moreList(name, 'datasets')}
              />
            </label>
          </div>
          <div className={cx('count')}>
            {t('ea.label', { count: datasets })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminWorkspaceDetail;
