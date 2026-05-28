import { __read } from '../../_virtual/_tslib.js';
import { useState, useEffect } from 'react';

function getWindowDimensions() {
    var width = window.innerWidth, height = window.innerHeight;
    return {
        width: width,
        height: height,
    };
}
function useWindowDimensions() {
    var _a = __read(useState(getWindowDimensions()), 2), windowDimensions = _a[0], setWindowDimensions = _a[1];
    useEffect(function () {
        function handleResize() {
            setWindowDimensions(getWindowDimensions());
        }
        window.addEventListener('resize', handleResize);
        return function () { return window.removeEventListener('resize', handleResize); };
    }, []);
    return windowDimensions;
}

export { useWindowDimensions as default };
//# sourceMappingURL=useWindowDimensions.js.map
