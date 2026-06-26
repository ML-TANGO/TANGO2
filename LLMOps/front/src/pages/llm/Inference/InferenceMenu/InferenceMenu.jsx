import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { getPlayground } from '@src/apis/llm/playground';
import { startPath } from '@src/store/modules/breadCrumb';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './InferenceMenu.module.scss';

const cx = classNames.bind(style);

// 추론(Inference, D6 v3 §7.5) 랜딩 — consume 레이어.
//   활성(running) 배포만 노출 → 선택 시 lean 추론 상세(InferenceDetail).
//   배포(provision)는 "배포" 탭. 여기선 "띄운 배포에 질의"만.
//   (이중모델 D2 + 배치 메트릭 = Tier-2, SP-7/SP-5 의존.)
const InferenceMenu = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const match = useRouteMatch();
  const history = useHistory();
  const { id: workspaceId } = match.params;

  const [activeList, setActiveList] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchActive = useCallback(async () => {
    const res = await getPlayground(workspaceId);
    if (res.status === STATUS_SUCCESS) {
      const list = Array.isArray(res.result) ? res.result : [];
      // 질의 가능 = 서빙 running 상태
      setActiveList(list.filter((d) => d.status === 'running'));
      setLoading(false);
      return;
    }
    errorToastMessage(res.error, res.message);
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Inference' } }]));
    fetchActive();
  }, [dispatch, fetchActive]);

  const openInference = (id) => {
    history.push(`/user/workspace/${workspaceId}/inference/${id}`);
  };

  return (
    <div className={cx('inference-cont')}>
      <h1 className={cx('title')}>{t('Inference')}</h1>
      {loading ? null : activeList.length === 0 ? (
        <p className={cx('empty')}>{t('inference.empty.label')}</p>
      ) : (
        <ul className={cx('list')}>
          {activeList.map((d) => (
            <li
              key={d.id}
              className={cx('item')}
              onClick={() => openInference(d.id)}
            >
              <span className={cx('name')}>{d.name}</span>
              <span className={cx('sub')}>{d.owner || '-'}</span>
              <span className={cx('status', 'running')}>{d.status}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default InferenceMenu;
