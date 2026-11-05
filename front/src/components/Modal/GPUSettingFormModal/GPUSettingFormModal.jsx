// i18n
import { withTranslation } from 'react-i18next';

// Components
import ModalFrame from '../ModalFrame';
import { InputNumber } from '@jonathan/ui-react';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// CSS Module
import classNames from 'classnames/bind';
import style from './GPUSettingFormModal.module.scss';
const cx = classNames.bind(style);

const GPUSettingFormModal = ({
  data,
  type,
  validate,
  totalGpu,
  trainingGpu,
  trainingGpuError,
  deploymentGpu,
  deploymentGpuError,
  inputHandler,
  onSubmit,
  t,
}) => {
  const { submit, cancel } = data;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };
  return (
    <ModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={type}
      validate={validate}
    >
      <h2 className={cx('title')}>{t('editGpuSettingForm.title.label')}</h2>
      <div className={cx('form')}>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('gpusForTraining.label')}
            disableErrorMsg
            labelSize='large'
          >
            <InputNumber
              placeholder={`${t('availableGpu.label')} : ${
                totalGpu - deploymentGpu
              }`}
              onChange={inputHandler}
              name='trainingGpu'
              value={trainingGpu}
              status={
                trainingGpuError === null
                  ? ''
                  : trainingGpuError === ''
                  ? 'success'
                  : 'error'
              }
              error={trainingGpuError}
              min={0}
              max={totalGpu}
              size='large'
              bottomTextExist={true}
            />
          </InputBoxWithLabel>
        </div>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('gpusForDeployment.label')}
            disableErrorMsg
            labelSize='large'
          >
            <InputNumber
              placeholder={`${t('availableGpu.label')} : ${
                totalGpu - trainingGpu
              }`}
              onChange={inputHandler}
              name='deploymentGpu'
              value={deploymentGpu}
              status={
                deploymentGpuError === null
                  ? ''
                  : deploymentGpuError === ''
                  ? 'success'
                  : 'error'
              }
              error={deploymentGpuError}
              min={0}
              max={totalGpu}
              size='large'
              bottomTextExist={true}
            />
          </InputBoxWithLabel>
        </div>
      </div>
    </ModalFrame>
  );
};

export default withTranslation()(GPUSettingFormModal);
