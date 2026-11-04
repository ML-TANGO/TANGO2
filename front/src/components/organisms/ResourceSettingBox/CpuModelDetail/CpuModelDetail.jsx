import { useTranslation } from 'react-i18next';
import Slider from '@mui/material/Slider';
// Components
import { InputNumber, Checkbox } from '@jonathan/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './CpuModelDetail.module.scss';
const cx = classNames.bind(style);

function CpuModelDetail({
  options,
  cpuIdx,
  detailSelectedOptions,
  detailCpuValueHandler,
  cpuValue,
  ramValue,
  totalSliderHandler,
  cpuSwitchStatus,
  cpuAndRamSliderValue,
  checkboxHandler,
}) {
  const { t } = useTranslation();

  return (
    <div className={cx('wrapper')}>
      <div className={cx('list-header')}>
        <div className={cx('block')}></div>
        <div className={cx('status')}>{t('status.label')}</div>
        <div className={cx('box')}>
          <div className={cx('header-title')}>
            <div className={cx('title')}>CPU</div>
            <div className={cx('title')}>RAM</div>
          </div>
          <div className={cx('header-column')}>
            <div className={cx('column-title')}>
              <div>{t('cpuMaxUsagePerPod.label')}</div>
              <div>{t('allocated.label')}</div>
              <div>{t('allocable.label')}</div>
            </div>
            <div className={cx('column-title')}>
              <div>{t('ramMaxUsagePerPod.label')}</div>
              <div>{t('allocated.label')}</div>
              <div>{t('allocable.label')}</div>
            </div>
          </div>
        </div>
      </div>
      <ul className={cx('list-body')}>
        {options.length > 0 &&
          options.map((value, idx) => {
            const { name, resource_info } = value;
            const {
              cpu_cores_limit_per_gpu,
              cpu_cores_limit_per_pod: cpuLimitPod,
              ram_limit_per_pod: ramLimitPod,
              resource_congestion_status_per_pod: statusColor, // 0 = Green, 1 = Yellow, 2 = Red
              resource_generable_status_per_pod: statusPod, // false === 금지마크
              pod_alloc_cpu_cores: allockCpu,
              pod_alloc_ram: allockRam,
              pod_alloc_avaliable_cpu_cores_per_pod: avaliableCpu,
              pod_alloc_avaliable_ram_per_pod: avaliableRam,
            } = resource_info;

            const [checked] = Object.values(detailSelectedOptions[cpuIdx]);
            let color = 'red';
            switch (statusColor) {
              case 0:
                color = 'green';
                break;
              case 1:
                color = 'yellow';
                break;
              case 2:
                color = 'red';
                break;
              default:
                break;
            }
            return (
              <li key={idx}>
                <div className={cx('list-item')}>
                  <div className={cx('checkbox')}>
                    {
                      <Checkbox
                        value={idx}
                        customLabelStyle={{
                          padding: '0 0 0 3px',
                          fontSize: '16px',
                        }}
                        name='gpuModel'
                        checked={checked?.length > 0 ? checked[idx] : ''}
                        onChange={() =>
                          checkboxHandler({
                            idx,
                            status: 'detail',
                            cpuIdx,
                            type: 'cpu',
                          })
                        }
                      />
                    }
                  </div>
                  <div className={cx('status-box')}>
                    {statusPod ? (
                      <div className={cx(`status-${color}`)}></div>
                    ) : (
                      <img
                        className={cx('image')}
                        src={`/images/icon/ic-ban-${color}.svg`}
                        alt='BanImage'
                      />
                    )}
                  </div>
                  <div>{cpuLimitPod}</div>
                  <div title={name}>
                    {allockCpu}/
                    {avaliableCpu === -1 ? (
                      <img
                        className={cx('image')}
                        src={`/images/icon/ic-infinite-black.svg`}
                        alt='InfiniteImage'
                      />
                    ) : (
                      Math.floor(avaliableCpu)
                    )}
                  </div>
                  <div>{cpu_cores_limit_per_gpu}</div>
                  <div>{ramLimitPod}</div>
                  <div>
                    {allockRam}/
                    {avaliableRam === -1 ? (
                      <img
                        className={cx('image')}
                        src={`/images/icon/ic-infinite-black.svg`}
                        alt='InfiniteImage'
                      />
                    ) : (
                      Math.floor(avaliableRam)
                    )}
                  </div>
                  <div>{resource_info['cpu_cores_limits/total']}</div>
                </div>
                {cpuSwitchStatus && checked[idx] && (
                  <div className={cx('slider-box')}>
                    <div className={cx('clear-space')}></div>
                    <div className={cx('slider')}>
                      <Slider
                        valueLabelDisplay='auto'
                        aria-label='pretto slider'
                        defaultValue={cpuValue ? cpuValue[cpuIdx][idx] : 0}
                        value={cpuValue ? cpuValue[cpuIdx][idx] : 0}
                        step={1}
                        min={0}
                        max={cpuAndRamSliderValue?.cpu}
                        onChange={(e, v) => {
                          if (cpuLimitPod < v) {
                            detailCpuValueHandler(
                              cpuIdx,
                              idx,
                              cpuLimitPod,
                              'cpu',
                            );
                            return;
                          }
                          detailCpuValueHandler(cpuIdx, idx, v, 'cpu');
                        }}
                        onMouseDown={() => totalSliderHandler('cpu')}
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
                          value={cpuValue[cpuIdx][idx]}
                          onChange={(e) => {
                            let inputValue = Number(e.value);
                            if (cpuLimitPod < inputValue) {
                              inputValue = cpuLimitPod;
                            }
                            detailCpuValueHandler(
                              cpuIdx,
                              idx,
                              inputValue,
                              'cpu',
                            );
                          }}
                          disableIcon={true}
                          customSize={{
                            width: '64px',
                            height: '24px',
                            textAlign: 'right',
                          }}
                        />
                        <div className={cx('unit')}>
                          {t('ea.label', { count: '' })}
                        </div>
                      </div>
                    </div>
                    <div className={cx('slider')}>
                      <Slider
                        valueLabelDisplay='auto'
                        aria-label='pretto slider'
                        defaultValue={ramValue ? ramValue[cpuIdx][idx] : 0}
                        value={ramValue ? ramValue[cpuIdx][idx] : 0}
                        step={1}
                        min={0}
                        max={cpuAndRamSliderValue?.ram}
                        onMouseDown={() => totalSliderHandler('cpu')}
                        onChange={(e, v) => {
                          if (ramLimitPod < v) {
                            detailCpuValueHandler(
                              cpuIdx,
                              idx,
                              ramLimitPod,
                              'ram',
                            );
                            return;
                          }
                          detailCpuValueHandler(cpuIdx, idx, v, 'ram');
                        }}
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
                          value={ramValue[cpuIdx][idx]}
                          onChange={(e) => {
                            let inputValue = Number(e.value);
                            if (ramLimitPod < inputValue) {
                              inputValue = ramLimitPod;
                            }
                            detailCpuValueHandler(
                              cpuIdx,
                              idx,
                              inputValue,
                              'ram',
                            );
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
                )}
              </li>
            );
          })}
      </ul>
    </div>
  );
}

export default CpuModelDetail;
