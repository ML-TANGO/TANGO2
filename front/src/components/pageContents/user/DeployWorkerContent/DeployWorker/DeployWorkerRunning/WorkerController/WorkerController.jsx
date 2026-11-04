import { Fragment } from 'react';

import { Button } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from './WorkerController.module.scss';

const cx = classNames.bind(style);

function WorkerController({
  workerSettingInfo,
  onEdit,
  addWorker,
  addLoading,
  workerSettingValue,
  t,
}) {
  const isObject = (content, value) => {
    if (typeof content === 'object') {
      if (value === 'gpu_model') {
        // value가 gpu_model일 경우 { key: value[] } 타입
        return Object.keys(content).map((gpuModel, idx) => (
          <li key={idx}>
            {gpuModel}
            {content[gpuModel].map((name, i) => (
              <Fragment key={i}>
                <br />
                <label> - {name}</label>
              </Fragment>
            ))}
          </li>
        ));
      }
      return Object.keys(content).map((name, idx) => (
        <li key={idx}>
          {name} : {content[name]}
        </li>
      ));
    }
    return <li>{content}</li>;
  };

  const getProjectName = () => {
    if (!workerSettingValue?.is_new_model)
      return workerSettingValue?.project_name;

    return workerSettingValue?.model_category;
  };

  const getTrainingName = () => {
    if (!workerSettingValue?.is_new_model)
      return workerSettingValue?.training_name;

    if (workerSettingValue?.model_type === 'huggingface')
      return workerSettingValue?.huggingface_model_id;

    return workerSettingValue?.model_name;
  };

  return (
    <div className={cx('new-worker-setting')}>
      <div className={cx('left-side')}>
        <label className={cx('title')}>{t('workerInfo.label')}</label>
        <div
          className={cx(
            'btn-wrap',
            workerSettingValue?.model_type !== 'custom' && 'no-custom',
          )}
        >
          {workerSettingValue?.model_type === 'custom' && (
            <button className={cx('deploy-btn', 'setting')} onClick={onEdit}>
              <span className={cx('text')}>{t('settingWorker.label')}</span>
            </button>
          )}

          <button
            className={cx('deploy-btn')}
            onClick={() => {
              if (!addLoading) {
                addWorker();
              }
            }}
          >
            <img
              src='/images/icon/00-ic-blue-plus.svg'
              alt='plus'
              width={20}
              height={20}
            />
            <span className={cx('text')}>
              {t('deploymentWorker.addWorker')}
            </span>
          </button>
        </div>
      </div>
      <div className={cx('middle-line')}></div>

      <ul className={cx('setting-wrap')}>
        {workerSettingInfo.map((info, idx) => {
          if (idx === 0) {
            return (
              <li key={idx}>
                <div className={cx('label')}>{t(info.label)}</div>
                <div className={cx('content')}>
                  {info.content ? (
                    <>
                      {info.content !== 'custom' && (
                        <ul className={cx('model-type')}>
                          <div className={cx('model-title')}>
                            {info.content === 'built-in'
                              ? 'Jonathan Intelligence'
                              : 'Hugging Face'}
                          </div>
                          <div className={cx('border')} />

                          <span className={cx('model-type-value')}>
                            <img
                              src={`/src/static/images/icon/00-ic-llm-group.svg`}
                              width={16}
                              height={16}
                              alt='icon'
                            />
                            {getProjectName()}
                          </span>
                          <span className={cx('model-type-value')}>
                            <img
                              src={`/src/static/images/icon/ic-job-training.svg`}
                              width={16}
                              height={16}
                              alt='icon'
                            />
                            {getTrainingName()}
                          </span>
                        </ul>
                      )}

                      {info.content === 'custom' && (
                        <ul>{isObject(info.content, info.value ?? '')}</ul>
                      )}
                      {/* {info.content === 'huggingface' && (
                        <ul>{isObject(info.content, info.value ?? '')}</ul>
                      )} */}
                    </>
                  ) : (
                    '-'
                  )}
                </div>
              </li>
            );
          } else {
            return (
              <li key={idx}>
                <div className={cx('label')}>{t(info.label)}</div>
                <div className={cx('content')}>
                  {info.content ? (
                    <ul>{isObject(info.content, info.value ?? '')}</ul>
                  ) : (
                    '-'
                  )}
                </div>
              </li>
            );
          }
        })}
      </ul>
    </div>
  );
}

export default WorkerController;
