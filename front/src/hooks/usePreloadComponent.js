import { lazy } from 'react';

/**
 * @param importComponent : () => import('../components/BackdropLayer')
 * @return preload() method
 */
const usePreloadComponent = () => {
  const lazyLoad = (importComponent) => {
    const Component = lazy(importComponent);
    Component.preload = importComponent;
    Component.preload();

    return Component;
  };
  return { lazyLoad };
};

export default usePreloadComponent;
