// Components
import { Badge } from '@jonathan/ui-react';

// CSS module
import style from './Card.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const Card = ({
  id,
  isTrained,
  title,
  name,
  label,
  desc,
  enableCpu,
  enableGpu,
  multiGpuMode,
  disabled,
  model,
  modelOptions,
  selectBuiltInModelHandler,
  thumbnailImageInfo,
  thumbnailList,
  readOnly,
  idx,
}) => {
  return (
    <li
      className={cx(
        'card',
        model && model.id === id && 'selected',
        disabled && 'disabled',
        readOnly && 'read-only',
      )}
      onClick={() => {
        if (!disabled && !readOnly) {
          selectBuiltInModelHandler(modelOptions[idx]);
        }
      }}
    >
      {!isTrained && (
        <div className={cx('image')}>
          <img
            className={cx(thumbnailImageInfo ? 'thumbnail' : 'default')}
            src={
              thumbnailImageInfo
                ? thumbnailList && thumbnailList[id]
                : '/images/icon/ic-built-in-blue.svg'
            }
            alt='built-in'
          />
        </div>
      )}
      <div className={cx('text-box')}>
        {isTrained ? (
          title
        ) : (
          <>
            <div className={cx('title')}>
              <div className={cx('model-name')}>{name}</div>
            </div>
          </>
        )}
        {isTrained ? (
          <div className={cx('desc')}>
            <img
              className={cx('icon')}
              src={
                thumbnailImageInfo
                  ? thumbnailList[id]
                  : '/images/icon/ic-built-in-blue.svg'
              }
              alt='built-in'
            />
            <span className={cx('model')}>{name}</span>
            <span className={cx('badge')}>
              {enableCpu ? (
                <Badge
                  type='yellow'
                  label='CPU'
                  customStyle={{
                    marginRight: '4px',
                  }}
                />
              ) : (
                ''
              )}
              {enableGpu ? (
                <Badge
                  type='green'
                  label='GPU'
                  customStyle={{
                    marginRight: '4px',
                  }}
                />
              ) : (
                ''
              )}
              {multiGpuMode ? <Badge type='blue' label='Multi-GPU' /> : ''}
            </span>
          </div>
        ) : (
          <div className={cx('desc')}>{desc}</div>
        )}
      </div>
      {!isTrained && (
        <div className={cx('badge')}>
          {enableCpu || enableGpu || multiGpuMode ? (
            <>
              <Badge
                type={enableCpu ? 'yellow' : 'disabled'}
                title={enableCpu ? 'Multi GPU' : ''}
                label='CPU'
                customStyle={{
                  marginLeft: '4px',
                  opacity: enableCpu ? '1' : '0.2',
                }}
              />
              <Badge
                type={enableGpu ? 'green' : 'disabled'}
                title={enableGpu ? 'Multi GPU' : ''}
                label='GPU'
                customStyle={{
                  marginLeft: '4px',
                  opacity: enableGpu ? '1' : '0.2',
                }}
              />
              <Badge
                type={multiGpuMode ? 'blue' : 'disabled'}
                title={multiGpuMode ? 'Multi GPU' : ''}
                label='Multi'
                customStyle={{
                  marginLeft: '4px',
                  opacity: multiGpuMode ? '1' : '0.2',
                }}
              />
            </>
          ) : (
            ''
          )}
        </div>
      )}
    </li>
  );
};

export default Card;
