// Atom

// Components
import { Checkbox, InputNumber } from '@jonathan/ui-react';

import { useMemo } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import InstanceTooltip from '@src/components/organisms/InstanceTooltip';

// Colors
// import { colors } from '@src/utils/colors';

// CSS Module
import classNames from 'classnames/bind';
import style from './GpuListItem.module.scss';

const cx = classNames.bind(style);

function GpuListItem({
  idx,
  model,
  gpuName,
  total = 0,
  selected,
  ram,
  gpu,
  cpu,
  free,
  inputValue,
  edit,
  list,
  checkboxHandler,
  onChangeInputValue,
  prevGpuCount = 0,
  type,
  isReadOnly,
}) {
  const { t } = useTranslation();
  let remainingSize = free;

  const maxValue = useMemo(() => {
    let newMaxValue = edit && selected ? free + prevGpuCount : free;

    if (edit && selected && `${newMaxValue}` === `0`) {
      newMaxValue = inputValue;
    }

    return newMaxValue;
  }, [edit, selected, free, prevGpuCount, inputValue]);

  return (
    <li key={idx}>
      <div className={cx('list-item')}>
        <div className={cx('check')}>
          <Checkbox
            value={idx}
            // label={model}
            customLabelStyle={{
              padding: '0 0 0 3px',
              fontSize: '14px',
            }}
            name='gpuModel'
            checked={selected}
            // customStyle={{}}
            onChange={() => {
              checkboxHandler({ idx });
            }}
          />
          <div className={cx('instance-name-box')}>
            <div className={cx('model-name')}>{model}</div>
            <InstanceTooltip
              instanceType={gpuName ? 'GPU' : 'CPU'}
              gpuName={gpuName}
              gpuAllocateNum={gpu}
              cpuAllocateNum={cpu}
              ramAllocateNum={ram}
            />
          </div>
        </div>
        {list && list.length > 0 ? (
          list.map((v) => {
            return <div className={cx('sub-row')}>{v}</div>;
          })
        ) : (
          <>
            <div className={cx('sub-row')}>
              {t('ea.label', { count: total })}
            </div>
            {type.includes('WORKSPACE') || type.includes('WORKER') ? (
              <div className={cx('sub-row')}>
                {t('ea.label', { count: remainingSize })}
              </div>
            ) : (
              ''
            )}
          </>
        )}

        {/* <div>{t('ea.label', { count: free })}</div> */}
        <InputNumber
          name='workspaceInput'
          placeholder={`${t('currentAvailableCount')} : ${
            maxValue === '' ? '0' : maxValue
          }`}
          min={0}
          max={8}
          value={inputValue}
          onChange={(e) => {
            if (`${maxValue}` === '0') return;
            let inputValue = e.value;

            if (e.value > maxValue) {
              inputValue = maxValue;
            }
            onChangeInputValue({
              idx,
              value: inputValue,
            });
          }}
          isReadOnly={isReadOnly || `${maxValue}` === '0'}
          disabled={`${maxValue}` === '0'}
          // isReadOnly={isReadOnly}
          // disableIcon={true}
          // bottomTextExist={true}
        />
      </div>
    </li>
  );
}

export default GpuListItem;
