// i18n

// Atom
import { useTranslation } from 'react-i18next';

import { Button, Tooltip } from '@tango/ui-react';

// lodash
import _ from 'lodash';

// CSS Module
import classNames from 'classnames/bind';
import style from './WorkerInfo.module.scss';

import downIcon from '@src/static/images/icon/00-ic-basic-arrow-02-down-blue.svg';
// Icon
import upIcon from '@src/static/images/icon/00-ic-basic-arrow-02-up-blue.svg';

const cx = classNames.bind(style);

function WorkerInfo({
  workerId,
  detailInfoData,
  detailInfoOverview,
  detailInfoOverviewHandler,
  workerMemoModalHandler,
}) {
  const { t } = useTranslation();
  const {
    description,
    resource_info: resourceInfo,
    version_info: versionInfo,
    version_info_changed: versionInfoChanged,
  } = detailInfoData;
  const {
    configuration,
    cpu_cores: cpuCores,
    node_name: nodeName,
    gpu,
    ram,
  } = resourceInfo;
  const {
    docker_image: dockerImage,
    built_in_model_name: builtInModelName,
    checkpoint,
    create_datetime: createdDatetime,
    end_datetime: endDatetime,
    job_info: jobInfo,
    run_code: runCode,
    training_name: trainingName,
    type,
  } = versionInfo;
  const { changed, changed_items: changedItems } = versionInfoChanged;

  return (
    <div className={cx('worker-info')}>
      <div className={cx('default', detailInfoOverview && 'border-bottom')}>
        <label>
          {t('workerInfo.label')}
          {!detailInfoOverview && changed && (
            <Tooltip
              title={t('workerVersionInfo.tooltip.message')}
              contents={
                <>
                  {changedItems.map(
                    (
                      {
                        item,
                        current_version: current,
                        latest_version: latest,
                      },
                      idx,
                    ) => (
                      <div key={idx} className={cx('tooltip-contents-box')}>
                        <label>[{t(`${_.camelCase(item)}.label`)}]</label>
                        <div>
                          <b>{t('currentVersion.label')}:</b>{' '}
                          {current && typeof current === 'object'
                            ? Object.keys(current).join(', ')
                            : Array.isArray(current)
                            ? current.join(', ')
                            : current || '-'}
                        </div>
                        <div>
                          <b>{t('latestVersion.label')}:</b>{' '}
                          {latest && typeof latest === 'object'
                            ? Object.keys(latest).join(', ')
                            : Array.isArray(latest)
                            ? latest.join(', ')
                            : latest || '-'}
                        </div>
                      </div>
                    ),
                  )}
                </>
              }
              contentsAlign={{ vertical: 'top' }}
              children={
                <img
                  src='/images/icon/00-ic-alert-warning-yellow.svg'
                  alt='warning'
                  style={{ width: '18px', marginLeft: '4px' }}
                />
              }
            />
          )}
        </label>
        <Button
          type='primary-reverse'
          customStyle={{
            width: '116px',
            height: '40px',
            border: 'none',
          }}
          iconAlign='right'
          iconStyle={{
            width: '16px',
            height: '16px',
          }}
          icon={detailInfoOverview ? upIcon : downIcon}
          onClick={() => {
            detailInfoOverviewHandler();
          }}
        >
          {t('seeDatail.label')}
        </Button>
      </div>
      {detailInfoOverview && (
        <div className={cx('worker-info-overview')}>
          <div className={cx('memo')}>
            <label className={cx('label')}>{t('memo.label')}</label>
            <div className={cx('text')}>{description || '-'}</div>
            <Button
              type='primary-reverse'
              customStyle={{
                backgroundColor: '#f9fafb',
                border: 'none',
              }}
              onClick={() => workerMemoModalHandler(workerId, description)}
            >
              {t('edit.label')}
            </Button>
          </div>
          <div className={cx('resource')}>
            <label className={cx('label')}>{t('resource.label')}</label>
            <ul>
              <li>
                <label className={cx('label')}>
                  {t('configuration.label')}
                </label>
                <span className={cx('value')}>
                  {configuration ? configuration.join(', ') : '-'}
                </span>
              </li>
              <li>
                <label className={cx('label')}>GPU</label>
                <span className={cx('value')}>
                  {gpu.name ? `${gpu.name} x ${gpu.count}EA` : '-'}
                </span>
              </li>
              <li>
                <label className={cx('label')}>CPU Core</label>
                <span className={cx('value')}>
                  {cpuCores || cpuCores === 0 ? cpuCores : '-'}
                </span>
              </li>
              <li>
                <label className={cx('label')}>RAM</label>
                <span className={cx('value')}>{ram || '-'}</span>
              </li>
            </ul>
          </div>
          <div className={cx('version-info')}>
            <label className={cx('label')}>
              {t('versionInfo.label')}
              {changed && (
                <Tooltip
                  title={t('workerVersionInfo.tooltip.message')}
                  contents={
                    <>
                      {changedItems.map(
                        (
                          {
                            item,
                            current_version: current,
                            latest_version: latest,
                          },
                          idx,
                        ) => (
                          <div key={idx} className={cx('tooltip-contents-box')}>
                            <label>[{t(`${_.camelCase(item)}.label`)}]</label>
                            <div>
                              <b>{t('currentVersion.label')}:</b>{' '}
                              {current && typeof current === 'object'
                                ? Object.keys(current).join(', ')
                                : Array.isArray(current)
                                ? current.join(', ')
                                : current || '-'}
                            </div>
                            <div>
                              <b>{t('latestVersion.label')}:</b>{' '}
                              {latest && typeof latest === 'object'
                                ? Object.keys(latest).join(', ')
                                : Array.isArray(latest)
                                ? latest.join(', ')
                                : latest || '-'}
                            </div>
                          </div>
                        ),
                      )}
                    </>
                  }
                  contentsAlign={{ vertical: 'top' }}
                  children={
                    <img
                      src='/images/icon/00-ic-alert-warning-yellow.svg'
                      alt='warning'
                      style={{ width: '18px', marginLeft: '4px' }}
                    />
                  }
                />
              )}
            </label>
            <ul>
              <li>
                <label className={cx('label')}>{t('createdAt.label')}</label>
                <span className={cx('value')}>{createdDatetime || '-'}</span>
              </li>
              {endDatetime && (
                <li>
                  <label className={cx('label')}>{t('stoppedAt.label')}</label>
                  <span className={cx('value')}>{endDatetime}</span>
                </li>
              )}
              <li>
                <label className={cx('label')}>{t('training.label')}</label>
                <span className={cx('value')}>{trainingName || '-'}</span>
              </li>
              {/* <li>
                <label className={cx('label')}>{t('model.label')}</label>
                <span className={cx('value')}>{builtInModelName || '-'}</span>
              </li> */}
              <li>
                <label className={cx('label')}>{t('runCode.label')}</label>
                <span className={cx('value')}>{runCode || '-'}</span>
              </li>
              {/* <li>
                <label className={cx('label')}>{t('jobInfo.label')}</label>
                <span className={cx('value')}>{jobInfo || '-'}</span>
              </li> */}
              {/* <li>
                <label className={cx('label')}>{t('checkpoint.label')}</label>
                <span className={cx('value')}>{checkpoint || '-'}</span>
              </li> */}
              <li>
                <label className={cx('label')}>{t('dockerImage.label')}</label>
                <span className={cx('value')}>{dockerImage || '-'}</span>
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

export default WorkerInfo;
