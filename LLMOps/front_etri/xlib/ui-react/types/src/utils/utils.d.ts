import i18n from 'react-i18next';
/**
 * 문자열 배열을 문자열로 변경
 * @param value
 * @param t
 * @returns
 */
declare function arrayToString(value: string | string[], t?: i18n.TFunction<'translation'>): string;
/**
 * intersection observer 설정
 * @param node Observing node
 * @param start 관찰될 경우 실행할 함수
 * @param pause 노드가 관찰되지 않을경우 실행할 함수
 */
declare function intersectionObserver<T, R>(node: Element, start?: () => T, pause?: () => R): () => void;
/**
 * Set<T> 비교
 * 같을 경우 true else false
 * @param beforeSet
 * @param afterSet
 * @returns boolean
 */
declare function isEqualSet<T>(beforeSet: Set<T>, afterSet: Set<T>): boolean;
/**
 * 배열의 일치 여부 확인
 * 일치 시 true, 일치하지 않을경우 false
 * 타입이 2d-array ↑, set, map일 경우, 검출x
 * 타입이 object일때 key에 대한 순서가 보장되어있지 않으면 검출x
 * @param prev
 * @param next
 * @returns
 */
declare function isSameArray<T>(prev: Array<T>, next: Array<T>): boolean;
/**
 * object 깊은 복사
 * object type이 아닐 경우 throw
 * @param obj
 * @returns
 */
declare function objectDeepCopy<T>(obj: T): any;
declare const theme: {
    PRIMARY_THEME: 'jp-primary';
    DARK_THEME: 'jp-dark';
};
export { arrayToString, intersectionObserver, isEqualSet, isSameArray, objectDeepCopy, theme, };
