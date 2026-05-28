import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

function ScrollToTop({
  children,
  scrollBox,
}) {
  const location = useLocation();
  const { pathname } = location
  useEffect(() => {
    const tmpScrollBox = scrollBox;
    if (tmpScrollBox) tmpScrollBox.scrollTop = 0;
  }, [pathname, scrollBox]);
  return children;
};

export default ScrollToTop;
