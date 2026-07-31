import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Switch, Tooltip } from '@tango/ui-react';

import DeleteXIcon from './gray-delete-x-icon.svg';
import useDevTool from './useDevTool';

import { decrypt } from '@src/utils';

import classNames from 'classnames/bind';
import style from './DevToolCard.module.scss';

const cx = classNames.bind(style);

const TOOL_NAME = { shell: 'Shell', vscode: 'VSCode', jupyter: 'Jupyter Lab' };
const TOOL_IMAGE = { shell: 'ssh', vscode: 'vscode', jupyter: 'jupyter' };
const DevToolCard = ({
  type,
  status,
  image,
  // pod,
  ip,
  instance,
  cpu,
  ram,
  gpu,
  id,
  did,
  wid,
  reason,
  commitStatus,
  instanceType,
}) => {
  const { t } = useTranslation();

  const [sshOpen, setSshOpen] = useState(false);
  const {
    getBackgroundColor,
    getMessage,
    handleSshGuideBtn,
    handleCopySshInfo,
    handleOpenResourceModal,
    handleCommitBtn,
    fetchSshInfo,
    handleExcuteLink,
    handletoolConfirmPopup,
    deleteToolConfirmPopup,
    sshInfo,
  } = useDevTool({ type, did, id, wid });

  const { sshUrl, toolPassword } = sshInfo;

  return (
    <div className={cx('container')}>
      <div className={cx('tool-delete')}>
        <img
          src={DeleteXIcon}
          width={24}
          height={24}
          alt='delete'
          onClick={deleteToolConfirmPopup}
        />
      </div>
      <div className={cx('tool-logo')}>
        <img
          width={32}
          height={32}
          src={`/images/icon/ic-${TOOL_IMAGE[type]}.svg`}
          alt='icon'
        />
      </div>
      <div className={cx('tool')}>
        <div className={cx('name')}>
          <span>{TOOL_NAME[type]}</span>
          {status === 'error' && (
            <div className={cx('tooltip-cont')}>
              <Tooltip
                title={
                  <span className={cx('tooltip-title')}>
                    {status?.toUpperCase()}
                  </span>
                }
                contents={
                  <div className={cx('tooltip-contents')}>
                    <div className={cx('error-message')}>
                      <label>Reason:</label>
                      {reason || ' -'}
                    </div>
                  </div>
                }
                contentsAlign={{ horizontal: 'center' }}
                contentsCustomStyle={{
                  maxWidth: '400px',
                }}
                children={
                  <img
                    src='/images/icon/00-ic-alert-yellow.svg'
                    alt='warning'
                    style={{ width: '24px', marginRight: '4px' }}
                  />
                }
              />
            </div>
          )}
        </div>
        <Switch
          disabled={false}
          size='large'
          checked={status !== 'stop'}
          customStyle={getBackgroundColor(status)}
          onChange={() => {
            if (status === 'stop') {
              handleOpenResourceModal();
            } else {
              handletoolConfirmPopup();
            }
          }}
        />
      </div>
      <div className={cx('message', status)}>{getMessage(status)}</div>
      <div className={cx('desc')}>
        도커 이미지를 기반으로 {TOOL_NAME[type]}을 실행합니다.
      </div>
      <div className={cx('environment-info')}>
        <div className={cx('header')}>{t('runEnvironment.label')}</div>
        <div className={cx('info-box')}>
          <div className={cx('column')}>
            <span className={cx('type')}>컨테이너 이미지</span>
            <span className={cx('value')}>{image}</span>
          </div>
          <div className={cx('column', 'pod')}>
            <span className={cx('type', 'pod')}>Master Pod</span>
            {/* <span className={cx('value')}>{pod}</span> */}
            <span className={cx('value')}>-</span>
          </div>
          <div className={cx('column')}>
            <span className={cx('type')}>IP</span>
            <span className={cx('value')}>{ip ?? '-'}</span>
          </div>
          <div className={cx('column')}>
            <span className={cx('type')}>vGPU</span>
            {instanceType === 'GPU' && gpu > 0 ? (
              <span className={cx('value')}>
                {instance} x {gpu} EA
              </span>
            ) : (
              <span className={cx('value')}>-</span>
            )}
          </div>
          <div className={cx('column')}>
            <span className={cx('type')}>vCPU</span>
            <span className={cx('value')}>{cpu} Cores</span>
          </div>
          <div className={cx('column')}>
            <span className={cx('type')}>RAM</span>
            <span className={cx('value')}>{ram} GB</span>
          </div>
        </div>
      </div>
      <div className={cx('footer-box')}>
        <Button
          disabled={status === 'stop' || !commitStatus}
          type='primary-light'
          size='large'
          iconAlign='right'
          customStyle={{
            fontSize: '14px',
            fontFamily: 'SpoqaB',
            fontWeight: 'normal',
            width: '90px',
            height: '36px',
            backgroundColor: status === 'stop' && '#F0F0F0',
            color: status === 'stop' && '#C1C1C1',
          }}
          iconStyle={{ marginLeft: '8px' }}
          onClick={handleCommitBtn}
        >
          Commit
        </Button>
        <div className={cx('ssh-box')}>
          {sshOpen && (
            <div className={cx('popup')}>
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
                  {toolPassword.slice(0, 29)}
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

          <Button
            disabled={status !== 'running'}
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
              backgroundColor: status !== 'running' && '#F0F0F0',
              color: status !== 'running' && '#C1C1C1',
            }}
            iconStyle={{
              marginLeft: '8px',
            }}
            onClick={() => {
              if (status !== 'running') return;
              setSshOpen((prev) => !prev);
              fetchSshInfo();
            }}
          >
            SSH
          </Button>
          <Button
            disabled={status !== 'running'}
            type='primary-light'
            size='large'
            icon={'/images/icon/00-ic-basic-link-external-blue.svg'}
            iconAlign='right'
            customStyle={{
              fontSize: '14px',
              fontFamily: 'SpoqaB',
              fontWeight: 'normal',
              width: '90px',
              height: '36px',
              backgroundColor: status !== 'running' && '#F0F0F0',
              color: status !== 'running' && '#C1C1C1',
            }}
            iconStyle={{ marginLeft: '8px' }}
            onClick={() => {
              if (status !== 'running') return;
              handleExcuteLink();
            }}
          >
            실행
          </Button>
        </div>
      </div>
    </div>
  );
};

export default DevToolCard;
