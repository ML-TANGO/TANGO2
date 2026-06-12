import { ButtonV2 } from '@tango/ui-react';

import { useRef } from 'react';
import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './LLMFile.module.scss';

const cx = classNames.bind(style);

const LLMFile = ({
  onUpload,
  buttonLabel = 'Select Files',
  disabled,
  customStyle,
  multiple = false, // 다중 업로드 가능 여부
  message,
}) => {
  const fileInputRef = useRef(null);

  const { t } = useTranslation();
  const handleFileChange = (event) => {
    const files = multiple
      ? Array.from(event.target.files)
      : [event.target.files[0]];
    onUpload(files);
  };

  const triggerFileInput = () => fileInputRef.current.click();

  return (
    <div style={customStyle} className={cx('container')}>
      <input
        type='file'
        ref={fileInputRef}
        style={{ display: 'none' }}
        onChange={handleFileChange}
        multiple={multiple} // 다중 선택 가능 여부
        disabled={disabled}
        accept='.json' // json만 받음
      />
      <ButtonV2
        colorType='skyblue'
        size='l'
        label={buttonLabel}
        onClick={triggerFileInput}
        disabled={disabled}
      />
      {message && <div className={cx('size-message')}>{t(message)}</div>}
    </div>
  );
};

export default LLMFile;
