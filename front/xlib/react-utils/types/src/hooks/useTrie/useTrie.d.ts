import Trie from './Trie';
import type { TrieDataType } from './types';
/**
 * trie Datastructure를 생성
 * @param dictionary trie 생성 데이터
 * @param isBuildTrie trie 생성 여부
 * @returns
 */
declare function useTrie(dictionary: TrieDataType[], isBuildTrie?: boolean): Trie;
export default useTrie;
