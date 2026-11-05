import { Button } from '@jonathan/ui-react';

import { toast } from 'react-toastify';

import { copyToClipboard, decrypt } from '@src/utils';

import classNames from 'classnames/bind';
import style from './ToolCardFooter.module.scss';

const cx = classNames.bind(style);

const MODE = import.meta.env.VITE_REACT_APP_MODE?.toLowerCase();

const handleCopySshInfo = (value, message) => {
  if (!value) return;
  copyToClipboard(value);
  toast.success(message);
};

const ToolCardFooter = ({
  t,
  status,
  toolType,
  btnDisable,
  sshInfo,
  isSshModal,
  isToolLinkLoading,
  toolLoading,
  isPermission,
  functionInfoArr,
  handleCommitBtn,
  handleSshGuideBtn,
  handleCheckFilebrowserFirst,
  handleSshBtn,
  handleExcuteLink,
}) => {
  const { sshUrl, toolPassword } = sshInfo;

  return (
    <div className={cx('footer')}>
      <div>
        {['running', 'installing'].includes(status.status) && (
          <Button
            type='primary'
            customStyle={{
              width: '95px',
              height: '36px',
              fontSize: '14px',
              fontFamily: 'SpoqaB',
              padding: '10px 20px',
              backgroundColor:
                status.status !== 'running' || toolLoading.current
                  ? '#f0f0f0'
                  : 'rgba(222, 233, 255, 0.50)',
              border:
                status.status !== 'running' || toolLoading.current
                  ? '1px solid #f0f0f0'
                  : 'rgba(222, 233, 255, 0.50)',
              color:
                status.status !== 'running' || toolLoading.current
                  ? '#fff'
                  : '#2D76F8',
            }}
            onClick={handleCommitBtn}
            disabled={status.status !== 'running' || toolLoading.current}
          >
            Commit
          </Button>
        )}
      </div>
      <div className={cx('flex-cont')}>
        {toolType === 'filebrowser' && isPermission && (
          <Button
            type='primary'
            size='large'
            customStyle={{ fontSize: '14px', fontFamily: 'SpoqaR' }}
            onClick={handleCheckFilebrowserFirst}
            disabled={btnDisable}
          >
            {t('resetPassword.label')}
          </Button>
        )}

        <Button
          disabled={btnDisable}
          type='primary-light'
          size='large'
          icon={'/images/icon/00-ic-basic-copy-o-blue.svg'}
          iconAlign='right'
          customStyle={{
            fontSize: '14px',
            fontFamily: 'SpoqaB',
            fontWeight: 'normal',
            width: '90px',
            height: '36px',
          }}
          iconStyle={{ marginLeft: '8px' }}
          onClick={handleSshBtn}
        >
          SSH
        </Button>
        {isSshModal.current && (
          <div className={cx('popup', MODE !== 'integration' && 'small')}>
            <div
              onClick={() => {
                handleCopySshInfo(sshUrl, 'ssh url 복사를 성공했습니다');
              }}
              className={cx('copy-cont')}
            >
              <span>Command</span>
              <p className={cx('url-paragraph')}>{sshUrl.slice(0, 34)}</p>
              <img src='/images/icon/00-ic-basic-copy-o.svg' alt='copy-img' />
            </div>
            <div
              onClick={() => {
                handleCopySshInfo(
                  decrypt(toolPassword),
                  '패스워드 복사를 성공했습니다.',
                );
              }}
              className={cx('copy-cont')}
            >
              <span>Password</span>
              <p className={cx('password-paragraph')}>
                {decrypt(toolPassword)?.slice(0, 29)}
              </p>
              <img src='/images/icon/00-ic-basic-copy-o.svg' alt='copy-img' />
            </div>
            <div className={cx('border')}></div>
            <div
              className={cx('connect-guide-cont')}
              onClick={handleSshGuideBtn}
            >
              <svg
                xmlns='http://www.w3.org/2000/svg'
                width='16'
                height='16'
                viewBox='0 0 16 16'
                fill='none'
              >
                <g clipPath='url(#clip0_136_10882)'>
                  <path
                    d='M11.9974 1.33398H3.9974C3.26406 1.33398 2.66406 1.93398 2.66406 2.66732V13.334C2.66406 14.0673 3.26406 14.6673 3.9974 14.6673H11.9974C12.7307 14.6673 13.3307 14.0673 13.3307 13.334V2.66732C13.3307 1.93398 12.7307 1.33398 11.9974 1.33398ZM3.9974 2.66732H7.33073V8.00065L5.66406 7.00065L3.9974 8.00065V2.66732Z'
                    fill='#2D76F8'
                  />
                </g>
                <defs>
                  <clipPath id='clip0_136_10882'>
                    <rect width='16' height='16' fill='white' />
                  </clipPath>
                </defs>
              </svg>
              <span>SSH 접속 가이드(필독)</span>
            </div>
          </div>
        )}
        {functionInfoArr.map(({ type }, key) => {
          if (type === 'link') {
            return (
              <Button
                key={key}
                disabled={btnDisable}
                type='primary-light'
                size='large'
                icon={'/images/icon/00-ic-basic-link-external-blue.svg'}
                iconStyle={{ marginLeft: '8px' }}
                iconAlign='right'
                customStyle={{
                  fontSize: '14px',
                  fontFamily: 'SpoqaB',
                  fontWeight: 'normal',
                  width: '90px',
                  height: '36px',
                }}
                loading={!isToolLinkLoading}
                onClick={handleExcuteLink}
              >
                {t('run.label')}
              </Button>
            );
          }
          return null;
        })}
      </div>
    </div>
  );
};

export default ToolCardFooter;
