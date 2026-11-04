import { useEffect } from 'react';
import { useHistory } from 'react-router-dom';

function usePreventWindowClose(status) {
  const history = useHistory();

  useEffect(() => {
    const handleBeforeUnload = (event) => {
      if (status) {
        event.preventDefault();
        event.returnValue = '';
      }
    };

    const unblock = history.block((location, action) => {
      if (status) {
        const confirmLeave = window.confirm(
          '작업이 진행 중입니다. 정말 페이지를 떠나시겠습니까?',
        );
        if (!confirmLeave) {
          return false;
        }
      }
      return true;
    });

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      unblock(); // Clean up the blocking when the component is unmounted or when the status changes
    };
  }, [status, history]);
}

export default usePreventWindowClose;
