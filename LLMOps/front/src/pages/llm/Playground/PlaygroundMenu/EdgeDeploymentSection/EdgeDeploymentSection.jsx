import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { getEdgeWorkers } from '@src/apis/flightbase/edge';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './EdgeDeploymentSection.module.scss';

const cx = classNames.bind(style);

// 배포(D6 v3) 탭의 온디바이스(엣지) 배포 섹션.
//   edge_worker(SP-8) 중 deploy_state 가 있는 워커 = 온디바이스에 배포된 패키지(SP-6).
//   현재클러스터(=Playground 카드)와 별개 타겟. read-only 목록(생성=Step 2b).
const EdgeDeploymentSection = () => {
  const { t } = useTranslation();
  const history = useHistory();
  const match = useRouteMatch();
  const wid = match.params.id;
  const [workers, setWorkers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      const res = await getEdgeWorkers();
      if (!alive) return;
      let list = [];
      if (res.status === STATUS_SUCCESS) {
        const raw = Array.isArray(res.result) ? res.result : [];
        list = raw.filter((w) => w.deploy_state);
      }
      setWorkers(list);
      setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section className={cx('edge-section')}>
      <h2 className={cx('section-title')}>{t('deploymentTarget.edge.label')}</h2>
      {loading ? null : workers.length === 0 ? (
        <p className={cx('empty')}>{t('deployment.empty.edge.label')}</p>
      ) : (
        <ul className={cx('list')}>
          {workers.map((w) => (
            <li
              key={w.id}
              className={cx('item')}
              role='button'
              tabIndex={0}
              style={{ cursor: 'pointer' }}
              onClick={() =>
                history.push(`/user/workspace/${wid}/edge-deploy/${w.id}`)
              }
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  history.push(`/user/workspace/${wid}/edge-deploy/${w.id}`);
                }
              }}
            >
              <span className={cx('name')}>{w.name || w.device_id}</span>
              <span className={cx('sub')}>{w.deploy_model || '-'}</span>
              <span className={cx('state', w.deploy_state)}>{w.deploy_state}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};

export default EdgeDeploymentSection;
