/**
 * 문자열 배열을 문자열로 변경
 * @param value
 * @param t
 * @returns
 */
function arrayToString(value, t) {
    if (Array.isArray(value)) {
        var makeStr_1 = '';
        value.forEach(function (val) {
            makeStr_1 = "".concat(makeStr_1).concat(t ? t(val) : val);
        });
        return makeStr_1;
    }
    return t ? t(value) : value;
}
/**
 * 배열의 일치 여부 확인
 * 일치 시 true, 일치하지 않을경우 false
 * 타입이 2d-array ↑, set, map일 경우, 검출x
 * 타입이 object일때 key에 대한 순서가 보장되어있지 않으면 검출x
 * @param prev
 * @param next
 * @returns
 */
function isSameArray(prev, next) {
    if (prev.length !== next.length)
        return false;
    var len = prev.length;
    for (var i = 0; i < len; i++) {
        var p = prev[i];
        var n = next[i];
        if (typeof p !== typeof n)
            return false;
        if (typeof p === 'object' && JSON.stringify(p) !== JSON.stringify(n)) {
            return false;
        }
        if (prev[i] !== next[i])
            return false;
    }
    return true;
}
var theme = {
    PRIMARY_THEME: 'jp-primary',
    DARK_THEME: 'jp-dark',
};

export { arrayToString, isSameArray, theme };
//# sourceMappingURL=utils.js.map
