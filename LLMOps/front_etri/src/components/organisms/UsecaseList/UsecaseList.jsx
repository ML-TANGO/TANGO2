// Components
import ToggleCard from '@src/components/molecules/ToggleCard/ToggleCard';

import classNames from 'classnames/bind';
// CSS module
import style from './UsecaseList.module.scss';

const cx = classNames.bind(style);

function UsecaseList({ list }) {
  return (
    <div className={cx('usecase-list')}>
      {list.map(({ title, description, button }, idx) => {
        return (
          <ToggleCard
            key={idx}
            subject={`Usecase ${idx + 1}`}
            title={title}
            defaultIsOpen={idx === 0 ? true : false}
          >
            <div>
              <div className={cx('description')}>{description}</div>
              {button}
            </div>
          </ToggleCard>
        );
      })}
    </div>
  );
}
export default UsecaseList;
