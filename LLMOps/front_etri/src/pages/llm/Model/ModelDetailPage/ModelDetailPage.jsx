import { memo, useMemo } from 'react';
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

import CommitList from './CommitList';
import ModelCommitListItem from './CommitList/ModelCommitListItem';
import FineTuning from './FineTuning';
import ModelInfo from './ModelInfo';

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

  // 모든 모델 (internal + external) 의 default 진입 탭은 'fine-tuning' 으로
  // 통일. external 모델은 FineTuning.jsx 안에서 ExternalFineTuningView 로
  // 자동 분기 — 사용자 운영 UX 가 internal 과 같다.
  const defaultSubPath = 'fine-tuning';

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

  const navList = useMemo(
    () => [
      { label: 'information.label', path: `${url}/info` },
      { label: 'fineTuning.label', path: `${url}/fine-tuning` },
      { label: 'commitList.label', path: `${url}/commit-list` },
    ],
    [url],
  );

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
