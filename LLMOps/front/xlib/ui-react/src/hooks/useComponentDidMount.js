import { __read } from '../../_virtual/_tslib.js';
import { useState } from 'react';
import { useIsomorphicLayoutEffect } from './useIsomorphicLayoutEffect.js';

/**
 * 컴포넌트 mount때 한번만 실행할 함수
 * @param callback
 */
function useComponentDidMount(callback) {
    var _a = __read(useState(false), 2), mount = _a[0], setMount = _a[1];
    useIsomorphicLayoutEffect(function () {
        if (mount === false) {
            setMount(true);
            var unmount_1 = callback();
            return function () {
                if (unmount_1) {
                    unmount_1();
                }
            };
        }
        return function () { };
    }, [callback, mount]);
}

export { useComponentDidMount };
//# sourceMappingURL=useComponentDidMount.js.map
