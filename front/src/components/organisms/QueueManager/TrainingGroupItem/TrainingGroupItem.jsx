import { Fragment } from 'react';

// Components
import HpsItem from '../HpsItem';
import JobItem from '../JobItem';
import { Badge } from '@jonathan/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './TrainingGroupItem.module.scss';
const cx = classNames.bind(style);

function TrainingGroupItem({
  training_name: trainingName,
  item_list: queueList,
  moveToTarget = () => {},
}) {
  return (
    <div className={cx('training-group-item')}>
      <div className={cx('top')}>
        <div className={cx('title-wrap')}>
          <Badge
            label={'GROUP'}
            type={'red'}
            customStyle={{ marginRight: '10px' }}
          />
          <span className={cx('title')}>{trainingName}</span>
        </div>
      </div>
      <ul className={cx('list')}>
        {queueList.map((item, i) => (
          <Fragment key={i}>
            {item.item_type === 'hps' && (
              <HpsItem {...item} moveToTarget={moveToTarget} />
            )}
            {item.item_type === 'job' && (
              <JobItem {...item} moveToTarget={moveToTarget} />
            )}
          </Fragment>
        ))}
      </ul>
    </div>
  );
}

export default TrainingGroupItem;
