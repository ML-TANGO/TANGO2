import { useCallback, useEffect } from 'react';
import { useSelector } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';

/**
 * 라벨링 페이지
 *
 * 라벨링 도구(marker)는 별도 서비스(/marker)로 배포되어 새 창에서 열린다.
 * 진입 시 자동으로 marker 어노테이션 도구를 새 창으로 열고,
 * 다시 열 수 있는 버튼을 함께 제공한다.
 *
 * marker 는 동일 호스트의 /marker/auth 로 라우팅되므로(Kong) 별도 host 설정 불필요.
 */
export default function UserDatasetLabelingPage() {
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const auth = useSelector((state) => state.auth);
  const userName = auth?.userName;
  const workspaces = useSelector((state) => state.workspace?.workspaces) || [];

  const openMarker = useCallback(() => {
    const token = sessionStorage.getItem('token');
    const session = sessionStorage.getItem('loginedSession');
    const ws = workspaces.find((v) => v.id === Number(workspaceId));
    const workspaceName = ws?.name ?? '';
    const base = `${window.location.protocol}//${window.location.host}/marker/auth`;
    const query = `user=${userName}&token=${token}&session=${session}&workspaceId=${workspaceId}&workspaceName=${workspaceName}`;
    // marker /marker/auth 는 동일 호스트(same-origin)이며 user/token/session 쿼리로 인증하는
    // 기존 marker 연동 규약(useMoveToMarker.jsx, MarkerBtn.jsx)을 따른다.
    // noopener,noreferrer 로 새 창의 opener 접근 및 Referer 헤더를 통한 토큰 URL 유출을 차단한다.
    window.open(`${base}?${query}`, '_blank', 'noopener,noreferrer');
  }, [workspaces, workspaceId, userName]);

  useEffect(() => {
    openMarker();
  }, [openMarker]);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '16px',
        height: '60vh',
        color: '#5b5b5b',
      }}
    >
      <img
        src='/images/logo/BI_Marker.svg'
        alt='marker'
        style={{ height: '40px', opacity: 0.9 }}
      />
      <p style={{ fontSize: '15px' }}>
        라벨링 도구(MARKER)가 새 창에서 열렸습니다.
      </p>
      <p style={{ fontSize: '13px', color: '#9b9b9b' }}>
        창이 열리지 않았다면 아래 버튼을 눌러 다시 여세요.
      </p>
      <button
        type='button'
        onClick={openMarker}
        style={{
          padding: '10px 20px',
          fontSize: '14px',
          fontWeight: 600,
          color: '#fff',
          background: '#3d6df6',
          border: 'none',
          borderRadius: '6px',
          cursor: 'pointer',
        }}
      >
        라벨링 도구 열기
      </button>
    </div>
  );
}
