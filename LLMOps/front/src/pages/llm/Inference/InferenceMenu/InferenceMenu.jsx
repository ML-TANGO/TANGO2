import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { getPlayground } from '@src/apis/llm/playground';
import useIntervalCall from '@src/hooks/useIntervalCall';
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

// 추론(Inference) 랜딩 — consume 레이어(목록·상세만, 생성 진입점 없음).
//   이중모델 세션(mode==='dual', WBS 4.2/4.3)은 전 상태 노출(생성 직후 준비중 추적),
//   단일 배포는 running 만 노출(질의 가능). 세션 생성은 배포 탭(NewDeploymentModal)에서.
//   자식(프롬프트생성) playground 는 BE(get_playground_list)가 목록에서 숨김.
const InferenceMenu = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const match = useRouteMatch();
  const history = useHistory();
  const { id: workspaceId } = match.params;

  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchSessions = useCallback(async () => {
    const res = await getPlayground(workspaceId);
    if (res.status === STATUS_SUCCESS) {
      const list = Array.isArray(res.result) ? res.result : [];
      // 프로비저닝된 이중 세션(prompt_gen_playground_id 링크됨) = 전 상태 노출(준비중 추적) /
      //   단일 배포 = running 만(질의 가능). 미프로비저닝 이중 셸은 배포 탭(구성/배포) 소관 → 제외.
      setSessions(
        list.filter(
          (d) =>
            (d.mode === 'dual' && d.prompt_gen_playground_id) ||
            (d.mode !== 'dual' && d.status === 'running'),
        ),
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

  // 준비 중(installing) 세션이 실행 중으로 바뀌는 것을 자동 반영 — 5s 폴링(탭 비활성 시 자동 정지).
  const pollSessions = useCallback(async () => {
    await fetchSessions();
    return true;
  }, [fetchSessions]);

  useIntervalCall(pollSessions, 5000);

  const openInference = (id) => {
    history.push(`/user/workspace/${workspaceId}/inference/${id}`);
  };

  return (
    <div className={cx('inference-cont')}>
      <div className={cx('title-bar')}>
        <h1 className={cx('title')}>{t('Inference')}</h1>
        <span className={cx('sub')}>
          생성된 배포(단일·이중모델)로 추론을 수행합니다. 새 배포는 배포 탭에서
          생성합니다.
        </span>
      </div>

      {loading ? null : sessions.length === 0 ? (
        <div className={cx('empty-state')}>
          <p>생성된 추론 세션이 없습니다.</p>
          <p className={cx('empty-state-hint')}>
            배포 탭에서 단일·이중모델 배포를 생성하세요.
          </p>
        </div>
      ) : (
        <div className={cx('card-grid')}>
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
    </div>
  );
};

export default InferenceMenu;
