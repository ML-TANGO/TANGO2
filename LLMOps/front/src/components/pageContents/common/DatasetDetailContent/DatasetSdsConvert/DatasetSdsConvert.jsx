// Components
import { Button, InputText, Selectbox } from '@jonathan/ui-react';

import { useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

// CSS module
import classNames from 'classnames/bind';
// 포맷 변환 버튼과 같은 팝오버 규격 — 나란히 놓이는 두 버튼이 다른 모양이면
// 하나가 다른 기능처럼 보인다. 스타일 시트를 공유해 시각 델타를 0 으로 둔다.
import style from '../DatasetFormatConvert/DatasetFormatConvert.module.scss';

const cx = classNames.bind(style);

/**
 * 빌트인 전처리 'SDS VLM 학습 데이터 변환'(apps/builtin_transform/sds_llava_convert.py) 파라미터.
 *
 * 포맷 변환과 달리 대상이 **디렉터리**다 — 스크립트가 입력 디렉터리를 스캔해
 * (시나리오 subdir 또는 png/·csv/ 타입별 디렉터리) 그 안에 LLaVA JSON 을 쓴다.
 * - sds_variant     : en | ko | ko_compact | all. 기본 all — 라벨이 있는 variant 만
 *                     생성되고 0 건인 variant 는 파일을 만들지 않는다.
 * - result_file_name: 출력 베이스명. 실제 파일은 <base>_<variant>.json.
 */
const VARIANT_OPTIONS = [
  { label: 'all', value: 'all' },
  { label: 'ko', value: 'ko' },
  { label: 'en', value: 'en' },
  { label: 'ko_compact', value: 'ko_compact' },
];

const DEFAULT_RESULT_FILE_NAME = 'sds_train';

// 스크립트가 basename 으로만 사용하므로 경로문자/공백/한글을 입력 단계에서 차단.
const INVALID_RESULT_NAME = /[^A-Za-z0-9._-]/;

function DatasetSdsConvert({
  targetDirName, // 변환 대상 디렉터리 표시명 (미선택이면 현재 경로)
  disabled,
  converting,
  onConfirm,
  btnCustomStyle,
}) {
  const { t } = useTranslation();

  const [isOpen, setIsOpen] = useState(false);
  const [variant, setVariant] = useState(VARIANT_OPTIONS[0]);
  const [resultFileName, setResultFileName] = useState(
    DEFAULT_RESULT_FILE_NAME,
  );

  const isNameInvalid =
    !resultFileName || INVALID_RESULT_NAME.test(resultFileName);

  const close = () => setIsOpen(false);

  return (
    <>
      <div className={cx('wrapper')}>
        <Button
          type='gray-light'
          onClick={() => setIsOpen(!isOpen)}
          disabled={disabled}
          loading={converting}
          customStyle={btnCustomStyle}
        >
          {t('sdsConvert.label', 'SDS 변환')}
        </Button>
        {isOpen && (
          <div className={cx('popup')}>
            <div className={cx('header')}>
              <span className={cx('file-name')} title={targetDirName}>
                {targetDirName}
              </span>
            </div>
            <div className={cx('body')}>
              <p className={cx('guide')}>
                {t(
                  'sdsConvertGuide.message',
                  'SDS 시나리오 데이터셋을 VLM 학습용 LLaVA JSON 으로 변환합니다. 선택한 폴더(미선택 시 현재 경로) 전체가 대상이며, 결과 파일은 그 폴더 안에 생성됩니다.',
                )}
              </p>
              <ul className={cx('requirements')}>
                <li>
                  {t(
                    'sdsConvertReqLayoutA.message',
                    '시나리오별 폴더 구조: 각 폴더 안에 input_data.csv, input_image.png, output_*.txt',
                  )}
                </li>
                <li>
                  {t(
                    'sdsConvertReqLayoutB.message',
                    '타입별 폴더 구조: png/, csv/, describe_ko/, advice_ko/ (같은 파일 이름으로 짝을 맞춥니다)',
                  )}
                </li>
                <li>
                  {t(
                    'sdsConvertReqAis.message',
                    'CSV 에는 ship_id, my_ship 컬럼이 반드시 있어야 합니다. 없는 샘플은 건너뜁니다.',
                  )}
                </li>
              </ul>
              <div className={cx('row')}>
                <label className={cx('label')}>
                  {t('sdsConvertVariant.label', '언어/형식')}
                </label>
                <Selectbox
                  size='medium'
                  list={VARIANT_OPTIONS}
                  selectedItem={variant}
                  onChange={setVariant}
                  customStyle={{
                    selectboxForm: { width: '160px' },
                    listForm: { width: '160px' },
                  }}
                />
              </div>
              <div className={cx('row')}>
                <label className={cx('label')}>
                  {t('formatConvertResultFileName.label', '결과 파일 이름')}
                </label>
                <InputText
                  size='small'
                  value={resultFileName}
                  onChange={(e) => setResultFileName(e?.target?.value ?? '')}
                  placeholder={DEFAULT_RESULT_FILE_NAME}
                  disableLeftIcon
                  disableClearBtn
                  customStyle={{ width: '160px' }}
                />
              </div>
              {isNameInvalid && (
                <p className={cx('error')}>
                  {t(
                    'formatConvertInvalidFileName.message',
                    "결과 파일 이름은 영문·숫자·'.'·'_'·'-' 만 사용할 수 있습니다.",
                  )}
                </p>
              )}
            </div>
            <div className={cx('footer')}>
              <Button type='none-border' size='small' onClick={close}>
                {t('cancel.label')}
              </Button>
              <Button
                type='primary'
                size='small'
                disabled={isNameInvalid || converting}
                onClick={() => {
                  close();
                  onConfirm({
                    sds_variant: variant.value,
                    result_file_name: resultFileName,
                  });
                }}
              >
                {t('confirm.label')}
              </Button>
            </div>
          </div>
        )}
      </div>
      {isOpen && <div className={cx('shadow')} onClick={close}></div>}
    </>
  );
}

export default DatasetSdsConvert;
