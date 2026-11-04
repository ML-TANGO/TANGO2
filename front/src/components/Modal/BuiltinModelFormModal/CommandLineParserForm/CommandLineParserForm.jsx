// i18n
import { useTranslation } from 'react-i18next';

// Components
import { InputText } from '@jonathan/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './CommandLineParserForm.module.scss';
const cx = classNames.bind(style);

function CommandLineParserForm({
  commandType,
  commandName,
  commandValue,
  textInputHandler,
  parserInputHandler,
  parserList,
}) {
  const { t } = useTranslation();
  return (
    <div>
      {commandName !== undefined && (
        <div className={cx('row')}>
          <label className={cx('label')}>
            {t('requiredCommandLine.label')}
          </label>
          <InputText
            size='medium'
            placeholder='python xxx.py'
            name={commandName}
            value={commandValue}
            onChange={textInputHandler}
            disableLeftIcon
            disableClearBtn
          />
        </div>
      )}
      <div>
        {parserList.map(({ label, value, placeholder, optional }, idx) => {
          return (
            <div key={idx} className={cx('row')}>
              <div className={cx('text-wrap')}>
                <label className={cx('label')}>
                  {t(`${label}.label`)}{' '}
                  {optional && (
                    <span className={cx('optional')}>
                      - {t('optional.label')}
                    </span>
                  )}
                </label>
                <InputText
                  size='medium'
                  placeholder={placeholder}
                  name={label}
                  value={value}
                  onChange={(e) => parserInputHandler(e, commandType)}
                  leftIcon='/images/icon/ic-parser.svg'
                  disableLeftIcon={false}
                  disableClearBtn
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default CommandLineParserForm;
