import { useEffect, useState } from 'react';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import { ButtonV2, Textarea } from '@jonathan/ui-react';

import {
  getDeploymentApi,
  publishDeploymentApi,
  rotateDeploymentApiKey,
  unpublishDeploymentApi,
} from '@src/apis/flightbase/deployment';
import { handleOpenPopup } from '@src/store/modules/popupState';
import { STATUS_INTERNAL_SERVER_ERROR, STATUS_SUCCESS } from '@src/network';

import { copyToClipboardWithToast } from '@src/utils';

import PlaygroundFrame from '../PlaygroundFrame';
import { calIsCompleteRunning } from '../PlaygroundHeader/PlaygroundButtonCont/util';

import classNames from 'classnames/bind';
import style from './PlaygroundExternalApi.module.scss';

const cx = classNames.bind(style);

// 키 마스킹 — 앞 4 / 뒤 4 만 노출, 나머지 •. 짧은 키는 전부 가림.
const maskKey = (key) => {
  if (!key) return '';
  if (key.length <= 8) return '••••••••';
  return `${key.slice(0, 4)}${'•'.repeat(6)}${key.slice(-4)}`;
};

// [API 호출] 통합 카드 — Playground 상세.
//   요청 JSON 포맷(항상) + 엔드포인트: 게시 시 외부(엔드포인트+키+curl) / 미게시 시 게시 버튼(내부 호출 URL 은 비노출).
//   외부 게시(D6)는 deployment_id(=fb_deployment PK) 있는 배포만 대상(Kong key-auth + ACL, 키 원본은 Kong 보관→라이브 fetch).
export default function PlaygroundExternalApi() {
  const dispatch = useDispatch();

  const { deployment_id: deploymentId } = useSelector(
    (state) => state.llmPlayground.info,
    shallowEqual,
  );
  const status = useSelector(
    (state) => state.llmPlayground.status,
    shallowEqual,
  );
  const isCompleteRunning = calIsCompleteRunning(status);
  const statusType = status?.status;

  // 요청 body 스키마(JSON 포맷)만 사용 — 내부 호출 URL 은 화면 비노출(사용자向 외부 게시 엔드포인트만 표출).
  const { format } = useSelector(
    (state) => state.llmPlayground.info_request,
    shallowEqual,
  );
  const formatJson = JSON.stringify(format, null, 2);

  const [loading, setLoading] = useState(true);
  const [info, setInfo] = useState(null); // 게시정보 or null(미게시)
  const [busy, setBusy] = useState(false);
  const [revealed, setRevealed] = useState(false);

  // 게시 상태 조회 — deployment_id 확정 시 1회 (SSE 로 deployment_id 가 채워지면 재조회).
  useEffect(() => {
    // 배포 없음 → 외부 게시 조회 skip. 내부 URL/JSON 만 표시.
    if (!deploymentId) {
      setInfo(null);
      setLoading(false);
      return undefined;
    }
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const res = await getDeploymentApi(deploymentId);
        if (!alive) return;
        if (res.status === STATUS_SUCCESS) {
          setInfo(res.result);
        } else {
          // status=0(미게시)은 정상 상태 → 조용히 처리. 전송/서버 오류만 토스트로 노출.
          setInfo(null);
          if (res.status === STATUS_INTERNAL_SERVER_ERROR) {
            toast.error(res.message || '게시 상태를 불러오지 못했습니다.');
          }
        }
        setRevealed(false);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [deploymentId]);

  const handlePublish = async () => {
    if (busy || !deploymentId) return;
    setBusy(true);
    try {
      const res = await publishDeploymentApi(deploymentId);
      if (res.status === STATUS_SUCCESS) {
        setInfo(res.result);
        setRevealed(true);
        toast.success('외부 API가 게시되었습니다.');
      } else {
        toast.error(res.message || '게시에 실패했습니다.');
      }
    } finally {
      setBusy(false);
    }
  };

  const handleRotate = () => {
    dispatch(
      handleOpenPopup({
        type: 'delete',
        popupTitle: 'API 키 재발급',
        popupContents:
          '기존 키는 즉시 폐기되고 새 키가 발급됩니다. 이 배포를 사용 중인 클라이언트는 새 키로 교체해야 합니다.',
        cancelBtnLabel: '취소',
        submitBtnLabel: '재발급',
        handleSubmit: async () => {
          if (busy) return;
          setBusy(true);
          try {
            const res = await rotateDeploymentApiKey(deploymentId);
            if (res.status === STATUS_SUCCESS) {
              setInfo((prev) => ({ ...prev, api_key: res.result.api_key }));
              setRevealed(true);
              toast.success('새 API 키가 발급되었습니다.');
            } else {
              toast.error(res.message || '키 재발급에 실패했습니다.');
            }
          } finally {
            setBusy(false);
          }
        },
      }),
    );
  };

  const handleUnpublish = () => {
    dispatch(
      handleOpenPopup({
        type: 'delete',
        popupTitle: '외부 API 게시 해제',
        popupContents:
          '외부 엔드포인트와 API 키가 삭제됩니다. 게시된 URL 로의 요청은 더 이상 인증되지 않습니다.',
        cancelBtnLabel: '취소',
        submitBtnLabel: '게시 해제',
        handleSubmit: async () => {
          if (busy) return;
          setBusy(true);
          try {
            const res = await unpublishDeploymentApi(deploymentId);
            if (res.status === STATUS_SUCCESS) {
              setInfo(null);
              setRevealed(false);
              toast.success('게시가 해제되었습니다.');
            } else {
              toast.error(res.message || '게시 해제에 실패했습니다.');
            }
          } finally {
            setBusy(false);
          }
        },
      }),
    );
  };

  const published = !!(info && info.enabled);

  return (
    <PlaygroundFrame style={{ backgroundColor: '#fff' }}>
      <div className={cx('header')}>
        <h3 className={cx('title')}>API 호출</h3>
        {deploymentId && (
          <span className={cx('badge', published ? 'on' : 'off')}>
            {published ? '게시됨' : '미게시'}
          </span>
        )}
      </div>

      {/* 요청 JSON 포맷 — 어느 경로든 요청 body 스키마이므로 항상 표시 */}
      <div className={cx('field')}>
        <span className={cx('label')}>요청 JSON 포맷</span>
        {statusType === 'stop' ? (
          <p className={cx('desc')}>
            배포가 활성화되면 JSON 포맷이 생성됩니다.
          </p>
        ) : (
          <Textarea
            value={formatJson}
            customStyle={{
              color: '#747474',
              width: '100%',
              minHeight: '140px',
            }}
          />
        )}
      </div>

      {loading ? (
        <p className={cx('desc')}>불러오는 중…</p>
      ) : published ? (
        <div className={cx('published')}>
          <div className={cx('field')}>
            <span className={cx('label')}>엔드포인트</span>
            <div className={cx('value-row')}>
              <span className={cx('value', 'mono')}>{info.endpoint}</span>
              <button
                type='button'
                className={cx('copy-btn')}
                onClick={() => copyToClipboardWithToast(info.endpoint)}
              >
                복사
              </button>
            </div>
          </div>

          <div className={cx('field')}>
            <span className={cx('label')}>API 키 (헤더 {info.key_name})</span>
            <div className={cx('value-row')}>
              <span className={cx('value', 'mono')}>
                {revealed ? info.api_key : maskKey(info.api_key)}
              </span>
              <button
                type='button'
                className={cx('link-btn')}
                aria-pressed={revealed}
                onClick={() => setRevealed((v) => !v)}
              >
                {revealed ? '숨기기' : '표시'}
              </button>
              <button
                type='button'
                className={cx('copy-btn')}
                onClick={() => copyToClipboardWithToast(info.api_key)}
              >
                복사
              </button>
            </div>
          </div>

          {info.published_at && (
            <div className={cx('field')}>
              <span className={cx('label')}>게시 일시</span>
              <span className={cx('value')}>{info.published_at}</span>
            </div>
          )}

          <p className={cx('hint')}>
            요청 헤더에 <code>{info.key_name}: &lt;API 키&gt;</code> 를 넣어 위
            엔드포인트를 호출합니다.
          </p>

          <div className={cx('actions')}>
            <ButtonV2
              colorType='skyblue'
              label='키 재발급'
              onClick={handleRotate}
              disabled={busy}
            />
            <ButtonV2
              colorType='red'
              label='게시 해제'
              onClick={handleUnpublish}
              disabled={busy}
            />
          </div>
        </div>
      ) : (
        <div className={cx('unpublished')}>
          {deploymentId ? (
            <>
              <p className={cx('desc')}>
                이 배포를 외부에서 호출할 수 있는 공개 엔드포인트와 API 키를
                발급합니다. 키 인증(Kong)이 적용되어 발급된 키로만 접근할 수
                있습니다.
              </p>
              {!isCompleteRunning && (
                <p className={cx('hint')}>
                  배포가 실행 중일 때 게시할 수 있습니다.
                </p>
              )}
              <div className={cx('actions')}>
                <ButtonV2
                  colorType='blue'
                  label='외부 API 게시'
                  onClick={handlePublish}
                  disabled={!isCompleteRunning || busy}
                  isLoading={busy}
                />
              </div>
            </>
          ) : (
            <p className={cx('desc')}>
              배포를 실행한 뒤 외부 API를 게시하면 호출 엔드포인트가 표시됩니다.
            </p>
          )}
        </div>
      )}
    </PlaygroundFrame>
  );
}
