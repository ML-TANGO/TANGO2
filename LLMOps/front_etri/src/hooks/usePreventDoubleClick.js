import { useCallback, useEffect, useState } from 'react';

const usePreventDoubleClick = (onClick, delay = 300) => {
  const [isClicked, setIsClicked] = useState(false);

  const handleClick = useCallback(
    (...args) => {
      if (!isClicked) {
        onClick(...args);
        setIsClicked(true);
      }
    },
    [isClicked, onClick],
  );

  useEffect(() => {
    if (isClicked) {
      const timer = setTimeout(() => {
        setIsClicked(false);
      }, delay);

      return () => clearTimeout(timer);
    }
  }, [isClicked, delay]);

  return handleClick;
};

export default usePreventDoubleClick;
