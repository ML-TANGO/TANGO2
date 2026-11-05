interface TrieDataType {
    label: string;
    key: string | number;
    options?: {
        [key: string]: any;
    };
    checked?: boolean;
}
interface ITrie {
    insert: (inputStr: string, word: TrieDataType) => void;
    initialize: () => void;
    startPrefixList: (prefix: string) => TrieDataType[];
    containList: (inputed: string) => TrieDataType[];
    isDiff: (newData: TrieDataType[]) => boolean;
}
export { ITrie, TrieDataType };
