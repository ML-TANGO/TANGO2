// i18n
import { useTranslation } from 'react-i18next';

// Components
import ListItem from './ListItem';
import { InputNumber, Switch } from '@jonathan/ui-react';
import Slider from '@mui/material/Slider';

// CSS Module
import classNames from 'classnames/bind';
import style from './GpuModelSelectBox.module.scss';
const cx = classNames.bind(style);

function GpuModelSelectBox({
  options,
  onChange,
  gpuSelectedOptions,
  gpuDetailSelectedOptions,
  gpuTotalValue,
  gpuRamTotalValue,
  gpuDetailValue,
  gpuRamDetailValue,
  gpuTotalSliderMove,
  gpuSwitchStatus,
  gpuAndRamSliderValue,
  totalValueHandler,
  sliderSwitchHandler,
  detailGpuValueHandler,
  checkboxHandler,
}) {
  const { t } = useTranslation();

  return (
    <div className={cx('wrapper')}>
      <div className={cx('slider-title')}>
        <div>CPU RAM {t('usageSettings.label')}</div>
        <div className={cx('switch')}>
          <span className={cx('switch-title')}>
            {t('individualSettings.label')}
          </span>
          <Switch
            checked={gpuSwitchStatus}
            labelAlign={'left'}
            customStyle={{ marginLeft: '10px' }}
            onChange={() => sliderSwitchHandler('gpu')}
          />
        </div>
      </div>
      <div className={cx('slider-box')}>
        <div className={cx('label')}>{t('totalSetting.label')}</div>
        <div className={cx('slider-content')}>
          <div className={cx('option')}>CPU Cores</div>
          <div className={cx('slider')}>
            <Slider
              valueLabelDisplay='auto'
              aria-label='pretto slider'
              defaultValue={gpuTotalValue}
              value={gpuTotalValue}
              step={1}
              min={0}
              max={gpuAndRamSliderValue?.cpu}
              onChange={(e, v) => totalValueHandler(v, 'gpu', 'gpu')}
              sx={{
                color: '#f5f5f5',
                width: 'fit-content(100%)',
                height: 8,
                minWidth: 142,
                zIndex: 1,
                '& .MuiSlider-thumb': {
                  border: '3px solid #ffffff',
                  backgroundColor: '#0067FF',
                },
                '& .MuiSlider-thumb:before': {
                  boxShadow: 'none',
                },
                '& .MuiSlider-track': {
                  border: '2px solid #ffffff',
                  opacity: 1,
                  backgroundColor: '#5395ff',
                  // 그라데이션
                  background:
                    'linear-gradient(90deg, rgba(2,0,36,1) 0%, rgba(147, 186, 255,1) 0%, rgba(22, 74, 190,1) 100%)',
                },
                '& .MuiSlider-rail': {
                  border: '2px solid white',
                  opacity: 1,
                  backgroundColor: '#DBDBDB',
                },
                '& .MuiSlider-markLabel': {
                  top: 30,
                  color: '#666666', // 밑에 글씨 색
                },
                '& .MuiSlider-mark': {
                  width: '1px',
                  height: 12,
                  color: '#ffffff', // 눈금자 색
                },
                '& .MuiSlider-mark[data-index="0"]': {
                  display: 'none',
                },
                '& .MuiSlider-mark[data-index="6"]': {
                  display: 'none',
                },
              }}
            />
            <div className={cx('slider-input')}>
              <InputNumber
                size={'x-small'}
                value={gpuTotalValue}
                onChange={(e) => {
                  totalValueHandler(Number(e.value), 'gpu', 'gpu');
                }}
                disableIcon={true}
                customSize={{
                  width: '64px',
                  height: '24px',
                  textAlign: 'right',
                }}
              />
              <div className={cx('unit')}>{t('ea.label', { count: '' })}</div>
            </div>
          </div>
        </div>
        <div className={cx('slider-content')}>
          <div className={cx('option')}>RAM</div>
          <div className={cx('slider')}>
            <Slider
              valueLabelDisplay='auto'
              aria-label='pretto slider'
              defaultValue={gpuRamTotalValue}
              value={gpuRamTotalValue}
              step={1}
              min={0}
              max={gpuAndRamSliderValue?.ram}
              onChange={(e, v) => totalValueHandler(v, 'ram', 'gpu')}
              sx={{
                color: '#f5f5f5',
                width: 'fit-content(100)',
                height: 8,
                minWidth: 142,
                zIndex: 1,
                '& .MuiSlider-thumb': {
                  border: '3px solid #ffffff',
                  backgroundColor: '#0067FF',
                },
                '& .MuiSlider-thumb:before': {
                  boxShadow: 'none',
                },
                '& .MuiSlider-track': {
                  border: '2px solid #ffffff',
                  opacity: 1,
                  backgroundColor: '#5395ff',
                  // 그라데이션
                  background:
                    'linear-gradient(90deg, rgba(2,0,36,1) 0%, rgba(147, 186, 255,1) 0%, rgba(22, 74, 190,1) 100%)',
                },
                '& .MuiSlider-rail': {
                  border: '2px solid white',
                  opacity: 1,
                  backgroundColor: '#DBDBDB',
                },
                '& .MuiSlider-markLabel': {
                  top: 30,
                  color: '#666666', // 밑에 글씨 색
                },
                '& .MuiSlider-mark': {
                  width: '1px',
                  height: 12,
                  color: '#ffffff', // 눈금자 색
                },
                '& .MuiSlider-mark[data-index="0"]': {
                  display: 'none',
                },
                '& .MuiSlider-mark[data-index="6"]': {
                  display: 'none',
                },
              }}
            />
            <div className={cx('slider-input')}>
              <InputNumber
                size={'x-small'}
                value={gpuRamTotalValue}
                onChange={(e) => {
                  totalValueHandler(Number(e.value), 'ram', 'gpu');
                }}
                disableIcon={true}
                customSize={{
                  width: '64px',
                  height: '24px',
                  textAlign: 'right',
                }}
              />
              <div className={cx('unit')}>GB</div>
            </div>
          </div>
        </div>
      </div>
      <p className={cx('info')}>*{t('gpuModelSelectInfo.message')}</p>
      <div className={cx('list-header')}>
        <div>{t('modelName.label')}</div>
        <div>{t('totalAllocable.label')}</div>
        <div>{t('currentlyAvailable.label')}</div>
        <div>{t('server.label')}</div>
      </div>
      <ul className={cx('list-body')}>
        {options.length === gpuSelectedOptions.length && options.length > 0 ? (
          options.map(({ model, total, aval, node_list: nodeList }, idx) => {
            return (
              <ListItem
                key={idx}
                idx={idx}
                model={model}
                total={total}
                aval={aval}
                selected={gpuSelectedOptions[idx][idx]}
                nodeList={nodeList}
                onChange={onChange}
                detailGpuValueHandler={detailGpuValueHandler}
                gpuDetailValue={gpuDetailValue}
                gpuRamDetailValue={gpuRamDetailValue}
                gpuAndRamSliderValue={gpuAndRamSliderValue}
                gpuDetailSelectedOptions={gpuDetailSelectedOptions}
                gpuTotalSliderMove={gpuTotalSliderMove}
                gpuSwitchStatus={gpuSwitchStatus}
                checkboxHandler={checkboxHandler}
              />
            );
          })
        ) : (
          <div className={cx('empty-item')}>{t('noGpuModel.message')}</div>
        )}
      </ul>
    </div>
  );
}

export default GpuModelSelectBox;
