import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { toast } from 'react-toastify';

import { ButtonV2 } from '@jonathan/ui-react';

import { STATUS_SUCCESS } from '@src/network';
import {
  getEdgeOpsToken,
  retireEdgeOpsTokenPrev,
  rotateEdgeOpsToken,
} from '@src/apis/flightbase/edge';
import { copyToClipboardWithToast } from '@src/utils';

import classNames from 'classnames/bind';
import style from './EdgeOpsToken.module.scss';

const cx = classNames.bind(style);

const MASK = '••••••••••••••••••••';

/**
 * ops 토큰 패널 (admin) — 플랫폼이 디바이스의 /ops·/metrics 를 부를 때 제시하는 공유 키.
 *
 * 디바이스별 토큰(워커 상세의 [토큰 발급])과 다른 물건이다. 그쪽은 디바이스가 자신을
 * 증명하는 값이라 1회만 노출하지만, 이 키는 **전 디바이스 공통**이라 조회를 허용한다 —
 * 1회 표시로 만들면 디바이스를 한 대 추가할 때마다 전체를 재발급해야 한다.
 *
 * 재발급은 무중단이다: 기존 키가 prev 로 내려가 아직 교체하지 않은 디바이스가 계속
 * 동작하고, 전부 교체한 뒤 [옛 키 폐기] 로 닫는다.
 */
const EdgeOpsToken = () => {
  const { t } = useTranslation();
  const [info, setInfo] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);

  // 실패를 삼키면 아래 `if (!info)` 에서 패널이 통째로 사라진다. 게이트웨이가 SPA HTML 을
  // 200 으로 돌려주는 사고가 실제로 있었고, 그때 화면에는 아무 단서도 남지 않았다.
  // 로딩중(info=null)과 실패(loadError)를 갈라서 실패는 반드시 눈에 보이게 한다.
  const load = useCallback(async () => {
    const { status, result, message } = await getEdgeOpsToken();
    if (status === STATUS_SUCCESS) {
      setInfo(result);
      setLoadError(null);
      return;
    }
    setLoadError(message || t('edge.opsToken.loadFail'));
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  const onRotate = useCallback(async () => {
    if (!window.confirm(t('edge.opsToken.rotateConfirm'))) return;
    setBusy(true);
    const { status, message } = await rotateEdgeOpsToken();
    setBusy(false);
    if (status === STATUS_SUCCESS) {
      setRevealed(true); // 새 값을 바로 복사할 수 있게 연다
      toast.success(t('edge.opsToken.rotated'));
      load();
    } else {
      toast.error(message || t('edge.opsToken.rotateFail'));
    }
  }, [t, load]);

  const onRetire = useCallback(async () => {
    if (!window.confirm(t('edge.opsToken.retireConfirm'))) return;
    setBusy(true);
    const { status, message } = await retireEdgeOpsTokenPrev();
    setBusy(false);
    if (status === STATUS_SUCCESS) {
      toast.success(t('edge.opsToken.retired'));
      load();
    } else {
      toast.error(message || t('edge.opsToken.retireFail'));
    }
  }, [t, load]);

  // 조회 자체가 실패했으면 껍데기라도 띄워서 원인과 재시도 수단을 남긴다.
  if (loadError) {
    return (
      <div className={cx('panel')}>
        <div className={cx('head')}>
          <span className={cx('title')}>{t('edge.opsToken.title')}</span>
        </div>
        <div className={cx('hint', 'warn')}>{loadError}</div>
        <div className={cx('actions')}>
          <ButtonV2
            type='outline'
            size='s'
            label={t('edge.opsToken.retry')}
            onClick={() => load()}
          />
        </div>
      </div>
    );
  }

  if (!info) return null;

  return (
    <div className={cx('panel')}>
      <div className={cx('head')}>
        <span className={cx('title')}>{t('edge.opsToken.title')}</span>
        {info.rotating ? (
          <span className={cx('badge', 'rotating')}>
            {t('edge.opsToken.rotating')}
          </span>
        ) : null}
      </div>

      {info.configured ? (
        <>
          <div className={cx('row')}>
            <code className={cx('value')}>{revealed ? info.token : MASK}</code>
            <ButtonV2
              type='outline'
              size='s'
              label={t(revealed ? 'edge.opsToken.hide' : 'edge.opsToken.show')}
              onClick={() => setRevealed((v) => !v)}
            />
            <ButtonV2
              type='outline'
              size='s'
              label={t('edge.opsToken.copy')}
              onClick={() => copyToClipboardWithToast(info.token)}
            />
          </div>
          <div className={cx('hint')}>
            {t('edge.opsToken.applyHint')}
            <code className={cx('cmd')}>export OPS_TOKEN=&apos;…&apos;</code>
          </div>
        </>
      ) : (
        <div className={cx('hint')}>{t('edge.opsToken.notConfigured')}</div>
      )}

      {/* 회전 중에는 옛 키도 아직 통과한다 — 교체가 끝나면 닫아야 한다. */}
      {info.rotating ? (
        <div className={cx('hint', 'warn')}>{t('edge.opsToken.rotatingHint')}</div>
      ) : null}

      {/* Secret 이 아니라 파드 env 로만 설정된 설치는 화면에서 회전할 수 없다. */}
      {info.managed ? (
        <div className={cx('actions')}>
          <ButtonV2
            colorType='blue'
            size='s'
            disabled={busy}
            label={t('edge.opsToken.rotate')}
            onClick={onRotate}
          />
          {info.rotating ? (
            <ButtonV2
              type='outline'
              size='s'
              disabled={busy}
              label={t('edge.opsToken.retire')}
              onClick={onRetire}
            />
          ) : null}
        </div>
      ) : (
        <div className={cx('hint', 'warn')}>{t('edge.opsToken.unmanaged')}</div>
      )}
    </div>
  );
};

export default EdgeOpsToken;
