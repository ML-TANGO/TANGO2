import { useEffect, useState } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Switch } from '@jonathan/ui-react';
import ModalFrame from '../ModalFrame';

// Library
import ReactJson from 'react-json-view';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

// CSS module
import classNames from 'classnames/bind';
import style from './PreviewModal.module.scss';
const cx = classNames.bind(style);

function PreviewModal({ type, data }) {
  const { t } = useTranslation();
  const {
    submit,
    index,
    fileName,
    fileType,
    previewData,
    showPrevData,
    showNextData,
  } = data;

  const [isLoading, setIsLoading] = useState(false);
  const [imgSrc, setImgSrc] = useState('');
  const [isMarkdownView, setIsMarkdownView] = useState(true);

  /**
   * 키보드 이벤트 인식
   * <-(왼쪽 화살표): 37, ->(오른쪽 화살표):39
   */
  useEffect(() => {
    const listener = (e) => {
      if (e.keyCode === 37) {
        showPrevData(index);
      } else if (e.keyCode === 39) {
        showNextData(index);
      }
    };
    document.addEventListener('keydown', listener);
    return () => {
      document.removeEventListener('keydown', listener);
    };
  }, [index, showNextData, showPrevData]);

  useEffect(() => {
    setIsLoading(true);
    if (previewData) {
      if (fileType === 'image') {
        const imageToLoad = new Image();
        imageToLoad.src = `data:image/jpeg;base64,${previewData}`;
        imageToLoad.onload = () => {
          // When image is loaded replace the src and set loading to false
          setImgSrc(`data:image/jpeg;base64,${previewData}`);
          setIsLoading(false);
        };
      } else {
        setIsLoading(false);
      }
    }
  }, [previewData, fileType]);

  return (
    <ModalFrame
      submit={submit}
      type={type}
      validate
      isResize={true}
      isMinimize={true}
      title={`${t('preview.title.label')} - ${fileName}`}
      isLoading={isLoading}
    >
      <h2 className={cx('title')}>{t('preview.title.label')}</h2>
      <label
        className={cx('name', fileType === 'markdown' && 'switch')}
        title={fileName}
      >
        {fileName}
      </label>
      <div className={cx('contents')}>
        <div className={cx('arrow-area', 'left')}>
          <img
            className={cx('arrow', 'left')}
            src='/images/icon/ic-angle-left.svg'
            alt='<'
            onClick={() => showPrevData(index)}
          />
        </div>
        <article className={cx('form')}>
          {fileType === 'image' && (
            <img className={cx('image')} src={imgSrc} alt='preview' />
          )}
          {fileType === 'text' && (
            <pre className={cx('text')}>{previewData}</pre>
          )}
          {fileType === 'json' && (
            <ReactJson
              src={previewData}
              theme='summerfruit:inverted'
              iconStyle='triangle'
              collapseStringsAfterLength={36}
              style={{
                textAlign: 'left',
                fontFamily: 'SpoqaM',
                fontSize: '14px',
                lineHeight: '1.2',
                overflowX: 'auto',
                paddingBottom: '8px',
              }}
            />
          )}
          {fileType === 'markdown' && (
            <div className={cx('markdown')}>
              <div className={cx('view-change')}>
                <Switch
                  size='medium'
                  checked={isMarkdownView}
                  label={t('markdownView.label')}
                  labelAlign='left'
                  onChange={() => setIsMarkdownView(!isMarkdownView)}
                />
              </div>
              {isMarkdownView ? (
                <div className={cx('md')}>
                  <ReactMarkdown
                    children={previewData}
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeRaw]}
                  />
                </div>
              ) : (
                <pre className={cx('text')}>{previewData}</pre>
              )}
            </div>
          )}
        </article>
        <div className={cx('arrow-area', 'right')}>
          <img
            className={cx('arrow', 'right')}
            src='/images/icon/ic-angle-right.svg'
            alt='>'
            onClick={() => showNextData(index)}
          />
        </div>
      </div>
    </ModalFrame>
  );
}

export default PreviewModal;
