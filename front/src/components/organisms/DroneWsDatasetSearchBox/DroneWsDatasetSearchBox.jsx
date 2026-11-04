import dayjs from 'dayjs';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { DateRangePicker, Selectbox } from '@jonathan/ui-react';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import Radio from '@src/components/atoms/input/Radio';

// Utils
import { DATE_FORM } from '@src/datetimeUtils';

// CSS Module
import classNames from 'classnames/bind';
import style from './DroneWsDatasetSearchBox.module.scss';
const cx = classNames.bind(style);

function DroneWsDatasetSearchBox({
  droneBm,
  droneStartDate,
  droneEndDate,
  timeRangeHandler,
  droneArea,
  droneAreaError,
  selectInputHandler,
  droneAccess,
  droneOptionHandler,
}) {
  const { t } = useTranslation();

  const droneBmOptions = [
    { label: 'POL', value: 'POL' },
    { label: 'FRM', value: 'FRM' },
    { label: 'STR', value: 'STR' },
    { label: 'WTR', value: 'WTR' },
    { label: 'COMN', value: 'COMN' },
  ];

  const droneAreaOptions = [
    { label: '서울시 강동구', value: '서울시 강동구' },
    { label: '대전시 유성구', value: '대전시 유성구' },
  ];

  const droneAccessOptions = [
    { label: 'BM', value: 'bm' },
    { label: '나만보기', value: 'myself' },
    { label: '전체공개', value: 'all' },
  ];

  return (
    <div className={cx('wrapper')}>
      <InputBoxWithLabel labelText='BM' labelSize='large'>
        <Radio
          name='droneBm'
          options={droneBmOptions}
          value={droneBm}
          onChange={droneOptionHandler}
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel
        labelText='촬영시간'
        labelSize='large'
        errorMsg={t(droneAreaError)}
      >
        <DateRangePicker
          from={dayjs(droneStartDate).format(DATE_FORM)}
          to={dayjs(droneEndDate).format(DATE_FORM)}
          submitLabel={'confirm.label'}
          cancelLabel={'cancel.label'}
          onSubmit={timeRangeHandler}
          customStyle={{
            globalForm: {
              marginTop: '8px',
            },
          }}
          t={t}
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel
        labelText='촬영지역'
        labelSize='large'
        errorMsg={t(droneAreaError)}
      >
        <Selectbox
          type='search'
          size='large'
          list={droneAreaOptions}
          selectedItem={droneArea}
          onChange={(value) => {
            selectInputHandler('droneArea', value);
          }}
          customStyle={{
            fontStyle: {
              selectbox: {
                color: '#121619',
                textShadow: 'None',
              },
            },
          }}
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel labelText='접근권한' labelSize='large'>
        <Radio
          name='droneAccess'
          options={droneAccessOptions}
          value={droneAccess}
          onChange={droneOptionHandler}
        />
      </InputBoxWithLabel>
    </div>
  );
}

export default DroneWsDatasetSearchBox;
