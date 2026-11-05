/**
 * 컴포넌트 mount때 한번만 실행할 함수
 * @param callback
 */
declare function useComponentDidMount(callback: () => (() => void) | void): void;
export { useComponentDidMount };
