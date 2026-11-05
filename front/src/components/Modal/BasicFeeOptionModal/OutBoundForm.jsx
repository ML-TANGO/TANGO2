import React from 'react';
import { useTranslation } from 'react-i18next';

import GrayDropDown from './GrayDropDown';

import classNames from 'classnames/bind';
import style from './OutBoundForm.module.scss';

const cx = classNames.bind(style);

const OutBoundForm = ({
  start,
  startUnit,
  end,
  endUnit,
  cost,
  id,
  deleteOutBoundOption,
  handleOutBoundOption,
}) => {
  const { t } = useTranslation();

  const unitList = [
    { label: 'KB', value: 'KB' },
    { label: 'MB', value: 'MB' },
    { label: 'GB', value: 'GB' },
    { label: 'TB', value: 'TB' },
  ];

  const handleFirstUnit = ({ value }) => {
    handleOutBoundOption({ id, type: 'startUnit', value });
  };

  const handleSecondUnit = ({ value }) => {
    handleOutBoundOption({ id, type: 'endUnit', value });
  };

  return (
    <div className={cx('bound-inner-container')}>
      <div className={cx('unit-form')}>
        <span className={cx('text')}>
          {t('section.label')} {id}
        </span>
        <input
          className={cx('unit-input', start && 'entered')}
          type='number'
          value={start}
          placeholder={t('enterCapacity')}
          onChange={(e) =>
            handleOutBoundOption({ id, type: 'start', value: e.target.value })
          }
        />
        <div className={cx('select-box')}>
          <GrayDropDown
            list={unitList}
            value={{ label: startUnit, value: startUnit }}
            placeholder={t('resolution.label')}
            handleSelectOption={handleFirstUnit}
          />
        </div>
        <input
          className={cx('unit-input', end && 'entered')}
          type='number'
          value={end}
          placeholder={t('enterCapacity')}
          onChange={(e) =>
            handleOutBoundOption({ id, type: 'end', value: e.target.value })
          }
        />
        <div className={cx('select-box')}>
          <GrayDropDown
            list={unitList}
            value={{ label: endUnit, value: endUnit }}
            placeholder={t('resolution.label')}
            handleSelectOption={handleSecondUnit}
          />
        </div>
      </div>
      <div className={cx('cost-form')}>
        <span className={cx('text')}>
          {t('section.label')} {id} {t('fee.label')}
        </span>
        {cost && (
          <span className={cx('unit', id === 1 && 'first-cost')}>원</span>
        )}
        <input
          type='text'
          className={cx('cost-input', cost && 'entered')}
          value={cost}
          placeholder={t('enter.fee.desc')}
          onChange={(e) =>
            handleOutBoundOption({ id, type: 'cost', value: e.target.value })
          }
        />
        {id !== 1 && (
          <span
            className={cx('delete')}
            onClick={() => deleteOutBoundOption(id)}
          >
            {`${t('section.label')} ${t('delete.label')}`}
          </span>
        )}
      </div>
    </div>
  );
};

export default OutBoundForm;
