// Components
import { Badge } from '@jonathan/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './DeployItem.module.scss';
const cx = classNames.bind(style);

/**
 * 우측 슬라이드 패널에서 보여줄 Deployment Task UI 컴포넌트
 * @param {string} deployment_name deployment 이름
 * @param {number} gpu_count 할당받은 gpu 수
 * @param {string} workspace_name 워크스페이스 이름
 * @param {string} executor 배포자
 * @param {function} t 다국어 지원 함수
 * @component
 * @example
 *
 * const deployObj = {
 *  deployment_name: 'deployment 1',
 *  gpu_count: 4,
 *  workspace_name: 'workspace 1',
 *  executor: 'robert',
 * };
 *
 * return (
 *  <Deployment
 *    { ...deployObj }
 *    t={t} // 다국어 지원 함수
 * />
 * )
 */
function DeployItem({
  deployment_name: deployName,
  gpu_count: gpu,
  workspace_name: wName,
  executor,
  t,
}) {
  return (
    <li className={cx('deploy-item')}>
      <div className={cx('top')}>
        <div className={cx('title-wrap')}>
          <Badge
            label={'Deployment'}
            type={'red'}
            customStyle={{ marginRight: '10px' }}
          />
          <span className={cx('title')}>{deployName}</span>
        </div>
      </div>
      <div className={cx('bottom')}>
        <div className={cx('info-group')}>
          <p className={cx('label')}>
            {t ? t('workspace.label') : 'Workspace'}
          </p>
          <span className={cx('value')}>{wName}</span>
        </div>
        {gpu > 0 && (
          <div className={cx('info-group')}>
            <p className={cx('label')}>{t ? t('gpus.label') : 'GPUs'}</p>
            <span className={cx('value')}>{gpu}</span>
          </div>
        )}
        <div className={cx('info-group')}>
          <p className={cx('label')}>{t ? t('executor.label') : 'Executor'}</p>
          <span className={cx('value')}>{executor}</span>
        </div>
      </div>
    </li>
  );
}

export default DeployItem;
