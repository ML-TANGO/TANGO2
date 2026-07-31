import { useEffect, useRef } from 'react';

/**
 * 인터벌 호출 커스텀 훅
 * @param {Function} callback 호출할 함수
 * @param {number} delay 호출 간격(ms)
 */
const useIntervalParam = (callback, delay) => {
  const savedCallback = useRef();

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    if (typeof delay !== 'number') return;

    const tick = () => {
      if (savedCallback.current) {
        savedCallback.current();
      }
    };

    const id = setInterval(tick, delay);
    return () => clearInterval(id);
  }, [delay]);
};

export default useIntervalParam;
