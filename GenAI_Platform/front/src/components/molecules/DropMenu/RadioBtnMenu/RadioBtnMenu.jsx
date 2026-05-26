// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button } from '@jonathan/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './RadioBtnMenu.module.scss';
const cx = classNames.bind(style);

/**
 * 라디오 버튼 메뉴 컴포넌트
 * @param {{
 *    options: Array<
 *      { name: string, options: Array<
 *        { label: string, value: any }
 *      > }
 *    >,
 *    onChange: () => {},
 *    clearAll: () => {},
 *  },
 * } props
 * @returns
 */
function RadioBtnMenu({ options, onChange, clearAll }) {
  const { t } = useTranslation();

  return (
    <div className={cx('radio-btn-menu')}>
      {options.map(({ name, options: opts, checked }, groupIndex) => (
        <div className={cx('group')} key={groupIndex}>
          <p className={cx('group-name')}>{t(name)}</p>
          <div className={cx('options')}>
            {opts.map(({ label }, optionIndex) => (
              <button
                className={cx('radio-btn', checked === optionIndex && 'active')}
                key={optionIndex}
                onClick={() => {
                  onChange(groupIndex, optionIndex);
                }}
              >
                {t(label)}
              </button>
            ))}
          </div>
        </div>
      ))}
      <div className={cx('bottom-box')}>
        <Button type='primary-reverse' size='x-small' onClick={clearAll}>
          {t('clearAll.label')}
        </Button>
      </div>
    </div>
  );
}

export default RadioBtnMenu;
