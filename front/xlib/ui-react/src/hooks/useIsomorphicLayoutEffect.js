import { useLayoutEffect, useEffect } from 'react';

/**
 * useEffect, useLayoutEffect 사용 분기 설정
 */
var useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;

export { useIsomorphicLayoutEffect };
//# sourceMappingURL=useIsomorphicLayoutEffect.js.map
