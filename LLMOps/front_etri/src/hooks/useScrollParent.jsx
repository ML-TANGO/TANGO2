import { useEffect } from 'react';

const useParentScrollListeners = (elementRef, onScroll) => {
  useEffect(() => {
    const addScrollListeners = (element) => {
      // 재귀적으로 부모 요소를 순회하면서 스크롤 이벤트 리스너 등록
      let currentElement = element;

      while (currentElement) {
        currentElement.addEventListener('scroll', onScroll);

        // 다음 상위 부모 요소로 이동
        currentElement = currentElement.parentElement;
      }

      // cleanup 함수로 이벤트 리스너 제거
      return () => {
        let cleanupElement = element;
        while (cleanupElement) {
          cleanupElement.removeEventListener('scroll', onScroll);
          cleanupElement = cleanupElement.parentElement;
        }
      };
    };

    if (elementRef.current) {
      const cleanup = addScrollListeners(elementRef.current);
      return cleanup; // cleanup 함수를 반환하여 useEffect에서 이벤트 리스너 제거 처리
    }
  }, [elementRef, onScroll]);
};

export default useParentScrollListeners;
