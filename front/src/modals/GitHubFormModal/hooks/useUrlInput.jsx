import { useState, useMemo } from 'react';

// Components
import UrlInputForm from '@src/components/modalContents/GitHubFormModalContent/UrlInputForm';

/**
 * 데이터셋 GitHub Clone 모달에서 URL 및 폴더이름 입력 폼의 로직과 컴포넌트를 함께 분리한 커스텀 훅
 *
 * @param {'CLONE_GITHUB'} modalData
 * @returns {[
 *  {
 *    url: string,
 *    folderName: string,
 *    urlError: string | undefined,
 *    folderNameError: string | undefined,
 *    isValid: boolean,
 *  },
 *  () => JSX.Element
 * ]}
 * 리턴 값(배열)의 첫번째 인덱스 값은 입력한 URL과 folderName 정보를 리턴한다.
 * 두번째 인덱스 값은 해당 URL과 folderName을 화면에 렌더링하는 함수이다.
 *
 * @component
 * @example
 *
 * const [
 *  urlState, // URL, folderName 관련 컴포넌트 상태
 *  renderUrlInputForm, // URL, folderName 인풋 렌더링 함수
 * ] = useUrlInput();
 *
 * return (
 *  <>
 *    {renderUrlInputForm()}
 *  </>
 * );
 *
 */
const useUrlInput = (modalData) => {
  // Component State
  const [url, setUrl] = useState('');
  const [urlError, setUrlError] = useState();
  const [folderName, setFolderName] = useState('');
  const [folderNameError, setFolderNameError] = useState();

  // Events
  const inputHandler = (e) => {
    const { name, value } = e.target;

    if (name === 'url') {
      // url 값 변경
      setUrl(value);
      // 유효성 검증
      let error = '';
      const regType =
        /^(http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-/]))?/;
      if (value === '') {
        error = 'url.empty.message';
      }
      if (!regType.test(value)) {
        error = 'url.error.message';
      }
      setUrlError(error);
    } else if (name === 'folderName') {
      setFolderName(value);
      // 유효성 검증
      let error = '';
      const folderReg = /(?=.*[:?*<>#$%&()/"|\\\s])/;
      if (value === '') {
        error = 'folderName.empty.message';
      }
      if (value.match(folderReg)) {
        error = 'folderNameRule.message';
      }
      setFolderNameError(error);
    }
  };

  // URL 컴포넌트 렌더링 함수
  const renderUrlInput = () => {
    return (
      <UrlInputForm
        url={url}
        urlError={urlError}
        folderName={folderName}
        folderNameError={folderNameError}
        inputHandler={inputHandler}
        modalData={modalData}
      />
    );
  };

  const result = useMemo(
    () => ({
      url,
      folderName,
      isValid: urlError === '' && folderNameError === '',
    }),
    [url, folderName, urlError, folderNameError],
  );

  return [result, renderUrlInput];
};

export default useUrlInput;
