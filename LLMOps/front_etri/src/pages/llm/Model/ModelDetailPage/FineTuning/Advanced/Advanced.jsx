// Components
import { ButtonV2 } from '@tango/ui-react';

import InfoIcon from '@src/static/images/icon/00-gray-tooltip-icon.svg';
import copyIcon from '@src/static/images/icon/00-ic-basic-copy-o.svg';
import { useRef, useState } from 'react';

import { toast } from '@src/components/Toast';

import TooltipPortal from '@src/hooks/TooltipPortal';

// Network
import { network } from '@src/network';
import { copyToClipboard, errorToastMessage } from '@src/utils';

import DataList from '../DataList';

import classNames from 'classnames/bind';
import style from './Advanced.module.scss';

const cx = classNames.bind(style);

const unapplicableParams = [
  'fp16',
  'weight_decay',
  'overwrite_output_dir',
  'output_dir',
  'logging_dir',
  'remove_unused_columns',
  'save_total_limit',
  'save_strategy',
  'logging_strategy',
  'evaluation_strategy',
  'eval_steps',
  'logging_stepst',
  'save_steps',
  'prediction_loss_only',
];

function TooltipContents({ t }) {
  return (
    <div className={cx('tooltip-box')}>
      <div className={cx('tooltip-title')}>
        {t('finetuning.UnapplicableParam.label')}
        {/* <div className={cx('border')}></div> */}
      </div>
      <div className={cx('params')}>
        {unapplicableParams.map((p) => {
          return <div className={cx('param')}>{p}</div>;
        })}
      </div>
    </div>
  );
}

function Advanced({
  list,
  gitLink,
  onClick,
  disabled = false,
  onClickDelete,
  git,
  t,
}) {
  const [isShowTooltip, setIsShowTooltip] = useState(false);

  const tooltipRef = useRef(null);

  // 링크 복사
  const copyLink = () => {
    copyToClipboard(git ?? '');
    toast.success(t('copyToClipboard.success.message'));
  };

  // * 다운로드
  const onClickDownload = async () => {
    const { data, status } = await network.callApiWithPromise({
      url: `models/option/download/default-configuration`,
      method: 'GET',
    });

    if (status === 200) {
      const url = window.URL.createObjectURL(new Blob([data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = `[Finetuning]Default-configuration.log`;
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } else {
      errorToastMessage();
    }
  };

  return (
    <div className={cx('container', disabled && 'disabled')}>
      <div className={cx('title')}>Configuration{t('fileUpload.label')}</div>
      <div className={cx('message')}>{t('fileGitLink.message')}</div>
      <div className={cx('down-box')}>
        <div className={cx('sub-title')}>
          {t('finetuning.detailDescUrl.label')}
        </div>
        <div className={cx('link')}>
          <div className={cx('link-text')}>{git ?? '-'}</div>
          <img
            src={copyIcon}
            alt='copy icon'
            onClick={() => {
              if (disabled) return;
              copyLink();
            }}
            style={{ cursor: 'pointer' }}
          />
        </div>
      </div>
      <div className={cx('down-box')}>
        <div className={cx('sub-title')}>
          {t('finetuning.exampleConfigurationFile.label')}
        </div>
        <div className={cx('link')}>
          <div className={cx('link-text')}>config.json</div>
          <img
            src={'/images/icon/ic-download-config.svg'}
            alt='copy icon'
            onClick={() => {
              if (disabled) return;
              onClickDownload();
            }}
            style={{ cursor: 'pointer' }}
          />
        </div>
        <span>{t('finetuning.advancedParamsNotice.message')}</span>
        <div className={cx('param-info')}>
          {t('finetuning.checkUnapplicableParam.label')}
          <img
            ref={tooltipRef}
            src={InfoIcon}
            alt='tooltip-icon'
            onMouseEnter={() => setIsShowTooltip(true)}
            onMouseLeave={() => setIsShowTooltip(false)}
          />

          <TooltipPortal
            direction='topRight'
            targetRef={tooltipRef}
            isShowTooltip={isShowTooltip}
          >
            <div className={cx('tooltip-box')}>
              <div className={cx('tooltip-title')}>
                {t('finetuning.UnapplicableParam.label')}
                {/* <div className={cx('border')}></div> */}
              </div>
              <div className={cx('params')}>
                {unapplicableParams.map((p) => {
                  return <div className={cx('param')}>{p}</div>;
                })}
              </div>
            </div>
          </TooltipPortal>
        </div>
      </div>
      {list?.length === 0 && (
        <ButtonV2 // 추가
          type='outline'
          size='l'
          label={`Configuration ${t('file.select.label')}`}
          disabled={disabled}
          onClick={onClick}
          style={{ width: '100%' }}
        />
      )}
      {list?.length > 0 && (
        <DataList
          list={list}
          disable={disabled}
          onClickDelete={onClickDelete}
          t={t}
        />
      )}
    </div>
  );
}

export default Advanced;
