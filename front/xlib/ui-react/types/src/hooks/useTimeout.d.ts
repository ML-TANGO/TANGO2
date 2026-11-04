/**
 * timeout을 사용하는 hook
 * @param callback
 * @param delay
 */
declare function useTimeout(callback: () => void, delay: number | null): void;
export { useTimeout };
