import { useEffect, useCallback } from 'react';
import { useLocation, useHistory } from 'react-router-dom';

// Components
import ScrollToTopBtn from '@src/components/ScrollToTopBtn';

let timer;
let position = 0;
/**
 * 페이지 콘텐츠 영역 스크롤 관련 hook
 * - 이전 페이지 위치로 스크롤 이동
 * -
 * @param {Object} scrollBox 스크롤 박스 엘리먼트
 * @returns {[renderScrollToTopBtn: function]}
 */
function useScrollHook(scrollBox) {
  // Router hooks
  const location = useLocation();
  const history = useHistory();

  // 스크롤 감지 이벤트
  // 스크롤시 현재 위치를 저장
  // 스크롤 이벤트
  const scrollEvent = useCallback((e) => {
    if (!timer) {
      timer = setTimeout(() => {
        timer = null;
        position = e.target.scrollTop;
      }, 300);
    }
  }, []);

  // useeffect 페이지 이동 할 때 이전 저장된 y축 값을 가져와서 스크롤
  useEffect(() => {
    if (scrollBox) scrollBox.addEventListener('scroll', scrollEvent);
    return () => {
      const { action } = history;
      if (action === 'PUSH') {
        sessionStorage.setItem('prevPosition', position);
        if (scrollBox)
          scrollBox.removeEventListener('scroll', scrollEvent, true);
      }
    };
  }, [location, history, scrollEvent, scrollBox]);

  const renderScrollToTopBtn = () => {
    if (!scrollBox) return null;
    return <ScrollToTopBtn scrollBox={scrollBox} />;
  };

  return [renderScrollToTopBtn];
}

export default useScrollHook;
