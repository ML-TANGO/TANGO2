import { Fragment } from 'react';
import { useDispatch } from 'react-redux';
import { useTranslation } from 'react-i18next';

import { Button, Tooltip } from '@jonathan/ui-react';
import { openModal, closeModal } from '@src/store/modules/modal';
import { capitalizeFirstLetter } from '@src/utils';

import classNames from 'classnames/bind';
import style from './UserTestContentOutputHeader.module.scss';
const cx = classNames.bind(style);

const UserTestContentOutputHeader = ({ outputStatus, outputObj }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  // * JSON 파일 보기 (모달)
  const viewJson = () => {
    dispatch(
      openModal({
        modalType: 'SHOW_JSON',
        modalData: {
          submit: {
            text: 'confirm.label',
            func: () => {
              dispatch(closeModal('SHOW_JSON'));
            },
          },
          jsonData: outputObj,
        },
      }),
    );
  };
  return (
    <div className={cx('result-label')}>
      <label className={cx('label')}>{t('analysisResult.label')}</label>
      <Button type='primary' size='small' onClick={() => viewJson()}>
        JSON
      </Button>
      <div className={cx('response-status')}>
        {outputStatus && (
          <Tooltip
            contents={
              <span>
                {t('responseStatus.tooltip.message')
                  .split('\n')
                  .map((text, i) => (
                    <Fragment key={i}>
                      {text} <br />
                    </Fragment>
                  ))}
              </span>
            }
            contentsAlign={{ vertical: 'top' }}
          />
        )}
        {outputStatus &&
          Object.keys(outputStatus).map((key, idx) => {
            return (
              <Fragment key={idx}>
                <label className={cx('key')}>
                  {capitalizeFirstLetter(key)}:
                </label>
                <span className={cx('value')}>{outputStatus[key]}</span>
              </Fragment>
            );
          })}
      </div>
    </div>
  );
};

export default UserTestContentOutputHeader;
