export declare const KOREAN_PHONEME: {
    CHOSUNG: string[];
    JUNGSUNG: string[];
    JONGSUNG: string[];
};
declare const Hangul: {
    assemble: (s: string[]) => string;
    disassemble: (c: string) => string[];
    make: (s: string) => string;
    isHangul: (word: string) => boolean;
};
export default Hangul;
