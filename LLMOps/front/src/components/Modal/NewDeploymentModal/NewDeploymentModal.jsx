import { useCallback, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory } from 'react-router-dom';
import { toast } from 'react-toastify';

import { InputText, Textarea } from '@jonathan/ui-react';

import Radio from '@src/components/atoms/input/Radio';
import AccessOwnerSelect from '@src/components/molecules/AccessOwnerSelect';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiSelect from '@src/components/molecules/MultiSelect';

// 이름 검증은 AddPlayground(구 생성 모달)의 규칙을 그대로 재사용 — 배포명 규약 일관성 유지.
import {
  calFooterMessage,
  calNameError,
} from '@src/components/Modal/AddPlayground/AddPlayground';
import {
  getPlaygroundOwner,
  postDualShell,
  postPlayground,
} from '@src/apis/llm/playground';
import useOwnerList from '@src/hooks/useOwnerList';
import { SHOW_DUAL_DEPLOY } from '@src/featureFlags';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './NewDeploymentModal.module.scss';

const cx = classNames.bind(style);

const EMPTY_LIST = [];
const DUAL_NAME_MAX_LENGTH = 20;

// 배포 대상(playground.deploy_type) 4종 — 라벨은 i18n(deploymentTarget.*.label).
// Radio 는 isTranLabel 기본값이 true 라 라벨 키를 그대로 넘기면 내부에서 번역한다
// (접근 권한 AccessOwnerSelect 의 accessOption 과 같은 관용구).
const TARGET_OPTIONS = [
  { value: 'cluster', label: 'deploymentTarget.cluster.label' },
  { value: 'edge', label: 'deploymentTarget.edge.label' },
  { value: 'standalone', label: 'deploymentTarget.standalone.label' },
  { value: 'remote_api', label: 'deploymentTarget.remote_api.label' },
].map((o) => ({
  ...o,
  labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
}));

// 배포 유형별 상세 라우팅(생성 셸 → 유형별 구성 화면). PlaygroundMenu 의 detailPath 규칙과 동일.
const detailPath = (wid, kind, id) => {
  if (kind === 'edge') return `/user/workspace/${wid}/edge-deploy/${id}`;
  if (kind === 'standalone')
    return `/user/workspace/${wid}/standalone-deploy/${id}`;
  if (kind === 'remote_api')
    return `/user/workspace/${wid}/remote-api-deploy/${id}`;
  return `/user/workspace/${wid}/llmplayground/${id}/llmplayground`;
};

// 배포 생성 모달(D6 v3) — 플랫폼 표준 단일 모달. 단일/이중 모두 '무엇을 만들지'만 받고,
//   모델·자원 선택은 생성 후 상세 화면에서(단일=llmplayground 상세, 이중=/dual-deploy 상세).
//   [단일] 배포 대상 + 이름/설명/공개범위/소유자 → POST /playgrounds(셸) → 유형별 상세.
//   [이중] 이름/설명/공개범위/소유자/사용자 → shell 생성 → 이중 배포 상세(LLM1/LLM2·GPU 선택).
const NewDeploymentModal = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const { workspace_id, handleRefresh } = data;

  const [mode, setMode] = useState('single'); // 'single' | 'dual'
  const [name, setName] = useState('');

  // 단일 모드
  const [target, setTarget] = useState(null);
  const [description, setDescription] = useState('');
  const [isAccess, setIsAccess] = useState(1);
  const { ownerList, owner, handleOwner } = useOwnerList(
    getPlaygroundOwner,
    workspace_id,
  );
  const userList = useRef([]);
  const handleSelectedUserList = useCallback((selectedList) => {
    userList.current = selectedList.map((info) => info.value);
  }, []);
  const handleIsAccess = useCallback((e) => {
    setIsAccess(+e.target.value);
  }, []);

  const nameError = calNameError(name);
  // 이중은 -promptgen 파생명이 DB VARCHAR(32)에 온전히 들어가도록 부모 이름을 20자로 제한한다.
  const singleFooter = calFooterMessage(name, nameError);
  const dualFooter =
    singleFooter ||
    (name.trim().length > DUAL_NAME_MAX_LENGTH
      ? '이중모델 배포 이름은 20자 이하로 입력해 주세요.'
      : '');
  const footerMessage = mode === 'dual' ? dualFooter : singleFooter;

  const validate =
    mode === 'single'
      ? !!target && !singleFooter && !!owner?.value
      : // 이중 세션명도 child 배포명(-promptgen)으로 파생 → 단일과 동일 규약 적용.
        name.trim().length > 0 && !dualFooter && !!owner?.value;

  const createSingle = async () => {
    const res = await postPlayground({
      workspace_id,
      name,
      description,
      access: isAccess,
      owner_id: owner?.value,
      user_id: userList.current,
      deploy_type: target, // cluster | edge | standalone (배포 유형 영속)
    });
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return false; // 실패 → 프레임 유지(footerMessage 노출)
    }
    // BE 가 생성 id 를 반환 — 목록 재조회+이름매칭(동명 경합 시 타 배포로 진입) 하지 않는다.
    await handleRefresh?.();
    const createdId = Number(res.result?.playground_id);
    if (createdId > 0) {
      history.push(detailPath(workspace_id, target, createdId));
    } else {
      // 생성 성공했으나 id 특정 실패 → 목록에서 확인하도록 안내(무신호 close 방지).
      toast.success('배포가 생성되었습니다. 목록에서 확인해 주세요.');
    }
    return true; // 성공 → 프레임 자동 close
  };

  const createDual = async () => {
    // 셸만 생성(모델/자원 없음) → 이중 배포 상세에서 LLM1/LLM2·GPU 선택 후 배포(provision).
    const res = await postDualShell({
      workspace_id,
      name: name.trim(),
      description,
      access: isAccess,
      owner_id: owner?.value,
      user_id: userList.current,
    });
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return false;
    }
    await handleRefresh?.();
    const newId = Number(res.result?.session_playground_id);
    if (newId > 0) {
      history.push(
        `/user/workspace/${workspace_id}/llmplayground/${newId}/dual-deploy`,
      );
    } else {
      toast.success(
        '이중모델 세션이 생성되었습니다. 배포 목록에서 확인해 주세요.',
      );
    }
    return true;
  };

  const handleSubmit = () =>
    mode === 'single' ? createSingle() : createDual();

  return (
    <NewStyleModalFrame
      title={t('deployment.create.title')}
      type={type}
      submit={{ text: t('create.label'), func: handleSubmit }}
      cancel={{ text: t('cancel.label') }}
      validate={validate}
      isResize={true}
      isMinimize={true}
      footerMessage={footerMessage}
    >
      <div className={cx('form')}>
        {/* 단일 / 이중 모드 선택 — 이중을 감추면 선택지가 하나뿐이라 탭 줄 자체를 숨긴다. */}
        {SHOW_DUAL_DEPLOY && (
          <div className={cx('mode-tabs')}>
            <button
              type='button'
              className={cx('mode-tab', mode === 'single' && 'active')}
              aria-pressed={mode === 'single'}
              onClick={() => setMode('single')}
            >
              단일 모델
            </button>
            <button
              type='button'
              className={cx('mode-tab', mode === 'dual' && 'active')}
              aria-pressed={mode === 'dual'}
              onClick={() => setMode('dual')}
            >
              이중 모델
            </button>
          </div>
        )}

        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={
              mode === 'dual' ? '세션 이름' : t('playground.name.label')
            }
            labelSize='large'
            disableErrorMsg
          >
            <InputText
              placeholder={t('playground.add.name.placeholder')}
              onChange={(e) => setName(e.target.value)}
              name='deployment-name'
              value={name}
              status={footerMessage ? 'error' : 'default'}
              options={{
                maxLength: mode === 'dual' ? DUAL_NAME_MAX_LENGTH : 50,
              }}
              autoFocus={true}
              customStyle={{ fontSize: '14px' }}
              disableLeftIcon
              disableClearBtn
            />
          </InputBoxWithLabel>
        </div>

        {mode === 'single' && (
          <InputBoxWithLabel
            labelText='배포 대상'
            labelSize='large'
            disableErrorMsg
          >
            <Radio
              name='deployTarget'
              value={target}
              options={TARGET_OPTIONS}
              onChange={(e) => setTarget(e.target.value)}
              customStyle={{ marginTop: '16px' }}
              isLabelColor
            />
          </InputBoxWithLabel>
        )}

        <InputBoxWithLabel
          labelText={t('playground.add.desc.label')}
          optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <Textarea
            size='large'
            placeholder={t('playground.add.desc.placeholder')}
            value={description}
            name='description'
            onChange={(e) => setDescription(e.target.value)}
            customStyle={{ fontSize: '14px', height: '120px' }}
            isShowMaxLength
          />
        </InputBoxWithLabel>

        <AccessOwnerSelect
          isAccess={isAccess}
          handleInputs={handleIsAccess}
          ownerValue={owner?.value}
          ownerList={ownerList}
          handleOwner={handleOwner}
        />
        {isAccess === 0 && (
          <MultiSelect
            label='users.label'
            listLabel='availableUsers.label'
            selectedLabel='chosenUsers.label'
            list={ownerList}
            selectedList={EMPTY_LIST}
            onChange={({ selectedList }) =>
              handleSelectedUserList(selectedList)
            }
            exceptItem={owner && owner.value}
            optional
          />
        )}

        {mode === 'dual' && (
          <p className={cx('note')}>
            이중 모델(프롬프트 생성 LLM1 + 추론 LLM2) 세션을 만듭니다. 생성 후
            배포 상세 화면에서 LLM1/LLM2 모델과 GPU 자원을 선택해 배포합니다.
            (클러스터 전용)
          </p>
        )}
      </div>
    </NewStyleModalFrame>
  );
};

export default NewDeploymentModal;
