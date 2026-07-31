import { useEffect } from 'react';
import { useHistory } from 'react-router-dom';

function usePrevScroll() {
  const history = useHistory();

  useEffect(() => {
    let timer;
    const scrollEvent = () => {
      if (timer) {
        clearTimeout(timer);
      }
      timer = setTimeout(() => {
        if (history.action !== 'PUSH') {
          sessionStorage.setItem('prev-scroll-pos', window.pageYOffset);
        }
      }, 200);
    };
    document.addEventListener('scroll', scrollEvent);
    return () => {
      document.removeEventListener('scroll', scrollEvent);
    };
  }, [history]);
}

export default usePrevScroll;
