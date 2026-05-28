import { useEffect, useState } from 'react';

// ** 지연시간 200ms 미만일 때 스켈레톤 미노출 / 200ms 이상일 때 스켈레톤 노출 **
const DeferredComponent = ({ children }) => {
  const [isDeferred, setIsDeferred] = useState(false);

  useEffect(() => {
    const timeOut = setTimeout(() => {
      setIsDeferred(true);
    }, 200);
    return () => clearInterval(timeOut);
  }, []);

  if (!isDeferred) return null;
  return children;
};

export default DeferredComponent;
