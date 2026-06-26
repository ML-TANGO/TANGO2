import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import TestComponent from '@src/components/Modal/PlaygroundTestModal/TestComponent';
import { getDetailPlayground } from '@src/apis/llm/playground';
import { startPath } from '@src/store/modules/breadCrumb';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './InferenceDetail.module.scss';

const cx = classNames.bind(style);

// 추론 상세(Inference detail, D6 v3 Tier-1) — 배포 config 없는 lean consume 화면.
//   배포(provision)는 "배포" 탭. 여기선 "띄운 배포에 질의"만.
//   기존 PlaygroundTestModal 의 TestComponent(PromptCom/DatasetCom/ExternalTestCom)를
//   모달 셸 없이 인라인 재사용 — 실 백엔드(postPlaygroundTestChat) 그대로.
//   redux 미오염: TestComponent 는 prop 컴포넌트, 하위는 auth.userName 만 읽음 →
//   getDetailPlayground 로 name/training_type 만 로컬 fetch (전체 payload dispatch X).
//   실시간 질문 ↔ 데이터셋 일괄 모드 토글. 외부 모델은 ExternalTestCom 자동.
//   (이중모델 D2 + 정량 메트릭 = Tier-2, SP-7/SP-5 의존.)
const InferenceDetail = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId, did: playgroundId } = match.params;

  const [info, setInfo] = useState(null); // { name, owner }
  const [trainingType, setTrainingType] = useState('');
  const [loading, setLoading] = useState(true);
  // 모드: 'realtime'(실시간 질문) | 'dataset'(데이터셋 일괄)
  // 기존 모달 규약 매핑 → integratedTestValue: true=DatasetCom / false=PromptCom
  const [mode, setMode] = useState('realtime');

  const isExternal = trainingType === 'external';
  const integratedTestValue = mode === 'dataset';

  const fetchDetail = useCallback(async () => {
    const { result, status, error, message } = await getDetailPlayground(
      playgroundId,
    );
    if (status === STATUS_SUCCESS) {
      setInfo({
        name: result?.info?.name ?? '-',
        owner: result?.info?.owner ?? '-',
      });
      setTrainingType(result?.model?.training_type ?? '');
      setLoading(false);
      return;
    }
    errorToastMessage(error, message);
    setLoading(false);
  }, [playgroundId]);

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Inference' } }]));
    fetchDetail();
  }, [dispatch, fetchDetail]);

  const goBack = () => {
    history.push(`/user/workspace/${workspaceId}/inference`);
  };

  return (
    <div className={cx('inference-detail')}>
      <div className={cx('header')}>
        <button type='button' className={cx('back-btn')} onClick={goBack}>
          ← {t('inference.backToList')}
        </button>
        <div className={cx('header-info')}>
          <h1 className={cx('title')}>{info?.name ?? ''}</h1>
          {info?.owner && info.owner !== '-' && (
            <span className={cx('owner')}>{info.owner}</span>
          )}
        </div>
      </div>

      {!loading && !info && (
        <p className={cx('not-found')}>{t('inference.detail.notFound')}</p>
      )}

      {!loading && info && (
        <>
          {/* 모드 토글 — 외부 모델(ExternalTestCom)은 단일 모드라 숨김 */}
          {!isExternal && (
            <div className={cx('mode-tabs')}>
              <button
                type='button'
                className={cx('tab', mode === 'realtime' && 'active')}
                onClick={() => setMode('realtime')}
              >
                {t('inference.mode.realtime')}
              </button>
              <button
                type='button'
                className={cx('tab', mode === 'dataset' && 'active')}
                onClick={() => setMode('dataset')}
              >
                {t('inference.mode.dataset')}
              </button>
            </div>
          )}
          <div className={cx('test-panel')}>
            <TestComponent
              integratedTestValue={integratedTestValue}
              playgroundId={playgroundId}
              isExternal={isExternal}
            />
          </div>
        </>
      )}
    </div>
  );
};

export default InferenceDetail;
