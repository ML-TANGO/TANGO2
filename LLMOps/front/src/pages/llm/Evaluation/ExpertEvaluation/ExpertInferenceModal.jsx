import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, Loading, Radio, Selectbox } from '@jonathan/ui-react';

import NewStyleModalFrame from '@src/components/Modal/NewStyleModalFrame';
import EmptyBox from '@src/components/molecules/EmptyBox';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import {
  getRunningPlaygrounds,
  hasAnyRunningPlayground,
} from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './ExpertInferenceModal.module.scss';

const cx = classNames.bind(style);

// 배포 상태는 조나단 Badge type으로 매핑한다.
const DEPLOYMENT_BADGE_TYPE = {
  running: 'green',
};

// 전문가 평가 세션 시작 모달 — **채점할 모델·데이터셋**(런의 선택)과 "출력을 어디서
//   가져오나"를 함께 고른다. 프로젝트는 이름·유형만 잠그므로 대상은 세션마다 다를 수 있다.
//   출력 경로는 두 가지뿐이고 **하나는 반드시 골라야 한다**(BE 가 둘 다 없으면 거절한다):
//     · 실행 중 배포 → 전문가가 여는 샘플만 지연 단위로 실추론(inference_playground_id)
//     · 이전 생성 런 → 그 런이 이미 만들어 둔 출력을 그대로 읽는다(inference_job_id)
//   mock 출력으로 진행하던 폴백은 없앴다 — 채점 화면이 진짜 모델 출력인지 예시인지 구분되지
//   않은 채 별점이 남았고, BE 도 더는 그 경로를 받지 않는다.
//   배포 후보는 **고른 모델을 서빙 중인** running 배포만 BE 가 내려 준다(모델 불일치 방지).
//   모델·데이터셋 목록은 상위(ProjectDetail)가 이미 조회한 것을 받는다(중복 조회 X).
const ExpertInferenceModal = ({
  workspaceId,
  modelOptions,
  datasetOptions,
  inferenceRun,
  onConfirm,
  onClose,
}) => {
  const { t } = useTranslation();

  const [deployments, setDeployments] = useState(null); // null=모름(미조회/로딩), []=없음
  // 후보가 0 건일 때만 채우는 판정값 — 워크스페이스에 running 배포가 하나라도 있나.
  // null=아직 안 물어봄. 빈 상태 문구를 두 갈래로 가르는 데만 쓴다.
  const [anyRunning, setAnyRunning] = useState(null);
  // 출력을 가져올 곳 — '' | 'job'(이전 생성 런) | 'pg:<배포 id>'. 두 종류를 한 값으로 두는
  // 이유: 사용자가 답하는 질문이 하나이고 배타적이라 상태를 둘로 쪼개면 둘 다 찬 상태가
  // 만들어질 수 있다(그러면 BE 우선순위가 선택을 조용히 덮는다).
  const [source, setSource] = useState('');
  const [modelId, setModelId] = useState('');
  const [datasetId, setDatasetId] = useState('');

  // 상위는 폴링마다 runs 배열을 새로 만든다 — 객체를 그대로 의존성에 두면 4초마다 후보를
  // 다시 조회하며 목록이 깜빡인다. 실제로 바뀌는 값(job_id)만 본다.
  // 재사용 후보도 **모델로 거른다** — 배포 후보를 모델로 좁히는 것과 같은 이유다. 다른
  // 모델로 만든 출력을 이 런의 점수로 남기면 그 사실이 어디에도 안 남는다.
  // (model_id 를 안 싣는 옛 런은 거르지 않는다 — 걸러 버리면 재사용 자체가 막힌다.)
  const reuseJobId =
    inferenceRun &&
    (inferenceRun.model_id == null ||
      Number(inferenceRun.model_id) === Number(modelId))
      ? inferenceRun.job_id
      : null;

  // 배포 후보는 모델이 정해져야 물어볼 수 있다. 모델을 바꾸면 다시 조회한다
  // (선택 비우기는 pickModel 이 맡는다).
  useEffect(() => {
    if (!workspaceId || !modelId) {
      setDeployments(null);
      return undefined;
    }
    let active = true;
    setDeployments(null);
    setAnyRunning(null);
    (async () => {
      const res = await getRunningPlaygrounds(workspaceId, modelId);
      if (!active) return;
      if (res.status !== STATUS_SUCCESS) {
        errorToastMessage(res.error, res.message);
        setDeployments([]);
        return;
      }
      const list = Array.isArray(res.result) ? res.result : [];
      // 후보가 없을 때만 워크스페이스 전체를 한 번 더 물어본다 — 문구가 한 프레임 뒤에
      // 바뀌지 않도록 판정이 끝난 뒤에 빈 상태를 렌더한다.
      if (list.length === 0) {
        const any = await hasAnyRunningPlayground(workspaceId);
        if (!active) return;
        setAnyRunning(any);
      }
      setDeployments(list);
      // 고를 것이 하나뿐이면 기본 선택 — 재사용 후보가 있으면 둘 중 하나이므로 묻는다.
      if (list.length === 1 && !reuseJobId) setSource(`pg:${list[0].id}`);
    })();
    return () => {
      active = false;
    };
  }, [workspaceId, modelId, reuseJobId]);

  // NewStyleModalFrame은 Redux 모달 스택(modalKeys.at(-1))을 닫는데, 이 모달은 Redux 가 아닌
  // 로컬 showInferModal 로 렌더된다. 그래서 (a) Esc 를 capture 단계에서 가로채
  // stopImmediatePropagation 으로 프레임의 document 핸들러 발화를 막고(안 막으면 무관한 다른
  // Redux 모달이 같이 닫힌다), (b) 이 모달만 닫는다.
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key !== 'Escape') return;
      event.stopImmediatePropagation();
      onClose();
    };
    document.addEventListener('keydown', handleEscape, true);
    return () => document.removeEventListener('keydown', handleEscape, true);
  }, [onClose]);

  // 프레임이 마운트 시 body.overflow='hidden' 만 걸고 unmount 복구가 없다
  // (NewStyleModalFrame.jsx 의 effect 에 cleanup 없음). Redux 모달은 스토어 변경 경로로
  // 복구되지만 로컬 조건부 렌더는 그 경로를 안 타므로, 평가 시작·백드롭 닫기 후 페이지
  // 스크롤이 잠긴 채 남는다 → 언마운트 시 직접 복구한다.
  useEffect(
    () => () => {
      document.body.style.overflow = 'auto';
    },
    [],
  );

  // 고를 것이 하나뿐이면 기본 선택 — 어차피 그것밖에 못 고른다.
  useEffect(() => {
    if (modelOptions?.length === 1)
      setModelId((prev) => prev || modelOptions[0].value);
  }, [modelOptions]);
  useEffect(() => {
    if (datasetOptions?.length === 1)
      setDatasetId((prev) => prev || datasetOptions[0].value);
  }, [datasetOptions]);

  // 모델을 바꾸면 출력 경로 선택을 비운다 — 후보가 모델로 걸러져 다시 조회되므로, 이전
  // 모델의 배포가 선택에 남으면 목록에 없는 값이 그대로 실려 나간다.
  const pickModel = (nextId) => {
    setModelId(nextId);
    setSource('');
    // 옛 모델의 후보가 한 프레임 남지 않게 즉시 '모름'으로 되돌린다(조회는 이펙트가 한다).
    setDeployments(null);
  };

  const selectedModel =
    (modelOptions || []).find((item) => item.value === modelId) || null;
  const selectedDataset =
    (datasetOptions || []).find((item) => item.value === datasetId) || null;

  const loading = !!modelId && deployments === null;

  // 실행을 막는 첫 이유 하나 — 다른 실행 모달과 같은 방식으로 푸터에 세운다.
  const blockReason = !modelId
    ? t('evaluation.run.needModel')
    : !datasetId
      ? t('evaluation.run.needDataset')
      : !source
        ? t('evaluation.run.needSource')
        : null;

  const submit = {
    text: 'evaluation.expert.inferStart',
    func: () =>
      onConfirm({
        // 고른 쪽 하나만 싣는다 — 둘을 함께 보내면 BE 우선순위(job > playground)가
        // 사용자의 선택을 조용히 덮는다.
        inferencePlaygroundId: source.startsWith('pg:')
          ? Number(source.slice(3))
          : null,
        inferenceJobId: source === 'job' ? reuseJobId : null,
        modelId,
        datasetId,
      }),
  };
  const cancel = {
    text: 'cancel.label',
    func: onClose,
  };
  const modalTitle = t('evaluation.expert.inferTitle');

  return (
    <div
      onClick={(event) => {
        // 기존 수제 오버레이와 동일하게 프레임 바깥을 누르면 닫는다.
        if (event.target.id === modalTitle) onClose();
      }}
    >
      <NewStyleModalFrame
        type='expertInferenceModal'
        title={modalTitle}
        submit={submit}
        cancel={cancel}
        footerMessage={blockReason}
        validate={!loading && !blockReason}
        isResize
        isMinimize
        customStyle={{ width: '664px' }}
      >
        <div className={cx('inference-content')}>
          <p className={cx('desc')}>{t('evaluation.expert.inferDesc')}</p>

          {/* 채점 대상 — 이 세션이 무엇을 재는지. 배포 선택보다 앞선다. */}
          <InputBoxWithLabel
            labelText={t('evaluation.selectModel')}
            labelSize='medium'
            disableErrorMsg
          >
            {(modelOptions || []).length === 0 ? (
              <p className={cx('desc')}>{t('evaluation.compare.noModels')}</p>
            ) : (
              <Selectbox
                size='medium'
                list={modelOptions}
                selectedItem={selectedModel}
                placeholder={t('evaluation.selectModel')}
                onChange={(item) => pickModel(item.value)}
                customStyle={{
                  selectboxForm: { width: '100%' },
                  listForm: { width: '100%' },
                }}
              />
            )}
          </InputBoxWithLabel>

          <InputBoxWithLabel
            labelText={t('evaluation.selectDatasets')}
            labelSize='medium'
            disableErrorMsg
          >
            {(datasetOptions || []).length === 0 ? (
              <p className={cx('desc')}>{t('evaluation.noDatasets')}</p>
            ) : (
              <Selectbox
                type='search'
                size='medium'
                list={datasetOptions}
                selectedItem={selectedDataset}
                placeholder={t('evaluation.searchDataset')}
                onChange={(item) => setDatasetId(item.value)}
                scrollAutoFocus={true}
                customStyle={{
                  selectboxForm: { width: '100%' },
                  listForm: { width: '100%' },
                }}
              />
            )}
          </InputBoxWithLabel>

          {/* 출력을 어디서 가져오나 — 배포(지연 실추론) 또는 이전 생성 런(이미 만든 출력).
              둘 다 없으면 시작할 수 없다: 예시 출력으로 채점하던 폴백은 사라졌다. */}
          <InputBoxWithLabel
            labelText={t('evaluation.run.sourceTitle')}
            labelSize='medium'
            disableErrorMsg
          >
            {!modelId ? (
              <p className={cx('desc')}>{t('evaluation.run.sourceNeedModel')}</p>
            ) : loading ? (
              <div className={cx('modal-loading')}>
                <Loading />
                <span>{t('evaluation.project.loading')}</span>
              </div>
            ) : (
              <div className={cx('deployment-list')}>
                {reuseJobId && (
                  <div className={cx('deployment-row')}>
                    <div className={cx('deployment-choice')}>
                      <Radio
                        name='expertInferenceSource'
                        options={[
                          {
                            label: t('evaluation.run.sourceReuse'),
                            value: 'job',
                          },
                        ]}
                        selectedValue={source}
                        onChange={() => setSource('job')}
                      />
                    </div>
                  </div>
                )}
                {deployments.map((deployment) => (
                  <div key={deployment.id} className={cx('deployment-row')}>
                    <div className={cx('deployment-choice')}>
                      <Radio
                        name='expertInferenceSource'
                        options={[
                          {
                            label: deployment.name,
                            value: `pg:${deployment.id}`,
                          },
                        ]}
                        selectedValue={source}
                        onChange={() => setSource(`pg:${deployment.id}`)}
                      />
                    </div>
                    <Badge
                      label='running'
                      type={DEPLOYMENT_BADGE_TYPE.running}
                      size='sm'
                    />
                  </div>
                ))}
                {deployments.length === 0 && !reuseJobId && (
                  <EmptyBox
                    text={
                      anyRunning
                        ? 'evaluation.run.sourceNoneForModel'
                        : 'evaluation.run.sourceNone'
                    }
                    isBox
                    customStyle={{
                      minHeight: '96px',
                      padding: '12px 16px',
                      boxSizing: 'border-box',
                    }}
                  />
                )}
              </div>
            )}
          </InputBoxWithLabel>
        </div>
      </NewStyleModalFrame>
    </div>
  );
};

export default ExpertInferenceModal;
