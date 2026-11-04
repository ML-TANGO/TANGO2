import PlaygroundFrame from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from '../../UserPipeLineInfo.module.scss';

const cx = classNames.bind(style);

const calType = (type) => {
  if (!type) return '-';
  if (type === 'data') return '신규 데이터량';
  if (type === 'time') return '실행 시간';
  return '타입을 확인하세요.';
};

const calUnitValue = (type, unit, value) => {
  if (!type) return '-';
  if (type === 'data') return `${value} ${unit}`;
  if (type === 'time') {
    if (unit === 'hours') return `${value} 시간 마다`;
    if (unit === 'minutes') return `${value} 분 마다`;
  }
  return '타입을 확인해보세요';
};

export default function UpdateSetting({ ...restart_setting }) {
  const { type, unit, value } = restart_setting;

  const settingType = calType(type);
  const settingUnitValue = calUnitValue(type, unit, value);

  return (
    <PlaygroundFrame>
      <div className={cx('row')}>
        <h2>자동 업데이트 설정</h2>
        <div className={cx('label-cont')}>
          <span className={cx('label')}>자동 업데이트 기준</span>
          <p className={cx('value')}>{settingType}</p>
        </div>
        <div className={cx('label-cont')}>
          <span className={cx('label')}>재시작 시작 조건</span>
          <span className={cx('value')}>{settingUnitValue}</span>
        </div>
      </div>
    </PlaygroundFrame>
  );
}
