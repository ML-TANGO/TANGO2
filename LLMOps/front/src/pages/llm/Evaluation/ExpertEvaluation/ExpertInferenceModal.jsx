import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { InputText, Selectbox, Textarea } from '@jonathan/ui-react';

import NewStyleModalFrame from '@src/components/Modal/NewStyleModalFrame';
import EmptyBox from '@src/components/molecules/EmptyBox';

import {
  getRunningPlaygrounds,
  hasAnyRunningPlayground,
} from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

// 평가 세트 규격 — BE constants.EXPERT_SAMPLE_SET_SIZE/COUNT 와 **같은 값이어야 한다**.
// 어긋나면 라벨에 적힌 구간(예: 201~300)과 실제 채점 구간이 달라진다.
//   공인시험은 평가자가 여러 명이라 1k 데이터셋을 100개씩 10구간으로 미리 나눠 두고 카드마다
//   하나를 맡는다. 종전의 자유 입력(상위 N개)은 두 카드가 같은 앞부분을 중복 채점하게 돼 폐기.
const SAMPLE_SET_SIZE = 100;
const SAMPLE_SET_COUNT = 10;

import classNames from 'classnames/bind';
import style from './ExpertEvaluation.module.scss';

// 실행 모달 폼 클래스(run-*)는 **세 실행 모달이 나눠 쓰는 한 벌**(Evaluation/_runModal.scss)
// 에서 온다. 종전에는 정답 대조 스타일시트의 rail-*·opt-* 를 빌려 썼는데, 그 시트는 결과
// 뷰까지 함께 import 하므로 손대면 무관한 화면이 같이 바뀐다 — 그래서 폼 규격만 뽑아 냈다.
// 전문가는 고를 '세트'가 없어 좌측 목록 패널 없이 단일 컬럼이다.
const cx = classNames.bind(style);

// 전문가 평가 세션 시작 모달 — **채점할 모델·데이터셋**(런의 선택)과 출력을 만들 배포를
//   함께 고른다. 프로젝트는 이름·유형만 잠그므로 대상은 세션마다 다를 수 있다.
//   출력 경로는 **실행 중 배포 하나뿐**이고 반드시 골라야 한다(BE 가 없으면 거절한다):
//   전문가가 여는 샘플만 지연 단위로 실추론한다(inference_playground_id).
//   종전에는 '이전 생성 런의 출력 재사용'(inference_job_id)이 또 하나의 선택지였다. 생성 런을
//   만드는 진입점을 없애면서(ProjectDetail 의 'Run generation') 새 생성 런이 더는 만들어지지
//   않아, 남겨 두면 **고를 수 없거나 옛 런에서만 뜨는 죽은 선택지**가 된다 — 그래서 뺐다.
//   mock 출력으로 진행하던 폴백도 없다 — 채점 화면이 진짜 모델 출력인지 예시인지 구분되지
//   않은 채 별점이 남았고, BE 도 더는 그 경로를 받지 않는다.
//   배포 후보는 **고른 모델을 서빙 중인** running 배포만 BE 가 내려 준다(모델 불일치 방지).
//   모델·데이터셋 목록은 상위(ProjectDetail)가 이미 조회한 것을 받는다(중복 조회 X).
const ExpertInferenceModal = ({
  workspaceId,
  modelOptions,
  datasetOptions,
  // 이 프로젝트에서 이미 잡힌 세트 [{ datasetId, set }] — 같은 데이터셋의 같은 세트를 두 카드가
  // 맡으면 두 사람이 같은 문항을 채점하게 되므로 목록에서 비활성화한다(BE 도 거절한다).
  usedSets,
  onConfirm,
  onClose,
}) => {
  const { t } = useTranslation();

  const [deployments, setDeployments] = useState(null); // null=모름(미조회/로딩), []=없음
  // 후보가 0 건일 때만 채우는 판정값 — 워크스페이스에 running 배포가 하나라도 있나.
  // null=아직 안 물어봄. 빈 상태 문구를 두 갈래로 가르는 데만 쓴다.
  const [anyRunning, setAnyRunning] = useState(null);
  // 출력을 만들 배포 — '' 이면 아직 고르지 않은 것. 선택지가 배포 하나뿐이라 종류를 섞어
  // 담던 'pg:<id>' 접두어를 걷어내고 id 를 그대로 든다(BenchmarkRunConfig 와 같은 이름·형).
  const [playgroundId, setPlaygroundId] = useState('');
  const [modelId, setModelId] = useState('');
  const [datasetId, setDatasetId] = useState('');
  // 채점할 샘플 수 — '' 이면 데이터셋 전량(BE 기본과 같다). 앞에서부터 자른다.
  const [sampleSet, setSampleSet] = useState('');
  // 세션 제목·평가 지침 — 둘 다 선택. 제목은 run 목록·채점 헤더의 표시원이고, 지침은
  // 채점 화면 상단 박스에 그대로 뜬다. 비우면 BE 가 기본값(데이터셋명 / 시나리오 기본
  // 지침)으로 폴백하므로 빈 문자열을 억지로 보내지 않는다.
  const [runName, setRunName] = useState('');
  const [guideline, setGuideline] = useState('');

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
      // 고를 것이 하나뿐이면 기본 선택 — 어차피 그것밖에 못 고른다(선택지가 배포뿐이라
      // 재사용 런과 견주느라 묻던 조건이 사라졌다).
      if (list.length === 1) setPlaygroundId(list[0].id);
    })();
    return () => {
      active = false;
    };
  }, [workspaceId, modelId]);

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
  // 데이터셋이 바뀌면 세트 선택을 비운다 — 세트는 데이터셋별로 세므로, 그대로 두면 새 데이터셋
  // 에서 이미 잡힌 세트가 선택된 채 남아 시작 시 BE 가 거절한다.
  useEffect(() => setSampleSet(''), [datasetId]);

  // 모델을 바꾸면 출력 경로 선택을 비운다 — 후보가 모델로 걸러져 다시 조회되므로, 이전
  // 모델의 배포가 선택에 남으면 목록에 없는 값이 그대로 실려 나간다.
  const pickModel = (nextId) => {
    setModelId(nextId);
    setPlaygroundId('');
    // 옛 모델의 후보가 한 프레임 남지 않게 즉시 '모름'으로 되돌린다(조회는 이펙트가 한다).
    setDeployments(null);
  };

  const selectedModel =
    (modelOptions || []).find((item) => item.value === modelId) || null;
  const selectedDataset =
    (datasetOptions || []).find((item) => item.value === datasetId) || null;

  const deploymentOptions = useMemo(
    () => (deployments ?? []).map((d) => ({ label: d.name, value: d.id })),
    [deployments],
  );
  const selectedDeployment =
    deploymentOptions.find((item) => item.value === playgroundId) || null;
  const deployment = (deployments ?? []).find((d) => d.id === playgroundId);

  const loading = !!modelId && deployments === null;

  // 세트 목록 — 고른 데이터셋에서 이미 잡힌 세트는 비활성화(disabled)해 남겨 둔다. 목록에서
  // 빼 버리면 "왜 세트 3 이 없지?" 가 되고, 남겨 두면 누가 이미 맡았다는 사실이 보인다.
  const takenSets = useMemo(() => {
    const ids = new Set();
    (usedSets || []).forEach((u) => {
      if (u && String(u.datasetId) === String(datasetId)) ids.add(Number(u.set));
    });
    return ids;
  }, [usedSets, datasetId]);
  const sampleSetOptions = useMemo(
    () =>
      Array.from({ length: SAMPLE_SET_COUNT }, (_, i) => {
        const n = i + 1;
        const from = i * SAMPLE_SET_SIZE + 1;
        const to = n * SAMPLE_SET_SIZE;
        const taken = takenSets.has(n);
        return {
          label: taken
            ? t('evaluation.expert.sampleSetTaken', { n, from, to })
            : t('evaluation.expert.sampleSetLabel', { n, from, to }),
          value: n,
          disabled: taken,
        };
      }),
    [takenSets, t],
  );
  const selectedSampleSet =
    sampleSetOptions.find((item) => item.value === sampleSet) || null;
  const allSetsTaken = takenSets.size >= SAMPLE_SET_COUNT;

  // 실행을 막는 첫 이유 하나 — 다른 실행 모달과 같은 방식으로 푸터에 세운다.
  const blockReason = !modelId
    ? t('evaluation.run.needModel')
    : !datasetId
      ? t('evaluation.run.needDataset')
      : allSetsTaken
        ? t('evaluation.expert.sampleSetAllTaken')
        : !sampleSet
          ? t('evaluation.expert.needSampleSet')
          : !playgroundId
            ? t('evaluation.bench.needDeployment')
            : null;

  const submit = {
    text: 'evaluation.expert.inferStart',
    func: () =>
      onConfirm({
        // 출처는 배포 하나뿐 — 상위가 inference_playground_id 로 싣는다.
        inferencePlaygroundId: Number(playgroundId),
        modelId,
        datasetId,
        // 세트가 구간(offset·개수)을 정한다 — BE 가 (N-1)*100 부터 100개를 잘라 준다.
        sampleSet: Number(sampleSet),
        // 빈 입력은 undefined 로 — BE 가 '미입력'으로 보고 기본값으로 폴백한다.
        runName: runName.trim() || undefined,
        expertPrompt: guideline.trim() || undefined,
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
        <div className={cx('run-form')}>
          {/* ⓪ 채점할 모델·데이터셋 — 이 세션이 무엇을 재는지. 배포 선택보다 앞선다. */}
          <div className={cx('run-sec')}>
            <p className={cx('run-sec-title')}>
              {t('evaluation.run.subjectTitle')}
            </p>
            <div className={cx('run-field')}>
              <span className={cx('run-label')}>
                {t('evaluation.selectModel')}
                <span className={cx('req')}>*</span>
              </span>
              {(modelOptions || []).length === 0 ? (
                <p className={cx('run-hint', 'err')}>
                  {t('evaluation.compare.noModels')}
                </p>
              ) : (
                <Selectbox
                  list={modelOptions}
                  selectedItem={selectedModel}
                  placeholder={t('select.label')}
                  onChange={(item) => pickModel(item.value)}
                  customStyle={{
                    selectboxForm: { width: '100%' },
                    listForm: { width: '100%' },
                  }}
                />
              )}
            </div>
            <div className={cx('run-field')}>
              <span className={cx('run-label')}>
                {t('evaluation.selectDatasets')}
                <span className={cx('req')}>*</span>
              </span>
              {(datasetOptions || []).length === 0 ? (
                <p className={cx('run-hint', 'err')}>
                  {t('evaluation.noDatasets')}
                </p>
              ) : (
                <Selectbox
                  type='search'
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
            </div>
            <div className={cx('run-field')}>
              <span className={cx('run-label')}>
                {t('evaluation.expert.sampleSet')}
                <span className={cx('req')}>*</span>
              </span>
              <Selectbox
                list={sampleSetOptions}
                selectedItem={selectedSampleSet}
                placeholder={t('select.label')}
                onChange={(item) => {
                  if (item.disabled) return; // 이미 잡힌 세트 — 표시만 하고 선택은 막는다
                  setSampleSet(item.value);
                }}
                customStyle={{
                  selectboxForm: { width: '100%' },
                  listForm: { width: '100%' },
                }}
              />
              {allSetsTaken && (
                <p className={cx('run-hint', 'err')}>
                  {t('evaluation.expert.sampleSetAllTaken')}
                </p>
              )}
            </div>
          </div>

          {/* ① 출력을 어디서 가져오나 — 실행 중 배포(전문가가 여는 샘플만 지연 실추론).
              고르지 않으면 시작할 수 없다: 예시 출력으로 채점하던 폴백은 사라졌다.
              빈 상태가 두 갈래(이 모델용 배포만 없음 / 워크스페이스에 아무 배포도 없음)라
              선택 상자를 disabled 로 세우는 대신 판정이 끝난 뒤 문구를 갈라 렌더한다. */}
          <div className={cx('run-sec')}>
            <p className={cx('run-sec-title')}>
              {t('evaluation.run.sourceTitle')}
              <span className={cx('req')}>*</span>
            </p>
            <div className={cx('run-field')}>
              {!modelId ? (
                <p className={cx('run-hint')}>
                  {t('evaluation.run.sourceNeedModel')}
                </p>
              ) : loading ? (
                <p className={cx('run-hint')}>
                  {t('evaluation.project.loading')}
                </p>
              ) : deploymentOptions.length === 0 ? (
                <EmptyBox
                  text={
                    anyRunning
                      ? 'evaluation.run.sourceNoneForModel'
                      : 'evaluation.run.sourceNone'
                  }
                  isBox
                  customStyle={{
                    minHeight: '96px',
                    padding: '12px 14px',
                    boxSizing: 'border-box',
                  }}
                />
              ) : (
                <>
                  <Selectbox
                    list={deploymentOptions}
                    selectedItem={selectedDeployment}
                    placeholder={t('select.label')}
                    onChange={(item) => setPlaygroundId(item.value)}
                    customStyle={{
                      selectboxForm: { width: '100%' },
                      listForm: { width: '100%' },
                    }}
                  />
                  {deployment && (
                    <ul className={cx('run-meta')}>
                      {deployment.description && (
                        <li>{deployment.description}</li>
                      )}
                      <li>{deployment.deploy_type || 'cluster'}</li>
                    </ul>
                  )}
                </>
              )}
            </div>
            <p className={cx('run-note')}>
              {t('evaluation.bench.targetDeployNote')}
            </p>
          </div>

          {/* ② 세션 정보 — 둘 다 선택. 제목은 run 목록과 채점 진행 헤더의 표시원이고,
              지침은 채점 화면 상단 '평가 지침' 박스에 그대로 뜬다. 비우면 BE 가
              기본값(제목=데이터셋명 / 지침=시나리오 기본 지침)으로 폴백한다. */}
          <div className={cx('run-sec')}>
            <p className={cx('run-sec-title')}>
              {t('evaluation.expert.sessionSection')}
            </p>
            <div className={cx('run-field')}>
              <span className={cx('run-label')}>
                {t('evaluation.expert.runName')}
                <span className={cx('opt')}>{t('optional.label')}</span>
              </span>
              <InputText
                size='medium'
                value={runName}
                placeholder={t('evaluation.expert.runNamePlaceholder')}
                onChange={(event) => setRunName(event.target.value)}
                onClear={() => setRunName('')}
                disableLeftIcon
                options={{ autoComplete: 'off', maxLength: 100 }}
                customStyle={{ width: '100%' }}
              />
            </div>
            <div className={cx('run-field')}>
              <span className={cx('run-label')}>
                {t('evaluation.expert.guideline')}
                <span className={cx('opt')}>{t('optional.label')}</span>
              </span>
              <Textarea
                size='large'
                maxLength={2000}
                options={{ id: 'expert-guideline', rows: 4 }}
                placeholder={t('evaluation.expert.guidelinePlaceholder')}
                value={guideline}
                onChange={(event) => setGuideline(event.target.value)}
                customStyle={{ width: '100%', minHeight: '96px' }}
              />
            </div>
          </div>
        </div>
      </NewStyleModalFrame>
    </div>
  );
};

export default ExpertInferenceModal;
