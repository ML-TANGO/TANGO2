import { Textarea } from '@jonathan/ui-react';

import React from 'react';
import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './PromptCommitListDetail.module.scss';

const cx = classNames.bind(style);

const PromptCommitListDetail = React.memo(
  ({
    commitName,
    commitMessage,
    system_message,
    user_message,
    update_datetime,
    owner,
  }) => {
    const { t } = useTranslation();
    return (
      <div className={cx('wrapper')}>
        <div className={cx('info-cont')}>
          <div className={cx('label-cont')}>
            <span className={cx('label')}>{t('commitName.label')}</span>
            <span className={cx('value')}>{commitName}</span>
          </div>
          <div className={cx('label-cont')}>
            <span className={cx('label')}>{t('commitMessage.label')}</span>
            <span className={cx('value')}>{commitMessage}</span>
          </div>
          <div className={cx('label-cont')}>
            <span className={cx('label')}>{t('writer.label')}</span>
            <span className={cx('value')}>{owner}</span>
          </div>
          <div className={cx('label-cont')}>
            <span className={cx('label')}>{t('commitDate.label')}</span>
            <span className={cx('value')}>{update_datetime}</span>
          </div>
        </div>
        <div className={cx('message-cont')}>
          <div className={cx('message-label-cont')}>
            <span className={cx('message-label-txt')}>System</span>
            <Textarea
              value={system_message}
              customStyle={{
                height: '408px',
                padding: '11px 12px',
                backgroundColor: '#fff',
                color: '#121619',
                border: '1px solid #c8d8fd',
                caretColor: 'transparent',
              }}
              onChange={() => {}}
            />
          </div>
          <div className={cx('message-label-cont')}>
            <span className={cx('message-label-txt')}>User</span>
            <Textarea
              value={user_message}
              customStyle={{
                height: '408px',
                padding: '11px 12px',
                backgroundColor: '#fff',
                color: '#121619',
                border: '1px solid #c8d8fd',
                caretColor: 'transparent',
              }}
              onChange={() => {}}
            />
          </div>
        </div>
      </div>
    );
  },
);

export default PromptCommitListDetail;
