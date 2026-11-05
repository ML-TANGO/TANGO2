import { useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { Button } from '@jonathan/ui-react';

// Type
import { TRAINING_TOOL_TYPE } from '@src/types';
import { transform } from 'lodash';

import DropMenu from '@src/components/molecules/DropMenu';
// Components
import { toast } from '@src/components/Toast';

// Actions
import { closeModal, openModal } from '@src/store/modules/modal';
// Network
import { callApi, STATUS_FAIL, STATUS_SUCCESS } from '@src/network';

// Utils
import { /* copyToClipboard,*/ errorToastMessage } from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './Workbench.module.scss';

// Icons
import WorkbenchIcon from '@src/static/images/icon/icon-workbench-blue.svg';

const cx = classNames.bind(style);

function Workbench({ toolList }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const [isActive, setIsActive] = useState(false);

  /**
   * SSH 접속 명령어 복사
   * @param {string} toolId 학습 툴 id
   */
  // const copySSHAddress = async (toolId) => {

  //   const response = await callApi({
  //     url: `trainings/ssh_login_cmd?training_tool_id=${toolId}`,
  //     method: 'get',
  //   });

  //   const { result, status, message, error } = response;

  //   if (status === STATUS_SUCCESS) {
  //     copyToClipboard(result);
  //     toast.success(result);
  //   } else if (status === STATUS_FAIL) {
  //     errorToastMessage(error, message);
  //   } else {
  //     toast.error(message);
  //   }
  // };

  /**
   * 도구 비밀번호 변경 모달
   * 현재는 파일브라우저만 해당
   */
  const onPasswordChange = (toolId, toolType, toolName) => {
    dispatch(
      openModal({
        modalType: 'TOOL_PASSWORD_CHANGE',
        modalData: {
          submit: {
            text: 'create.label',
            func: () => {
              dispatch(closeModal('TOOL_PASSWORD_CHANGE'));
              moveToolLink(toolId);
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          toolId,
          toolType,
          toolName,
          isReset: false,
        },
      }),
    );
  };

  /**
   * Tool 새창에서 열기
   * @param {string} toolId 학습 툴 id
   */
  const moveToolLink = async (toolId, toolType, toolName) => {
    const response = await callApi({
      url: `projects/tool-url?project_tool_id=${toolId}&protocol=${window.location.protocol.replace(
        ':',
        '',
      )}`,
      method: 'get',
    });

    const { result, status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      if (result.url !== '') {
        window.open(result.url, '_blank');
      } else {
        if (result?.need_password_change) {
          // 비밀번호 변경 필요
          onPasswordChange(toolId, toolType, toolName);
        }
      }
    } else if (status === STATUS_FAIL) {
      errorToastMessage(error, message);
    } else {
      toast.error(message);
    }
  };

  useEffect(() => {
    if (toolList.length > 0) {
      setIsActive(true);
    } else {
      setIsActive(false);
    }
  }, [toolList]);

  return (
    <div className={`${cx('workbench', !isActive && 'disabled')} event-block`}>
      <DropMenu
        customStyle={{ width: '100%' }}
        maxHeight={'160px'}
        popMenuCustomStyle={{
          transform: `translate(98px, 0px)`,
          zIndex: 1,
        }}
        menuRender={() =>
          isActive
            ? toolList.map(
                ({
                  tool_id: id,
                  tool_status: status,
                  tool_type: type,
                  tool_name: name,
                  // tool_replica_number: replicaNumber,
                  function_info: functionInfoArr,
                }) => (
                  <div className={cx('tool-item')} key={`${name}${id}`}>
                    <div className={cx('tool-resource')}>
                      <img
                        className={cx('tool-icon')}
                        src={`/images/icon/ic-${TRAINING_TOOL_TYPE[type].type}.svg`}
                        alt={TRAINING_TOOL_TYPE[type].type}
                      />
                      {/* <div className={cx('tool-replica-number')}>
                      {replicaNumber === 0
                        ? '00'
                        : replicaNumber < 10
                        ? `0${replicaNumber}`
                        : replicaNumber}
                    </div> */}

                      <label
                        className={cx('tool-name')}
                        title={name || TRAINING_TOOL_TYPE[type].label}
                      >
                        {name || TRAINING_TOOL_TYPE[type].label}
                      </label>
                    </div>

                    <div className={cx('tool-btn')}>
                      {status &&
                      status.status &&
                      (status.status === 'pending' ||
                        status.status === 'scheduling' ||
                        status.status === 'installing' ||
                        status.status === 'error') ? (
                        <div className={cx('status', status.status)}>
                          {t(`${status.status}`)}
                        </div>
                      ) : (
                        functionInfoArr.map((value, key) => {
                          // if (value === 'ssh') {
                          //   return (
                          //     <Button
                          //       key={key}
                          //       type='none-border'
                          //       size='small'
                          //       icon={'/images/icon/00-ic-basic-copy-o.svg'}
                          //       iconAlign='right'
                          //       customStyle={{
                          //         width: 'auto',
                          //         fontFamily: 'SpoqaR',
                          //         padding: '0 6px',
                          //       }}
                          //       onClick={() => {
                          //         copySSHAddress(id);
                          //       }}
                          //     >
                          //       SSH
                          //     </Button>
                          //   );
                          // } else

                          if (value.type === 'link') {
                            return (
                              <div className={cx('link-btn')} key={key}>
                                <Button
                                  type='none-border'
                                  size='small'
                                  icon={
                                    '/images/icon/00-ic-basic-link-external.svg'
                                  }
                                  iconAlign='right'
                                  customStyle={{
                                    width: 'auto',
                                    fontFamily: 'SpoqaR',
                                    padding: '0 6px',
                                  }}
                                  onClick={() => {
                                    moveToolLink(id, type, name);
                                  }}
                                >
                                  <span className={cx('btn-label')}>
                                    {/* {name || TRAINING_TOOL_TYPE[type].label} */}
                                    {t('run.label')}
                                  </span>
                                </Button>
                              </div>
                            );
                          }
                          return null;
                        })
                      )}
                    </div>
                  </div>
                ),
              )
            : []
        }
        btnRender={(isUp) => (
          <Button
            type='primary-light'
            icon={WorkbenchIcon}
            disabled={!isActive}
            customStyle={{
              width: '100%',
              backgroundColor: isUp
                ? '#c8dbfd'
                : isActive
                ? '#dee9ff'
                : '#f9fafb',
              borderColor: isUp ? '#c8dbfd' : isActive ? '#dee9ff' : '#f9fafb',
              boxShadow: isActive
                ? '0px 3px 6px 0px rgba(45, 118, 248, 0.1)'
                : '',

              fontSize: '16px',
              fontFamily: 'SpoqaB',
            }}
          >
            {t('developTool.label')}
          </Button>
        )}
        align='LEFT'
        isDropUp
        isScroll
      />
    </div>
  );
}

export default Workbench;
