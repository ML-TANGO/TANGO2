import { Switch, Tooltip } from '@jonathan/ui-react';

import { TRAINING_TOOL_TYPE } from '@src/types';

import classNames from 'classnames/bind';
import style from './ToolCardContent.module.scss';

const cx = classNames.bind(style);

const calToogleButtonColor = (status, toolLoading) => {
  const yellowStatus = ['pending', 'scheduling'];

  if (status === 'installing') {
    return { backgroundColor: '#00C775' };
  }

  if (yellowStatus.includes(status) || toolLoading.current) {
    return { backgroundColor: '#ffab31' };
  }

  if (status === 'failed' || status === 'error') {
    return { backgroundColor: '#eb3e2a' };
  }

  return {};
};

const ToolCardContent = ({
  isNameEditable = false,
  // ** 툴 이름 관련 **
  toolName,
  toolTypeId,
  tool_index,
  toolStatus,
  // ** 스위치 관련 **
  isDisabledSwitch,
  isSwitchPossible,
  switchBackgroundColor,
  checked,
  handleSwitch,
  // ** 메세지 관련 **
  runningMessage,
  runningMessageColor,
  isHideExplanation,
  i18n,
}) => {
  return (
    <>
      <div className={cx('name-box')}>
        <div className={cx('name-cont')}>
          <span className={cx('tool-name', isNameEditable && 'edit')}>
            {toolName === 'SSH' ? 'Shell' : toolName}{' '}
            {tool_index > 0 && `(${tool_index})`}
          </span>
          {(toolStatus.status === 'error' ||
            toolStatus.status === 'failed') && (
            <div className={cx('tooltip-cont')}>
              <Tooltip
                title={
                  <span className={cx('tooltip-title')}>
                    {toolStatus?.status?.toUpperCase()}
                  </span>
                }
                contents={
                  <div className={cx('tooltip-contents')}>
                    <div className={cx('error-message')}>
                      <label>Reason:</label>
                      {toolStatus.reason || ' -'}
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
        {isSwitchPossible && (
          <Switch
            disabled={isDisabledSwitch}
            size='large'
            checked={checked}
            message={toolStatus.reason}
            customStyle={switchBackgroundColor}
            onChange={handleSwitch}
          />
        )}
      </div>
      <p
        className={cx('running-message')}
        style={{ color: runningMessageColor }}
      >
        {runningMessage}
      </p>
      {!isHideExplanation && (
        <div className={cx('explanation')}>
          {TRAINING_TOOL_TYPE[toolTypeId]?.explanation[i18n.language]}
        </div>
      )}
    </>
  );
};

export default ToolCardContent;
