// i18n

// Components
import { Badge, Tooltip } from '@tango/ui-react';

import { withTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
// CSS module
import style from './InputLabelBox.module.scss';

const cx = classNames.bind(style);

const InputLabelBox = ({ idx, type, apiKey, description, children, t }) => {
  return (
    <>
      <div
        className={cx('wrapper')}
        style={{ marginTop: idx === 0 ? '64px' : '' }}
      >
        <div className={cx('top')}>
          <span className={cx('index')}>
            {`${t('inputData.label')} ${idx + 1}`}
          </span>
        </div>
        {children}
      </div>
      <div className={cx('bottom')}>
        <div className={cx('type')}>
          {/* <Badge label={type} type='blue' /> */}
          {type}
        </div>
        <div className={cx('key')}>API Key: {apiKey}</div>
        {description && <Tooltip contents={description} />}
      </div>
    </>
  );
};

export default withTranslation()(InputLabelBox);
