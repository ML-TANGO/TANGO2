// i18n
import { useTranslation } from 'react-i18next';

// Components
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import { InputText, InputNumber, Textarea, Radio } from '@jonathan/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './NetworkGroupBasicInfoForm.module.scss';
const cx = classNames.bind(style);

function NetworkGroupBasicInfoForm({
  modalType,
  name,
  nameError,
  category,
  categoryOptions,
  speed,
  speedError,
  description,
  inputHandler,
}) {
  const { t } = useTranslation();

  return (
    <div className={cx('form')}>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('network.groupName.label')}
          labelSize='large'
          errorMsg={t(nameError)}
        >
          <InputText
            size='large'
            name='name'
            value={name}
            onChange={inputHandler}
            onClear={() =>
              inputHandler({ target: { name: 'name', value: '' } })
            }
            disableLeftIcon
            disableClearBtn={false}
            autoFocus={modalType === 'CREATE_NETWORK_GROUP'}
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('network.category.label')}
          labelSize='large'
        >
          <Radio
            name='category'
            options={categoryOptions}
            selectedValue={category}
            onChange={inputHandler}
            isReadonly={modalType === 'NETWORK_GROUP_SETTING'}
            t={t}
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('network.speed.label')}
          labelSize='large'
          errorMsg={t(speedError)}
        >
          <div className={cx('speed')}>
            <InputNumber
              size='large'
              name='speed'
              value={speed}
              onChange={inputHandler}
              min={0}
              step={10}
              customSize={{
                width: '160px',
                marginRight: '8px',
                textAlign: 'right',
              }}
            />
            <span className={cx('unit')}>Gbps</span>
          </div>
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('description.label')}
          optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='large'
        >
          <Textarea
            size='large'
            name='description'
            value={description}
            placeholder={t('network.description.placeholder')}
            onChange={inputHandler}
            maxLength={500}
            isShowMaxLength={true}
          />
        </InputBoxWithLabel>
      </div>
    </div>
  );
}

export default NetworkGroupBasicInfoForm;
