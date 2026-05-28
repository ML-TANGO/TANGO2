import { RefObject } from 'react';
interface Args extends IntersectionObserverInit {
    freezeOnceVisible?: boolean;
}
/**
 * intersection observer hook
 * @param elementRef
 * @param param1
 * @returns
 */
declare function useIntersectionObserver(elementRef: RefObject<Element>, { threshold, // node 교차 영역 비율
root, // 교차 영역의 기준 (observe 대상의 요소는 root의 하위 요소)
rootMargin, // root 요소의 css margin
freezeOnceVisible, }: Args): IntersectionObserverEntry | undefined;
export { useIntersectionObserver };
