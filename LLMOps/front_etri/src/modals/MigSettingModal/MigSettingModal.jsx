import { Radio, Selectbox } from '@jonathan/ui-react';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import ModalFooter from '@src/components/organisms/modal/ModalFooter';
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
import ModalTemplate from '@src/components/templates/ModalTemplate';

import classNames from 'classnames/bind';
import style from './MigSettingModal.module.scss';

const cx = classNames.bind(style);

const MigSettingModal = ({ data, type }) => {
  const { t } = useTranslation();

  const [inputState, setInputState] = useState({
    radioMode: 0,
    instanceCount: null,
  });

  const onChangeHandler = (e) => {
    setInputState((prev) => {
      return {
        ...prev,
        radioMode: +e.target.value,
        instanceCount: null,
      };
    });
  };

  const handleInstanceCount = (value) => {
    setInputState((prev) => {
      return {
        ...prev,
        instanceCount: value,
      };
    });
  };

  const handleErrorMessage = (migMode, selectCount) => {
    if (migMode === 0 && !selectCount) return t('node.MIGModal.placeholder');
    return '';
  };

  return (
    <ModalTemplate
      headerRender={<ModalHeader title={t('migSetting.label')} />}
      footerRender={
        <ModalFooter
          submit={{
            text: t('saveBtn.label'),
            func: () => {},
          }}
          cancel={{
            text: t('cancel.label'),
            func: () => {},
          }}
          type={type}
          isValidate={
            !handleErrorMessage(inputState.radioMode, inputState.instanceCount)
          }
          deployFooterMessage={handleErrorMessage(
            inputState.radioMode,
            inputState.instanceCount,
          )}
        />
      }
    >
      <div className={cx('modal-content')}>
        <div className={cx('input-group')}>
          <div className={cx('wrapper')}>
            <InputBoxWithLabel
              labelText={`MIG ${t('onAndOff.label')}`}
              labelSize='large'
              disableErrorMsg={true}
            >
              <Radio
                selectedValue={inputState.radioMode}
                options={[
                  { label: t('turnOn.label'), value: 0 },
                  { label: t('turnOff.label'), value: 1 },
                ]}
                customStyle={{
                  marginBottom: '26px',
                  transform: 'translateX(-6px)',
                }}
                onChange={(e) => onChangeHandler(e)}
              />
            </InputBoxWithLabel>
          </div>
          {inputState.radioMode === 0 && (
            <div className={cx('wrapper')}>
              <InputBoxWithLabel
                labelText={t('node.MIGModal.count')}
                labelSize='large'
                disableErrorMsg={true}
              >
                <Selectbox
                  list={[
                    { label: 2, value: 2 },
                    { label: 3, value: 3 },
                    { label: 5, value: 5 },
                    { label: 6, value: 6 },
                    { label: 7, value: 7 },
                  ]}
                  placeholder={t('node.MIGModal.placeholder')}
                  onChange={({ value }) => handleInstanceCount(value)}
                />
              </InputBoxWithLabel>
            </div>
          )}
        </div>
      </div>
    </ModalTemplate>
  );
};

export default MigSettingModal;
