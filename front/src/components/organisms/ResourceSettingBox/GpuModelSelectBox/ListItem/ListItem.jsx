import { useState, useEffect } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Checkbox } from '@jonathan/ui-react';
import ArrowButton from '@src/components/atoms/button/ArrowButton';
import GpuModelDetail from '@src/components/organisms/ResourceSettingBox/GpuModelDetail';

// CSS Module
import classNames from 'classnames/bind';
import style from './ListItem.module.scss';
const cx = classNames.bind(style);

function ListItem({
  idx,
  model,
  total,
  aval,
  selected, // boolean
  nodeList,
  onChange,
  detailGpuValueHandler,
  gpuDetailValue,
  gpuRamDetailValue,
  gpuAndRamSliderValue,
  gpuDetailSelectedOptions,
  gpuTotalSliderMove,
  gpuSwitchStatus,
  checkboxHandler,
}) {
  const { t } = useTranslation();
  const [showServerList, setShowServerList] = useState(false);
  const [selectedCount, setSelectedCount] = useState(0);

  useEffect(() => {
    let count = 0;
    const selectedArr = gpuDetailSelectedOptions[idx][idx];

    if (selectedArr?.length > 0) {
      selectedArr.forEach((boolean) => {
        if (boolean) count += 1;
      });
      setSelectedCount(count);
    }
  }, [gpuDetailSelectedOptions, idx]);
  return (
    <li key={idx}>
      <div className={cx('list-item')}>
        <Checkbox
          value={idx}
          label={model}
          customLabelStyle={{
            padding: '0 0 0 3px',
            fontSize: '14px',
          }}
          name='gpuModel'
          checked={selected}
          onChange={() => {
            checkboxHandler({ idx, status: 'all', type: 'gpu' });
            onChange('gpu', idx);
          }}
        />
        <div>{t('ea.label', { count: total })}</div>
        <div>{t('ea.label', { count: aval })}</div>
        <div>
          <ArrowButton
            isUp={!showServerList}
            color='blue'
            onClick={() => {
              setShowServerList(!showServerList);
            }}
          >
            <span className={cx('server-selected')}>
              <span>{t('selected.label')}</span>
              <span className={cx('fixed')}>
                ({selectedCount}/{nodeList.length})
              </span>
            </span>
          </ArrowButton>
        </div>
      </div>
      {showServerList && nodeList && (
        <GpuModelDetail
          options={nodeList}
          onChange={onChange}
          gpuIdx={idx}
          detailGpuValueHandler={detailGpuValueHandler}
          gpuDetailValue={gpuDetailValue}
          gpuRamDetailValue={gpuRamDetailValue}
          gpuAndRamSliderValue={gpuAndRamSliderValue}
          gpuDetailSelectedOptions={gpuDetailSelectedOptions}
          gpuTotalSliderMove={gpuTotalSliderMove}
          gpuSwitchStatus={gpuSwitchStatus}
          checkboxHandler={checkboxHandler}
        />
      )}
    </li>
  );
}

export default ListItem;
