import type { ReactDOM } from '../types';
/**
 * virtual dom을 real dom에 적용 (재귀적으로 동작)
 * @param node - 부모노드
 * @param dom - virtual dom
 */
export declare const createDOM: (node: HTMLElement, dom?: ReactDOM[] | ReactDOM | string | null) => void;
/**
 * 연속 rerendering 방지
 * @param callback - 실행 callback함수
 * @returns 다음 호출
 */
export declare const debounceFrame: (callback: FrameRequestCallback) => () => void;
