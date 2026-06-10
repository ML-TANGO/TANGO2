import { ITrie, TrieDataType } from './types';
declare type TrieObjectType = {
    [key: string]: TrieNode;
};
declare class TrieNode {
    isWord: boolean;
    info: TrieDataType[] | null;
    next: TrieObjectType;
    constructor();
}
declare class Trie implements ITrie {
    private root;
    private memo;
    constructor();
    /**
     * 입력받은 문자열을 추출하여 배열로 저장
     * @param str
     */
    private extractStr;
    /**
     * 문자열을 trie객체에 주입
     * @param inputStr 입력된 문자열
     * @param info trie의 info에 넣을 데이터
     */
    insert: (inputStr: string, info: TrieDataType) => void;
    /**
     * 접두어 기준 다음에 올 수 있는 모든 문자열 반환
     * @param prefix 접두어
     * @returns
     */
    startPrefixList: (prefix: string) => TrieDataType[];
    /**
     * 입력된 문자열이 포함된 모든 데이터 출력
     * @param inputed
     */
    containList: (inputed: string) => TrieDataType[];
    /**
     * trie 초기화
     */
    initialize: () => void;
    /**
     * trie memoization
     * 일치할 경우 false, 일치하지 않을 경우 true
     * @param {TrieDataType} newData
     * @returns
     */
    isDiff: (newData: TrieDataType[]) => boolean;
    /**
     * 생성된 trie ds getter
     */
    get makedTrie(): TrieNode;
}
export default Trie;
