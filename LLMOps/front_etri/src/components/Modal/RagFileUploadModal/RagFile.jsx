import { ButtonV2 } from '@tango/ui-react';

import { useRef } from 'react';
import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './RagFileUploadModal.module.scss';

const cx = classNames.bind(style);

const RagFile = ({
  onUpload,
  buttonLabel = 'Select Files',
  disabled,
  customStyle,
  multiple = false, // 다중 업로드 가능 여부
}) => {
  const fileInputRef = useRef(null);
  const { t } = useTranslation();

  const MAX_FILE_SIZE_MB = 5;
  const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

  const handleFileChange = (event) => {
    const files = multiple
      ? Array.from(event.target.files)
      : [event.target.files[0]];

    const validFiles = files.filter((file) => {
      if (file.size > MAX_FILE_SIZE_BYTES) {
        alert(`File "${file.name}" exceeds the ${MAX_FILE_SIZE_MB}MB limit.`);
        return false;
      }
      return true;
    });

    if (validFiles.length > 0) {
      onUpload(validFiles);
    }
    event.target.value = ''; // 동일 파일 업로드 시도 시 초기화
  };

  const triggerFileInput = () => fileInputRef.current.click();

  return (
    <div style={customStyle} className={cx('rag-docs')}>
      <input
        type='file'
        ref={fileInputRef}
        style={{ display: 'none' }}
        onChange={handleFileChange}
        multiple={multiple} // 다중 선택 가능 여부
        disabled={disabled}
        accept='.pdf' // PDF만 받음
      />
      <ButtonV2
        colorType='skyblue'
        size='l'
        label={buttonLabel}
        onClick={triggerFileInput}
        disabled={disabled}
      />

      <div className={cx('size-message')}>
        {t('llm.rag.upload.size.message')}
      </div>
    </div>
  );
};

export default RagFile;
