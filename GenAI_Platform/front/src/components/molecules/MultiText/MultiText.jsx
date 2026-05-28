// i18n

// Components
import { useTranslation } from 'react-i18next';

import { InputText } from '@jonathan/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './MultiText.module.scss';

const cx = classNames.bind(style);

function MultiText({
  label,
  status = '',
  onChange,
  onAdd,
  name,
  onRemove,
  placeholder = '',
  error,
  readOnly,
  multiValues,
  isSampleShow = false,
}) {
  const { t } = useTranslation();
  return (
    <div className={cx('fb', 'input', status, 'input-wrap')}>
      {label && (
        <label className={cx('fb', 'label')}>
          {t(label)}{' '}
          <span className={cx('sample')}>
            {isSampleShow &&
              `(EX) --epochs=value1 --weights=value2 --batch-size=value3 --checkpoint-path=value ...`}
          </span>
        </label>
      )}
      {multiValues && (
        <div className={cx('item-list')}>
          {multiValues.map(({ val }, idx) => (
            <div key={idx} className={cx('fb', 'input', 'item')}>
              <div className={cx('input-wrap')}>
                <InputText
                  placeholder={placeholder}
                  onChange={(e) => {
                    onChange(e, idx);
                  }}
                  size='medium'
                  name={name}
                  value={val}
                  idx={idx}
                  readOnly={readOnly}
                  customStyle={{
                    fontSize: '14px',
                  }}
                />
              </div>
              {/* <button
                className={cx('remove-btn')}
                onClick={() => {
                  onRemove(idx);
                }}
              ></button> */}
            </div>
          ))}
        </div>
      )}
      {/* <Button
        type='secondary'
        size='medium'
        customStyle={{ marginTop: '10px' }}
        onClick={onAdd}
      >
        {t('add.label')}
      </Button> */}
      <span className={cx('error')}>{error && t(error)}</span>
    </div>
  );
}

export default MultiText;
