/* eslint-disable react/no-danger */

import { withTranslation } from 'react-i18next';

import { getKoreaTime } from '@src/datetimeUtils';

import CustomTooltip from './CustomTooltip';

import classNames from 'classnames/bind';
// CSS module
import style from './LatestJob.module.scss';

import info from '@src/static/images/icon/00-ic-gray-info.svg';

const cx = classNames.bind(style);

const LatestJob = ({
  name,
  type,
  t,
  statusHps,
  statusJob,
  statusTool,
  statusDeployment,
  instance,
  workerList,
  toolList,
  job_list,
  order,
  scrollPosition,
}) => {
  const getToolCount = (tool) => {
    if (!toolList) return 0;

    return toolList.filter(({ type }) => type === tool).length;
  };

  const iconHeight = 70 * (order + 1) - scrollPosition;

  const vscodeCnt = getToolCount('vscode');
  const jupyterCnt = getToolCount('jupyter');
  const shellCnt = getToolCount('shell');

  const isInitialInstance =
    (type === 'project' || type === 'preprocessing') &&
    !instance.gpu_name &&
    !instance.cpu_allocate &&
    !instance.ram_allocate;

  const toolListContent = (tool) => {
    return toolList
      .filter(({ type }) => type === tool)
      .map(
        (
          {
            start_datetime,
            gpu_name,
            gpu_allocate,
            cpu_allocate,
            ram_allocate,
            type,
          },
          index,
        ) => (
          <div className={cx('tool-info')} key={start_datetime}>
            <div className={cx('name')}>
              <img
                src={`/images/icon/00-ic-tool-${
                  type === 'shell' ? 'ssh' : type
                }.svg`}
                alt='deploy'
                width={20}
                height={20}
              />
              {/* 변경해주세요 */}
              <span>{type}</span>
            </div>
            <span className={cx('date')}>{getKoreaTime(start_datetime)}</span>
            <div className={cx('detail')}>
              <div className={cx('resource')}>
                <span>vGPU</span>
                <span>vCPU</span>
                <span>RAM</span>
              </div>
              <div className={cx('value')}>
                <span>
                  {gpu_name ? `${gpu_name} x ${gpu_allocate}EA` : '-'}
                </span>
                <span>{cpu_allocate ? `${cpu_allocate} Cores` : '-'}</span>
                <span>{ram_allocate ? `${ram_allocate} GB` : '-'}</span>
              </div>
            </div>
            {index !==
              toolList.filter(({ type }) => type === tool).length - 1 && (
              <div className={cx('line')}></div>
            )}
          </div>
        ),
      );
  };

  return (
    <div className={cx('history-row')}>
      {(type === 'project' || type === 'preprocessing') && (
        <div className={cx('training-container')}>
          <div className={cx('basic-info')}>
            <div className={cx('first')}>
              <div className={cx('badge', type)}>{t(type)}</div>
              <span className={cx('name')}>
                {name.length < 12 ? name : `${name.slice(0, 12)}... `}
              </span>
            </div>
            <div className={cx('second')}>
              {isInitialInstance && (
                <div className={cx('empty-instance')}>
                  {t('instance.reallocation.desc')}
                </div>
              )}
              {!isInitialInstance && (
                <>
                  <div className={cx('info')}>
                    <span className={cx('resource')}>vGPU</span>
                    <span className={cx('detail')}>
                      {instance.gpu_name
                        ? `${instance.gpu_name} x ${instance.gpu_allocate}EA`
                        : '-'}
                    </span>
                  </div>
                  <div className={cx('info')}>
                    <span className={cx('resource')}>vCPU</span>
                    <span className={cx('detail')}>
                      {instance.cpu_allocate
                        ? `${instance.cpu_allocate} Cores`
                        : '-'}
                    </span>
                  </div>
                  <div className={cx('info')}>
                    <span className={cx('resource')}>RAM</span>
                    <span className={cx('detail')}>
                      {instance.ram_allocate
                        ? `${instance.ram_allocate}GB`
                        : '-'}
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>
          <div className={cx('running-info', type)}>
            <div className={cx('tool-container')}>
              {vscodeCnt > 0 && (
                <div className={cx('tool')}>
                  <img src='/images/icon/00-ic-tool-vscode.svg' alt='vscode' />
                  <span className={cx('count')}>{vscodeCnt}개</span>
                  <CustomTooltip
                    icon={info}
                    position={iconHeight < 200 ? 'down' : 'up'}
                    contents={
                      <div className={cx('tool-list')}>
                        {toolListContent('vscode')}
                      </div>
                    }
                    iconStyle={{ transform: 'translateY(1px)' }}
                  />
                </div>
              )}
              {shellCnt > 0 && (
                <div className={cx('tool')}>
                  <img src='/images/icon/00-ic-tool-ssh.svg' alt='ssh' />
                  <span className={cx('count')}>{shellCnt}개</span>
                  <CustomTooltip
                    icon={info}
                    position={iconHeight < 200 ? 'down' : 'up'}
                    contents={
                      <div className={cx('tool-list')}>
                        {toolListContent('shell')}
                      </div>
                    }
                    iconStyle={{ transform: 'translateY(1px)' }}
                  />
                </div>
              )}
              {jupyterCnt > 0 && (
                <div className={cx('tool')}>
                  <img
                    src='/images/icon/00-ic-tool-jupyter.svg'
                    alt='jupyterCnt'
                  />
                  <span className={cx('count')}>{jupyterCnt}개</span>
                  <CustomTooltip
                    icon={info}
                    position={iconHeight < 200 ? 'down' : 'up'}
                    contents={
                      <div className={cx('tool-list')}>
                        {toolListContent('jupyter')}
                      </div>
                    }
                    iconStyle={{ transform: 'translateY(1px)' }}
                  />
                </div>
              )}
            </div>
            <div className={cx('job-container')}>
              <div className={cx('job')}>
                <img
                  src='/images/icon/00-ic-job-orange.svg'
                  alt='job'
                  width={20}
                  height={20}
                />
                <span>JOB</span>
              </div>
              <div className={cx('working')}>
                {type === 'project' &&
                  !!statusJob.running &&
                  !!job_list.length && (
                    <CustomTooltip
                      icon={info}
                      position={iconHeight < 200 ? 'down' : 'up'}
                      customStyle={{ left: '-280px' }}
                      contents={
                        <div className={cx('train-list')}>
                          {job_list.map(
                            (
                              {
                                job_id,
                                cpu_allocate,
                                gpu_allocate,
                                ram_allocate,
                                gpu_name,
                                start_datetime,
                              },
                              index,
                            ) => (
                              <div className={cx('train-info')} key={job_id}>
                                <div className={cx('name')}>
                                  <img
                                    src='/images/icon/00-ic-job-orange.svg'
                                    alt='train'
                                    width={20}
                                    height={20}
                                  />
                                  <span>JOB {job_id}</span>
                                </div>
                                <span className={cx('date')}>
                                  {getKoreaTime(start_datetime)}
                                </span>
                                <div className={cx('detail')}>
                                  <div className={cx('resource')}>
                                    <span>vGPU</span>
                                    <span>vCPU</span>
                                    <span>RAM</span>
                                  </div>
                                  <div className={cx('value')}>
                                    <span>
                                      {gpu_name
                                        ? `${gpu_name} x ${gpu_allocate ?? 0}EA`
                                        : '-'}
                                    </span>
                                    <span>
                                      {cpu_allocate
                                        ? `${cpu_allocate ?? 0} Cores`
                                        : '-'}
                                    </span>
                                    <span>
                                      {ram_allocate
                                        ? `${ram_allocate ?? 0} GB`
                                        : '-'}
                                    </span>
                                  </div>
                                </div>
                                {index !== job_list.length - 1 && (
                                  <div className={cx('line')}></div>
                                )}
                              </div>
                            ),
                          )}
                        </div>
                      }
                    />
                  )}

                <span>
                  {statusJob.running}
                  {t('eaOnly.label')}
                </span>
              </div>
              <div className={cx('pending')}>
                <span>{t('job.pending')}</span>
                <span>
                  {statusJob.pending}
                  {t('eaOnly.label')}
                </span>
              </div>
              {!!statusJob.pending && (
                <span className={cx('status')}>{t('deactivated.label')}</span>
              )}
            </div>
          </div>
        </div>
      )}
      {type === 'deployment' && (
        <div
          className={cx(
            'deployment-container',
            workerList.length === 0 && 'empty',
          )}
        >
          <div className={cx('left-side')}>
            <div className={cx('badge')}>{t(type)}</div>
            <span className={cx('name')}>{name}</span>
          </div>
          {statusDeployment ? (
            <div className={cx('right-side')}>
              <div className={cx('worker')}>
                <img
                  src='/images/icon/00-ic-blue-deploy.svg'
                  alt='deploy'
                  width={20}
                  height={20}
                />
                <span>Worker</span>
              </div>
              <div className={cx('info')}>
                {workerList.length > 0 && (
                  <CustomTooltip
                    icon={info}
                    position={iconHeight < 200 ? 'down' : 'up'}
                    customStyle={{ left: '-280px' }}
                    contents={
                      <div className={cx('worker-list')}>
                        {workerList.map(
                          (
                            {
                              worker_id,
                              start_datetime,
                              gpu_name,
                              gpu_allocate,
                              cpu_allocate,
                              ram_allocate,
                            },
                            index,
                          ) => (
                            <div className={cx('worker-info')} key={worker_id}>
                              <div className={cx('name')}>
                                <img
                                  src='/images/icon/00-ic-blue-deploy.svg'
                                  alt='deploy'
                                  width={20}
                                  height={20}
                                />
                                <span>워커 {worker_id}</span>
                              </div>
                              <span className={cx('date')}>
                                {getKoreaTime(start_datetime)}
                              </span>
                              <div className={cx('detail')}>
                                <div className={cx('resource')}>
                                  <span>vGPU</span>
                                  <span>vCPU</span>
                                  <span>RAM</span>
                                </div>
                                <div className={cx('value')}>
                                  <span>
                                    {gpu_name
                                      ? `${gpu_name} x ${gpu_allocate}EA`
                                      : '-'}
                                  </span>
                                  <span>
                                    {cpu_allocate
                                      ? `${cpu_allocate} Cores`
                                      : '-'}
                                  </span>
                                  <span>
                                    {ram_allocate ? `${ram_allocate} GB` : '-'}
                                  </span>
                                </div>
                              </div>
                              {index !== workerList.length - 1 && (
                                <div className={cx('line')}></div>
                              )}
                            </div>
                          ),
                        )}
                      </div>
                    }
                  />
                )}

                <span>{workerList.length}개</span>
              </div>
              {workerList.length > 0 && (
                <span className={cx('status')}>{t('deploymentRunning')}</span>
              )}
            </div>
          ) : (
            ''
          )}
        </div>
      )}
    </div>
  );
};

export default withTranslation()(LatestJob);
