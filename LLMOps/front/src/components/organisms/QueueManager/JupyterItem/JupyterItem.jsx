// Components
import { Badge } from '@jonathan/ui-react';

// CSS Module
import style from './JupyterItem.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const JupyterItem = ({
  workspace_name: wName,
  training_name: tName,
  gpu_count: gpu,
  executor,
  t,
}) => {
  return (
    <li className={cx('jupyter-item')}>
      <div className={cx('top')}>
        <div className={cx('title-wrap')}>
          <Badge
            label={'JUPYTER'}
            type={'yellow'}
            customStyle={{ marginRight: '10px' }}
          />
          <span className={cx('title')}>Jupyter</span>
        </div>
      </div>
      <div className={cx('bottom')}>
        <div className={cx('info-group')}>
          <p className={cx('label')}>
            {t ? t('workspace.label') : 'Workspace'}
          </p>
          <span className={cx('value')}>{wName}</span>
        </div>
        <div className={cx('info-group')}>
          <p className={cx('label')}>{t ? t('training.label') : 'Training'}</p>
          <span className={cx('value')}>{tName}</span>
        </div>
        {gpu > 0 && (
          <div className={cx('info-group')}>
            <p className={cx('label')}>{t ? t('gpus.label') : 'GPUs'}</p>
            <span className={cx('value')}>{gpu}</span>
          </div>
        )}
        <div className={cx('info-group')}>
          <p className={cx('label')}>{t ? t('executor.label') : 'Executor'}</p>
          <span className={cx('value')}>{executor || '-'}</span>
        </div>
      </div>
    </li>
  );
};

export default JupyterItem;
