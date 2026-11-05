import { useCallback, useEffect, useState } from 'react';

function useObserver() {
  const [ref, setRef] = useState(null);

  const scrollHandler = useCallback(
    ([entry], observer) => {
      if (!entry.isVisible)
        ref.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
          inline: 'nearest',
        });
      observer.disconnect();
    },
    [ref],
  );

  useEffect(() => {
    let observer;
    if (ref) {
      observer = new IntersectionObserver(scrollHandler, {
        threshold: 0.0,
      });
      observer.observe(ref);
    }
    return () => observer && observer.disconnect();
  }, [ref, scrollHandler]);

  return [setRef];
}
export default useObserver;
