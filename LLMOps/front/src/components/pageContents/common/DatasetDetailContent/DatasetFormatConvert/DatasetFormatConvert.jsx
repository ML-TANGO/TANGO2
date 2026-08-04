// Components
import { Button, InputText, Selectbox } from '@jonathan/ui-react';

import { useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

// CSS module
import classNames from 'classnames/bind';
import style from './DatasetFormatConvert.module.scss';

const cx = classNames.bind(style);

/**
 * 빌트인 전처리 '데이터 포맷 변환'(apps/builtin_transform/format_convert.py) 파라미터.
 * - target_format : 레코드 스키마. instruction={instruction,output,input?}(Alpaca SFT),
 *                   text={text}, chat={messages:[user,assistant]}.
 *                   기본 instruction = 스크립트 자체 기본값이자 SFT 학습 입력 표준형.
 * - output_format : json(배열) | jsonl(줄단위). 기본 jsonl.
 * - result_file_name : 출력 베이스명(원본과 같은 폴더에 sidecar 로 생성). 기본 converted.
 */
const TARGET_FORMAT_OPTIONS = [
  { label: 'instruction', value: 'instruction' },
  { label: 'text', value: 'text' },
  { label: 'chat', value: 'chat' },
];

const OUTPUT_FORMAT_OPTIONS = [
  { label: 'jsonl', value: 'jsonl' },
  { label: 'json', value: 'json' },
];

const DEFAULT_RESULT_FILE_NAME = 'converted';

// 스크립트가 basename 으로만 사용하므로 경로문자/공백/한글을 입력 단계에서 차단.
const INVALID_RESULT_NAME = /[^A-Za-z0-9._-]/;

function DatasetFormatConvert({
  targetFileName, // 변환 대상 파일명 (선택된 파일 1개)
  disabled,
  converting,
  onConfirm,
  btnCustomStyle,
}) {
  const { t } = useTranslation();

  const [isOpen, setIsOpen] = useState(false);
  const [targetFormat, setTargetFormat] = useState(TARGET_FORMAT_OPTIONS[0]);
  const [outputFormat, setOutputFormat] = useState(OUTPUT_FORMAT_OPTIONS[0]);
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
          {t('formatConvert.label', '포맷 변환')}
        </Button>
        {isOpen && (
          <div className={cx('popup')}>
            <div className={cx('header')}>
              <span className={cx('file-name')} title={targetFileName}>
                {targetFileName}
              </span>
            </div>
            <div className={cx('body')}>
              <p className={cx('guide')}>
                {t(
                  'formatConvertGuide.message',
                  'CSV/TXT/Parquet 파일 1개를 JSON/JSONL 학습 포맷으로 변환합니다. 결과 파일은 원본과 같은 폴더에 생성됩니다.',
                )}
              </p>
              <div className={cx('row')}>
                <label className={cx('label')}>
                  {t('formatConvertTargetFormat.label', '학습 포맷')}
                </label>
                <Selectbox
                  size='medium'
                  list={TARGET_FORMAT_OPTIONS}
                  selectedItem={targetFormat}
                  onChange={setTargetFormat}
                  customStyle={{
                    selectboxForm: { width: '160px' },
                    listForm: { width: '160px' },
                  }}
                />
              </div>
              <div className={cx('row')}>
                <label className={cx('label')}>
                  {t('formatConvertOutputFormat.label', '출력 형식')}
                </label>
                <Selectbox
                  size='medium'
                  list={OUTPUT_FORMAT_OPTIONS}
                  selectedItem={outputFormat}
                  onChange={setOutputFormat}
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
                    target_format: targetFormat.value,
                    output_format: outputFormat.value,
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

export default DatasetFormatConvert;
