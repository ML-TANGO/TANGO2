import { Fragment, useState } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Tooltip, InputText } from '@jonathan/ui-react';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// CSS Module
import classNames from 'classnames/bind';
import style from './AccessInputForm.module.scss';
const cx = classNames.bind(style);

/**
 * 데이터셋 GitHub Clone 폼에서 사용되는 접근 입력 폼 컴포넌트
 * @param {{
 *  username: string,
 *  accessToken: string,
 *  usernameError: string,
 *  accessTokenError: string,
 *  inputHandler: Function
 * }} props
 * @returns
 */
function AccessInputForm({
  username,
  accessToken,
  usernameError,
  accessTokenError,
  inputHandler,
}) {
  const { t } = useTranslation();

  const [hideInputForm, setHideInputForm] = useState(true);

  return (
    <InputBoxWithLabel
      labelText={t('accessSettings.title.label')}
      optionalText={t('optional.label')}
      labelSize='large'
      optionalSize='large'
      labelRight={
        <>
          <Tooltip contents={t('githubAccessSettings.tooltip.message')} />
          <button
            className={cx('show-hide-btn')}
            onClick={() => setHideInputForm(!hideInputForm)}
          >
            <img
              src={`/images/icon/00-ic-basic-arrow-04-${
                hideInputForm ? 'up' : 'down'
              }.svg`}
              className={cx('arrow-btn')}
              alt='show/hide button'
            />
          </button>
        </>
      }
    >
      <div className={cx('input-wrap', hideInputForm ? 'hide' : 'show')}>
        <InputBoxWithLabel
          labelText='Username'
          labelSize='medium'
          errorMsg={usernameError}
        >
          <InputText
            size='medium'
            value={username}
            name='username'
            onChange={inputHandler}
            placeholder='GitHub Username'
            status={
              usernameError === '' || !usernameError ? 'default' : 'error'
            }
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText='Access Token'
          labelSize='medium'
          labelRight={
            <Tooltip
              contents={
                <div style={{ width: '400px' }}>
                  <h3>GitHub Access Token</h3>
                  <p>
                    {t('githubAccessToken.tooltip.message')
                      .split('\n')
                      .map((text, i) => (
                        <Fragment key={i}>
                          {text} <br />
                        </Fragment>
                      ))}
                  </p>
                </div>
              }
              contentsAlign={{ vertical: 'top', horizontal: 'left' }}
            />
          }
          errorMsg={accessTokenError}
        >
          <InputText
            size='medium'
            value={accessToken}
            name='accessToken'
            onChange={inputHandler}
            placeholder='GitHub Access Token'
            status={
              accessTokenError === '' || !accessTokenError ? 'default' : 'error'
            }
          />
        </InputBoxWithLabel>
      </div>
    </InputBoxWithLabel>
  );
}

export default AccessInputForm;
