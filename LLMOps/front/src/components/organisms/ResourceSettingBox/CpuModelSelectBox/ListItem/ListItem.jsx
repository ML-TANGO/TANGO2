import { useState, useEffect, useCallback } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Checkbox } from '@jonathan/ui-react';
import ArrowButton from '@src/components/atoms/button/ArrowButton';
import CpuModelDetail from '@src/components/organisms/ResourceSettingBox/CpuModelDetail';

// CSS Module
import classNames from 'classnames/bind';
import style from './ListItem.module.scss';
const cx = classNames.bind(style);

function ListItem({
  idx,
  model,
  total,
  selected, // boolean
  nodeList,
  checkboxHandler,
  detailSelectedOptions,
  cpuValue,
  detailCpuValueHandler,
  cpuSliderMove,
  cpuTotalValue,
  totalSliderHandler,
  cpuSwitchStatus,
  ramDetailValue,
  cpuAndRamSliderValue,
}) {
  const { t } = useTranslation();
  const [showServerList, setShowServerList] = useState(false);
  const [selectedCount, setSelectedCount] = useState(0);

  const selectedCountHandler = useCallback(() => {
    const count = detailSelectedOptions[idx][idx]?.reduce(
      (cnt, ele) => cnt + (ele === true),
      0,
    );
    setSelectedCount(count);
  }, [detailSelectedOptions, idx]);

  useEffect(() => {
    if (detailSelectedOptions[idx]) {
      selectedCountHandler();
    }
  }, [detailSelectedOptions, idx, selectedCountHandler]);

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
          checked={selected ? selected : ''}
          onChange={() => checkboxHandler({ idx, status: 'all', type: 'cpu' })}
        />
        <div>{t('ea.label', { count: total })}</div>
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
        <CpuModelDetail
          options={nodeList}
          checkboxHandler={checkboxHandler}
          cpuIdx={idx}
          detailSelectedOptions={detailSelectedOptions}
          detailCpuValueHandler={detailCpuValueHandler}
          cpuValue={cpuValue}
          ramValue={ramDetailValue}
          cpuSliderMove={cpuSliderMove}
          cpuTotalValue={cpuTotalValue}
          totalSliderHandler={totalSliderHandler}
          cpuSwitchStatus={cpuSwitchStatus}
          cpuAndRamSliderValue={cpuAndRamSliderValue}
        />
      )}
    </li>
  );
}

export default ListItem;
