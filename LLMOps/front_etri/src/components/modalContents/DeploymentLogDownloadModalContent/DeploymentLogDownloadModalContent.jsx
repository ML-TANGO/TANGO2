// ui-react
import { DateRangePicker, Radio } from '@tango/ui-react';

// Date Utils
import { DATE_FORM, today } from '@src/datetimeUtils';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';

import ModalFooter from '@src/components/organisms/modal/ModalFooter';
// Organisms
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
// Templates
import ModalTemplate from '@src/components/templates/ModalTemplate';

// CSS Module
import classNames from 'classnames/bind';
import style from './DeploymentLogDownloadModalContent.module.scss';

const cx = classNames.bind(style);

/**
 * 배포 로그 다운로드 모달 컨텐츠 컴포넌트
 * @param {Object} props - 배포 로그 다운로드 모달 폼 데이터
 * @param {'DEPLOYMENT_LOG_DOWNLOAD'} props.type - 모달 타입
 * @param {{
 *    cancel: {
 *      func: () => void | undefined,
 *      text: string | undefined
 *    },
 *    submit: {
 *      func: () => void | undefined,
 *      text: string | undefined,
 *    },
 * }} props.modalData - 모달 Footer의 cancel, submit 버튼 관련 값(버튼에 보여줄 텍스트, 클릭 이벤트) 및 deployment id 값
 * @param {string} props.title 모달 타이틀
 * @param {boolean} props.isValidate - 활성화된 커스텀 훅의 인풋 값이 유효하면 true 하나라도 유효하지 않으면 false
 * @param {Function} props.onSubmit - Submit 버튼 클릭 이벤트
 * @param {string} from - 달력 시작 날짜
 * @param {string} to - 달력 종료 날짜
 * @param {() => void} rangeSettingOption - 로그 다운로드 범위 옵션 선택 리스트
 * @param {string} selectedValue - 선택된 로그 다운로드 범위 옵션
 * @param {() => void} onSubmitDateRange - 날짜 범위 선택 이벤트
 * @param {() => void} onRangeSetting - 로그 다운로드 범위 옵션 선택 이벤트
 * @returns {JSX.Element}
 */
function DeploymentLogDownloadModalContent({
  type,
  title,
  modalData,
  onSubmit,
  isValidate,
  renderLogOptionCheck,
  from,
  to,
  rangeSettingOption,
  selectedValue,
  onSubmitDateRange,
  onRangeSetting,
}) {
  const { t } = useTranslation();

  const { submit, cancel, createDatetime } = modalData;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };
  const isAll = selectedValue === 'all';
  const isDateRange = selectedValue === 'daterange';

  return (
    <ModalTemplate
      headerRender={<ModalHeader title={title} />}
      footerRender={
        <ModalFooter
          submit={newSubmit}
          cancel={cancel}
          type={type}
          isValidate={isValidate}
        />
      }
    >
      <div className={cx('modal-content')}>
        <div className={cx('row')}>
          <div className={cx('date-text')}>
            {isAll
              ? t('allLogDownload.message')
              : t('selectedTimeLogDownload.message')}
          </div>
          <div className={cx('radio')}>
            <Radio
              name='downloadType'
              options={rangeSettingOption}
              selectedValue={selectedValue}
              onChange={onRangeSetting}
              t={t}
            />
          </div>
          {isDateRange && (
            <DateRangePicker
              from={from}
              to={to}
              onSubmit={onSubmitDateRange}
              calendarSize='small'
              customStyle={{
                globalForm: {
                  position: 'static',
                },
                splitType: {
                  inputForm: {
                    width: '206px',
                  },
                },
              }}
              minDate={dayjs(createDatetime).format(DATE_FORM)}
              maxDate={today(DATE_FORM)}
              submitLabel='set.label'
              cancelLabel='cancel.label'
              t={t}
            />
          )}
        </div>
        <div className={cx('row')}>{renderLogOptionCheck()}</div>
      </div>
    </ModalTemplate>
  );
}

export default DeploymentLogDownloadModalContent;
