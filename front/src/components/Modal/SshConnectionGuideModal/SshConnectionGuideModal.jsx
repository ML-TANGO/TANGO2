import React, { useState } from 'react';
import { useTranslation, withTranslation } from 'react-i18next';

import { toast } from '@src/components/Toast';

import ModalFrame from '../ModalFrame';

import { copyToClipboard } from '@src/utils';

import classNames from 'classnames/bind';
import style from './SshConnectionGuideModal.module.scss';

const cx = classNames.bind(style);

const SshConnectionGuideModal = ({ type, data }) => {
  const { t } = useTranslation();

  const { submit, sshGuideInfo, sshInfo } = data;

  const { ingressIp, toolIp, user } = sshGuideInfo;
  const [selectedTab, setSelectedTab] = useState('window');

  const newSubmit = {
    text: submit.text,
    func: () => {
      submit.func();
    },
  };

  const extractPort = (sshCommand) => {
    const match = sshCommand.match(/-p (\d+)/);
    return match ? match[1] : '8222'; // 포트 번호가 있으면 반환, 없으면 null 반환
  };

  const port = extractPort(sshInfo?.sshUrl);

  const copyCommand = (value, message) => {
    copyToClipboard(value);
    toast.success(message);
  };

  return (
    <ModalFrame
      validate={true}
      submit={newSubmit}
      isResize={true}
      isMinimize={true}
      customStyle={{ width: '664px' }}
      type={'SSH_CONNECTION_GUIDE'}
    >
      <h2 className={cx('title')}>{t('sshConnectionGuide.title')}</h2>
      <div className={cx('form')}>
        <div className={cx('row')}>
          <div className={cx('tab-container')}>
            <div
              className={cx('tab', selectedTab === 'window' && 'selected')}
              onClick={() => setSelectedTab('window')}
            >
              Windows
            </div>

            <div
              className={cx('tab', selectedTab === 'linux' && 'selected')}
              onClick={() => setSelectedTab('linux')}
            >
              Linux/Mac
            </div>
          </div>
        </div>
        <div className={cx('row')}>
          <div className={cx('first-step')}>
            <div className={cx('header')}>
              <div className={cx('number')}>1</div>
              <div className={cx('text')}>{t('sshKeyDownload.label')}</div>
            </div>
            <div className={cx('content')}>
              <div className={cx('left-line')}></div>
              <div className={cx('profile-text')}>우측 상단의 프로필</div>
              <div className={cx('sample-image')}>
                <div className={cx('first-column')}>
                  <span>안녕하세요</span>
                  <span>로그아웃</span>
                </div>
                <div className={cx('second-column')}>
                  <span>{user}</span>
                  <span>님</span>
                </div>
                <div className={cx('third-column')}>비밀변호 변경하기</div>
                <div className={cx('download')}>
                  <img
                    src='/images/icon/00-ic-ssh-download.svg'
                    alt='ssh'
                    height={28}
                    width={28}
                  />
                  <span>SSH Key 다운로드</span>
                </div>
              </div>
              <div className={cx('click-text')}>
                [SSH Key 다운로드] 버튼 클릭
              </div>
            </div>
          </div>
        </div>
        <div className={cx('row')}>
          <div className={cx('second-step')}>
            <div className={cx('header')}>
              <div className={cx('number')}>2</div>
              <div className={cx('text')}>{t('sshPermissionChange.title')}</div>
            </div>
            <div className={cx('content')}>
              <div className={cx('left-line')}></div>
              <div className={cx('change-step')}>
                <div className={cx('first')}>
                  <img
                    src={`${
                      selectedTab === 'window'
                        ? '/images/icon/00-ic-ssh-window.png'
                        : '/images/icon/00-ic-ssh-linux.svg'
                    }`}
                    alt='icon'
                    height={24}
                    width={24}
                  />
                  <span>
                    {selectedTab === 'window'
                      ? 'PowerShell 실행'
                      : 'Terminal 실행'}
                  </span>
                </div>
                <div className={cx('second')}>
                  <div className={cx('desc')}>
                    <span>SSH Permission Key를 ssh 디렉토리로 이동</span>
                    <img
                      src='/images/icon/00-ic-ssh-gray-copy.svg'
                      alt='copy'
                      width={20}
                      height={20}
                      onClick={() =>
                        copyCommand(
                          selectedTab === 'window'
                            ? `mv ${user}.pem ~\\.ssh`
                            : `mv ${user}.pem ~/.ssh`,
                          '디렉토리 이동 명령어 복사 성공',
                        )
                      }
                      className={cx('copy-icon')}
                    />
                  </div>
                  {/* <span className={cx('sample')}>
                    예시&#41;
                    {selectedTab === 'window'
                      ? '바탕화면에 다운로드 했을 경우'
                      : '사용자 home 경로에 다운로드 했을 경우'}
                  </span> */}
                  <div className={cx('command')}>
                    {selectedTab === 'window'
                      ? `mv ${user}.pem ~\\.ssh`
                      : `mv ${user}.pem ~/.ssh`}
                  </div>
                </div>
                <div className={cx('third')}>
                  <div className={cx('desc')}>
                    <span>키 파일의 권한 변경</span>
                    <img
                      src='/images/icon/00-ic-ssh-gray-copy.svg'
                      alt='copy'
                      width={20}
                      height={20}
                      onClick={() =>
                        copyCommand(
                          selectedTab === 'window'
                            ? `icacls $env:USERPROFILE\\.ssh\\${user}.pem /reset \n icacls $env:USERPROFILE\\.ssh\\${user}.pem /grant:r "$($env:USERNAME):(R)" \n icacls $env:USERPROFILE\\.ssh\\${user}.pem /inheritance:r`
                            : `chmod 400 ~/.ssh/${user}.pem`,
                          '키 파일 권한 변경 명령어 복사 성공',
                        )
                      }
                      className={cx('copy-icon')}
                    />
                  </div>
                  <div className={cx('command')}>
                    {selectedTab === 'window' ? (
                      <>
                        <span>{`icacls $env:USERPROFILE\\.ssh\\${user}.pem /reset`}</span>
                        <span>{`icacls $env:USERPROFILE\\.ssh\\${user}.pem /grant:r "$($env:USERNAME):(R)"`}</span>
                        <span>{`icacls $env:USERPROFILE\\.ssh\\${user}.pem /inheritance:r`}</span>
                      </>
                    ) : (
                      <span>chmod 400 ~/.ssh/{user}.pem</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className={cx('row')}></div>
        <div className={cx('third-step')}>
          <div className={cx('header')}>
            <div className={cx('number')}>3</div>
            <div className={cx('text')}>SSH 접속</div>
          </div>
          <div className={cx('content')}>
            <div className={cx('direct-ssh')}>
              <div className={cx('header')}>
                <span>Direct SSH</span>
                <img
                  src='/images/icon/00-ic-ssh-gray-copy.svg'
                  alt='copy'
                  width={20}
                  height={20}
                  onClick={() =>
                    copyCommand(
                      `${
                        selectedTab === 'window'
                          ? `ssh -o ProxyCommand="ssh -i $env:USERPROFILE\\.ssh\\${user}.pem -p ${port} -W %h:%p ${user}@${ingressIp}" root@${toolIp}`
                          : `ssh -o ProxyCommand="ssh -i ~/.ssh/${user}.pem -p ${port} -W %h:%p ${user}@${ingressIp}" root@${toolIp}`
                      }`,
                      'Direct SSH 명령어 복사 성공',
                    )
                  }
                  className={cx('copy-icon')}
                />
              </div>
              <div className={cx('command')}>
                <span>
                  {selectedTab === 'window'
                    ? `ssh -o ProxyCommand="ssh -i $env:USERPROFILE\\.ssh\\${user}.pem -p ${port} -W`
                    : `ssh -o ProxyCommand="ssh -i ~/.ssh/${user}.pem -p ${port} -W`}
                </span>
                <span>{`%h:%p ${user}@${ingressIp}" root@${toolIp}`}</span>
              </div>
            </div>
            <div className={cx('ssh-config-file')}>
              <div className={cx('header')}>
                <img
                  src='/images/icon/00-ic-ssh-empty-folder.svg'
                  alt='folder'
                  width={24}
                  height={24}
                />
                <span>SSH config file (VSCode 등)</span>
              </div>
              <div className={cx('sample')}>
                {/* <span>Linux 경로: /home/design/.ssh/config</span> */}
                {/* <span>Windows 경로: C:\Users\design\.ssh\config</span> */}
                <span>
                  config file 경로:
                  {` ${
                    selectedTab === 'window'
                      ? `~\\.ssh\\config`
                      : `~/.ssh/config`
                  }`}
                </span>
              </div>
              <div className={cx('config')}>
                <div className={cx('desc')}>
                  <span>1&#41; config file에 아래 내용 추가</span>
                  <img
                    src='/images/icon/00-ic-ssh-gray-copy.svg'
                    alt='copy'
                    width={20}
                    height={20}
                    onClick={() =>
                      copyCommand(
                        `${
                          selectedTab === 'window'
                            ? `Host ${toolIp} \n  HostName ${toolIp} \n ProxyCommand ssh -i (절대 경로입력)\\.ssh\\${user}.pem -p ${port} -W%h:%p ${user}@${ingressIp} \n User root`
                            : `Host ${toolIp} \n  HostName ${toolIp} \n ProxyCommand ssh -i ~/.ssh/${user}.pem -p ${port} -W%h:%p ${user}@${ingressIp} \n User root`
                        }`,
                        'Config file 내용 복사 성공',
                      )
                    }
                    className={cx('copy-icon')}
                  />
                </div>
                <div className={cx('command')}>
                  <span>Host {toolIp}</span>
                  <span>&nbsp; &nbsp;HostName {toolIp}</span>
                  <span>
                    &nbsp; &nbsp;
                    {selectedTab === 'window' ? (
                      <>
                        {`ProxyCommand ssh -i (절대 경로입력)\\.ssh\\${user}.pem`}
                        <br />
                        &nbsp; &nbsp;{`-p ${port} -W %h:%p`}
                      </>
                    ) : (
                      `ProxyCommand ssh -i ~/.ssh/${user}.pem -p ${port} -W %h:%p`
                    )}
                    <br />
                    &nbsp; &nbsp;{user}@{ingressIp}
                  </span>
                  <span>&nbsp; &nbsp;User root</span>
                </div>
              </div>
              <div className={cx('line')}></div>
              <div className={cx('ssh')}>
                <div className={cx('desc')}>
                  <span>2&#41; SSH</span>
                  <img
                    src='/images/icon/00-ic-ssh-gray-copy.svg'
                    alt='copy'
                    width={20}
                    height={20}
                    onClick={() =>
                      copyCommand(`ssh root@${toolIp}`, 'SSH 주소 복사 성공')
                    }
                    className={cx('copy-icon')}
                  />
                </div>
                <div className={cx('command')}>ssh root@{toolIp}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ModalFrame>
  );
};

export default withTranslation()(SshConnectionGuideModal);
