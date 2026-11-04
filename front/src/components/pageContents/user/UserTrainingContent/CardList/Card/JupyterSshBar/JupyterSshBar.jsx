import { useState } from 'react';

import { useTranslation } from 'react-i18next';

// Components
import { toast } from '@src/components/Toast';

// Molecules
import DropMenu from '@src/components/molecules/DropMenu';
import BtnMenu from '@src/components/molecules/DropMenu/BtnMenu';

// Network
import { callApi, STATUS_SUCCESS, STATUS_FAIL } from '@src/network';

// Utils
import { copyToClipboard, errorToastMessage } from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './JupyterSshBar.module.scss';

const cx = classNames.bind(style);

/**
 * 에디터용 학습용 Jupyter 정보 컴포넌트
 * @param {{
 *  editorForCodeInfo : {
 *    id: string,
 *    port: number | '-',
 *    status: 'running' | 'pending' | 'error' | 'installing',
 *    config: [ { name: string } ],
 *  },
 *  editorForTrainInfo: {
 *    id: string,
 *    port: number | '-',
 *    status: 'running' | 'pending' | 'error' | 'installing',
 *    config: [ { name: string } ],
 *    gpuCount: number,
 *  }
 * }} props jupyter 정보
 * @component
 * @example
 *
 * const editorForCodeInfo = {
 *  id: '',
 *  port: 1234,
 *  status: 'running' | 'pending' | 'error' | 'installing',
 *  config: [ 'A', 'B' ],
 * };
 * const editorForTrainInfo = {
 *  id: '',
 *  port: 1234,
 *  status: 'running' | 'pending' | 'error' | 'installing',
 *  config: [ 'A', 'B' ],
 * };
 * return (
 *  <JupyterSshBar editorForCodeInfo={editorForCodeInfo} editorForTrainInfo={editorForTrainInfo} />
 * );
 *
 *
 */
function JupyterSshBar({ editorForCodeInfo, editorForTrainInfo }) {
  // 다국어 지원
  const { t } = useTranslation();

  // 컴포넌트 State
  const [editorForCodeLoading, setEditorForCodeLoading] = useState(false);
  const [editorForTrainLoading, setEditorForTrainLoading] = useState(false);

  /**
   * SSH 접속 명령어 복사
   * @param {string} toolId 학습 툴(현재는 Jupyter만 있음) id
   * @param {'EDITOR_FOR_CODE' | 'EDITOR_FOR_TRAIN'} target EDITOR_FOR_CODE: 편집용 Jupyter, EDITOR_FOR_TRAIN: 학습용 Jupyter
   */
  const copySSHAddress = async (toolId, target) => {
    if (target === 'EDITOR_FOR_CODE') {
      setEditorForCodeLoading(true);
    } else if (target === 'EDITOR_FOR_TRAIN') {
      setEditorForTrainLoading(true);
    }
    const response = await callApi({
      url: `trainings/ssh_login_cmd?training_tool_id=${toolId}`,
      method: 'get',
    });

    setEditorForCodeLoading(false);
    setEditorForTrainLoading(false);

    const { result, status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      copyToClipboard(result);
      toast.success(result);
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * Jupyter 새창에서 열기
   * @param {string} toolId 학습 툴(현재는 Jupyter만 있음) id
   * @param {'EDITOR_FOR_CODE' | 'EDITOR_FOR_TRAIN'} target EDITOR_FOR_CODE: 편집용 Jupyter, EDITOR_FOR_TRAIN: 학습용 Jupyter
   */
  const openJupyter = async (toolId, target) => {
    if (target === 'EDITOR_FOR_CODE') {
      setEditorForCodeLoading(true);
    } else if (target === 'EDITOR_FOR_TRAIN') {
      setEditorForTrainLoading(true);
    }

    const response = await callApi({
      url: `trainings/jupyter_url?training_tool_id=${toolId}&protocol=${window.location.protocol.replace(
        ':',
        '',
      )}`,
      method: 'get',
    });

    setEditorForCodeLoading(false);
    setEditorForTrainLoading(false);

    const { result, status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      const jupyterUrl = result.url;
      // const jupyterUrl = result.url.replace('http:', window.location.protocol);
      window.open(jupyterUrl, '_blank');
    } else if (status === STATUS_FAIL) {
      errorToastMessage(error, message);
    } else {
      toast.error(message);
    }
  };

  // CPU Jupyter 컨트롤러 옵션
  const editorCpuMenuList = [
    {
      name: `SSH ${editorForCodeInfo.port}`,
      iconPath: '/images/icon/00-ic-basic-copy-o.svg',
      onClick: () => {
        copySSHAddress(editorForCodeInfo.id, 'EDITOR_FOR_CODE');
      },
    },
    {
      name: 'Jupyter',
      iconPath: '/images/icon/00-ic-basic-link-external.svg',
      onClick: () => {
        openJupyter(editorForCodeInfo.id, 'EDITOR_FOR_CODE');
      },
    },
  ];

  // GPU Jupyter 컨트롤러 옵션
  const trainGpuMenuList = [
    {
      name: `SSH ${editorForTrainInfo.port}`,
      iconPath: '/images/icon/00-ic-basic-copy-o.svg',
      onClick: () => {
        copySSHAddress(editorForTrainInfo.id, 'EDITOR_FOR_TRAIN');
      },
    },
    {
      name: 'Jupyter',
      iconPath: '/images/icon/00-ic-basic-link-external.svg',
      onClick: () => {
        openJupyter(editorForTrainInfo.id, 'EDITOR_FOR_TRAIN');
      },
    },
  ];

  // GPU 장치 목록
  const gpuSpecList = editorForTrainInfo.config;

  // CPU 장치 목록
  const cpuSpecList = editorForCodeInfo.config;
  return (
    <div className={cx('jupyter-ssh')}>
      <div className={'event-block'}>
        <div className={cx('btn-wrap', editorForCodeInfo.status)}>
          <DropMenu
            btnRender={(isOpen) => (
              <button
                className={cx(
                  'btn',
                  isOpen && 'active',
                  editorForCodeLoading && 'loading',
                )}
                disabled={editorForCodeInfo.status !== 'running'}
              >
                {editorForCodeInfo.status === 'installing'
                  ? 'installing'
                  : t('editor.label')}
              </button>
            )}
            menuRender={(popupHandler) => (
              <BtnMenu btnList={editorCpuMenuList} callback={popupHandler} />
            )}
            align='LEFT'
            isDropUp
          />
          <span className={`${cx('divider')} event-block`}></span>
          <DropMenu
            btnRender={(isOpen) => (
              <button
                className={cx('btn', isOpen && 'active')}
                disabled={editorForCodeInfo.status !== 'running'}
              >
                {t('cpu.label')}
              </button>
            )}
            menuRender={() => <BtnMenu btnList={cpuSpecList} />}
            align='LEFT'
            isDropUp
          />
        </div>
      </div>
      <div className={'event-block'}>
        <div className={cx('btn-wrap', editorForTrainInfo.status)}>
          <DropMenu
            btnRender={(isOpen) => (
              <button
                className={cx(
                  'btn',
                  isOpen && 'active',
                  editorForTrainLoading && 'loading',
                )}
                disabled={editorForTrainInfo.status !== 'running'}
              >
                {editorForTrainInfo.status === 'installing'
                  ? 'installing'
                  : t('train.label')}
              </button>
            )}
            menuRender={(popupHandler) => (
              <BtnMenu btnList={trainGpuMenuList} callback={popupHandler} />
            )}
            align='RIGHT'
            isDropUp
          />
          <span className={`${cx('divider')} event-block`}></span>
          <DropMenu
            btnRender={(isOpen) => (
              <button
                className={cx('btn', isOpen && 'active')}
                disabled={editorForTrainInfo.status !== 'running'}
              >
                {t('gpu.label')}
                {editorForTrainInfo.status === 'running'
                  ? `*${editorForTrainInfo.gpuCount}`
                  : ''}
              </button>
            )}
            menuRender={() => <BtnMenu btnList={gpuSpecList} />}
            align='RIGHT'
            isDropUp
          />
        </div>
      </div>
    </div>
  );
}

export default JupyterSshBar;
