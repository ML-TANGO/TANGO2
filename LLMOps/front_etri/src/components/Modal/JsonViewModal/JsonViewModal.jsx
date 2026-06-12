import { useEffect, useState } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import ModalFrame from '@src/components/Modal/ModalFrame';
import ReactJson from 'react-json-view';

// CSS module
import classNames from 'classnames/bind';
import style from './JsonViewModal.module.scss';
const cx = classNames.bind(style);

const JsonViewModal = ({ type, data }) => {
  const { t } = useTranslation();
  const { submit, jsonData } = data;
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (jsonData) {
      setIsLoading(false);
    } else {
      jsonData(true);
    }
  }, [jsonData]);

  return (
    <ModalFrame
      submit={submit}
      type={type}
      isLoading={isLoading}
      isResize={true}
      isMinimize={true}
      title={t('jsonResult.title.label')}
      validate
    >
      <h2 className={cx('title')}>{t('jsonResult.title.label')}</h2>
      <div className={cx('form')}>
        <ReactJson
          src={jsonData}
          theme='summerfruit:inverted'
          iconStyle='triangle'
          collapseStringsAfterLength={36}
          style={{
            fontFamily: 'SpoqaM',
            fontSize: '16px',
            lineHeight: '18px',
            overflowX: 'auto',
            paddingBottom: '8px',
          }}
        />
      </div>
    </ModalFrame>
  );
};

export default JsonViewModal;
