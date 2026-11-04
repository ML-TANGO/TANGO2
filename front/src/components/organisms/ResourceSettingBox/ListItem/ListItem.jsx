import { useState } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Checkbox } from '@jonathan/ui-react';
import ArrowButton from '@src/components/atoms/button/ArrowButton';
import CpuModelSelectBox from '@src/components/organisms/ResourceSettingBox/GpuModelDetail';

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
  cpuModelList,
  isReadOnly, // boolean
}) {
  const { t } = useTranslation();

  const [showServerList, setShowServerList] = useState(false);

  return (
    <li key={idx}>
      <div className={cx('list-item')}>
        <Checkbox
          value={idx}
          label={model}
          customLabelStyle={{
            padding: '0 0 0 3px',
            fontSize: '16px',
          }}
          name='gpuModel'
          checked={selected}
          onChange={() => onChange('gpu', idx)}
          readOnly={isReadOnly}
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
                ({cpuModelList ? cpuModelList.length : 0}/{nodeList.length})
              </span>
            </span>
          </ArrowButton>
        </div>
      </div>
      {showServerList && nodeList && (
        <CpuModelSelectBox
          options={nodeList}
          onChange={onChange}
          gpuIdx={idx}
          isReadOnly={isReadOnly}
        />
      )}
    </li>
  );
}

export default ListItem;
