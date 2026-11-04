import Info from './Content/Info';
import TrainDataset from './Content/TrainDataset';
import UpdateSetting from './Content/UpdateSetting';

import classNames from 'classnames/bind';
import style from './UserPipeLineInfo.module.scss';

const cx = classNames.bind(style);

export default function UserPipeLineInfo({
  datasetInfo,
  pipeline_info,
  restart_setting,
}) {
  return (
    <div className={cx('cont')}>
      <Info {...pipeline_info} />
      <TrainDataset {...datasetInfo} />
      <UpdateSetting {...restart_setting} />
    </div>
  );
}
