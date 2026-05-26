// i18n

// Type
import { TRAINING_TOOL_TYPE } from '@src/types';
import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useRouteMatch } from 'react-router-dom';

import { callApi } from '@src/network';
import { executeWithLogging } from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './ToolCreateButton.module.scss';

const cx = classNames.bind(style);

function ToolCreateButton({ type }) {
  const { t } = useTranslation();
  const match = useRouteMatch();
  const { tid: projectId } = match.params;

  const { type: toolType } = TRAINING_TOOL_TYPE[type];
  const { label: toolName } = TRAINING_TOOL_TYPE[type];

  const handleCreateTool = useCallback(async (projectId, type) => {
    executeWithLogging(async () => {
      await callApi({
        url: 'projects/tool-add',
        method: 'post',
        body: {
          project_id: +projectId,
          project_tool_type: type,
        },
      });
    });
  }, []);

  return (
    <div
      className={cx('duplicate-btn')}
      onClick={() => handleCreateTool(projectId, type)}
    >
      <div className={cx('icon')}>
        <img src={`/images/icon/ic-${toolType}.svg`} alt={`${toolType} icon`} />
      </div>
      <label className={cx('label')}>
        {t('createTool.label', { tool: toolName })}
      </label>
      <div className={cx('plus')}></div>
    </div>
  );
}

export default ToolCreateButton;
