import PropTypes from 'prop-types';

// Components
import { Badge } from '@jonathan/ui-react';

// CSS Module
import style from './HpsItem.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

/**
 * 우측 슬라이드 패널에서 보여줄 HPS Task UI 컴포넌트
 * @param {string} hps_name hps 이름
 * @param {number} gpu_count hps에서 사용 중인 gpu 수
 * @param {number} workspace_id hps가 속한 워크스페이스 id
 * @param {number} training_id hps가 속한 트레이닝 id
 * @param {string} training_name hps가 속한 트레이닝 이름
 * @param {string} executor hps 생성자 이름
 * @param {number} hps_group_index hps 인덱스
 * @param {function} moveToTarget 해당 hps가 속한 상세 화면으로 이동
 * @component
 * @example
 * const hpsObj = {
 *  hps_name: 'hps1',
 *  gpu_count: 1,
 *  workspace_id: 4,
 *  training_id: 3,
 *  training_name: 'training 1',
 *  executor: 'robert',
 *  hps_group_index: 2,
 *  moveToTarget: () => {}, // 해당 hps가 속한 Training 상세 화면으로 이동하는 함수
 * };
 * return (
 *  <HpsItem
 *    { ...hpsObj }
 *    t={t} // 다국어 지원 함수
 *  />
 * )
 */
function HpsItem({
  hps_name: hpsName,
  gpu_count: gpu,
  workspace_id: wId,
  training_id: tId,
  training_name: tName,
  executor,
  hps_group_index: hpsIndex,
  moveToTarget = () => {},
  t,
}) {
  return (
    <li className={cx('hps-item')}>
      <div className={cx('top')}>
        <div className={cx('title-wrap')}>
          <Badge
            label={'HPS'}
            type={'blue'}
            customStyle={{ marginRight: '10px' }}
          />
          <span className={cx('title')}>{`${hpsName} (HPS ${
            hpsIndex + 1
          })`}</span>
        </div>
        <button
          className={cx('move-to-job-btn')}
          onClick={() => {
            moveToTarget(wId, tId, tName, 'hps');
          }}
        >
          {t ? t('moveToJob.label') : 'Move to Job'}
          <img src='/images/icon/ic-right.svg' alt='>'></img>
        </button>
      </div>
      <div className={cx('bottom')}>
        <div className={cx('info-group')}>
          <p className={cx('label')}>{t ? t('training.label') : 'Training'}</p>
          <span className={cx('value')}>{tName}</span>
        </div>
        <div className={cx('info-group')}>
          <p className={cx('label')}>{t ? t('gpus.label') : 'GPUs'}</p>
          <span className={cx('value')}>{gpu}</span>
        </div>
        <div className={cx('info-group')}>
          <p className={cx('label')}>{t ? t('creator.label') : 'Creator'}</p>
          <span className={cx('value')}>{executor}</span>
        </div>
      </div>
    </li>
  );
}

HpsItem.propTypes = {
  hps_name: PropTypes.string,
  gpu_count: PropTypes.number,
  workspace_id: PropTypes.number,
  training_id: PropTypes.number,
  training_name: PropTypes.string,
  executor: PropTypes.string,
  hps_group_index: PropTypes.number,
  moveToTarget: PropTypes.func,
  t: PropTypes.func,
};

export default HpsItem;
