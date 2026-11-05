// i18n
import { useTranslation } from 'react-i18next';

// Components
import { InputNumber } from '@jonathan/ui-react';
import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import GpuModelSelectBox from '@src/components/organisms/ResourceSettingBox/GpuModelSelectBox';
import CpuModelSelectBox from '@src/components/organisms/ResourceSettingBox/CpuModelSelectBox';

// CSS Module
import classNames from 'classnames/bind';
import style from './ResourceSettingBox.module.scss';
const cx = classNames.bind(style);

const IS_HIDE_SPECIFIC_GPU_MODEL =
  import.meta.env.VITE_REACT_APP_IS_HIDE_SPECIFIC_GPU_MODEL === 'true';
const IS_HIDE_SPECIFIC_CPU_MODEL =
  import.meta.env.VITE_REACT_APP_IS_HIDE_SPECIFIC_CPU_MODEL === 'true';

function ResourceSettingBox({
  gpuModelType,
  cpuModelType,
  gpuTotalCount,
  maxGpuUsageCount,
  gpuTotalCountForRandom,
  maxGpuUsageCountForRandom,
  minGpuUsage,
  maxGpuUsage,
  isGuranteedGpu,
  isMigModel,
  gpuModelListOptions,
  gpuModelList,
  cpuModelList,
  gpuUsage,
  gpuUsageError,
  gpuModelTypeHandler,
  cpuModelTypeHandler,
  gpuSelectHandler,
  gpuUsageHandler,
  visualStatus,
  modelTypeHandler,
  modelType,
  sliderData,
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
  totalSliderHandler,
  sliderSwitchHandler,
  gpuSliderSwitch,
  detailGpuValueHandler,
  checkboxHandler,
  detailCpuValueHandler,
  cpuAndRamSliderValue,
  cpuSwitchStatus,
  cpuSliderMove,
  ramDetailValue,
  cpuDetailValue,
  ramTotalValue,
  cpuTotalValue,
  detailSelectedOptions,
  cpuSelectedOptions,
  prevSliderData,
  sliderIsValidate,
}) {
  const { t } = useTranslation();

  return (
    <>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('resourceType.label')}
          labelSize='large'
        >
          <Radio
            options={[
              {
                label: 'gpuModel.label',
                value: 0,
              },
              { label: 'cpuModel.label', value: 1 },
            ]}
            name='modelTypeOptions'
            value={modelType}
            onChange={(e) => {
              modelTypeHandler(Number(e.target.value));
            }}
            customStyle={{ marginTop: '15px' }}
          />
        </InputBoxWithLabel>
        {modelType === 0 && !IS_HIDE_SPECIFIC_GPU_MODEL && (
          <InputBoxWithLabel
            labelText={t('gpuModel.label')}
            labelSize='large'
            disableErrorMsg={gpuModelType === 1}
          >
            <Radio
              readOnly={visualStatus?.resourceInfo.disable}
              options={[
                {
                  label: 'random.label',
                  value: 0,
                },
                { label: 'specificModel.label', value: 1 },
              ]}
              name='gpuModelType'
              value={gpuModelType}
              onChange={(e) => {
                gpuModelTypeHandler(e.target.value);
              }}
            />
          </InputBoxWithLabel>
        )}
        {modelType === 1 && !IS_HIDE_SPECIFIC_CPU_MODEL && (
          <InputBoxWithLabel
            labelText={t('cpuModel.label')}
            labelSize='large'
            disableErrorMsg={cpuModelType === 1}
          >
            <Radio
              options={[
                {
                  label: 'random.label',
                  value: 0,
                },
                { label: 'specificModel.label', value: 1 },
              ]}
              name='cpuModelType'
              value={cpuModelType}
              onChange={(e) => {
                cpuModelTypeHandler(e.target.value);
              }}
            />
          </InputBoxWithLabel>
        )}
      </div>
      {!IS_HIDE_SPECIFIC_GPU_MODEL &&
        sliderData &&
        modelType === 0 &&
        gpuModelType === 1 && ( //GPU이면서 specific model
          <div className={cx('row')}>
            <GpuModelSelectBox
              options={gpuModelListOptions}
              onChange={gpuSelectHandler}
              cpuModelList={cpuModelList}
              gpuSelectedOptions={gpuSelectedOptions}
              gpuDetailSelectedOptions={gpuDetailSelectedOptions}
              gpuTotalValue={gpuTotalValue}
              gpuRamTotalValue={gpuRamTotalValue}
              gpuDetailValue={gpuDetailValue}
              gpuRamDetailValue={gpuRamDetailValue}
              gpuTotalSliderMove={gpuTotalSliderMove}
              gpuSwitchStatus={gpuSwitchStatus}
              gpuAndRamSliderValue={gpuAndRamSliderValue}
              totalValueHandler={totalValueHandler}
              totalSliderHandler={totalSliderHandler}
              sliderSwitchHandler={sliderSwitchHandler}
              sliderSwitchStatus={gpuSliderSwitch} // ! delete
              detailGpuValueHandler={detailGpuValueHandler}
              checkboxHandler={checkboxHandler}
              prevSliderData={prevSliderData}
            />
          </div>
        )}
      {!IS_HIDE_SPECIFIC_CPU_MODEL &&
        sliderData &&
        modelType === 1 &&
        cpuModelType === 1 && (
          <div className={cx('row')}>
            <CpuModelSelectBox
              options={sliderData?.cpu_model_status}
              cpuSelectedOptions={cpuSelectedOptions}
              detailSelectedOptions={detailSelectedOptions}
              cpuTotalValue={cpuTotalValue}
              ramTotalValue={ramTotalValue}
              cpuDetailValue={cpuDetailValue}
              ramDetailValue={ramDetailValue}
              cpuSwitchStatus={cpuSwitchStatus}
              cpuSliderMove={cpuSliderMove}
              cpuAndRamSliderValue={cpuAndRamSliderValue}
              checkboxHandler={checkboxHandler}
              detailCpuValueHandler={detailCpuValueHandler}
              totalValueHandler={totalValueHandler}
              totalSliderHandler={totalSliderHandler}
              sliderSwitchHandler={sliderSwitchHandler}
              prevSliderData={prevSliderData}
            />
          </div>
        )}
      {modelType !== 1 && (
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('gpuUsage.label')}
            labelSize='large'
            disableErrorMsg
          >
            <InputNumber
              placeholder={
                gpuModelType === 0 || (gpuModelList && gpuModelList.length > 0)
                  ? t(
                      isGuranteedGpu
                        ? 'guaranteedGpuStatus.placeholder'
                        : 'gpuStatus.placeholder',
                      {
                        total:
                          gpuModelType === 0
                            ? gpuTotalCountForRandom
                            : gpuTotalCount,
                        free:
                          gpuModelType === 0
                            ? maxGpuUsageCountForRandom
                            : maxGpuUsageCount,
                      },
                    )
                  : t('gpuUsage.placeholder')
              }
              onChange={gpuUsageHandler}
              name='gpuUsage'
              value={gpuUsage}
              testId='gpu-count-input'
              status={
                gpuUsageError === null
                  ? ''
                  : gpuUsageError === ''
                  ? 'success'
                  : 'error'
              }
              error={t(gpuUsageError)}
              info={
                gpuTotalCount < gpuUsage
                  ? t('gpuUsageOver.info.message')
                  : gpuModelType === 1
                  ? gpuModelList
                    ? isMigModel
                      ? t('gpuUsageMigModel.info.message')
                      : gpuModelList.length > 1 &&
                        t('gpuUsageMultiModel.info.message')
                    : null
                  : null
              }
              min={minGpuUsage}
              max={maxGpuUsage}
              isReadOnly={
                // !workspace ||
                visualStatus?.resourceInfo.disable ||
                (gpuModelType === 1 && !sliderIsValidate) ||
                (isMigModel && modelType === 0 && gpuModelType === 1)
              }
              bottomTextExist={true}
              size='large'
            />
          </InputBoxWithLabel>
        </div>
      )}
    </>
  );
}

export default ResourceSettingBox;
