import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Selectbox } from '@tango/ui-react';

import TextInput from '@src/components/atoms/input/TextInput';

import classNames from 'classnames/bind';
import style from './UserTestContentRequestBox.module.scss';

const cx = classNames.bind(style);

const UserTestContentRequestBox = ({
  info,
  setApiUrl,
  apiUrl,
  runAnalysis,
  loading,
  inputText,
  selectedImage,
  selectedVideo,
  selectedAudio,
  selectedCSV,
  selectedCanvas,
}) => {
  const { t } = useTranslation();
  const {
    api_method: apiMethod,
    input_type: inputType,
    data_input_form_list: inputFormList,
    api_address: apiAddress,
  } = info;
  const [isBtnDisable, setIsBtnDisable] = useState(true);

  const testCategory = useMemo(
    () => [
      { data: inputText, type: 'text' },
      { data: selectedImage, type: 'image' },
      { data: selectedVideo, type: 'video' },
      { data: selectedAudio, type: 'audio' },
      { data: selectedCSV, type: 'csv' },
      { data: selectedCanvas, type: 'canvas-image' },
    ],
    [
      inputText,
      selectedImage,
      selectedVideo,
      selectedAudio,
      selectedCSV,
      selectedCanvas,
    ],
  );

  useEffect(() => {
    if (!inputFormList || inputFormList.length === 0) {
      setIsBtnDisable(true);
      return;
    }

    // 카테고리별 개수 세기
    const categoryCount = inputFormList.reduce((acc, item) => {
      const cat = item.category;
      acc[cat] = (acc[cat] || 0) + 1;
      return acc;
    }, {});

    // testCategory 중 하나라도 불일치가 있으면 true
    const hasMismatch = testCategory.some(({ data, type }) => {
      const expectedCount = categoryCount[type] || 0;
      return expectedCount > 0 && Object.keys(data).length !== expectedCount;
    });

    setIsBtnDisable(hasMismatch);
  }, [inputFormList, testCategory, setIsBtnDisable]);

  return (
    <div className={cx('request-box')}>
      <div className={cx('label-box')}>
        <div className={cx('label')}>Request URL</div>
        {/* <Button
          type='none-border'
          icon='/images/icon/ic-refresh.svg'
          iconAlign='left'
          size='small'
          customStyle={{ width: '30px', padding: '6px' }}
          onClick={() => setApiUrl(apiAddress)}
          title='Reset API URL'
        /> */}

        {!['llm-single', 'llm-multi'].includes(inputType) && (
          <div className={cx('send-box')}>
            <button
              type='primary-light'
              size='small'
              className={cx(
                'analysis-btn',
                inputFormList && loading && 'loading',
              )}
              onClick={(e) => {
                if (inputFormList && loading) return;
                e.preventDefault();
                e.stopPropagation();
                const fullApi = `${window.location.origin}${apiAddress}`;
                runAnalysis(info, fullApi);
              }}
              customStyle={{ width: '87px', height: '32px' }}
              disabled={isBtnDisable}
            >
              {t('startAnalysis.label')}
            </button>
            {/* <Button
              type='primary-light'
              size='small'
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                runAnalysis(info, apiUrl);
              }}
              loading={inputFormList && loading}
              customStyle={{ width: '87px', height: '32px' }}
            >
              {t('startAnalysis.label')}
            </Button> */}
          </div>
        )}
      </div>
      <div className={cx('one-line')}>
        <div className={cx('api-address-box')}>
          <Selectbox
            list={[
              { label: 'POST', value: 'POST' },
              { label: 'GET', value: 'GET' },
            ]}
            selectedItem={
              apiMethod
                ? {
                    label: apiMethod,
                    value: apiMethod,
                  }
                : undefined
            }
            customStyle={{
              selectboxForm: {
                width: '226px',
              },
              listForm: {
                width: '226px',
              },
            }}
            isReadOnly
          />
          <div className={cx('text-input')}>
            <TextInput
              value={apiUrl ? `${window.location.origin}${apiAddress}` : ''}
              onChange={(e) => setApiUrl(e.target.value)}
              maxLength='200'
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserTestContentRequestBox;
