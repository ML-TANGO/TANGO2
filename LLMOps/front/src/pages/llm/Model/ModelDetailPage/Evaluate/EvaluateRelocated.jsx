import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { useHistory } from 'react-router-dom';

import { ButtonV2 } from '@jonathan/ui-react';

import SimpleNav from '../SimpleNav';

import classNames from 'classnames/bind';
import style from './EvaluateRelocated.module.scss';

const cx = classNames.bind(style);

/**
 * §14.12 ③ — 모델탭 'Evaluate'(SP-5 자체메트릭)는 '평가(Evaluation)' 탭으로 이전.
 * 자체메트릭(BLEU/ROUGE/perplexity)은 벤치마크 평가(17메트릭, BLEU/ROUGE 포함)가 대체하고,
 * 과거 self-metric 런은 평가 탭의 모델 이력 비교표에 계속 노출된다(공용 eval_result).
 * 기존 Evaluate.jsx(+EvaluateModal)는 보존 — index.js 가 이 배너를 export(언마운트). 추후 제거.
 */
const EvaluateRelocated = memo(function EvaluateRelocated({ navList, data }) {
  const { t } = useTranslation();
  const history = useHistory();
  const workspaceId = data?.workspaceId;

  return (
    <div className={cx('relocated-tab')}>
      <SimpleNav navList={navList} />
      <div className={cx('banner')}>
        <div className={cx('icon')}>📊</div>
        <div className={cx('title')}>{t('evaluate.relocated.title')}</div>
        <div className={cx('desc')}>{t('evaluate.relocated.desc')}</div>
        <ButtonV2
          colorType='blue'
          label={t('evaluate.relocated.cta')}
          onClick={() =>
            workspaceId &&
            history.push(`/user/workspace/${workspaceId}/evaluation`)
          }
        />
      </div>
    </div>
  );
});

export default EvaluateRelocated;
