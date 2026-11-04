// i18n
import { useTranslation } from 'react-i18next';

import { convertLocalTime } from '@src/datetimeUtils';

// Utils
import { capitalizeFirstLetter } from '@src/utils';

import classNames from 'classnames/bind';
// CSS module
import style from './History.module.scss';

const cx = classNames.bind(style);

const History = ({
  type,
  data: {
    time_stamp: datetime,
    user,
    workspace,
    task,
    task_name: taskName,
    action,
    update_details: details,
  },
}) => {
  const { t, i18n } = useTranslation();
  const lan = i18n.language;
  // console.log('task', action);

  function makeMessage() {
    let message = '';
    if (user === 'root') {
      user = t('admin.label');
    } else {
      user = capitalizeFirstLetter(user);
    }
    if (type === 'admin') {
      switch (task) {
        case 'workspace':
          if (lan === 'ko') {
            message = `관리자가 '${workspace}' 워크스페이스를 ${t(
              `${action}.label`,
            )}하였습니다.`;
          } else {
            message = `Admin ${action}d a '${workspace}' workspace.`;
          }
          break;
        case 'training':
          if (lan === 'ko') {
            message = `${user}님이 '${workspace}' 워크스페이스에서 '${taskName.replace(
              'advanced',
              'custom',
            )}' 학습을 ${t(`${action}.label`)}하였습니다.`;
          } else {
            message = `${user} ${action}d a '${taskName.replace(
              'advanced',
              'custom',
            )}' training in the '${workspace}' workspace.`;
          }
          break;
        case 'job':
        case 'hyperparamsearch':
          if (lan === 'ko') {
            message = `${user}님이 '${workspace}' 워크스페이스의 '${taskName
              .split('/')[0]
              .trim()}' 학습에서 '${taskName.split('/')[1].trim()}' ${t(
              `${task}.label`,
            )}을 ${t(`${action}.label`)}하였습니다.`;
          } else {
            message = `${user} ${
              action === 'add' ? 'added' : `${action}d`
            } a '${taskName.split('/')[1].trim()}' ${t(
              `${task}.label`,
            )} in the '${taskName
              .split('/')[0]
              .trim()}' training of '${workspace}' workspace.`;
          }
          break;
        case 'image':
          if (lan === 'ko') {
            if (action === 'create') {
              message = `${user}님이 ${workspace}에 ${
                taskName !== '-' ? taskName.split('/')[0].trim() : taskName
              } 방식으로 '${
                taskName !== '-' ? taskName.split('/')[1].trim() : taskName
              }' 도커 이미지를 업로드하였습니다.`;
            } else {
              message = `${user}님이 '${taskName}' 도커 이미지를 ${t(
                `${action}.label`,
              )}하였습니다.`;
            }
          } else if (action === 'create') {
            message = `${user} uploaded a '${
              taskName !== '-' ? taskName.split('/')[1].trim() : taskName
            }' Docker Image in the '${workspace}' workspace with a ${
              taskName !== '-' ? taskName.split('/')[0].trim() : taskName
            } type.`;
          } else {
            message = `${user} ${action}d a '${taskName}' Docker Image in the '${workspace}' workspace.`;
          }
          break;
        case 'dataset':
          if (lan === 'ko') {
            if (action === 'create') {
              message = `${user}님이 '${workspace}' 워크스페이스에서 '${taskName}' 데이터셋을 생성하였습니다.`;
            } else if (action.toLowerCase().indexOf('data') !== -1) {
              if (action.toLowerCase().indexOf('upload') !== -1) {
                message = `${user}님이 '${workspace}' 워크스페이스의 '${taskName}' 데이터셋에 데이터를 업로드하였습니다.`;
              } else {
                message = `${user}님이 '${workspace}' 워크스페이스의 '${taskName}' 데이터셋의 데이터를 ${t(
                  `${action.replace('Data', '')}.label`,
                )}하였습니다.`;
              }
            } else if (action.toLowerCase().indexOf('download') !== -1) {
              if (details) {
                message = `${user}님이 '${workspace}' 워크스페이스의 '${taskName}' 데이터셋의 데이터를 다운로드하였습니다.`;
              } else {
                message = `${user}님이 '${workspace}' 워크스페이스의 '${taskName}' 데이터셋을 다운로드하였습니다.`;
              }
            } else {
              message = `${user}님이 '${workspace}' 워크스페이스의 '${taskName}' 데이터셋을 ${t(
                `${action}.label`,
              )}하였습니다.`;
            }
          } else if (action.toLowerCase().indexOf('data') !== -1) {
            if (action.toLowerCase().indexOf('upload') !== -1) {
              message = `${user} uploaded data in the '${taskName}' dataset of '${workspace}' workspace.`;
            } else {
              message = `${user} ${action.replace(
                'Data',
                '',
              )}d data in the '${taskName}' dataset of '${workspace}' workspace.`;
            }
          } else if (action.toLowerCase().indexOf('labeling') !== -1) {
            message = `${user} ${action.replace(
              '_labeling',
              '-labeled',
            )} a '${taskName}' dataset in the '${workspace}' workspace.`;
          } else if (action.toLowerCase().indexOf('download') !== -1) {
            if (details) {
              message = `${user} downloaded data of the '${taskName}' dataset in the '${workspace}' workspace.`;
            } else {
              message = `${user} downloaded a '${taskName}' dataset in the '${workspace}' workspace.`;
            }
          } else {
            message = `${user} ${action}d a '${taskName}' dataset in the '${workspace}' workspace.`;
          }
          break;
        default:
          // 배포
          if (lan === 'ko') {
            message = `${user}님이 '${workspace}' 워크스페이스에서 ${taskName} ${t(
              `${task}.label`,
            )}를 ${t(`${action}.label`)}하였습니다.`;
          } else {
            message = `${user} ${action}d a '${taskName}' ${task} in the '${workspace}' workspace.`;
          }
      }
    } else {
      // 사용자
      switch (task) {
        case 'workspace':
          if (lan === 'ko') {
            message = `관리자가 워크스페이스를 ${t(
              `${action}.label`,
            )}하였습니다.`;
          } else {
            message = `Admin ${action}d a workspace.`;
          }
          break;
        case 'training':
          if (lan === 'ko') {
            message = `${user}님이 '${taskName.replace(
              'advanced',
              'custom',
            )}' 학습을 ${t(`${action}.label`)}하였습니다.`;
          } else {
            message = `${user} ${action}d a '${taskName.replace(
              'advanced',
              'custom',
            )}' training.`;
          }
          break;
        case 'job':
        case 'hyperparamsearch':
          if (lan === 'ko') {
            message = `${user}님이 '${taskName
              .split('/')[0]
              .trim()}' 학습에서 '${taskName.split('/')[1].trim()}' ${t(
              `${task}.label`,
            )}을 ${t(`${action}.label`)}하였습니다.`;
          } else {
            message = `${user} ${
              action === 'add' ? 'added' : `${action}d`
            } a '${taskName.split('/')[1].trim()}' ${t(
              `${task}.label`,
            )} in the '${taskName.split('/')[0].trim()}' training.`;
          }
          break;
        case 'image':
          if (lan === 'ko') {
            if (action === 'create') {
              message = `${user}님이 ${
                taskName !== '-' ? taskName.split('/')[0].trim() : taskName
              } 방식으로 '${
                taskName !== '-' ? taskName.split('/')[1].trim() : taskName
              }' 도커 이미지를 업로드하였습니다.`;
            } else {
              message = `${user}님이 '${taskName}' 도커 이미지를 ${t(
                `${action}.label`,
              )}하였습니다.`;
            }
          } else if (action === 'create') {
            message = `${user} uploaded a '${
              taskName !== '-' ? taskName.split('/')[1].trim() : taskName
            }' Docker Image with a ${
              taskName !== '-' ? taskName.split('/')[0].trim() : taskName
            } type.`;
          } else {
            message = `${user} ${action}d a '${taskName}' Docker Image.`;
          }
          break;
        case 'dataset':
          if (lan === 'ko') {
            if (action.toLowerCase().indexOf('data') !== -1) {
              if (action.toLowerCase().indexOf('upload') !== -1) {
                message = `${user}님이 '${taskName}' 데이터셋에 데이터를 업로드하였습니다.`;
              } else {
                message = `${user}님이 '${taskName}' 데이터셋의 데이터를 ${t(
                  `${action.replace('Data', '')}.label`,
                )}하였습니다.`;
              }
            } else if (action.toLowerCase().indexOf('download') !== -1) {
              if (details) {
                message = `${user}님이 '${taskName}' 데이터셋의 데이터를 다운로드하였습니다.`;
              } else {
                message = `${user}님이 '${taskName}' 데이터셋을 다운로드하였습니다.`;
              }
            } else {
              message = `${user}님이 '${taskName}' 데이터셋을 ${t(
                `${action}.label`,
              )}하였습니다.`;
            }
          } else if (action.toLowerCase().indexOf('data') !== -1) {
            if (action.toLowerCase().indexOf('upload') !== -1) {
              message = `${user} uploaded data in the '${taskName}' dataset.`;
            } else {
              message = `${user} ${action.replace(
                'Data',
                '',
              )}d data in the '${taskName}' dataset.`;
            }
          } else if (action.toLowerCase().indexOf('labeling') !== -1) {
            message = `${user} ${action.replace(
              '_labeling',
              '-labeled',
            )} a '${taskName}' dataset.`;
          } else if (action.toLowerCase().indexOf('download') !== -1) {
            if (details) {
              message = `${user} downloaded data of the '${taskName}' dataset.`;
            } else {
              message = `${user} downloaded a '${taskName}' dataset.`;
            }
          } else {
            message = `${user} ${action}d a '${taskName}' dataset.`;
          }
          break;
        case 'pipeline':
          if (lan === 'ko') {
            message = `${user}님이 '${taskName}' ${t(`${task}.label`)}을 ${t(
              `${action}.label`,
            )}하였습니다.`;
          } else {
            message = `${user} ${action}d  a '${taskName}' ${task}.`;
          }
          break;
        default:
          // 배포
          if (lan === 'ko') {
            message = `${user}님이 '${taskName}' ${t(`${task}.label`)}를 ${t(
              `${action}.label`,
            )}하였습니다.`;
          } else {
            message = `${user} ${action}d  a '${taskName}' ${task}.`;
          }
      }
    }

    return message;
  }

  return (
    <div className={cx('history-row')}>
      <div className={cx('message-container')}>
        <div className={cx('circle', action)}></div>
        <div className={cx('message')}>{makeMessage()}</div>
      </div>
      <div className={cx('datetime', type)}>{convertLocalTime(datetime)}</div>
    </div>
  );
};

export default History;
