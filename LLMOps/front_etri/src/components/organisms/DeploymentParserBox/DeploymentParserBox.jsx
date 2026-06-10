// i18n
import { useTranslation } from 'react-i18next';

// Components
import { InputText } from '@jonathan/ui-react';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// CSS module
import classNames from 'classnames/bind';
import style from './DeploymentParserBox.module.scss';
const cx = classNames.bind(style);

function DeploymentParserBox({ parserList, parserInputHandler }) {
  const { t } = useTranslation();
  return (
    <div className={cx('wrapper')}>
      <label className={cx('label')}>
        {t('deploymentRunCommandParser.label')}
      </label>
      <div className={cx('command-form')}>
        <div>
          {parserList.map(({ label, value, placeholder, optional }, idx) => {
            return (
              <div key={idx} className={cx('row')}>
                <div className={cx('text-wrap')}>
                  <InputBoxWithLabel
                    labelText={t(`${label}.label`)}
                    optionalText={optional ? t('optional.label') : ''}
                  >
                    <InputText
                      size='medium'
                      placeholder={t(placeholder)}
                      name={label}
                      value={value}
                      onChange={(e) => parserInputHandler(e)}
                      leftIcon='/images/icon/ic-parser.svg'
                      disableLeftIcon={false}
                      disableClearBtn
                    />
                  </InputBoxWithLabel>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default DeploymentParserBox;
