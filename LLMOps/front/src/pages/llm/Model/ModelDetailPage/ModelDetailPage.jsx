import { memo, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Redirect,
  Route,
  Switch,
  useHistory,
  useLocation,
  useParams,
  useRouteMatch,
} from 'react-router-dom';

import { callApi, STATUS_SUCCESS } from '@src/network';

import CommitList from './CommitList';
import ModelCommitListItem from './CommitList/ModelCommitListItem';
import Evaluate from './Evaluate';
import ExternalCheckpointList from './ExternalCheckpointList';
import FineTuning from './FineTuning';
import ModelInfo from './ModelInfo';
import Quantize from './Quantize';

import classNames from 'classnames/bind';
import style from './ModelDetailPage.module.scss';

const cx = classNames.bind(style);

const ModelDetailPage = memo(function ModelDetailPage({
  trackingEvent,
  ...rest
}) {
  const test = useParams();

  const { id: workspaceId, mId: modelId } = useParams();

  const history = useHistory();

  const location = useLocation(); // 현재 URL 확인
  const match = useRouteMatch(`${location.pathname}/:cId`); // cId 매칭

  // pathname에서 cId 값 추출
  const pathSegments = location.pathname.split('/');
  const cId = pathSegments[pathSegments.length - 1]; // 마지막 부분이 cId
  const isCommitDetailPage =
    location.pathname.includes('commit-list') && !isNaN(cId);

  const backLabel = isCommitDetailPage ? 'commitList.label' : 'model.label';

  const { path, url } = useRouteMatch();

  const { t } = useTranslation();

  // 모든 모델 (internal + SDS/external) 의 default 진입 탭은 'fine-tuning' 으로
  // 통일. SDS/external 모델은 FineTuning.jsx 안에서 SDSFineTuningView 로
  // 자동 분기 — 사용자 운영 UX 가 internal 과 같다.
  const defaultSubPath = 'fine-tuning';

  // SDS/external 모델(training_type='external') 여부 — 여기서만 '커밋 목록' 탭을
  // '체크포인트' 탭으로 교체한다. lightweight summary 엔드포인트가 이 판단 전용
  // (BE get_model_summary docstring 참고). 미해결(null)/internal 은 기존 동작 유지.
  const [isExternalModel, setIsExternalModel] = useState(false);
  useEffect(() => {
    let alive = true;
    // 모델 전환 시 이전 값 잔존 방지(external→internal 네비에서 '체크포인트' nav 가 남는 문제).
    // 라우트는 항상 마운트되므로 이 값은 nav 표기 전용 — 미해결/실패 시 internal 기본으로 폴백.
    setIsExternalModel(false);
    (async () => {
      const res = await callApi({
        url: `models/fine-tuning/summary?model_id=${modelId}`,
        method: 'get',
      });
      if (alive && res.status === STATUS_SUCCESS)
        setIsExternalModel(
          (res.result?.training_type ?? 'internal') === 'external',
        );
    })();
    return () => {
      alive = false;
    };
  }, [modelId]);

  /**
   * 뒤로가기
   */
  const goBack = (isCommit) => {
    trackingEvent({
      category: 'LLM Model Page',
      action: 'Move To Prev Page',
    });
    // history.goBack();

    if (isCommit) {
      history.push(
        `/user/workspace/${workspaceId}/model/${modelId}/commit-list`,
      );
    } else {
      history.push(`/user/workspace/${workspaceId}/model`);
    }
  };

  const navList = useMemo(() => {
    // external 은 '커밋 목록' 자리를 '체크포인트' 로 교체(라벨은 목업 문구 하드코딩).
    const commitOrCheckpoint = isExternalModel
      ? { label: '체크포인트', path: `${url}/checkpoints` }
      : { label: 'commitList.label', path: `${url}/commit-list` };
    return [
      { label: 'information.label', path: `${url}/info` },
      { label: 'fineTuning.label', path: `${url}/fine-tuning` },
      commitOrCheckpoint,
      { label: 'evaluate.label', path: `${url}/evaluate` },
      { label: 'quantize.label', path: `${url}/quantize` },
    ];
  }, [url, isExternalModel]);

  const filteredRest = useMemo(() => {
    const { tReady, dispatch, trackingEvent, ...remainingProps } = rest;
    return remainingProps;
  }, [rest]);

  const props = { workspaceId, modelId, t, cId };

  return (
    <div id='ModelDetailPage' className={cx('container')}>
      <div
        className={cx('back-to-list')}
        onClick={() => goBack(isCommitDetailPage)}
      >
        <img
          className={cx('back-btn-image')}
          src='/images/icon/00-ic-basic-arrow-02-left.svg'
          alt='<'
        />
        <span className={cx('back-btn-label')}>{t(backLabel)}</span>
      </div>
      <div className={cx('content')}>
        <Switch>
          <Route exact path={path}>
            <Redirect to={`${url}/${defaultSubPath}`} />
          </Route>
          <Route path={`${path}/info`}>
            <ModelInfo navList={navList} {...filteredRest} data={props} />
          </Route>
          <Route path={`${path}/fine-tuning`}>
            <FineTuning navList={navList} {...filteredRest} data={props} />
          </Route>
          <Route path={`${path}/evaluate`}>
            <Evaluate navList={navList} {...filteredRest} data={props} />
          </Route>
          <Route path={`${path}/quantize`}>
            <Quantize navList={navList} {...filteredRest} data={props} />
          </Route>
          {/* 라우트는 모델 타입과 무관하게 항상 마운트 — '커밋 탭 제거'는 nav(navList)에서만.
              external 은 nav 에 '체크포인트'만, internal 은 '커밋 목록'만 노출한다. URL 이 직접
              열려도(딥링크·새로고침·모델 간 네비 전환) 대응 라우트가 항상 존재해 Switch 가 null 을
              렌더(빈 화면)하지 않는다. checkpoints 는 external 전용 뷰지만 BE 가 training_type!=
              external 이면 빈 목록을 반환하므로 internal 로 열려도 안전. (route ≠ nav) */}
          <Route path={`${path}/checkpoints`}>
            <ExternalCheckpointList
              navList={navList}
              {...filteredRest}
              data={props}
            />
          </Route>
          <Route path={`${path}/commit-list/:cId`}>
            <ModelCommitListItem
              navList={navList}
              {...filteredRest}
              data={props}
            />
          </Route>
          <Route path={`${path}/commit-list`}>
            <CommitList navList={navList} {...filteredRest} data={props} />
          </Route>
        </Switch>
      </div>
    </div>
  );
});

export default ModelDetailPage;
