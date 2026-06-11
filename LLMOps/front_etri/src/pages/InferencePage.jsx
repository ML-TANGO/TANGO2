import { useState, useEffect } from 'react';
import { useHistory, useLocation } from 'react-router-dom';
import { callApi, STATUS_SUCCESS } from '@src/network';
import classNames from 'classnames/bind';
import style from './InferencePage.module.scss';
import NewInferenceWizard from '@src/components/Modal/NewInferenceWizard/NewInferenceWizard';

const cx = classNames.bind(style);

const STATUS_META = {
  ready:   { label: '준비',   color: '#00c775' },
  running: { label: '실행 중', color: '#ffc500' },
  error:   { label: '오류',   color: '#fa4e57' },
};

export default function InferencePage() {
  const history  = useHistory();
  const location = useLocation();
  const wid      = location.pathname.split('/')[3];

  const [sessions, setSessions]       = useState([]);
  const [loading, setLoading]         = useState(true);
  const [wizardOpen, setWizardOpen]   = useState(false);

  useEffect(() => {
    callApi({ url: `inference/sessions?workspace_id=${wid}`, method: 'GET' }).then((res) => {
      if (res.status === STATUS_SUCCESS) {
        setSessions(Array.isArray(res.result) ? res.result : []);
      }
      setLoading(false);
    });
  }, [wid]);

  const handleCreate = (session) => {
    setSessions((prev) => [session, ...prev]);
    setWizardOpen(false);
  };

  return (
    <div className={cx('page')}>
      <div className={cx('title-bar')}>
        <h1 className={cx('title')}>추론</h1>
        <span className={cx('sub')}>학습된 모델을 조합하고 쿠버네티스 자원을 할당하여 추론을 테스트합니다.</span>
      </div>

      {loading ? (
        <div className={cx('loading')}>로딩 중...</div>
      ) : (
        <div className={cx('card-grid')}>
          <div className={cx('create-card')} onClick={() => setWizardOpen(true)}>
            <span className={cx('create-plus')}>＋</span>
            <span className={cx('create-label')}>새 추론 생성</span>
          </div>
          {sessions.map((s) => {
            const infModel   = s.models?.find((m) => m.role === 'inference');
            const promptModel = s.models?.find((m) => m.role === 'prompt');
            const st = STATUS_META[s.status] ?? STATUS_META.ready;
            return (
              <div
                key={s.id}
                className={cx('session-card')}
                onClick={() => history.push(`/user/workspace/${wid}/inference/${s.id}`)}
              >
                <div className={cx('card-top')}>
                  <span className={cx('session-name')}>{s.name}</span>
                  <span className={cx('status')} style={{ color: st.color }}>● {st.label}</span>
                </div>

                <div className={cx('model-row')}>
                  {promptModel && (
                    <span className={cx('model-tag', 'prompt')}>
                      📝 {promptModel.name}
                    </span>
                  )}
                  {infModel && (
                    <span className={cx('model-tag', 'inference')}>
                      🤖 {infModel.name}
                    </span>
                  )}
                </div>

                <div className={cx('res-row')}>
                  <span className={cx('res-chip')}>{s.resources?.gpu}</span>
                  <span className={cx('res-chip')}>CPU {s.resources?.cpu}코어</span>
                  <span className={cx('res-chip')}>{s.resources?.memory}</span>
                </div>

                <div className={cx('mode-badge', s.mode)}>
                  {s.mode === 'dual' ? '이중 모델' : '단일 모델'}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {wizardOpen && (
        <NewInferenceWizard
          wid={wid}
          onClose={() => setWizardOpen(false)}
          onCreate={handleCreate}
        />
      )}
    </div>
  );
}
