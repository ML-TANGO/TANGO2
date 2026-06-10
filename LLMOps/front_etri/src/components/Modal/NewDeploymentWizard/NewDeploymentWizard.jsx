import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { callApi, STATUS_SUCCESS } from '@src/network';
import classNames from 'classnames/bind';
import style from './NewDeploymentWizard.module.scss';

const cx = classNames.bind(style);

function NewDeploymentWizard({ isOpen, onClose, onSubmit }) {
  const { t } = useTranslation();
  const [currentStep, setCurrentStep] = useState(1);
  
  // Step 1: Model Selection
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState(null);
  const [isLoadingModels, setIsLoadingModels] = useState(false);

  // Step 2: Convert Type Selection
  const [convertType, setConvertType] = useState('');

  // Step 3: Target Device Selection
  const [targetDevice, setTargetDevice] = useState('');
  const [deploymentName, setDeploymentName] = useState('');

  // Load models on open
  useEffect(() => {
    if (isOpen) {
      setIsLoadingModels(true);
      callApi({ url: 'models', method: 'GET' })
        .then((res) => {
          if (res.status === STATUS_SUCCESS) {
            setModels(res.result || []);
          }
        })
        .catch((err) => {
          console.error('Failed to load models:', err);
        })
        .finally(() => {
          setIsLoadingModels(false);
        });
      
      // Reset state
      setCurrentStep(1);
      setSelectedModel(null);
      setConvertType('');
      setTargetDevice('');
      setDeploymentName('');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleNext = () => {
    if (currentStep < 3) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrev = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleDeploy = () => {
    if (selectedModel && convertType && targetDevice && deploymentName.trim()) {
      onSubmit({
        model_name: selectedModel.name,
        convert_type: convertType,
        target_device: targetDevice,
        deployment_name: deploymentName.trim(),
      });
    }
  };

  // Validation
  const isNextDisabled = () => {
    if (currentStep === 1) return !selectedModel;
    if (currentStep === 2) return !convertType;
    if (currentStep === 3) return !targetDevice || !deploymentName.trim();
    return true;
  };

  return (
    <div className={cx('overlay')} onClick={onClose}>
      <div className={cx('modal-container')} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={cx('modal-header')}>
          <h2>{t('newDeployment.label', 'New Deployment')}</h2>
          <button className={cx('close-btn')} onClick={onClose}>
            &times;
          </button>
        </div>

        {/* Steps Progress Bar */}
        <div className={cx('steps-indicator')}>
          <div className={cx('step-item', currentStep >= 1 && 'active', currentStep > 1 && 'completed')}>
            <span className={cx('step-number')}>1</span>
            <span className={cx('step-label')}>{t('wizard.step1', 'Model Selection')}</span>
          </div>
          <div className={cx('step-line', currentStep > 1 && 'active')}></div>
          <div className={cx('step-item', currentStep >= 2 && 'active', currentStep > 2 && 'completed')}>
            <span className={cx('step-number')}>2</span>
            <span className={cx('step-label')}>{t('wizard.step2', 'Convert Format')}</span>
          </div>
          <div className={cx('step-line', currentStep > 2 && 'active')}></div>
          <div className={cx('step-item', currentStep >= 3 && 'active')}>
            <span className={cx('step-number')}>3</span>
            <span className={cx('step-label')}>{t('wizard.step3', 'Target Device')}</span>
          </div>
        </div>

        {/* Content */}
        <div className={cx('modal-body')}>
          {currentStep === 1 && (
            <div className={cx('step-content')}>
              <h3>{t('wizard.selectModelTitle', 'Select LLM/VLM Model')}</h3>
              <p className={cx('step-description')}>
                {t('wizard.selectModelDesc', 'Choose a trained LLM/VLM model from the list.')}
              </p>
              
              {isLoadingModels ? (
                <div className={cx('loading-box')}>
                  <div className={cx('spinner')}></div>
                  <span>{t('loading.label', 'Loading models...')}</span>
                </div>
              ) : (
                <div className={cx('models-list')}>
                  {models.map((model) => {
                    const isSelected = selectedModel?.id === model.id;
                    const isVlm = model.load_type === 'multimodal';
                    const formattedDate = model.created_at ? new Date(model.created_at).toLocaleDateString() : '-';
                    const fineTunedStatus = model.is_finetuned ? t('yes.label', 'Yes') : t('no.label', 'No');

                    return (
                      <div
                        key={model.id}
                        className={cx('model-row', isSelected && 'selected')}
                        onClick={() => setSelectedModel(model)}
                      >
                        <div className={cx('radio-btn', isSelected && 'selected')}></div>
                        <div className={cx('model-info')}>
                          <span className={cx('model-name')}>{model.name}</span>
                          <span className={cx('model-type', isVlm ? 'vlm' : 'llm')}>
                            {isVlm ? 'VLM' : 'LLM'}
                          </span>
                          <span className={cx('model-date')}>{formattedDate}</span>
                          <span className={cx('model-finetuned', model.is_finetuned ? 'yes' : 'no')}>
                            FT: {fineTunedStatus}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {currentStep === 2 && (
            <div className={cx('step-content')}>
              <h3>{t('wizard.selectFormatTitle', 'Select Convert Format')}</h3>
              <p className={cx('step-description')}>
                {t('wizard.selectFormatDesc', 'Choose optimization technique to convert model format.')}
              </p>

              <div className={cx('format-cards')}>
                <div
                  className={cx('format-card', convertType === 'vLLM' && 'selected')}
                  onClick={() => setConvertType('vLLM')}
                >
                  <div className={cx('format-icon')}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                    </svg>
                  </div>
                  <span className={cx('format-title')}>vLLM</span>
                  <span className={cx('format-desc')}>
                    High-throughput GPU serving
                  </span>
                </div>

                <div
                  className={cx('format-card', convertType === 'llama.cpp' && 'selected')}
                  onClick={() => setConvertType('llama.cpp')}
                >
                  <div className={cx('format-icon')}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
                    </svg>
                  </div>
                  <span className={cx('format-title')}>llama.cpp</span>
                  <span className={cx('format-desc')}>
                    Lightweight CPU/Edge inference
                  </span>
                </div>

                <div
                  className={cx('format-card', convertType === 'TensorRT' && 'selected')}
                  onClick={() => setConvertType('TensorRT')}
                >
                  <div className={cx('format-icon')}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10"></circle>
                      <line x1="2" y1="12" x2="22" y2="12"></line>
                      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                    </svg>
                  </div>
                  <span className={cx('format-title')}>TensorRT</span>
                  <span className={cx('format-desc')}>
                    NVIDIA TensorRT optimized
                  </span>
                </div>
              </div>
            </div>
          )}

          {currentStep === 3 && (
            <div className={cx('step-content')}>
              <h3>{t('wizard.selectDeviceTitle', 'Select Target Device')}</h3>
              <p className={cx('step-description')}>
                {t('wizard.selectDeviceDesc', 'Select hardware device architecture to deploy target.')}
              </p>

              <div className={cx('devices-grid')}>
                <div
                  className={cx('device-card', targetDevice === 'Local' && 'selected')}
                  onClick={() => setTargetDevice('Local')}
                >
                  <div className={cx('device-icon')}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
                      <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
                      <line x1="6" y1="6" x2="6.01" y2="6"></line>
                      <line x1="6" y1="18" x2="6.01" y2="18"></line>
                    </svg>
                  </div>
                  <span className={cx('device-name')}>{t('device.local', 'Local')}</span>
                </div>

                <div
                  className={cx('device-card', targetDevice === 'Cloud' && 'selected')}
                  onClick={() => setTargetDevice('Cloud')}
                >
                  <div className={cx('device-icon')}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path>
                    </svg>
                  </div>
                  <span className={cx('device-name')}>{t('device.cloud', 'Cloud')}</span>
                </div>

                <div
                  className={cx('device-card', targetDevice === 'Orin' && 'selected')}
                  onClick={() => setTargetDevice('Orin')}
                >
                  <div className={cx('device-icon')}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="4" y="4" width="16" height="16" rx="2"></rect>
                      <rect x="9" y="9" width="6" height="6"></rect>
                      <line x1="9" y1="1" x2="9" y2="4"></line>
                      <line x1="15" y1="1" x2="15" y2="4"></line>
                      <line x1="9" y1="20" x2="9" y2="23"></line>
                      <line x1="15" y1="20" x2="15" y2="23"></line>
                      <line x1="20" y1="9" x2="23" y2="9"></line>
                      <line x1="20" y1="15" x2="23" y2="15"></line>
                      <line x1="1" y1="9" x2="4" y2="9"></line>
                      <line x1="1" y1="15" x2="4" y2="15"></line>
                    </svg>
                  </div>
                  <span className={cx('device-name')}>{t('device.orin', 'Orin')}</span>
                </div>

                <div
                  className={cx('device-card', targetDevice === 'Raspberry Pi' && 'selected')}
                  onClick={() => setTargetDevice('Raspberry Pi')}
                >
                  <div className={cx('device-icon')}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                      <path d="M2 17l10 5 10-5"></path>
                      <path d="M2 12l10 5 10-5"></path>
                    </svg>
                  </div>
                  <span className={cx('device-name')}>{t('device.raspberrypi', 'Raspberry Pi')}</span>
                </div>
              </div>

              <div className={cx('name-input-section')}>
                <label htmlFor="deployment-name">
                  {t('wizard.deploymentNameLabel', 'Deployment Name')}
                </label>
                <input
                  id="deployment-name"
                  type="text"
                  placeholder={t('wizard.deploymentNamePlaceholder', 'Enter deployment name...')}
                  value={deploymentName}
                  onChange={(e) => setDeploymentName(e.target.value)}
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer Buttons */}
        <div className={cx('modal-footer')}>
          <div>
            {currentStep > 1 ? (
              <button className={cx('btn', 'btn-secondary')} onClick={handlePrev}>
                {t('prev.label', 'Back')}
              </button>
            ) : (
              <button className={cx('btn', 'btn-secondary')} onClick={onClose}>
                {t('cancel.label', 'Cancel')}
              </button>
            )}
          </div>
          <div>
            {currentStep < 3 ? (
              <button
                className={cx('btn', 'btn-primary')}
                disabled={isNextDisabled()}
                onClick={handleNext}
              >
                {t('next.label', 'Next')}
              </button>
            ) : (
              <button
                className={cx('btn', 'btn-success')}
                disabled={isNextDisabled()}
                onClick={handleDeploy}
              >
                {t('deploy.label', 'Deploy')}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default NewDeploymentWizard;
