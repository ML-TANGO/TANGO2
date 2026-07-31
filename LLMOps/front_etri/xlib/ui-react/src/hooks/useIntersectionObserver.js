import { __read } from '../../_virtual/_tslib.js';
import { useState, useEffect } from 'react';

/**
 * intersection observer hook
 * @param elementRef
 * @param param1
 * @returns
 */
function useIntersectionObserver(elementRef, _a) {
    var _b = _a.threshold, threshold = _b === void 0 ? 0 : _b, // node 교차 영역 비율
    _c = _a.root, // node 교차 영역 비율
    root = _c === void 0 ? null : _c, // 교차 영역의 기준 (observe 대상의 요소는 root의 하위 요소)
    _d = _a.rootMargin, // 교차 영역의 기준 (observe 대상의 요소는 root의 하위 요소)
    rootMargin = _d === void 0 ? '0%' : _d, // root 요소의 css margin
    _e = _a.freezeOnceVisible, // root 요소의 css margin
    freezeOnceVisible = _e === void 0 ? false : _e;
    var _f = __read(useState(), 2), entry = _f[0], setEntry = _f[1];
    var frozen = (entry === null || entry === void 0 ? void 0 : entry.isIntersecting) && freezeOnceVisible;
    var updateEntry = function (_a, observer) {
        var _b = __read(_a, 1), entry = _b[0];
        setEntry(entry);
        observer.disconnect();
    };
    useEffect(function () {
        var node = elementRef === null || elementRef === void 0 ? void 0 : elementRef.current;
        // Intersection observer 지원 여부
        var hasIOSupport = !!window.IntersectionObserver;
        if (!hasIOSupport || frozen || !node)
            return undefined;
        var observerParams = { threshold: threshold, root: root, rootMargin: rootMargin };
        var observer = new IntersectionObserver(updateEntry, observerParams);
        observer.observe(node);
        return function () { return observer.disconnect(); };
    }, [elementRef, frozen, root, rootMargin, threshold]);
    return entry;
}

export { useIntersectionObserver };
//# sourceMappingURL=useIntersectionObserver.js.map
