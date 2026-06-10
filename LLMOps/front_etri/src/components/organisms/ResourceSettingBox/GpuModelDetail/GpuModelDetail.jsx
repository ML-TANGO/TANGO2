// i18n
import { useTranslation } from 'react-i18next';

// Components
import { InputNumber, Checkbox, Tooltip } from '@jonathan/ui-react';
import Slider from '@mui/material/Slider';

// CSS Module
import classNames from 'classnames/bind';
import style from './GpuModelDetail.module.scss';
const cx = classNames.bind(style);

function GpuModelDetail({
  options,
  onChange,
  gpuIdx,
  isReadOnly,
  detailGpuValueHandler,
  gpuDetailValue,
  gpuRamDetailValue,
  gpuAndRamSliderValue,
  gpuSwitchStatus,
  gpuDetailSelectedOptions,
  checkboxHandler,
}) {
  const { t } = useTranslation();

  return (
    <div className={cx('wrapper')}>
      <div className={cx('list-header')}>
        <div className={cx('block')}></div>
        <div className={cx('box')}>
          <div className={cx('status')}>{t('status.label')}</div>
          <div>{t('currentlyAvailableGPU.label')}</div>
          <div>GPU MEM</div>
          <div>{t('cpuModel.label')}</div>
          <div>{t('cpuCoresPerPod.label')}</div>
          <div>{t('ramPerPod.label')}</div>
          <div>{t('networkInterface.label')}</div>
        </div>
      </div>
      <ul className={cx('list-body')}>
        {options.length > 0 &&
          options.map((option, idx) => {
            const {
              name,
              total,
              aval,
              memory,
              resource_info: {
                cpu_model,
                cpu_cores_limit_per_gpu: cpuLimitGpu,
                resource_congestion_status_per_gpu: statusColor, // 0 = Green, 1 = Yellow, 2 = Red
                resource_generable_status_per_gpu: statusPod, // false === 금지마크
                ram_limit_per_gpu: ramLimitGpu,
                allocate_network_groups: networkGroups,
              },
            } = option;

            const [checked] = Object.values(gpuDetailSelectedOptions[gpuIdx]);
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
                  <Checkbox
                    customLabelStyle={{
                      padding: '0 0 0 8px',
                      fontSize: '16px',
                    }}
                    checked={checked?.length > 0 ? checked[idx] : ''}
                    onChange={() => {
                      checkboxHandler({
                        idx,
                        status: 'detail',
                        cpuIdx: gpuIdx,
                        type: 'gpu',
                      });
                      onChange('cpu', gpuIdx, idx);
                    }}
                    disabled={isReadOnly}
                  />
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
                  <div>
                    ({aval}/{total})
                  </div>
                  <div>{memory}</div>
                  <div title={`${cpu_model}\n[${name}]`}>
                    {cpu_model}
                    {/* <div>{name}</div> */}
                  </div>
                  <div>{cpuLimitGpu}</div>
                  <div>{ramLimitGpu}</div>
                  <div>
                    {networkGroups?.length > 0 && (
                      <Tooltip
                        title={t('networkInterface.label')}
                        contents={
                          <table className={cx('tooltip-table')}>
                            <thead>
                              <tr>
                                <th>{t('network.groupName.label')}</th>
                                <th>{t('network.category.label')}</th>
                                <th>{t('network.speed.label')}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {networkGroups.map(
                                ({ name, category, speed }) => {
                                  return (
                                    <tr key={name}>
                                      <td>{name}</td>
                                      <td>{category}</td>
                                      <td>{speed} Gbps</td>
                                    </tr>
                                  );
                                },
                              )}
                            </tbody>
                          </table>
                        }
                        contentsCustomStyle={{
                          fontSize: '12px',
                          minWidth: '300px',
                        }}
                        contentsAlign={{
                          vertical: 'bottom',
                          horizontal: 'right',
                        }}
                      />
                    )}
                    {networkGroups
                      .map(({ name }) => {
                        return name;
                      })
                      .join(', ')}
                  </div>
                </div>

                {gpuSwitchStatus && checked[idx] && (
                  <div className={cx('slider-box')}>
                    <div className={cx('clear-space')}></div>
                    <div className={cx('slider')}>
                      <Slider
                        valueLabelDisplay='auto'
                        aria-label='pretto slider'
                        defaultValue={gpuDetailValue[gpuIdx][idx]}
                        value={gpuDetailValue[gpuIdx][idx]}
                        step={1}
                        min={0}
                        max={gpuAndRamSliderValue?.cpu}
                        onChange={(e, v) => {
                          if (cpuLimitGpu < v) {
                            detailGpuValueHandler(
                              gpuIdx,
                              idx,
                              cpuLimitGpu,
                              'gpu',
                            );
                            return;
                          }
                          detailGpuValueHandler(gpuIdx, idx, v, 'gpu');
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
                          value={gpuDetailValue[gpuIdx][idx]}
                          onChange={(e) => {
                            let inputValue = Number(e.value);
                            if (cpuLimitGpu < inputValue) {
                              inputValue = cpuLimitGpu;
                            }
                            detailGpuValueHandler(
                              gpuIdx,
                              idx,
                              inputValue,
                              'gpu',
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
                        defaultValue={
                          gpuRamDetailValue ? gpuRamDetailValue[gpuIdx][idx] : 0
                        }
                        value={
                          gpuRamDetailValue ? gpuRamDetailValue[gpuIdx][idx] : 0
                        }
                        step={1}
                        min={0}
                        max={gpuAndRamSliderValue?.ram}
                        onChange={(e, v) => {
                          if (ramLimitGpu < v) {
                            detailGpuValueHandler(
                              gpuIdx,
                              idx,
                              ramLimitGpu,
                              'ram',
                            );
                            return;
                          }
                          detailGpuValueHandler(gpuIdx, idx, v, 'ram');
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
                          value={gpuRamDetailValue[gpuIdx][idx]}
                          onChange={(e) => {
                            let inputValue = Number(e.value);
                            if (ramLimitGpu < inputValue) {
                              inputValue = ramLimitGpu;
                            }
                            detailGpuValueHandler(
                              gpuIdx,
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

export default GpuModelDetail;
