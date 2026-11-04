// library
import { JsonEditor as JsonView } from 'jsoneditor-react';

// i18n
import { useTranslation } from 'react-i18next';

// Icons
import Download from '@src/static/images/icon/00-ic-data-download-blue.svg';
import ErrorIcon from '@src/static/images/icon/icon-error-c-red.svg';

// CSS Module
import style from './List.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

function ListInfo({ data, clickedTemplateLists }) {
  const { t } = useTranslation();
  const downloadJSON = (exportData) => {
    const jsonString = `data:text/json;chatset=utf-8,${encodeURIComponent(
      JSON.stringify(exportData.deployment_template),
    )}`;
    const link = document.createElement('a');
    link.href = jsonString;
    link.download = `${exportData.name}.json`;

    link.click();
  };
  return (
    <div
      className={cx(
        clickedTemplateLists.length > 0 &&
          clickedTemplateLists.includes(data.id) &&
          'template-description',
        clickedTemplateLists.id === data.id && 'template-description',
        'inactive-description',
      )}
    >
      {data.deployment_template_type === 'usertrained' && (
        <div className={cx('detail-container')}>
          {data.description && (
            <p className={cx('description')}>{data.description}</p>
          )}
          <div>
            <p className={cx('title')}>{t('template.training.label')}</p>
            <p className={cx('contents')}>
              {data.deployment_template.training_name
                ? data.deployment_template.training_name
                : '-'}
            </p>
          </div>
          {data.item_deleted.includes('training') && (
            <span className={cx('error')}>
              <img src={ErrorIcon} alt='deleted' />
              {t('trainingDeleted.message')}
            </span>
          )}
          <div>
            <p className={cx('title')}>{t('template.tool.label')}</p>
            <div className={cx('contents')}>
              {data.deployment_template.training_type && (
                <span>
                  {data.deployment_template.training_type.toUpperCase()}
                </span>
              )}
              {data.deployment_template.training_type === 'hps' ? (
                <>
                  <div className={cx('model')}>/</div>
                  {data.deployment_template.hps_name && (
                    <span> {data.deployment_template.hps_name}</span>
                  )}
                  <div className={cx('model')}>/</div>
                  {data.deployment_template.hps_group_index && (
                    <span>
                      {data.deployment_template.training_type}
                      {data.deployment_template.hps_group_index}
                    </span>
                  )}
                </>
              ) : (
                <>
                  <div className={cx('model')}>/</div>
                  {data.deployment_template.job_name && (
                    <span>{data.deployment_template.job_name}</span>
                  )}
                  <div className={cx('model')}>/</div>
                  {data.deployment_template.job_id && (
                    <span> {data.deployment_template.job_id}</span>
                  )}
                </>
              )}
            </div>
          </div>
          {data.item_deleted.includes('job') && (
            <span className={cx('error')}>
              <img src={ErrorIcon} alt='deleted' />
              {t('jobDeleted.message')}
            </span>
          )}
          {data.item_deleted.includes('hps') && (
            <span className={cx('error')}>
              <img src={ErrorIcon} alt='deleted' />
              {t('hpsDeleted.message')}
            </span>
          )}
          {data.deployment_template.training_type === 'hps' && (
            <div>
              <p className={cx('title')}>{t('template.hpsNo.label')}</p>
              <p className={cx('contents')}>
                {data.deployment_template.hps_number}
              </p>
            </div>
          )}
          <div>
            <p className={cx('title')}>{t('template.model.label')}</p>
            <p className={cx('contents', 'model-ckpt')}>
              <span>
                {data.deployment_template?.built_in_model_name
                  ? data.deployment_template.built_in_model_name
                  : '-'}
              </span>
              {data.deployment_template?.checkpoint && (
                <span>{data.deployment_template.checkpoint}</span>
              )}
            </p>
          </div>
        </div>
      )}
      {data.deployment_template_type === 'custom' && (
        <div className={cx('detail-container')}>
          <div>
            <p className={cx('title')}>{t('template.training.label')}</p>
            <p className={cx('contents')}>
              {data.deployment_template.training_name
                ? data.deployment_template.training_name
                : '-'}
            </p>
          </div>
          {data.item_deleted.includes('training') && (
            <span className={cx('error')}>
              <img src={ErrorIcon} alt='deleted' />
              {t('trainingDeleted.message')}
            </span>
          )}
          <div>
            <p className={cx('title')}>{t('template.runCommand.label')}</p>
            <p className={cx('contents')}>
              {data.deployment_template.command?.binary &&
                data.deployment_template.command.binary}{' '}
              {data.deployment_template.command?.script &&
                data.deployment_template.command.script}{' '}
              {data.deployment_template.command?.arguments &&
                data.deployment_template.command.arguments}
            </p>
          </div>
          <div>
            <p className={cx('title')}>{t('template.envParam.label')}</p>
            <div className={cx('env-contents', 'contents')}>
              {data.deployment_template?.environments?.map((data, idx) => {
                return (
                  <span
                    key={`${data.value}-${idx}`}
                    className={cx('key-value')}
                  >
                    {data.name ? `--${data.name}` : '-'}
                    <span className={cx('value')}>{data.value}</span>
                  </span>
                );
              })}
            </div>
          </div>
        </div>
      )}
      {data.deployment_template_type === 'pretrained' && (
        <div className={cx('detail-container')}>
          <div>
            <p className={cx('title')}>{t('template.model.label')}</p>
            <p className={cx('contents')}>
              {data.deployment_template.built_in_model_name
                ? data.deployment_template.built_in_model_name
                : t('deleteDeploymentModelInfo.label')}
            </p>
          </div>
          {data.item_deleted.includes('built_in_model') && (
            <span className={cx('error')}>
              <img src={ErrorIcon} alt='deleted' />
              {t('builtInModelDeleted.message')}
            </span>
          )}
        </div>
      )}
      {data.deployment_template_type === 'sandbox' && (
        <div className={cx('detail-container')}>
          <div>
            <div className={cx('json-title-box')}>
              <p className={cx('title')}>JSON</p>
              <div className={cx('button')} onClick={() => downloadJSON(data)}>
                <label className={cx('label')}>{t('download.label')}</label>
                <img className={cx('icon')} src={Download} alt='download' />
              </div>
            </div>
          </div>
          <div className={cx('jsonType-contents')}>
            <JsonView
              value={data.deployment_template}
              mode='view'
              navigationBar={false}
              statusBar={false}
              search={false}
            />
          </div>
        </div>
      )}
    </div>
  );
}
export default ListInfo;
