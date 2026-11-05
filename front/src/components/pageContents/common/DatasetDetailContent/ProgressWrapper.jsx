import { useState, useEffect } from 'react';
import Progressbar from './Progressbar';

const ProgressbarWrapper = () => {
  const [progressValue, setProgressValue] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setProgressValue((prevValue) => (prevValue < 100 ? prevValue + 1 : 100));
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  return <Progressbar value={progressValue} />;
};

export default ProgressbarWrapper;
