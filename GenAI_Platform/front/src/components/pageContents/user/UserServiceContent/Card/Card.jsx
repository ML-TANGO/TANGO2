// i18n
import { useTranslation } from 'react-i18next';

import { convertLocalTime } from '@src/datetimeUtils';

// Components
import Status from '@src/components/atoms/Status';

import JobStatus from '../../UserJobContent/JobList/JobStatus';
import SimulationStatus from './SimulationStatus';

// Utils
import { capitalizeFirstLetter } from '@src/utils';

import classNames from 'classnames/bind';
// CSS module
import style from './Card.module.scss';

const cx = classNames.bind(style);

const statusObj = {
  done: 'job.done',
  stop: 'job.pending',
  pending: 'job.pending',
  scheduling: 'job.pending',
  installing: 'job.installing',
  running: 'job.running',
  error: 'job.error',
};

const calReturnJobStatus = (status) => {
  if (!statusObj[status]) return 'none.label';
  return statusObj[status];
};

const calIcon = (type) => {
  if (type === 'Jonathan Intelligence')
    return '/src/static/images/icon/jonathan-intell.svg';
  if (type === 'Hugging Face')
    return '/src/static/images/icon/hugging-face.svg';
  return '/src/static/images/icon/00-ic-deploy-project.svg';
};

function Card({ data, openTest, wid }) {
  const { t } = useTranslation();
  const {
    status: { status },
    type,
    name,
    create_datetime: date,
    creator,
    description,
    built_in_model_name: modelName,
    input_type: inputType,
  } = data;

  const active = status === 'running' || status === 'active';

  const calCardType = (type) => {
    if (type === 'custom') return 'Custom';
    if (type === 'built-in') return 'Jonathan Intelligence';
    return 'Hugging Face';
  };

  const cardType = calCardType(type);
  const icon = calIcon(cardType);

  return (
    <div
      className={cx('card', status)}
      onClick={() => {
        sessionStorage.setItem(`services/${wid}_scroll_pos`, window.scrollY);
        if (status === 'running' || status === 'active') {
          openTest(data);
        }
      }}
    >
      <div className={cx('contents-box')}>
        <div className={cx('header')}>
          <div className={cx('type-status')}>
            <div className={cx('type')}>
              {/* {type !== 'example' && (
                <img
                  className={cx('type-icon')}
                  src={`/images/icon/00-ic-data-${type}-yellow.svg`}
                  alt={type}
                />
              )} */}
              <span
                className={cx('type-label', active && 'active', 'custom-text')}
              >
                <img
                  className={cx('icon', !active && 'gray')}
                  src={icon}
                  alt='Custom'
                />
                <span className={cx('cardType', active && 'blue')}>
                  {cardType}
                </span>
              </span>
            </div>
            <SimulationStatus status={active ? 'serviceRunning' : status} />
          </div>
          <div className={cx('creator')} title={creator}>
            {creator}
          </div>
          <div className={cx('service-name')} title={name}>
            {name}
          </div>
          <div className={cx('created-box')}>
            <span className={cx('created')}>{convertLocalTime(date)}</span>
          </div>
        </div>
        <div className={cx('body')}>
          <div className={cx('description-box')}>
            <div className={cx('description')} title={description}>
              {description
                ? description
                    .trim()
                    .split('\n')
                    .map((line, index) => {
                      return (
                        <span key={index}>
                          {line}
                          <br />
                        </span>
                      );
                    })
                : '-'}
            </div>
          </div>
          <ul className={cx('detail-info')}>
            {/* <li>
              <label className={cx('label')}>{t('modelName.label')}</label>
              <span className={cx('value')} title={modelName}>
                {modelName || '-'}
              </span>
            </li> */}
            <li>
              <label className={cx('label')}>{t('dataInputType.label')}</label>
              <span className={cx('value')} title={inputType}>
                {inputType ? inputType.split(',').join(', ') : '-'}
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default Card;
