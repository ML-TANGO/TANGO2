import { useEffect, useRef } from 'react';

/**
 * 외부 클릭을 감지하는 커스텀 훅
 * @param {function} fn - 외부 클릭 시 실행할 콜백 함수
 * @returns {object} - ref 객체와 전달된 콜백 함수
 */

const useOutsideClick = (fn) => {
  const ref = useRef(null);

  useEffect(() => {
    const handleClick = (event) => {
      if (ref.current && !ref.current.contains(event.target)) {
        fn();
      }
    };

    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [fn]);

  return { ref };
};

export default useOutsideClick;
