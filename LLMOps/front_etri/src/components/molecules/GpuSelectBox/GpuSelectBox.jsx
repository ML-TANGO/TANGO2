// i18n
import { useTranslation } from 'react-i18next';

import GpuListItem from './GpuListItem';

// CSS module
import classNames from 'classnames/bind';
import style from './GpuSelectBox.module.scss';

const cx = classNames.bind(style);

function GpuSelectBox({
  models,
  checkboxHandler,
  gpuSelectedOptions,
  onChangeGpuInputValue,
  inputValue,
  prevGpuCount,
  edit,
  type,
  children,
  colList,
  rowList,
  isReadOnly = false,
}) {
  const { t } = useTranslation();

  return (
    <div className={cx('wrapper')}>
      <div className={cx('list-header')}>
        {colList && colList.length > 0 ? (
          colList.map((v, index) => {
            if (index === 0) {
              return <div key={index}>{v}</div>;
            }
            return (
              <div key={index} className={cx('sub-col')}>
                {v}
              </div>
            );
          })
        ) : (
          <>
            <div>{t('modelName.label')}</div>
            <div className={cx('sub-col')}>
              <div>{t('totalAmount.label')}</div>
              {/* <div>{t('gpuNumber.label')}</div> */}
            </div>

            <div className={cx('sub-col')}>
              <div>{t('availableCapacity.label')}</div>
              {/* <div>{t('gpuNumber.label')}</div> */}
            </div>

            <div className={cx('sub-col')}>
              <div>{t('allocation.label')}</div>
              {/* <div>{t('gpuNumber.label')}</div> */}
            </div>
          </>
        )}
      </div>
      <ul className={cx('list-body')}>
        {models && models.length > 0 ? (
          models.map(
            (
              {
                cpu,
                gpu,
                resource_name: ResourceName,
                name = '',
                total,
                free,
                ram,
                allocate,
                gpu_name: gpuName,
              },
              idx,
            ) => {
              let newName = ResourceName ? ResourceName : name;
              const isGpuName = name?.includes('CPU');

              return (
                <GpuListItem
                  key={idx}
                  idx={idx}
                  model={newName}
                  gpuName={!isGpuName && name}
                  ram={ram}
                  cpu={cpu}
                  gpu={gpu}
                  total={typeof total === 'number' && total ? total : allocate}
                  free={free === undefined ? total : free}
                  selected={
                    gpuSelectedOptions[idx]
                      ? gpuSelectedOptions[idx][idx]
                      : false
                  }
                  edit={edit}
                  prevGpuCount={prevGpuCount}
                  inputValue={inputValue[idx]}
                  list={rowList}
                  checkboxHandler={checkboxHandler}
                  onChangeInputValue={onChangeGpuInputValue}
                  type={type}
                  isReadOnly={isReadOnly}
                />
              );
            },
          )
        ) : (
          <div className={cx('empty-item')}>{t('noData.message')}</div>
        )}
      </ul>
      {children}
    </div>
  );
}

export default GpuSelectBox;
