import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, Loading, Radio, Selectbox, Textarea } from '@jonathan/ui-react';

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
import style from './EvalGenerateModal.module.scss';

const cx = classNames.bind(style);

// 배포 상태는 조나단 Badge type으로 매핑한다.
const DEPLOYMENT_BADGE_TYPE = {
  running: 'green',
};

// 평가 추론 러너(generate) 실행 모달 — 출력을 만들 running 배포를 골라 데이터셋 전량 batch
// 추론으로 output 을 생성·영속(_samples). system_prompt 는 이 생성 런이 소유하는 시스템
// 프롬프트로, 헤더 고정 박스(생성 시스템 프롬프트)에 표시되고 채점(benchmark/judge/expert)이
// 그 output 을 소비한다(생성·채점 분리). 재사용 경로(running 배포 선택)만 — 전용 인스턴스
// 할당은 후속(P4).
// 후보는 **고른 모델을 서빙 중인** running 배포만 BE 가 내려 준다 — 다른 모델의 배포로
// 생성하면 만들어진 출력이 대상 모델의 것이 아니게 되고, 그 사실이 채점 화면에 남지 않는다.
const EvalGenerateModal = ({
  workspaceId,
  modelOptions,
  datasetOptions,
  running,
  onConfirm,
  onClose,
}) => {
  const { t } = useTranslation();

  const [deployments, setDeployments] = useState(null); // null=로딩, []=없음
  // 후보가 0 건일 때만 채우는 판정값 — 워크스페이스에 running 배포가 하나라도 있나.
  // null=아직 안 물어봄. 빈 상태 문구를 두 갈래로 가르는 데만 쓴다.
  const [anyRunning, setAnyRunning] = useState(null);
  const [selected, setSelected] = useState(null); // playground id
  const [sysPrompt, setSysPrompt] = useState('');
  // 생성 런도 대상 모델·데이터셋을 스스로 지정한다(프로젝트 상속 아님).
  const [modelId, setModelId] = useState('');
  const [datasetId, setDatasetId] = useState('');

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
      // 후보가 하나면 기본 선택, 여럿/없음이면 사용자 선택.
      if (list.length === 1) setSelected(list[0].id);
    })();
    return () => {
      active = false;
    };
  }, [workspaceId, modelId]);

  // NewStyleModalFrame은 Redux 모달을 닫으므로, 로컬 조건부 렌더 경로의 Esc 닫기도 유지한다.
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  // 고를 것이 하나뿐이면 기본 선택 — 어차피 그것밖에 못 고른다.
  useEffect(() => {
    if (modelOptions?.length === 1)
      setModelId((prev) => prev || modelOptions[0].value);
  }, [modelOptions]);
  useEffect(() => {
    if (datasetOptions?.length === 1)
      setDatasetId((prev) => prev || datasetOptions[0].value);
  }, [datasetOptions]);

  // 모델을 바꾸면 배포 선택을 비운다 — 후보가 모델로 걸러져 다시 조회되므로, 이전 모델의
  // 배포가 선택에 남으면 목록에 없는 값이 그대로 실려 나간다.
  const pickModel = (nextId) => {
    setModelId(nextId);
    setSelected(null);
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
      : !selected
        ? t('evaluation.run.needSourceDeploy')
        : null;

  const submit = {
    text: running ? 'evaluation.running' : 'evaluation.generate.start',
    func: () =>
      onConfirm({
        inference_playground_id: selected,
        system_prompt: sysPrompt.trim() || undefined,
        model_id: Number(modelId),
        dataset_ids: [Number(datasetId)],
      }),
  };
  const cancel = {
    text: 'cancel.label',
    func: onClose,
  };
  const modalTitle = t('evaluation.generate.title');

  return (
    <div
      onClick={(event) => {
        // 기존 수제 오버레이와 동일하게 프레임 바깥을 누르면 닫는다.
        if (event.target.id === modalTitle) onClose();
      }}
    >
      <NewStyleModalFrame
        type='evalGenerateModal'
        title={modalTitle}
        submit={submit}
        cancel={cancel}
        footerMessage={blockReason}
        validate={!loading && !running && !blockReason}
        isResize
        isMinimize
        customStyle={{ width: '664px' }}
      >
        <div className={cx('generate-content')}>
          <p className={cx('desc')}>{t('evaluation.generate.desc')}</p>

          {/* 생성 대상 — 어느 모델의 어느 데이터셋으로 output 을 만드나. */}
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

          <InputBoxWithLabel
            labelText={t('evaluation.generate.systemPrompt')}
            labelSize='medium'
            disableErrorMsg
          >
            <Textarea
              size='large'
              name='eval-gen-sysprompt'
              maxLength={4000}
              options={{ id: 'eval-gen-sysprompt', rows: 4 }}
              placeholder={t('evaluation.generate.systemPromptPlaceholder')}
              value={sysPrompt}
              customStyle={{ width: '100%', minHeight: '112px' }}
              onChange={(event) => setSysPrompt(event.target.value)}
            />
          </InputBoxWithLabel>

          {/* 출력을 만들 배포 — 고른 모델을 서빙 중인 running 배포만 후보다. */}
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
                {deployments.map((deployment) => (
                  <div key={deployment.id} className={cx('deployment-row')}>
                    <div className={cx('deployment-choice')}>
                      <Radio
                        name='evalGenerateDeployment'
                        options={[
                          {
                            label: deployment.name,
                            value: deployment.id,
                          },
                        ]}
                        selectedValue={selected}
                        onChange={() => setSelected(deployment.id)}
                      />
                    </div>
                    <Badge
                      label='running'
                      type={DEPLOYMENT_BADGE_TYPE.running}
                      size='sm'
                    />
                  </div>
                ))}
                {deployments.length === 0 && (
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

export default EvalGenerateModal;
