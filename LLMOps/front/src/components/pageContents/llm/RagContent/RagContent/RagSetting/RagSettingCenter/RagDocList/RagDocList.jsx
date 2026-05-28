import { ButtonV2, Checkbox, Radio } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from './RagDocList.module.scss';

const cx = classNames.bind(style);

function RagDocList({
  list,
  selectedList,
  handleCheckbox,
  disable,
  onClickLeft,
  onClickRight,
  t,
}) {
  return (
    <div className={cx('training-data')}>
      <div className={cx('training-list')}>
        {list &&
          list.length > 0 &&
          list?.map((data) => {
            const {
              dataset_name: datasetName,
              model_file_path: path,
              file_name: fileName,
              name,
            } = data;
            return (
              <div className={cx('training-item')} key={name}>
                <Checkbox
                  label={name}
                  checked={selectedList.includes(name)}
                  onChange={() => {
                    handleCheckbox(name);
                  }}
                  disabled={disable}
                />
              </div>
            );
          })}
      </div>
      <div className={cx('training-btn')}>
        <ButtonV2 // 삭제
          type='clear'
          size='l'
          colorType='red'
          label={t('remove.label')}
          disabled={selectedList.length === 0 || disable}
          onClick={onClickLeft}
          style={{ width: '100%', height: '30px' }}
        />
        <ButtonV2 // 추가
          type='outline'
          size='l'
          label={t('add.label')}
          disabled={disable}
          onClick={onClickRight}
          style={{ width: '100%', height: '30px' }}
        />
      </div>
    </div>
  );
}
export default RagDocList;
