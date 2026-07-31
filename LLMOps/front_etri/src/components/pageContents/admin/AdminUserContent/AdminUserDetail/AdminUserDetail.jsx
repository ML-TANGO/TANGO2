// i18n
import { ButtonV2 } from '@tango/ui-react';

import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
// CSS module
import style from './AdminUserDetail.module.scss';

const cx = classNames.bind(style);

const AdminUserDetail = ({ data, moreList }) => {
  const { t } = useTranslation();
  const { name, workspaces, trainings, deployments, images, datasets } = data;
  return (
    <div className={cx('detail')}>
      <div className={cx('header')}>
        <span className={cx('id-txt')}>{name}</span>
        <span className={cx('title-txt')}>
          {t('detailsOf.label', { name: '' })}
        </span>
      </div>
      <div className={cx('block')}>
        <div className={cx('more-info')}>
          <ButtonV2
            label={t('workspace')}
            type='outline'
            style={{ height: '30px' }}
            onClick={() => moreList(name, 'workspaces')}
          />
          <div className={cx('count')}>
            {t('includedCount.label', { count: workspaces })}
          </div>
        </div>
        <div className={cx('more-info')}>
          <ButtonV2
            label={t('trainings.label')}
            type='outline'
            style={{ height: '30px' }}
            onClick={() => moreList(name, 'trainings')}
          />
          <div className={cx('count')}>
            {t('accessibleCount.label', { count: trainings })}
          </div>
        </div>
        <div className={cx('more-info')}>
          <ButtonV2
            label={t('deployments.label')}
            type='outline'
            style={{ height: '30px' }}
            onClick={() => moreList(name, 'deployments')}
          />
          <div className={cx('count')}>
            {t('accessibleCount.label', { count: deployments })}
          </div>
        </div>
        <div className={cx('more-info')}>
          <ButtonV2
            label={t('dockerImages.label')}
            type='outline'
            style={{ height: '30px' }}
            onClick={() => moreList(name, 'docker_images')}
          />
          <div className={cx('count')}>
            {t('createdCount.label', { count: images })}
          </div>
        </div>
        <div className={cx('more-info')}>
          <ButtonV2
            label={t('datasets.label')}
            type='outline'
            style={{ height: '30px' }}
            onClick={() => moreList(name, 'datasets')}
          />
          <div className={cx('count')}>
            {t('createdCount.label', { count: datasets })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminUserDetail;
