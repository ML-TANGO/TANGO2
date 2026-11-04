// i18n
import { useTranslation } from 'react-i18next';

// Components
import { InputText, Button } from '@jonathan/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './TrainingParameterForm.module.scss';
const cx = classNames.bind(style);

const TrainingParameterForm = ({
  trainingParameters,
  /** 이벤트 핸들러 */
  addInputForm,
  removeInputForm,
  inputHandler, // 입력 이벤트 핸들러
}) => {
  const { t } = useTranslation();
  return (
    <div className={cx('training-parameter-form')}>
      <div className={cx('parameter-list')}>
        <div className={cx('label-box')}>
          <label className={cx('label')}>{t('name.label')}</label>
          <label className={cx('label')}>{t('defaultValue.label')}</label>
          <label className={cx('label')}>
            {t('description.label')}{' '}
            <span className={cx('optional')}>- {t('optional.label')}</span>
          </label>
        </div>
        {trainingParameters.length > 0 ? (
          trainingParameters.map(({ name, value, description }, idx) => {
            return (
              <div key={idx} className={cx('input-box')}>
                <div className={cx('input-wrap')}>
                  <InputText
                    size='medium'
                    name='name'
                    value={name}
                    onChange={(e) => {
                      inputHandler(e, idx);
                    }}
                    onClear={() =>
                      inputHandler({ target: { name: 'name', value: '' } }, idx)
                    }
                    disableLeftIcon
                  />
                </div>
                <div className={cx('input-wrap')}>
                  <InputText
                    size='medium'
                    name='value'
                    value={value}
                    onChange={(e) => {
                      inputHandler(e, idx);
                    }}
                    onClear={() =>
                      inputHandler(
                        { target: { name: 'value', value: '' } },
                        idx,
                      )
                    }
                    disableLeftIcon
                  />
                </div>
                <div className={cx('input-wrap')}>
                  <InputText
                    size='medium'
                    name='description'
                    value={description}
                    onChange={(e) => {
                      inputHandler(e, idx);
                    }}
                    onClear={() =>
                      inputHandler(
                        { target: { name: 'description', value: '' } },
                        idx,
                      )
                    }
                    disableLeftIcon
                  />
                </div>
                <button
                  className={cx(
                    'remove-btn',
                    trainingParameters.length === 1 && 'disabled',
                  )}
                  onClick={() => {
                    if (trainingParameters.length !== 1) {
                      removeInputForm(idx);
                    }
                  }}
                ></button>
              </div>
            );
          })
        ) : (
          <div></div>
        )}
      </div>
      <div className={cx('btn-wrap')}>
        <Button type='secondary' size='medium' onClick={addInputForm}>
          {t('add.label')}
        </Button>
      </div>
    </div>
  );
};

export default TrainingParameterForm;
