import { useEffect, useMemo, useState } from 'react';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import Tab from '@src/components/molecules/Tab';
import DeployDetailHeader from '@src/components/pageContents/llm/DeployDetail/DeployDetailHeader';
import { getModel, getQuantizeLineage } from '@src/apis/llm/model';
import { STATUS_SUCCESS } from '@src/network';
import { copyToClipboardWithToast } from '@src/utils';
import { getDetailPlayground } from '@src/apis/llm/playground';

import classNames from 'classnames/bind';
import style from './StandaloneDeploymentDetail.module.scss';

const cx = classNames.bind(style);

// 런타임 엔진 기본 6종(+ 커스텀 도커 이미지 pull). standalone 은 오프라인 번들이라 이미지가 실행 스크립트에 박힘.
const ENGINES = [
  {
    id: 'vllm',
    label: 'vLLM',
    image: 'docker.io/acrylaaai/llm_deployment:dev',
  },
  {
    id: 'llama_cpp',
    label: 'llama.cpp',
    image: 'docker.io/acrylaaai/llm_deployment_llamacpp:dev',
  },
  {
    id: 'tgi',
    label: 'TGI',
    image: 'docker.io/acrylaaai/llm_deployment_tgi:dev',
  },
  {
    id: 'ollama',
    label: 'Ollama',
    image: 'docker.io/acrylaaai/llm_deployment_ollama:dev',
  },
  {
    id: 'triton',
    label: 'Triton',
    image: 'docker.io/acrylaaai/llm_deployment_triton:dev',
  },
  {
    id: 'tensorrt',
    label: 'TensorRT',
    image: 'docker.io/acrylaaai/llm_deployment_tensorrt:dev',
  },
];
const CUSTOM_ENGINE = 'custom';

const DEFAULT_PARAMS = {
  temperature: 1,
  top_p: 0.9,
  top_k: 50,
  max_new_tokens: 512,
};
const PARAM_META = [
  { key: 'temperature', label: 'Temperature', min: 0, max: 2, step: 0.1 },
  { key: 'top_p', label: 'Top P', min: 0, max: 1, step: 0.05 },
  { key: 'top_k', label: 'Top K', min: 0, max: 100, step: 1 },
  { key: 'max_new_tokens', label: 'Max Sequence', min: 1, max: 4096, step: 1 },
];

function Row({ k, v }) {
  return (
    <div className={cx('row')}>
      <span className={cx('k')}>{k}</span>
      <span className={cx('v')}>{v}</span>
    </div>
  );
}

// standalone(오프라인 번들) 배포 상세 — 3탭(정보/배포/스크립트), Playground 셸 미러.
//   정보: 배포 정보 요약.
//   배포: 2열 [모델·런타임(6+커스텀)] | 파라미터 (인스턴스/API/디바이스 열 없음).
//   스크립트: 배포 실행 스크립트(복사). 모니터링 탭 대체.
export default function StandaloneDeploymentDetail() {
  const { t } = useTranslation();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId, deployId } = match.params;

  const [tab, setTab] = useState('INFO');

  // 배포 폼 상태(목업 — 오프라인 번들 구성)
  const [engine, setEngine] = useState('llama_cpp');
  const [image, setImage] = useState(ENGINES[1].image);
  const [models, setModels] = useState([]);
  const [modelId, setModelId] = useState('');
  const [lineage, setLineage] = useState([]);
  const [lineageId, setLineageId] = useState('');
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [project, setProject] = useState(null); // 배포 프로젝트 메타(정보 탭)

  const isCustomEngine = engine === CUSTOM_ENGINE;

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
        setLineage(
          (result?.lineage || []).filter((l) => l.status === 'completed'),
        );
      }
    })();
    return () => {
      alive = false;
    };
  }, [modelId]);

  // 배포 프로젝트 메타 — 실 playground 상세 조회('new' 생성 진입 시엔 미조회).
  useEffect(() => {
    if (!deployId || deployId === 'new') return undefined;
    let alive = true;
    (async () => {
      const { status, result } = await getDetailPlayground(deployId);
      // 상세 응답은 {info, model, model_parameter, ...} 중첩 — 프로젝트 메타(name/description/owner/access/일시)는 info.
      if (alive && status === STATUS_SUCCESS) setProject(result?.info || null);
    })();
    return () => {
      alive = false;
    };
  }, [deployId]);

  const selectedModel = models.find((m) => String(m.id) === String(modelId));
  const selectedLineage = lineage.find(
    (l) => String(l.id) === String(lineageId),
  );

  const handleSelectEngine = (id) => {
    setEngine(id);
    const eng = ENGINES.find((e) => e.id === id);
    if (eng) setImage(eng.image);
  };

  const handleParam = (key, value) =>
    setParams((p) => ({ ...p, [key]: +value }));

  // 배포 실행 스크립트(목업) — 선택 구성으로 docker run 스크립트 생성.
  const runScript = useMemo(() => {
    const gguf = selectedLineage?.gguf_path?.split('/').pop() || '<model.gguf>';
    const modelName = selectedModel?.name || '<model>';
    return [
      '#!/usr/bin/env bash',
      '# TANGO standalone 오프라인 배포 스크립트 (자동 생성)',
      `# 모델: ${modelName} · 엔진: ${engine}`,
      'set -e',
      '',
      '# 1) 런타임 이미지 로드 (오프라인 번들 포함 tar → load, 온라인 시 pull)',
      `docker load -i ./images/runtime.tar 2>/dev/null || docker pull ${image}`,
      '',
      '# 2) 모델/파라미터 마운트 후 서빙 컨테이너 기동',
      'docker run -d --name tango-serving \\',
      '  --gpus all -p 8000:8000 \\',
      '  -v "$(pwd)/models:/models" \\',
      `  -e MODEL_PATH="/models/${gguf}" \\`,
      `  -e TEMPERATURE="${params.temperature}" -e TOP_P="${params.top_p}" \\`,
      `  -e TOP_K="${params.top_k}" -e MAX_NEW_TOKENS="${params.max_new_tokens}" \\`,
      `  ${image}`,
    ].join('\n');
  }, [engine, image, selectedModel, selectedLineage, params]);

  const tabOptions = [
    { label: 'information.label', value: 'INFO' },
    { label: 'deployment.label', value: 'DEPLOY' },
    { label: 'standalone.tab.script', value: 'SCRIPT' },
  ];

  return (
    <div className={cx('playground-cont')}>
      <DeployDetailHeader
        title={project?.name || t('standalone.title')}
        onBack={() =>
          history.push(`/user/workspace/${workspaceId}/llmplayground`)
        }
        right={<span className={cx('type-chip')}>Standalone</span>}
      />

      <div className={cx('tab-bar')}>
        <Tab
          type='c'
          sidePaddingNone
          option={tabOptions}
          select={{ value: tab }}
          tabHandler={({ value }) => setTab(value)}
        />
      </div>

      {/* ── 정보 (배포 프로젝트 설정 정보 — Playground 정보 탭과 동형) ── */}
      {tab === 'INFO' && (
        <div className={cx('content-cont')}>
          <section className={cx('card')}>
            <h3 className={cx('card-title')}>{t('information.label')}</h3>
            <div className={cx('info-field')}>
              <span className={cx('label')}>{t('description.label')}</span>
              <p className={cx('info-value')}>{project?.description || '-'}</p>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>{t('deploymentType.label')}</span>
              <span className={cx('info-value')}>
                {t('standalone.deployType')}
              </span>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>{t('releaseType.label')}</span>
              <span className={cx('info-value')}>
                {project?.access ? 'Public' : 'Private'}
              </span>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>{t('owner.label')}</span>
              <span className={cx('info-value')}>{project?.owner || '-'}</span>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>{t('createdAt.label')}</span>
              <span className={cx('info-value')}>
                {project?.create_datetime || '-'}
              </span>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>
                {t('deployDetail.info.lastUpdated')}
              </span>
              <span className={cx('info-value')}>
                {project?.update_datetime || '-'}
              </span>
            </div>
          </section>
        </div>
      )}

      {/* ── 배포 (3열) ── */}
      {tab === 'DEPLOY' && (
        <div className={cx('deploy-cont')}>
          {/* 1열: 런타임 엔진 + 모델 선택/정보 */}
          <section className={cx('card')}>
            <h3 className={cx('card-title')}>
              {t('deployDetail.section.modelRuntime')}
            </h3>

            <span className={cx('label')} id='sa-engine-label'>
              {t('deployDetail.field.engine')}
            </span>
            <div
              className={cx('engine-grid')}
              role='radiogroup'
              aria-labelledby='sa-engine-label'
            >
              {ENGINES.map((eng) => (
                <button
                  key={eng.id}
                  type='button'
                  role='radio'
                  aria-checked={engine === eng.id}
                  className={cx('engine-opt', engine === eng.id && 'selected')}
                  onClick={() => handleSelectEngine(eng.id)}
                >
                  {eng.label}
                </button>
              ))}
              <button
                type='button'
                role='radio'
                aria-checked={isCustomEngine}
                className={cx(
                  'engine-opt',
                  'custom',
                  isCustomEngine && 'selected',
                )}
                onClick={() => handleSelectEngine(CUSTOM_ENGINE)}
              >
                {t('deployDetail.engine.custom')}
              </button>
            </div>

            <label className={cx('label')} htmlFor='sa-image'>
              {isCustomEngine
                ? t('deployDetail.field.customImage')
                : t('deployDetail.field.runtimeImage')}
            </label>
            <input
              id='sa-image'
              className={cx('input')}
              value={image}
              onChange={(e) => setImage(e.target.value)}
              placeholder='docker.io/org/image:tag'
              readOnly={!isCustomEngine}
            />

            <div className={cx('divider')} />

            <label className={cx('label')} htmlFor='sa-model'>
              {t('model.label')}
            </label>
            <select
              id='sa-model'
              className={cx('select')}
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
            >
              <option value=''>{t('deployDetail.model.select')}</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>

            <label className={cx('label')} htmlFor='sa-gguf'>
              {t('deployDetail.field.ggufModel')}
            </label>
            <select
              id='sa-gguf'
              className={cx('select')}
              value={lineageId}
              onChange={(e) => setLineageId(e.target.value)}
              disabled={!modelId}
            >
              <option value=''>
                {modelId
                  ? t('deployDetail.gguf.select')
                  : t('deployDetail.gguf.selectModelFirst')}
              </option>
              {lineage.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.quantization_type} · {l.gguf_path?.split('/').pop()}
                </option>
              ))}
            </select>

            {selectedModel && (
              <>
                <div className={cx('divider')} />
                <span className={cx('sub-title')}>
                  {t('deployDetail.section.modelInfo')}
                </span>
                <Row k={t('name.label')} v={selectedModel.name || '-'} />
                <Row
                  k={t('deployDetail.row.quantization')}
                  v={selectedLineage?.quantization_type || '-'}
                />
                <Row
                  k='GGUF'
                  v={selectedLineage?.gguf_path?.split('/').pop() || '-'}
                />
              </>
            )}
          </section>

          {/* 2열: 파라미터 */}
          <section className={cx('card')}>
            <h3 className={cx('card-title')}>{t('parameterSettings.label')}</h3>
            {PARAM_META.map((p) => (
              <div key={p.key} className={cx('param')}>
                <div className={cx('param-head')}>
                  <span className={cx('label')}>{p.label}</span>
                  <span className={cx('param-val')}>{params[p.key]}</span>
                </div>
                <input
                  type='range'
                  className={cx('slider')}
                  min={p.min}
                  max={p.max}
                  step={p.step}
                  value={params[p.key]}
                  onChange={(e) => handleParam(p.key, e.target.value)}
                />
              </div>
            ))}
          </section>
        </div>
      )}

      {/* ── 스크립트(모니터링 대체) ── */}
      {tab === 'SCRIPT' && (
        <div className={cx('grid')}>
          <section className={cx('card', 'script-card')}>
            <div className={cx('card-head')}>
              <h3 className={cx('card-title')}>
                {t('standalone.script.title')}
              </h3>
              <button
                type='button'
                className={cx('copy-btn')}
                onClick={() => copyToClipboardWithToast(runScript)}
              >
                {t('copy.label')}
              </button>
            </div>
            <pre className={cx('script')}>{runScript}</pre>
          </section>
        </div>
      )}
    </div>
  );
}
