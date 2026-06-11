// Components
import { ButtonV2, Checkbox, Radio } from '@tango/ui-react';

import classNames from 'classnames/bind';
import style from '../RagSearch.module.scss';

const cx = classNames.bind(style);

const initialStatus = {
  commit_status: {
    status: 'done',
  },
  fine_tuning_status: {
    status: 'stop',
  },
};

const TopButtonList = ({ t, onClickSystemLog, onClickTest }) => {
  return (
    <div className={cx('btn-list')}>
      {'Status '}
      <ButtonV2
        type='solid'
        size='l'
        colorType='skyblue'
        label={t('systemLog.label')}
        onClick={onClickSystemLog}
        style={{ width: '100%' }}
      />

      <ButtonV2
        type='solid'
        size='l'
        label={t('test.label')} // 실행
        onClick={onClickTest}
        style={{ width: '100%' }}
      />

      {/* {finetuningStatus?.status === 'running' && (
        <ButtonV2
          type='solid'
          size='l'
          colorType='red'
          label={t('stop.label')} // 중지
          // onClick={onClickRun}
          style={{ width: '100%' }}
        />
      )} */}
    </div>
  );
};

export default TopButtonList;
