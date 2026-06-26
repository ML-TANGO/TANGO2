import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { getEdgeWorkers } from '@src/apis/flightbase/edge';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './EdgeDeploymentSection.module.scss';

const cx = classNames.bind(style);

// ⚠️⚠️ PREVIEW DUMMY — 화면 확인용. 커밋 금지. 끄려면 false 또는 이 블록 삭제. ⚠️⚠️
//   실 클러스터에 배포된 엣지 워커가 아직 없어 섹션이 비어 보임 → 더미로 UI 렌더만 확인.
//   실데이터(deploy_state 있는 워커)가 있으면 그쪽이 우선, 없을 때만 더미 폴백.
//   getEdgeWorkers 응답 shape 와 동일: { id, name, device_id, deploy_model, deploy_state }.
const PREVIEW_DUMMY = false;
const DUMMY_EDGE_DEPLOYMENTS = [
  {
    id: 'dummy-1',
    name: 'jetson-orin-01',
    deploy_model: 'EVA-VLM · Q4_K_M',
    deploy_state: 'running',
  },
  {
    id: 'dummy-2',
    name: 'rpi5-edge-02',
    deploy_model: 'Qwen2.5-0.5B · Q5_K_M',
    deploy_state: 'stopped',
  },
  {
    id: 'dummy-3',
    name: 'agx-xavier-03',
    deploy_model: 'Llama-3.2-1B · Q6_K',
    deploy_state: 'error',
  },
];

// 배포(D6 v3) 탭의 온디바이스(엣지) 배포 섹션.
//   edge_worker(SP-8) 중 deploy_state 가 있는 워커 = 온디바이스에 배포된 패키지(SP-6).
//   현재클러스터(=Playground 카드)와 별개 타겟. read-only 목록(생성=Step 2b).
const EdgeDeploymentSection = () => {
  const { t } = useTranslation();
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
      // ⚠️ PREVIEW DUMMY 폴백 — 실데이터 0건일 때만.
      if (PREVIEW_DUMMY && list.length === 0) {
        list = DUMMY_EDGE_DEPLOYMENTS;
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
            <li key={w.id} className={cx('item')}>
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
