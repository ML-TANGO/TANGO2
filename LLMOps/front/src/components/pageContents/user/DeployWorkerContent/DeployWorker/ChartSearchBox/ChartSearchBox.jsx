// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Selectbox, Button, Tooltip } from '@jonathan/ui-react';
import OptionTabMenu from '@src/components/molecules/OptionTabMenu';
import MutliCheckSelect from '@src/components/molecules/MutliCheckSelect';

// ui-react
import { DateRangePicker } from '@jonathan/ui-react';

// Date Utils
import { today, DATE_FORM } from '@src/datetimeUtils';

// Icon
import search from '@src/static/images/icon/ic-search-white.svg';

// CSS Module
import classNames from 'classnames/bind';
import style from './ChartSearchBox.module.scss';
const cx = classNames.bind(style);

function ChartSearchBox({
  workerStatus,
  searchType,
  onChangeSearchType,
  startDate,
  endDate,
  minDate,
  onChangeDate,
  resolution,
  resolutionList,
  onChangeResolution,
  workers,
  workerList,
  onChangeWorker,
  onSubmit,
}) {
  const { t } = useTranslation();
  return (
    <div className={cx('setting-wrap')}>
      {searchType && workerStatus !== 'stop' && (
        <div className={cx('toggle-btn')}>
          <span className={cx('label')}>{t('type.label')}</span>
          <OptionTabMenu
            option={[
              { label: t('rangeSearch.label'), value: 'range' },
              { label: t('live.label'), value: 'live' },
            ]}
            selected={searchType}
            onChangeHandler={onChangeSearchType}
          />
        </div>
      )}
      <div className={cx('input-date')}>
        <span className={cx('label')}>{t('range.label')}(UTC+9)</span>
        {searchType === 'range' && (
          <DateRangePicker
            type='split-input'
            from={startDate}
            to={endDate}
            minDate={minDate}
            maxDate={today(DATE_FORM)}
            submitLabel='set.label'
            cancelLabel='cancel.label'
            onSubmit={onChangeDate}
            customStyle={{
              splitType: {
                inputForm: {
                  width: '140px',
                },
              },
            }}
            t={t}
          />
        )}
        {searchType === 'live' && (
          <Selectbox
            list={[{ label: `3${t('minute.label').substring(0, 3)}` }]}
            selectedItemIdx={0}
            isReadOnly={true}
          />
        )}
      </div>
      <div className={cx('resolution')}>
        <span className={cx('label')}>
          {t('resolution.label')}
          {searchType === 'range' && (
            <Tooltip
              contents={
                resolutionList &&
                resolutionList.map((_, idx) => {
                  return (
                    <div key={idx}>
                      {t(`resolution.${searchType}.tooltip.message${idx + 1}`)}
                    </div>
                  );
                })
              }
              iconCustomStyle={{
                width: '20px',
                marginLeft: '2px',
              }}
            />
          )}
        </span>
        {searchType === 'range' && (
          <Selectbox
            list={resolutionList}
            selectedItem={resolution}
            onChange={onChangeResolution}
            customStyle={{
              selectboxForm: {
                width: '120px',
              },
              listForm: {
                width: '120px',
              },
            }}
            t={t}
          />
        )}
        {searchType === 'live' && (
          <Selectbox
            selectboxWidth={'100px'}
            isReadOnly={true}
            list={[{ label: `1${t('second.label').substring(0, 3)}` }]}
            selectedItemIdx={0}
            customStyle={{
              globalForm: {
                width: 'auto',
              },
            }}
          />
        )}
      </div>
      {workerList && (
        <div className={cx('Worker')}>
          <span className={cx('label')}>{t('worker.label')}</span>
          <MutliCheckSelect
            name='workers'
            options={workerList}
            sizeType='small'
            selected={workers}
            onSubmit={onChangeWorker}
            customStyle={{ width: '180px' }}
            disabledErrorText
            t={t}
          />
        </div>
      )}
      {searchType === 'range' && (
        <div className={cx('search-btn')}>
          <Button
            type='primary'
            customStyle={{
              width: '36px',
              height: '36px',
            }}
            onClick={onSubmit}
          >
            <img
              src={search}
              alt='search'
              style={{
                width: '24px',
              }}
            ></img>
          </Button>
        </div>
      )}
    </div>
  );
}

export default ChartSearchBox;
