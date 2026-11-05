import { useContext } from 'react';

import { TestUrlContext } from './TestComProvider';

const useTestUrl = () => {
  const value = useContext(TestUrlContext);
  return value;
};

export default useTestUrl;
