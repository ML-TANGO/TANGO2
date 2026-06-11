import { ButtonV2, DateRangePicker } from '@tango/ui-react';

import { DATE_FORM } from '@src/datetimeUtils';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';

import TitleSelect from '@src/components/molecules/TitleSelect';

import classNames from 'classnames/bind';
import style from './InstanceSearch.module.scss';

const cx = classNames.bind(style);

const InstanceSearch = ({
  selectedWorkspaceValue,
  workspaceOptions,
  handleWorkspace,
  dateState,
  handleCalendar,
}) => {
  const { t } = useTranslation();

  const { startDate, endDate } = dateState;

  return (
    <div className={cx('search-cont')}>
      <h3 className={cx('title')}>{t('resourceUsageRecords.title.label')}</h3>
      <div className={cx('flex-cont')}>
        <TitleSelect
          placeholder={t('selectWorkspace.placeholder')}
          sizeType={'small'}
          options={workspaceOptions}
          selected={selectedWorkspaceValue}
          onChange={handleWorkspace}
          disabledErrorText
          searchable
        />
        <div className={cx('line')} />
        <DateRangePicker
          from={dayjs(startDate).format(DATE_FORM)}
          to={dayjs(endDate).format(DATE_FORM)}
          cancelLabel='cancel.label'
          submitLabel='confirm.label'
          onSubmit={handleCalendar}
          t={t}
        />
        <ButtonV2 label={t('search.label')} size='l' colorType='skyblue' />
      </div>
    </div>
  );
};

export default InstanceSearch;
