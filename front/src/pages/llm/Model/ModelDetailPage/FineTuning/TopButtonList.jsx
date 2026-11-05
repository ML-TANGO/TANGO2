import { ButtonV2 } from '@jonathan/ui-react';

import { loadModalComponent } from '@src/modal';
import { useEffect, useState } from 'react';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import { openConfirm } from '@src/store/modules/confirm';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './FineTuning.module.scss';

const cx = classNames.bind(style);

const initialStatus = {
  commit_status: {
    status: null,
    type: null,
    reason: null,
  },
  fine_tuning_status: {
    status: null,
    reason: null,
  },
};

// ** 시스템 로그 Disabled
const isCalSystemlog = (commit, finetuning) => {
  const { status: commitStatus, type: commitType } = commit;
  const { status: finetuningStatus } = finetuning;
  if (!commitStatus || !finetuningStatus) return true;
  if (commitStatus === 'error' && commitType === 'download') {
    return true;
  }
  return false;
};

// ** 커밋,커밋 불러오기 Disabled
const isCalCommitLoad = (commit, finetuning) => {
  const { status: commitStatus, type: commitType } = commit;
  const { status: finetuningStatus } = finetuning;
  if (!commitStatus || !finetuningStatus) return true;
  if (commitStatus === 'error' && commitType === 'download') {
    return true;
  }
  if (
    commitStatus === 'running' ||
    finetuningStatus === 'running' ||
    finetuningStatus === 'pending' ||
    finetuningStatus === 'installing'
  ) {
    return true;
  }
  return false;
};

// ** 실행  Disabled
const isCalRun = (commit, finetuning) => {
  const { status: commitStatus, type: commitType } = commit;
  const { status: finetuningStatus } = finetuning;
  if (!commitStatus || !finetuningStatus) return true;
  if (commitStatus === 'error' && commitType === 'download') {
    return true;
  }
  if (commitStatus === 'running' || finetuningStatus === 'running') {
    return true;
  }
  return false;
};

// ** 중지  Disabled
const isCalStop = (commit, finetuning) => {
  const { status: commitStatus, type: commitType } = commit;
  const { status: finetuningStatus } = finetuning;
  if (!commitStatus || !finetuningStatus) return true;
  if (commitStatus === 'error' && commitType === 'download') {
    return true;
  }
  if (commitStatus === 'running') {
    return true;
  }
  return false;
};

// ** header 메시지 출력 - 케이스가 너무 많음
const isCalMessage = (commit, finetuning) => {
  const { status: commitStatus, type: commitType } = commit;
  const { status: finetuningStatus } = finetuning;

  if (commitStatus !== 'done') {
    if (commitStatus === 'error' && commitType === 'download') {
      return { message: 'finetuning.commit.error.message', color: '#fa4e57' };
    }

    if (commitType === 'download') {
      return {
        message: 'finetuning.commit.download.message',
        color: '#fa4e57',
      };
    }

    if (commitType === 'commit') {
      return { message: 'finetuning.commit.save.message', color: '#fa4e57' };
    }

    if (commitType === 'load') {
      return {
        message: 'finetuning.commit.load.message',
        color: '#fa4e57',
      };
    }

    if (commitType === 'stop') {
      return {
        message: 'finetuning.commit.stop.message',
        color: '#fa4e57',
      };
    }
  }

  if (finetuningStatus === 'pending') {
    return { message: 'finetuning.pending.message', color: '#ff7a00' };
  }
  if (finetuningStatus === 'installing') {
    return { message: 'finetuning.installing.message', color: '#00c775' };
  }

  if (finetuningStatus === 'running') {
    return { message: 'finetuning.running.message', color: '#00c775' };
  }
  if (finetuningStatus === 'error') {
    return { message: 'finetuning.error.message', color: '#fa4e57' };
  }
  if (finetuningStatus === 'stop') {
    return { message: 'finetuning.stop.message', color: '#fa4e57' };
  }
  if (finetuningStatus === 'done') {
    return { message: 'finetuning.stop.message', color: '#fa4e57' };
  }
  return { message: '', color: '' };
};

const test = {
  fine_tuning_status: { status: 'running', reason: null },
  commit_status: { status: 'done', type: 'load', reason: '' },
};

const TopButtonList = ({
  t,
  onClickSystemLog,
  modelId,
  fineStatus,
  onClickRun,
  btnDisable,
  onClickCommitLoad,
  onClickCommit,
}) => {
  const dispatch = useDispatch();
  const { commit_status: commitStatus, fine_tuning_status: finetuningStatus } =
    fineStatus ?? initialStatus;

  const { status } = finetuningStatus;

  const [stopLoading, setStopLoading] = useState(false);
  const { info } = useSelector((state) => state.llmModel, shallowEqual);

  const isCommitLoadDisabled = isCalCommitLoad(commitStatus, finetuningStatus);
  const isCommitDisabled = isCalCommitLoad(commitStatus, finetuningStatus);
  const isSystemlogDisabled = isCalSystemlog(commitStatus, finetuningStatus);
  const isRunDisabled = isCalRun(commitStatus, finetuningStatus);
  const isStopDisabled = isCalStop(commitStatus, finetuningStatus);
  const { message, color } = isCalMessage(commitStatus, finetuningStatus);

  const onClickStop = async () => {
    setStopLoading(true);
    // const body = {
    //   model_id: modelId,
    // };

    const response = await callApi({
      url: 'models/fine-tuning/stop',
      method: 'post',
      body: JSON.stringify(modelId),
    });

    const { status, message, error } = response;

    if (status === STATUS_SUCCESS) {
    } else {
      errorToastMessage(error, message);
    }
    setStopLoading(false);
  };

  const stopBtnVisible =
    status === 'running' || status === 'pending' || status === 'installing';

  const runBtnVisible =
    status === 'stop' || status === 'done' || status === 'error';

  useEffect(() => {
    loadModalComponent('FINETUNING_COMMIT');
  }, []);

  return (
    <div className={cx('btn-list')}>
      <div className={cx('message')} style={{ color }}>
        {t(message)}
      </div>

      <div className={cx('btn')}>
        <ButtonV2 // 시스템 로그
          type='solid'
          size='l'
          colorType='skyblue'
          label={t('systemLog.label')}
          onClick={onClickSystemLog}
          disabled={isSystemlogDisabled}
          style={{ width: '100%' }}
        />
        <ButtonV2 // 커밋 불러오기
          type='solid'
          size='l'
          colorType='skyblue'
          label={t('commitLoad.label')}
          onClick={onClickCommitLoad}
          disabled={isCommitLoadDisabled}
          style={{ width: '100%' }}
        />
        <ButtonV2 // 커밋
          type='solid'
          size='l'
          colorType='skyblue'
          label={t('commit.label')}
          onClick={onClickCommit}
          disabled={isCommitDisabled}
          style={{ width: '100%' }}
        />
        {runBtnVisible && (
          <ButtonV2 // 실행
            type='solid'
            size='l'
            label={t('run.label')}
            onClick={onClickRun}
            disabled={btnDisable.run || isRunDisabled}
            style={{ width: '100%' }}
          />
        )}
        {stopBtnVisible && (
          <ButtonV2 // 중지
            type='solid'
            size='l'
            colorType='red'
            label={t('stop.label')}
            // onClick={openCommitConfirmPopup}
            onClick={onClickStop}
            disabled={stopLoading || isStopDisabled}
            style={{ width: '100%' }}
          />
        )}
      </div>
    </div>
  );
};

export default TopButtonList;
