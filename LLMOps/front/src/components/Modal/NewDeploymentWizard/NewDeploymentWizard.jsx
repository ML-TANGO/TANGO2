import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useHistory } from 'react-router-dom';
import { toast } from 'react-toastify';

import AccessOwnerSelect from '@src/components/molecules/AccessOwnerSelect';
import MultiSelect from '@src/components/molecules/MultiSelect';

import {
  calFooterMessage,
  calNameError,
} from '@src/components/Modal/AddPlayground/AddPlayground';
import { getPlaygroundOwner, postPlayground } from '@src/apis/llm/playground';
import useOwnerList from '@src/hooks/useOwnerList';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './NewDeploymentWizard.module.scss';

const cx = classNames.bind(style);

// 배포(D6 v3) 생성 마법사 — ETRI 목업의 스텝 위저드 UI 를 우리 실 BE 로 재배선.
//   Step1 배포 대상(현재 클러스터 / 온디바이스 / 독립) → 클러스터만 계속, 나머지는 양자화 선행 안내(터미널).
//   Step2 배포 정보(이름·설명·공개범위·사용자) → Step3 확인 → POST /playgrounds (메타 셸 생성).
//   생성 후 상세화면으로 이동 = 모델 구성·자원 할당·배포 실행은 기존 상세 플로우 유지(2026-06-18 분리 결정:
//   모델 서빙 설정은 상세, 대상 분기만 위저드). 단일모델 배포는 dual-session 같은 원샷 콜이 아니라 셸→상세→배포다.
// chrome(step-bar/✕/Esc/in-flight 락)은 시블링 NewInferenceWizard 와 일치.
const STEPS = ['배포 대상', '배포 정보', '확인'];
const EMPTY_LIST = [];

const TARGETS = [
  {
    id: 'cluster',
    label: 'deploymentTarget.cluster.label',
    desc: 'deploymentTarget.cluster.desc',
  },
  {
    id: 'edge',
    label: 'deploymentTarget.edge.label',
    desc: 'deploymentTarget.edge.desc',
  },
  {
    id: 'standalone',
    label: 'deploymentTarget.standalone.label',
    desc: 'deploymentTarget.standalone.desc',
  },
];

const NewDeploymentWizard = ({ wid, onClose, onRefresh }) => {
  const { t } = useTranslation();
  const history = useHistory();

  const [step, setStep] = useState(1);

  // Step1 — 배포 대상
  const [target, setTarget] = useState(null);

  // Step2 — 배포 정보
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isAccess, setIsAccess] = useState(1);
  const { ownerList, owner, handleOwner } = useOwnerList(
    getPlaygroundOwner,
    wid,
  );
  const userList = useRef([]);
  // MultiSelect 는 remount(스텝 back-nav / access 토글) 때 selectedList prop 으로 재시드된다.
  // 빈 상수를 주면 mount effect 가 onChange([]) 로 선택을 지워버리므로, 실제 선택 객체를 state 로 보유해 되먹인다.
  const [selectedUsers, setSelectedUsers] = useState(EMPTY_LIST);

  const [creating, setCreating] = useState(false);
  const creatingRef = useRef(false); // 인플라이트 락(state 지연 더블서브밋 방지)
  const mountedRef = useRef(true); // 성공 후 onClose 언마운트 뒤 setState 방지

  const handleClose = useCallback(() => {
    if (creatingRef.current) return;
    onClose?.();
  }, [onClose]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') handleClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [handleClose]);

  useEffect(
    () => () => {
      mountedRef.current = false;
    },
    [],
  );

  const handleSelectedUserList = useCallback((selected) => {
    userList.current = selected.map((info) => info.value);
    // 내용이 동일하면 identity 를 유지해 MultiSelect 재시드 ↔ onChange 되먹임 루프를 끊는다.
    setSelectedUsers((prev) =>
      prev.length === selected.length &&
      prev.every((p, i) => p.value === selected[i].value)
        ? prev
        : selected,
    );
  }, []);

  const handleIsAccess = useCallback((e) => {
    setIsAccess(+e.target.value);
  }, []);

  const isNameError = calNameError(name);
  const footerMessage = calFooterMessage(name, isNameError);
  const isNameValid = !footerMessage;

  const canStep1 = target === 'cluster';
  // owner 는 useOwnerList 가 비동기로 채움 → 프리로드 전 빠른 생성 시 owner_id undefined 방지.
  const canCreate = canStep1 && isNameValid && !!owner?.value;
  const needsQuantize = target === 'edge' || target === 'standalone';

  const goToModel = () => {
    onClose?.();
    history.push(`/user/workspace/${wid}/model`);
  };

  const handleCreate = async () => {
    if (!canCreate || creatingRef.current) return;
    creatingRef.current = true;
    setCreating(true);
    try {
      const res = await postPlayground({
        workspace_id: wid,
        name,
        description,
        access: isAccess,
        owner_id: owner?.value,
        user_id: userList.current,
      });
      if (res.status !== STATUS_SUCCESS) {
        errorToastMessage(res.error, res.message);
        return;
      }
      // postPlayground 는 생성 id 를 직접 주지 않음 → 목록 재조회 후 name+desc 매칭.
      //   동명+동일설명 중복 시 첫 매칭이 기존 배포일 수 있어, 매칭들 중 최대 id(=방금 생성된 auto-increment PK)를 택한다.
      const list = (await onRefresh?.()) ?? [];
      const matches = list.filter(
        (el) => el.title === name && el.subTitle === description,
      );
      const created = matches.length
        ? matches.reduce((a, b) => (Number(b.id) > Number(a.id) ? b : a))
        : null;
      if (created) {
        history.push(
          `/user/workspace/${wid}/llmplayground/${created.id}/llmplayground`,
        );
      } else {
        // 생성은 성공(위 status 통과)했으나 재조회/매칭 실패 → 목록에서 확인하도록 안내(무신호 close 방지).
        toast.success('배포가 생성되었습니다. 목록에서 확인해 주세요.');
      }
      onClose?.();
    } catch (err) {
      errorToastMessage(null, '배포 생성 중 오류가 발생했습니다.');
    } finally {
      creatingRef.current = false;
      if (mountedRef.current) setCreating(false);
    }
  };

  const targetLabel = TARGETS.find((tg) => tg.id === target)?.label ?? null;

  return (
    <div className={cx('overlay')} onClick={handleClose}>
      <div
        className={cx('wizard')}
        role='dialog'
        aria-modal='true'
        aria-labelledby='deploy-wizard-title'
        onClick={(e) => e.stopPropagation()}
      >
        <div className={cx('header')}>
          <span className={cx('title')} id='deploy-wizard-title'>
            {t('deployment.create.title')}
          </span>
          <button
            type='button'
            className={cx('close-btn')}
            onClick={handleClose}
          >
            ✕
          </button>
        </div>

        {/* 단계 표시 */}
        <div className={cx('step-bar')}>
          {STEPS.map((label, i) => (
            <div
              key={label}
              className={cx(
                'step-item',
                step === i + 1 && 'active',
                step > i + 1 && 'done',
              )}
            >
              <div className={cx('step-circle')}>
                {step > i + 1 ? '✓' : i + 1}
              </div>
              <span className={cx('step-label')}>{label}</span>
              {i < STEPS.length - 1 && (
                <div className={cx('step-line', step > i + 1 && 'filled')} />
              )}
            </div>
          ))}
        </div>

        <div className={cx('body')}>
          {/* Step 1 — 배포 대상 */}
          {step === 1 && (
            <div className={cx('section')}>
              <div className={cx('target-grid')}>
                {TARGETS.map((tg) => (
                  <button
                    key={tg.id}
                    type='button'
                    className={cx(
                      'target-card',
                      target === tg.id && 'selected',
                    )}
                    onClick={() => setTarget(tg.id)}
                  >
                    <span className={cx('target-label')}>{t(tg.label)}</span>
                    <span className={cx('target-desc')}>{t(tg.desc)}</span>
                  </button>
                ))}
              </div>
              {needsQuantize && (
                <div className={cx('notice')}>
                  <p>{t('deployment.requiresQuantize')}</p>
                  <button
                    type='button'
                    className={cx('notice-btn')}
                    onClick={goToModel}
                  >
                    {t('goToModel.label')}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Step 2 — 배포 정보 (클러스터) */}
          {step === 2 && (
            <>
              <div className={cx('section')}>
                <h3 className={cx('section-title')}>
                  {t('playground.name.label')}
                </h3>
                <input
                  className={cx('name-input', isNameError && 'error')}
                  type='text'
                  maxLength={50}
                  autoFocus
                  aria-label={t('playground.name.label')}
                  placeholder={t('playground.add.name.placeholder')}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
                {footerMessage && <p className={cx('warn')}>{footerMessage}</p>}
              </div>
              <div className={cx('section')}>
                <h3 className={cx('section-title')}>
                  {t('playground.add.desc.label')}
                </h3>
                <textarea
                  className={cx('desc-input')}
                  maxLength={200}
                  aria-label={t('playground.add.desc.label')}
                  placeholder={t('playground.add.desc.placeholder')}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
              <div className={cx('section')}>
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
                    selectedList={selectedUsers}
                    onChange={({ selectedList }) =>
                      handleSelectedUserList(selectedList)
                    }
                    exceptItem={owner && owner.value}
                    optional
                    style={{ marginTop: '24px' }}
                  />
                )}
              </div>
            </>
          )}

          {/* Step 3 — 확인 */}
          {step === 3 && (
            <div className={cx('summary')}>
              <div className={cx('s-row')}>
                <span className={cx('s-key')}>{STEPS[0]}</span>
                <span className={cx('s-val')}>
                  {targetLabel ? t(targetLabel) : '-'}
                </span>
              </div>
              <div className={cx('s-row')}>
                <span className={cx('s-key')}>
                  {t('playground.name.label')}
                </span>
                <span className={cx('s-val')}>{name || '-'}</span>
              </div>
              <div className={cx('s-row')}>
                <span className={cx('s-key')}>
                  {t('playground.add.desc.label')}
                </span>
                <span className={cx('s-val')}>{description || '-'}</span>
              </div>
              <div className={cx('s-row')}>
                <span className={cx('s-key')}>공개 범위</span>
                <span className={cx('s-val')}>
                  {isAccess === 0 ? '지정 사용자' : '워크스페이스 전체'}
                </span>
              </div>
            </div>
          )}
        </div>

        <div className={cx('footer')}>
          {step > 1 && (
            <button
              type='button'
              className={cx('back-btn')}
              onClick={() => setStep((s) => s - 1)}
            >
              이전
            </button>
          )}
          <button
            type='button'
            className={cx('cancel-btn')}
            onClick={handleClose}
          >
            취소
          </button>
          {step < 3 ? (
            <button
              type='button'
              className={cx(
                'next-btn',
                ((step === 1 && !canStep1) || (step === 2 && !isNameValid)) &&
                  'disabled',
              )}
              disabled={
                (step === 1 && !canStep1) || (step === 2 && !isNameValid)
              }
              onClick={() => setStep((s) => s + 1)}
            >
              다음
            </button>
          ) : (
            <button
              type='button'
              className={cx(
                'create-btn',
                (!canCreate || creating) && 'disabled',
              )}
              disabled={!canCreate || creating}
              onClick={handleCreate}
            >
              {creating ? '생성 중...' : '생성'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default NewDeploymentWizard;
