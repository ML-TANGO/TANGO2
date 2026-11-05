import { useEffect, useState } from 'react';

/**
 * @param {(() => any) | void} callback
 */
function useComponentDidMount(callback) {
  const [mount, setMount] = useState(false);

  useEffect(() => {
    if (!mount) {
      setMount(true);
      const unmount = callback();
      return () => {
        if (typeof unmount === 'function') {
          unmount();
        }
      };
    }
    return () => {};
  }, [callback, mount]);
}

export default useComponentDidMount;
