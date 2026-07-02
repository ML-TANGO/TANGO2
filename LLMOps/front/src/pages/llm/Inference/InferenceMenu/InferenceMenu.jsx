import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { getPlayground } from '@src/apis/llm/playground';
import NewInferenceWizard from '@src/components/Modal/NewInferenceWizard/NewInferenceWizard';
import { startPath } from '@src/store/modules/breadCrumb';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './InferenceMenu.module.scss';

const cx = classNames.bind(style);

const STATUS_LABEL = {
  running: { label: '실행 중', cls: 'running' },
  installing: { label: '준비 중', cls: 'installing' },
  stop: { label: '정지', cls: 'stop' },
};

// 추론(Inference) 랜딩 — consume 레이어.
//   이중모델 세션(mode==='dual', WBS 4.2/4.3)은 전 상태 노출(생성 직후 준비중 추적),
//   단일 배포는 running 만 노출(질의 가능). "새 이중모델 세션" → NewInferenceWizard.
//   자식(프롬프트생성) playground 는 BE(get_playground_list)가 목록에서 숨김.
const InferenceMenu = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const match = useRouteMatch();
  const history = useHistory();
  const { id: workspaceId } = match.params;

  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [wizardOpen, setWizardOpen] = useState(false);

  const fetchSessions = useCallback(async () => {
    const res = await getPlayground(workspaceId);
    if (res.status === STATUS_SUCCESS) {
      const list = Array.isArray(res.result) ? res.result : [];
      // 이중모델 세션 = 전 상태 노출 / 단일 배포 = running 만(질의 가능)
      setSessions(
        list.filter((d) => d.mode === 'dual' || d.status === 'running'),
      );
      setLoading(false);
      return;
    }
    errorToastMessage(res.error, res.message);
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Inference' } }]));
    fetchSessions();
  }, [dispatch, fetchSessions]);

  const openInference = (id) => {
    history.push(`/user/workspace/${workspaceId}/inference/${id}`);
  };

  const handleCreated = (result) => {
    setWizardOpen(false);
    const newId = Number(result?.session_playground_id);
    if (newId > 0) {
      openInference(newId);
      return;
    }
    fetchSessions();
  };

  return (
    <div className={cx('inference-cont')}>
      <div className={cx('title-bar')}>
        <h1 className={cx('title')}>{t('Inference')}</h1>
        <span className={cx('sub')}>
          학습된 모델을 조합하고 자원을 할당하여 추론을 수행합니다.
        </span>
      </div>

      {loading ? null : (
        <div className={cx('card-grid')}>
          <div
            className={cx('create-card')}
            onClick={() => setWizardOpen(true)}
          >
            <span className={cx('create-plus')}>＋</span>
            <span className={cx('create-label')}>새 이중모델 세션</span>
          </div>

          {sessions.map((s) => {
            const st = STATUS_LABEL[s.status] ?? STATUS_LABEL.stop;
            const isDual = s.mode === 'dual';
            return (
              <div
                key={s.id}
                className={cx('session-card')}
                onClick={() => openInference(Number(s.id))}
              >
                <div className={cx('card-top')}>
                  <span className={cx('session-name')}>{s.name}</span>
                  <span className={cx('status', st.cls)}>● {st.label}</span>
                </div>
                <span className={cx('owner')}>{s.owner || '-'}</span>
                {isDual &&
                  (s.prompt_gen_model_name || s.inference_model_name) && (
                    <div className={cx('model-row')}>
                      {s.prompt_gen_model_name && (
                        <span className={cx('model-tag', 'prompt')}>
                          📝 {s.prompt_gen_model_name}
                        </span>
                      )}
                      {s.inference_model_name && (
                        <span className={cx('model-tag', 'inference')}>
                          🤖 {s.inference_model_name}
                        </span>
                      )}
                    </div>
                  )}
                <div className={cx('mode-badge', isDual && 'dual')}>
                  {isDual ? '프롬프트 + 추론 이중모델' : '단일 모델'}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {wizardOpen && (
        <NewInferenceWizard
          wid={workspaceId}
          onClose={() => setWizardOpen(false)}
          onCreate={handleCreated}
        />
      )}
    </div>
  );
};

export default InferenceMenu;
