import { useRef } from 'react';
import { useCallback, useEffect, useState } from 'react';

function useComponentExistObserver() {
  const [ref, setRef] = useState(null);
  const isMount = useRef(false);
  const count = useRef(0);
  const scrollHandler = useCallback(
    ([entry], observer) => {
      if (count.current >= 2 && !entry.isVisible) {
        ref.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
          inline: 'nearest',
        });
        observer.disconnect();
      }
    },
    [ref],
  );

  useEffect(() => {
    if (!isMount.current) {
      isMount.current = true;
    }
  }, []);

  useEffect(() => {
    if (isMount.current && ref) {
      count.current += 1;
      const observer = new IntersectionObserver(scrollHandler, {
        threshold: 0.0,
      });
      ref && observer.observe(ref);
    }
  }, [ref, scrollHandler]);

  return [setRef];
}
export default useComponentExistObserver;
