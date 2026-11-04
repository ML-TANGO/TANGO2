import { useState } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import AccessInputForm from '@src/components/modalContents/GitHubFormModalContent/AccessInputForm';

/**
 * 데이터셋 GitHub Clone 모달에서 접근 설정 입력 폼의 로직과 컴포넌트를 함께 분리한 커스텀 훅
 *
 * @param {'CLONE_GITHUB'} modalData
 * @returns {[
 *  {
 *    username: string,
 *    accessToken: string,
 *    usernameError: string | undefined,
 *    accessTokenError: string | undefined,
 *  },
 *  () => JSX.Element
 * ]}
 * 리턴 값(배열)의 첫번째 인덱스 값은 입력한 username accessToken 정보를 리턴한다.
 * 두번째 인덱스 값은 해당 username accessToken을 화면에 렌더링하는 함수이다.
 *
 * @component
 * @example
 *
 * const [
 *  accessState, // username, accessToken 관련 컴포넌트 상태
 *  renderAccessInputForm, // username, accessToken 인풋 렌더링 함수
 * ] = useAccessInput();
 *
 * return (
 *  <>
 *    {renderAccessInputForm()}
 *  </>
 * );
 *
 */
const useAccessInput = () => {
  const { t } = useTranslation();

  // Component State
  const [username, setUsername] = useState('');
  const [usernameError, setUsernameError] = useState();
  const [accessToken, setAccessToken] = useState('');
  const [accessTokenError, setAccessTokenError] = useState();

  // Events
  const inputHandler = (e) => {
    const { name, value } = e.target;
    if (name === 'username') {
      setUsername(value);
      if (value !== '') {
        setUsernameError('');
      } else {
        setUsernameError(t('username.empty.message'));
      }
    } else if (name === 'accessToken') {
      setAccessToken(value);
      if (value !== '') {
        setAccessTokenError('');
      } else {
        setAccessTokenError(t('accesstoken.empty.message'));
      }
    }
  };

  // URL 컴포넌트 렌더링 함수
  const renderAccessInput = () => {
    return (
      <AccessInputForm
        username={username}
        accessToken={accessToken}
        inputHandler={inputHandler}
        usernameError={usernameError}
        accessTokenError={accessTokenError}
      />
    );
  };

  const result = {
    username,
    accessToken,
    isValid: usernameError === '' && accessTokenError === '',
  };

  return [result, renderAccessInput];
};

export default useAccessInput;
