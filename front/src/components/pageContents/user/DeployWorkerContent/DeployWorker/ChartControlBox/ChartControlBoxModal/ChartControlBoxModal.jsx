// Components
import { Checkbox } from '@jonathan/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './ChartControlBoxModal.module.scss';

const cx = classNames.bind(style);

function ChartControlBoxModal({
  options,
  listClickHandler,
  clickedTitle,
  width,
  height,
  hasCheckbox = false,
  checkboxClickHandler,
  checkboxOptions,
  t,
}) {
  return (
    <div
      className={cx('wrapper')}
      style={{ width, height }}
      onClick={(e) => e.stopPropagation()}
    >
      {options?.map((option) => {
        return (
          <div key={option.label} className={cx('option-container')}>
            <span
              className={cx(option.isDisabled ? 'option-disable' : 'option')}
              onClick={() => listClickHandler(clickedTitle, option)}
            >
              {t(option.label)}
            </span>
          </div>
        );
      })}
      {hasCheckbox && (
        <>
          <div className={cx('line-box')}>
            <span className={cx('line')}></span>
          </div>
          <div className={cx('option-container')}>
            <span className={cx('option-disable')}>From</span>{' '}
          </div>
          <div className={cx('option-container')}>
            <div className={cx('check-container')}>
              <Checkbox
                label='NGINX'
                checked={checkboxOptions.nginx}
                onChange={() => checkboxClickHandler('nginx')}
              />
            </div>
          </div>
          <div className={cx('option-container')}>
            <div className={cx('check-container')}>
              <Checkbox
                label='API'
                checked={checkboxOptions.api}
                onChange={() => checkboxClickHandler('api')}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default ChartControlBoxModal;
