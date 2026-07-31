// i18n

// Components
import { InputText, Tooltip } from '@tango/ui-react';

import { useTranslation } from 'react-i18next';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

/**
 * 데이터셋 GitHub Clone 폼에서 사용되는 필수입력 폼 컴포넌트
 * @param {{
 *  url: string,
 *  urlError: string,
 *  folderName: string,
 *  folderNameError: string,
 *  inputHandler: Function
 * }} props
 * @returns
 */
function UrlInputForm({
  url,
  urlError,
  folderName,
  folderNameError,
  inputHandler,
  modalData,
}) {
  const { t } = useTranslation();
  const { datasetName, loc } = modalData;

  return (
    <>
      <InputBoxWithLabel
        labelText='URL'
        labelRight={
          <Tooltip
            contents={
              <>
                <span>{t('githubUrl.tooltip.message')}</span>
                <img
                  src='/images/icon/github-clone.png'
                  alt=''
                  width='300px'
                  style={{ marginTop: '8px' }}
                />
              </>
            }
          />
        }
        labelSize='large'
        errorMsg={t(urlError)}
      >
        <InputText
          value={url}
          name='url'
          onChange={inputHandler}
          placeholder='GitHub HTTPS URL'
          status={urlError === '' || !urlError ? 'default' : 'error'}
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel
        labelText={t('folderCreate.label')}
        labelRight={<Tooltip contents={t('githubFolder.tooltip.message')} />}
        labelSize='large'
        errorMsg={t(folderNameError)}
      >
        <InputBoxWithLabel labelText={`/${datasetName}${loc}`} leftLabel bgBox>
          <InputText
            placeholder={t('folderName.placeholder')}
            value={folderName}
            name='folderName'
            onChange={inputHandler}
            status={
              folderNameError === '' || !folderNameError ? 'default' : 'error'
            }
            maxLength={50}
          />
        </InputBoxWithLabel>
      </InputBoxWithLabel>
    </>
  );
}

export default UrlInputForm;
