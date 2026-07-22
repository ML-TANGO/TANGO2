import { useCallback, useEffect, useMemo, useState } from 'react';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { ButtonV2 } from '@jonathan/ui-react';

import Tab from '@src/components/molecules/Tab';
import {
  deployEdgeWorker,
  getEdgeWorkers,
  refreshEdgeWorker,
} from '@src/apis/flightbase/edge';
import { getModel, getQuantizeLineage } from '@src/apis/llm/model';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './EdgeDeploymentDetail.module.scss';

const cx = classNames.bind(style);

// 엣지 배포 이미지 기본값(기관 제공 이미지로 교체 가능). 클러스터용 llama.cpp 서빙 이미지 참고.
const DEFAULT_EDGE_IMAGE = 'docker.io/acrylaaai/llm_deployment_llamacpp:dev';

function Row({ k, v }) {
  return (
    <div className={cx('row')}>
      <span className={cx('k')}>{k}</span>
      <span className={cx('v')}>{v}</span>
    </div>
  );
}

// 사용자용 엣지 배포 상세 — 디바이스(edge_worker) 중심. 탭 셸(정보/모니터링) 재사용.
//   정보: 디바이스 정보 + 현재 배포 + 배포 설정(양자화 모델 선택→배포 실행).
//   모니터링: refresh(/metrics 폴링) + heartbeat 로 자원/상태.
export default function EdgeDeploymentDetail() {
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId, workerId } = match.params;

  const [worker, setWorker] = useState(null);
  const [tab, setTab] = useState('INFO');

  // 배포 폼 상태
  const [models, setModels] = useState([]);
  const [modelId, setModelId] = useState('');
  const [lineage, setLineage] = useState([]);
  const [lineageId, setLineageId] = useState('');
  const [image, setImage] = useState(DEFAULT_EDGE_IMAGE);
  const [deploying, setDeploying] = useState(false);

  const loadWorker = useCallback(async () => {
    const { status, result } = await getEdgeWorkers();
    if (status === STATUS_SUCCESS) {
      const w = (result || []).find((x) => String(x.id) === String(workerId));
      setWorker(w || null);
    }
  }, [workerId]);

  useEffect(() => {
    loadWorker();
  }, [loadWorker]);

  // 배포 폼용 모델 목록
  useEffect(() => {
    let alive = true;
    (async () => {
      const { status, result } = await getModel(workspaceId);
      if (alive && status === STATUS_SUCCESS) setModels(result || []);
    })();
    return () => {
      alive = false;
    };
  }, [workspaceId]);

  // 모델 선택 시 완료된 양자화 산출물(lineage) 로드
  useEffect(() => {
    if (!modelId) {
      setLineage([]);
      setLineageId('');
      return undefined;
    }
    let alive = true;
    (async () => {
      const { status, result } = await getQuantizeLineage(modelId);
      if (alive && status === STATUS_SUCCESS) {
        setLineage((result?.lineage || []).filter((l) => l.status === 'completed'));
      }
    })();
    return () => {
      alive = false;
    };
  }, [modelId]);

  // 모니터링 탭에서만 refresh 폴링(마운트 기준 → 탭 떠나면 정지)
  useEffect(() => {
    if (tab !== 'MONITOR') return undefined;
    let alive = true;
    const tick = async () => {
      const { status, result } = await refreshEdgeWorker(workerId);
      if (alive && status === STATUS_SUCCESS) setWorker(result);
    };
    tick();
    const iv = setInterval(tick, 10000);
    return () => {
      alive = false;
      clearInterval(iv);
    };
  }, [tab, workerId]);

  const selectedModel = models.find((m) => String(m.id) === String(modelId));
  const selectedLineage = lineage.find((l) => String(l.id) === String(lineageId));

  const handleDeploy = async () => {
    if (!selectedLineage) return toast.error('양자화 모델을 선택하세요.');
    if (!image) return toast.error('서빙 이미지를 입력하세요.');
    setDeploying(true);
    const { status, message } = await deployEdgeWorker(workerId, {
      image,
      model_name: selectedModel?.name,
      model_version: selectedLineage.quantization_type,
      gguf_path: selectedLineage.gguf_path,
    });
    setDeploying(false);
    if (status === STATUS_SUCCESS) {
      toast.success('배포를 요청했습니다.');
      loadWorker();
    } else {
      toast.error(message || '배포에 실패했습니다.');
    }
  };

  const heartbeat = useMemo(() => {
    try {
      return worker?.last_heartbeat_json ? JSON.parse(worker.last_heartbeat_json) : null;
    } catch {
      return null;
    }
  }, [worker]);

  const isOnline = worker?.conn_status === 'online';
  const tabOptions = [
    { label: 'information.label', value: 'INFO' },
    { label: 'Monitoring', value: 'MONITOR' },
  ];

  return (
    <div className={cx('edge-cont')}>
      <div className={cx('header')}>
        <button
          type='button'
          className={cx('back')}
          onClick={() => history.push(`/user/workspace/${workspaceId}/llmplayground`)}
        >
          ← 배포 목록
        </button>
        <h2 className={cx('title')}>{worker?.name || '엣지 디바이스'}</h2>
        <span className={cx('badge', isOnline ? 'on' : 'off')}>
          {worker?.conn_status || '-'}
        </span>
      </div>

      <div className={cx('tab-bar')}>
        <Tab
          type='c'
          sidePaddingNone
          option={tabOptions}
          select={{ value: tab }}
          tabHandler={({ value }) => setTab(value)}
        />
      </div>

      {tab === 'INFO' && (
        <div className={cx('grid')}>
          <section className={cx('card')}>
            <h3 className={cx('card-title')}>디바이스 정보</h3>
            <Row k='이름' v={worker?.name || '-'} />
            <Row k='유형' v={worker?.device_type || '-'} />
            <Row k='연결' v={worker?.conn_status || '-'} />
            <Row k='최근 확인' v={worker?.last_seen || '-'} />
            <Row
              k='자원'
              v={`CPU ${worker?.cpu_cores ?? '-'} / MEM ${worker?.mem_total ?? '-'}GB / ${worker?.gpu_info || '-'}`}
            />
          </section>

          <section className={cx('card')}>
            <h3 className={cx('card-title')}>현재 배포</h3>
            <Row k='모델' v={worker?.deploy_model || '-'} />
            <Row k='버전' v={worker?.deploy_version || '-'} />
            <Row k='상태' v={worker?.deploy_state || '-'} />
          </section>

          <section className={cx('card')}>
            <h3 className={cx('card-title')}>배포 설정</h3>
            <label className={cx('label')} htmlFor='edge-deploy-model'>모델</label>
            <select
              id='edge-deploy-model'
              className={cx('select')}
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
            >
              <option value=''>모델 선택</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>

            <label className={cx('label')} htmlFor='edge-deploy-gguf'>양자화 모델(GGUF)</label>
            <select
              id='edge-deploy-gguf'
              className={cx('select')}
              value={lineageId}
              onChange={(e) => setLineageId(e.target.value)}
              disabled={!modelId}
            >
              <option value=''>
                {modelId ? '양자화 산출물 선택' : '모델 먼저 선택'}
              </option>
              {lineage.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.quantization_type} · {l.gguf_path?.split('/').pop()}
                </option>
              ))}
            </select>

            <label className={cx('label')} htmlFor='edge-deploy-image'>서빙 이미지</label>
            <input
              id='edge-deploy-image'
              className={cx('input')}
              value={image}
              onChange={(e) => setImage(e.target.value)}
              placeholder={DEFAULT_EDGE_IMAGE}
            />

            <ButtonV2
              label={deploying ? '배포 중…' : '배포 실행'}
              colorType='skyblue'
              disabled={deploying || !isOnline}
              onClick={handleDeploy}
              style={{ width: '100%', marginTop: '8px' }}
            />
            {!isOnline && (
              <p className={cx('hint')}>디바이스가 online일 때 배포할 수 있습니다.</p>
            )}
          </section>
        </div>
      )}

      {tab === 'MONITOR' && (
        <div className={cx('grid')}>
          <section className={cx('card')}>
            <h3 className={cx('card-title')}>자원 / 상태</h3>
            <Row k='연결' v={worker?.conn_status || '-'} />
            <Row k='배포 상태' v={worker?.deploy_state || '-'} />
            <Row k='CPU 코어' v={worker?.cpu_cores ?? '-'} />
            <Row k='메모리(GB)' v={worker?.mem_total ?? '-'} />
            <Row k='GPU' v={worker?.gpu_info || '-'} />
            <Row k='컨테이너 수' v={worker?.container_count ?? '-'} />
          </section>

          <section className={cx('card')}>
            <h3 className={cx('card-title')}>Heartbeat</h3>
            <Row k='최근 확인' v={worker?.last_seen || '-'} />
            {heartbeat ? (
              <>
                <Row k='CPU %' v={heartbeat.cpu_pct ?? '-'} />
                <Row k='GPU %' v={heartbeat.gpu_pct ?? '-'} />
                <Row k='로드 모델' v={heartbeat.model_loaded || '-'} />
                <Row k='추론 수' v={heartbeat.inference_count_total ?? '-'} />
              </>
            ) : (
              <p className={cx('hint')}>heartbeat 수신 대기 중…</p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
