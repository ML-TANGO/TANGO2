import { useState, useEffect, useRef } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { InputNumber } from '@jonathan/ui-react';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import Slider from '@mui/material/Slider';

// CSS Module
import classNames from 'classnames/bind';
import style from './ServerResourceSettingForm.module.scss';
const cx = classNames.bind(style);

function ServerResourceSettingForm({
  modeOptions,
  gpuModeCpuRsc,
  cpuModeCpuRsc,
  gpuModeRam,
  cpuModeRam,
  gpuModeCpuRscError,
  cpuModeCpuRscError,
  gpuModeRamError,
  cpuModeRamError,
  maxCpuResource,
  numGpuResource,
  maxRamResource,
  temporarySizeLimit,
  temporarySizeLimitError,
  inputHandler,
  deviceInfo,
  cpuServerSliderHandler,
  cpuServerInitialValue,
  modalType,
  addNodeMinNum,
}) {
  const { t } = useTranslation();
  const [coresValue, setCoresValue] = useState(0);
  const [ramValue, setRamValue] = useState(0);
  const [minCores, setMinCores] = useState(0);
  const [minRam, setMinRam] = useState(0);

  const isMount = useRef(true);

  const inputValueHandler = (select, v) => {
    if (select === 'core') {
      setCoresValue(v);
    } else {
      setRamValue(v);
    }
    cpuServerSliderHandler(select, v);
  };

  const SLIDER_MARKS = [
    {
      value: 1,
      label: '0',
    },
    {
      value: 100,
      label: '100',
    },
    {
      value: 200,
      label: '200',
    },
    {
      value: 300,
      label: '300',
    },
    {
      value: 400,
      label: '400',
    },
    {
      value: 500,
      label: '500',
    },
    {
      value: 600,
      label: t('noLimit.label'),
    },
  ];

  const valueLabelHandler = (value) => {
    if (value > 500) {
      if (value < 550) {
        return 500;
      } else {
        return t('noLimit.label');
      }
    } else {
      return value;
    }
  };

  useEffect(() => {
    if (deviceInfo && isMount.current && cpuServerInitialValue) {
      const minCore = Math.ceil((1 / deviceInfo?.cpu_cores) * 100);
      let minRam = 0;
      if (deviceInfo?.ram <= 50 && deviceInfo?.ram <= 99) {
        minRam = 2;
      } else {
        minRam = Math.ceil((1 / deviceInfo?.ram) * 100);
      }

      if (modalType === 'ADD') {
        cpuServerSliderHandler('core', minCore);
        cpuServerSliderHandler('ram', minCore);
      }

      setMinCores(minCore);
      setMinRam(minRam);
      setCoresValue(cpuServerInitialValue?.cores);
      setRamValue(cpuServerInitialValue?.ram);
    }

    return () => {
      if (deviceInfo) {
        isMount.current = false;
      }
    };
  }, [cpuServerInitialValue, cpuServerSliderHandler, deviceInfo, modalType]);

  useEffect(() => {
    if (modalType === 'ADD' && isMount.current && addNodeMinNum) {
      setCoresValue(100);
      setRamValue(100);
      const minCore = Math.ceil((1 / addNodeMinNum?.cores) * 100);
      let minRam = 0;
      if (addNodeMinNum?.ram <= 50 && addNodeMinNum?.ram <= 99) {
        minRam = 2;
      } else {
        minRam = Math.ceil((1 / addNodeMinNum?.ram) * 100);
      }

      setMinCores(minCore);
      setMinRam(minRam);
    }

    return () => {
      if (addNodeMinNum) {
        isMount.current = false;
      }
    };
  }, [addNodeMinNum, modalType]);

  return (
    <>
      <p className={cx('input-group-title')}>{t('serverSetting.label')}</p>
      {modeOptions.map(
        ({ value, checked }, idx) =>
          checked && (
            <div className={cx('inner-box')} key={idx}>
              <div className={cx('box-title')}>
                {value === 'gpu' ? t('gpuServer.label') : t('cpuServer.label')}
              </div>
              <div className={cx('row')}>
                <InputBoxWithLabel
                  labelText={
                    value === 'gpu'
                      ? t('cpuUsagePerGpu.label', { numGpuResource })
                      : t('cpuUsagePerPod.label')
                  }
                  disableErrorMsg
                  labelSize='medium'
                >
                  <InputNumber
                    name={value === 'gpu' ? 'gpuModeCpuRsc' : 'cpuModeCpuRsc'}
                    value={value === 'gpu' ? gpuModeCpuRsc : cpuModeCpuRsc}
                    optional
                    onChange={inputHandler}
                    min={0}
                    max={maxCpuResource}
                    placeholder={`${maxCpuResource} Core Available`}
                    status={
                      value === 'gpu'
                        ? gpuModeCpuRscError !== '' &&
                          gpuModeCpuRscError !== undefined &&
                          'error'
                        : cpuModeCpuRscError !== '' &&
                          cpuModeCpuRscError !== undefined &&
                          'error'
                    }
                    error={
                      value === 'gpu' ? gpuModeCpuRscError : cpuModeCpuRscError
                    }
                    size='medium'
                    bottomTextExist={true}
                  />
                </InputBoxWithLabel>
              </div>
              <div className={cx('row')}>
                <InputBoxWithLabel
                  labelText={
                    value === 'gpu'
                      ? t('ramUsagePerGpu.label')
                      : t('ramUsagePerPod.label')
                  }
                  disableErrorMsg
                  labelSize='medium'
                >
                  <InputNumber
                    label={
                      value === 'gpu'
                        ? t('ramUsagePerGpu.label')
                        : t('ramUsagePerPod.label')
                    }
                    name={value === 'gpu' ? 'gpuModeRam' : 'cpuModeRam'}
                    value={
                      value === 'gpu'
                        ? parseInt(gpuModeRam)
                        : parseInt(cpuModeRam)
                    }
                    optional
                    onChange={inputHandler}
                    min={0}
                    max={maxRamResource}
                    placeholder={`${parseInt(maxRamResource, 10)} GB Available`}
                    status={
                      value === 'gpu'
                        ? gpuModeRamError !== '' &&
                          gpuModeRamError !== undefined &&
                          'error'
                        : cpuModeRamError !== '' &&
                          cpuModeRamError !== undefined &&
                          'error'
                    }
                    error={value === 'gpu' ? gpuModeRamError : cpuModeRamError}
                    step={1}
                    size='medium'
                    bottomTextExist={true}
                  />
                </InputBoxWithLabel>
              </div>

              {value === 'cpu' && (
                <div className={cx('row')}>
                  {t('cpuResourceOverdistributing.label')}
                  <div className={cx('slider-box')}>
                    <div className={cx('slider-title')}>
                      {t('coreUsageRestrictions.label')}
                    </div>
                    <div className={cx('slider-gage')}>
                      <Slider
                        valueLabelDisplay='auto'
                        aria-label='pretto slider'
                        defaultValue={coresValue}
                        value={coresValue}
                        marks={SLIDER_MARKS}
                        step={1}
                        min={0}
                        max={600}
                        onChange={(e, v) => inputValueHandler('core', v)}
                        // onMouseUp={(e) => mouseUpHandler()}
                        // onMouseDown={mouseDownHandler}
                        onChangeCommitted={(e, val) => {
                          if (val > 500 && val <= 550) {
                            setCoresValue(500);
                          } else if (val > 550) {
                            setCoresValue(600);
                          } else if (minCores > val) {
                            setCoresValue(minCores);
                          }
                        }}
                        valueLabelFormat={(v) => valueLabelHandler(v)}
                        sx={{
                          color: '#f5f5f5',
                          width: 500,
                          height: 12,
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
                          value={
                            coresValue > 550
                              ? ''
                              : coresValue > 500
                              ? 500
                              : coresValue
                          }
                          onChange={(e) => {
                            setCoresValue(Number(e.value));
                          }}
                          placeholder={
                            coresValue > 550 ? t('noLimit.label') : ''
                          }
                          onBlur={(e) => {
                            if (
                              coresValue < minCores ||
                              coresValue === '' ||
                              isNaN(e.target.value)
                            ) {
                              setCoresValue(minCores);
                            }
                          }}
                          customSize={{
                            textAlign: 'right',
                          }}
                        />
                        <div className={cx('percent')}>%</div>
                      </div>
                    </div>
                  </div>
                  <div className={cx('slider-box')}>
                    <div className={cx('slider-title')}>
                      {t('ramUsageRestrictions.label')}
                    </div>
                    <div className={cx('slider-gage')}>
                      <Slider
                        valueLabelDisplay='auto'
                        aria-label='pretto slider'
                        defaultValue={ramValue}
                        value={ramValue}
                        marks={SLIDER_MARKS}
                        step={1}
                        min={0}
                        max={600}
                        onChange={(e, v) => inputValueHandler('ram', v)}
                        // onMouseUp={(e) => mouseUpHandler()}
                        // onMouseDown={mouseDownHandler}
                        onChangeCommitted={(e, val) => {
                          if (val > 500 && val <= 550) {
                            setRamValue(500);
                          } else if (val > 550) {
                            setRamValue(600);
                          } else if (minRam > val) {
                            setRamValue(minRam);
                          }
                        }}
                        valueLabelFormat={(v) => valueLabelHandler(v)}
                        sx={{
                          color: '#f5f5f5',
                          width: 500,
                          height: 12,
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
                          value={
                            ramValue > 550
                              ? ''
                              : ramValue > 500
                              ? 500
                              : ramValue
                          }
                          onChange={(e) => {
                            if (Number(e.value) > 500) {
                              if (Number(e.value) < 550) {
                                setRamValue(500);
                              }
                            } else {
                              setRamValue(Number(e.value));
                            }
                          }}
                          max={500}
                          placeholder={ramValue > 550 ? t('noLimit.label') : ''}
                          onBlur={(e) => {
                            if (
                              ramValue < minRam ||
                              ramValue === '' ||
                              isNaN(e.target.value)
                            ) {
                              setRamValue(minRam);
                            }
                          }}
                          customSize={{
                            textAlign: 'right',
                          }}
                        />
                        <div className={cx('percent')}>%</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ),
      )}
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('temporaryCapacitySizeLimit.label')}
          disableErrorMsg
          labelSize='large'
        >
          <InputNumber
            name={'temporarySizeLimit'}
            value={parseInt(temporarySizeLimit)}
            onChange={inputHandler}
            min={0}
            status={
              temporarySizeLimitError !== '' &&
              temporarySizeLimitError !== undefined &&
              'error'
            }
            error={temporarySizeLimitError}
            size='medium'
            bottomTextExist={true}
          />
        </InputBoxWithLabel>
      </div>
    </>
  );
}

export default ServerResourceSettingForm;
