import { useTranslation } from 'react-i18next';
import { useHistory, useParams } from 'react-router-dom';

import 'react-sweet-progress/lib/style.css';

import { useCallback } from 'react';

import { TRAINING_TOOL_TYPE } from '@src/types';

import classNames from 'classnames/bind';
import style from './QueueTool.module.scss';

const cx = classNames.bind(style);

const toolList = [
  {
    toolId: 2,
    toolType: 'job',
  },
  {
    toolId: 3,
    toolType: 'hps',
  },
  {
    toolId: 9,
    toolType: 'federatedLearning',
  },
];

// ** isHideExplanation 현재 사용하는 버튼이 없어서 지워 버림 나중에 쓸 수도 **
// ** Default 값 false로 남겨둠 **
function QueueTool({ isHideExplanation = false }) {
  const history = useHistory();
  const { id: workspaceId, tid: trainingId } = useParams();
  const { t, i18n } = useTranslation();

  const handleMoveToolType = useCallback(
    (toolType, workspaceId, trainingId, history) => {
      if (toolType === 'hps') {
        history.push({
          pathname: `/user/workspace/${workspaceId}/trainings/${trainingId}/workbench/${toolType}`,
        });
        return;
      }
      if (toolType === 'federatedLearning') {
        window.open('http://seven.acryl.ai:10000');
        return;
      }

      history.push({
        pathname: `/user/workspace/${workspaceId}/trainings/${trainingId}/workbench/${toolType}`,
      });
    },
    [],
  );

  return (
    <div className={cx('queue-tool-box')}>
      <h2 className={cx('tool-title')}>{t('trainingTool.label')}</h2>
      <div className={cx('tool-list')}>
        {toolList.map(({ toolId, toolType }) => {
          return (
            <div
              key={toolId}
              className={cx('card-box')}
              onClick={() =>
                handleMoveToolType(toolType, workspaceId, trainingId, history)
              }
            >
              <div className={cx('header', isHideExplanation && 'no-desc')}>
                <div className={cx('icon', toolType)}>
                  <img
                    src={`/images/icon/ic-${toolType}.svg`}
                    alt={`${toolType} icon`}
                  />
                </div>
                <label className={cx('label')}>
                  {TRAINING_TOOL_TYPE[toolId].label}
                </label>
                {/* {toolType && (
                  <img
                    className={cx('arrow-icon')}
                    src='/images/icon/ic-arrow-right-blue.svg'
                    alt='>'
                  />
                )} */}
              </div>
              {!isHideExplanation && (
                <div className={cx('body')}>
                  <p className={cx('description')}>
                    {TRAINING_TOOL_TYPE[toolId].explanation[i18n.language]}
                  </p>
                </div>
              )}
              {/* {toolType === 'hps' && <div className={cx('background')} />}
              {toolType === 'hps' && (
                <span className={cx('later')}>{t('comingsoon.label')}</span>
              )} */}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default QueueTool;
