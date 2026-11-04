import CloseIcon from '@src/static/images/icon/00-ic-close-gray.svg';
import DisabledCloseIcon from '@src/static/images/icon/delete-x-gray.svg';

import classNames from 'classnames/bind';
import style from './DataList.module.scss';

const cx = classNames.bind(style);

function DataList({
  list,
  selectedList,
  handleCheckbox,
  disable,
  onClickDelete,
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
            } = data;
            return (
              <div className={cx('training-item')} key={data?.id}>
                <div className={cx('item')}>
                  {/* <Checkbox
                    // label={`${datasetName ? datasetName : fileName}${
                    //   path ? ` / ${path}` : ''
                    // }`}
                    checked={selectedList.includes(data?.id)}
                    onChange={() => {
                      handleCheckbox(data?.id);
                    }}
                    disabled={disable}
                  /> */}
                  <div className={cx('item-name')}>
                    {`${datasetName ? datasetName : fileName}${
                      path ? ` / ${path}` : ''
                    }`}
                  </div>
                  <img
                    src={disable ? DisabledCloseIcon : CloseIcon}
                    alt='close-icon'
                    onClick={(e) => {
                      if (!disable) {
                        onClickDelete(data?.id ?? 0);
                      }
                    }}
                    className={cx('close', disable && 'disabled')}
                  />
                </div>
              </div>
            );
          })}
      </div>
      {/* <div className={cx('training-btn')}>
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
      </div> */}
    </div>
  );
}
export default DataList;
