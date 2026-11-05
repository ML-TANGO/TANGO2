import Char from '@src/Char';

export const KOREAN_PHONEME = {
  CHOSUNG: [
    'ㄱ',
    'ㄲ',
    'ㄴ',
    'ㄷ',
    'ㄸ',
    'ㄹ',
    'ㅁ',
    'ㅂ',
    'ㅃ',
    'ㅅ',
    'ㅆ',
    'ㅇ',
    'ㅈ',
    'ㅉ',
    'ㅊ',
    'ㅋ',
    'ㅌ',
    'ㅍ',
    'ㅎ',
  ],
  JUNGSUNG: [
    'ㅏ',
    'ㅐ',
    'ㅑ',
    'ㅒ',
    'ㅓ',
    'ㅔ',
    'ㅕ',
    'ㅖ',
    'ㅗ',
    'ㅘ',
    'ㅙ',
    'ㅚ',
    'ㅛ',
    'ㅜ',
    'ㅝ',
    'ㅞ',
    'ㅟ',
    'ㅠ',
    'ㅡ',
    'ㅢ',
    'ㅣ',
  ],
  JONGSUNG: [
    '',
    'ㄱ',
    'ㄲ',
    'ㄳ',
    'ㄴ',
    'ㄵ',
    'ㄶ',
    'ㄷ',
    'ㄹ',
    'ㄺ',
    'ㄻ',
    'ㄼ',
    'ㄽ',
    'ㄾ',
    'ㄿ',
    'ㅀ',
    'ㅁ',
    'ㅂ',
    'ㅄ',
    'ㅅ',
    'ㅆ',
    'ㅇ',
    'ㅈ',
    'ㅊ',
    'ㅋ',
    'ㅌ',
    'ㅍ',
    'ㅎ',
  ],
};

const Hangul = (() => {
  /**
   * 한글의 어절임을 구분
   * @param word
   * @returns {boolean}
   */
  function isHangul(word) {
    const code = word.charCodeAt(0) - 0xac00;

    // 한글 범위 계산
    const start = '가'.charCodeAt(0) - 0xac00; // 0
    const end = '힣'.charCodeAt(0) - 0xac00; // 11171

    return code >= start && code <= end;
  }

  /**
   * 한글 음소를 받아 음절로 병합
   * @param s 한글 음소 배열 (배열 길이 3 고정)
   * @returns character type
   */
  function assemble(s) {
    const cho = s[0] || '';
    const jung = s[1] || '';
    const jong = s[2] || '';
    if (!jung) return cho;

    const jungUniCode = jung.charCodeAt(0);

    const connectorCho = KOREAN_PHONEME.CHOSUNG.reduce(
      (acc, cur, idx) => ({
        ...acc,
        [cur]: idx,
      }),
      {},
    );

    const connectorJongsung = KOREAN_PHONEME.JONGSUNG.reduce(
      (acc, cur, idx) => ({
        ...acc,
        [cur]: idx,
      }),
      {},
    );

    const JA_START = 'ㅎ'.charCodeAt(0) + 1; // 'ㄱ'.charCodeAt(0);
    const UNI_START = '가'.charCodeAt(0);

    const choIdx = connectorCho[cho];
    const jungIdx = jungUniCode - JA_START;
    const jongIdx = connectorJongsung[jong];

    return String.fromCharCode(
      UNI_START + choIdx * 588 + jungIdx * 28 + jongIdx,
    );
  }

  /**
   * 중성을 분해
   * @param jungsung
   * @returns {string[]}
   */
  // function disassembleJungsung(jungsung) {
  //   if (jungsung === 'ㅘ') {
  //     return ['ㅗ', 'ㅏ'];
  //   }
  //   if (jungsung === 'ㅙ') {
  //     return ['ㅗ', 'ㅐ'];
  //   }
  //   if (jungsung === 'ㅚ') {
  //     return ['ㅗ', 'ㅣ'];
  //   }
  //   if (jungsung === 'ㅝ') {
  //     return ['ㅜ', 'ㅓ'];
  //   }
  //   if (jungsung === 'ㅞ') {
  //     return ['ㅜ', 'ㅔ'];
  //   }
  //   if (jungsung === 'ㅟ') {
  //     return ['ㅜ', 'ㅣ'];
  //   }
  //   if (jungsung === 'ㅢ') {
  //     return ['ㅡ', 'ㅣ'];
  //   }
  //   return [jungsung];
  // }

  /**
   * 종성을 분해
   * @param jongsung
   * @returns {string[]}
   */
  // function disassembleJongsung(jongsung) {
  //   if (jongsung === 'ㄲ') {
  //     return ['ㄱ', 'ㄱ'];
  //   }
  //   if (jongsung === 'ㄳ') {
  //     return ['ㄱ', 'ㅅ'];
  //   }
  //   if (jongsung === 'ㄵ') {
  //     return ['ㄴ', 'ㅈ'];
  //   }
  //   if (jongsung === 'ㄶ') {
  //     return ['ㄴ', 'ㅎ'];
  //   }
  //   if (jongsung === 'ㄺ') {
  //     return ['ㄹ', 'ㄱ'];
  //   }
  //   if (jongsung === 'ㄻ') {
  //     return ['ㄹ', 'ㅁ'];
  //   }
  //   if (jongsung === 'ㄼ') {
  //     return ['ㄹ', 'ㅂ'];
  //   }
  //   if (jongsung === 'ㄽ') {
  //     return ['ㄹ', 'ㅅ'];
  //   }
  //   if (jongsung === 'ㄾ') {
  //     return ['ㄹ', 'ㅌ'];
  //   }
  //   if (jongsung === 'ㄿ') {
  //     return ['ㄹ', 'ㅍ'];
  //   }
  //   if (jongsung === 'ㅀ') {
  //     return ['ㄹ', 'ㅎ'];
  //   }
  //   if (jongsung === 'ㅄ') {
  //     return ['ㅂ', 'ㅅ'];
  //   }
  //   if (jongsung === 'ㅆ') {
  //     return ['ㅅ', 'ㅅ'];
  //   }

  //   return [jongsung];
  // }

  /**
   * 음절을 음소단위로 분해
   * @param c
   * @returns {string[]}
   */
  function disassemble(c) {
    const uniVal = c.charCodeAt(0) - 0xac00;

    const cho = Math.floor(uniVal / 28 / 21);
    // const jung = Math.floor((uniVal / 28) % 21);
    // const jong = Math.floor(uniVal % 28);
    return [
      KOREAN_PHONEME.CHOSUNG[cho], // 초성
      // ...disassembleJungsung(KOREAN_PHONEME.JUNGSUNG[jung]), // 중성
      // ...disassembleJongsung(KOREAN_PHONEME.JONGSUNG[jong]), // 종성
    ];
  }

  function make(s) {
    let result = '';
    const sentence = s;

    for (let i = 0; i < sentence.length; i++) {
      const c = new Char(sentence[i]);
      if (isHangul(c)) {
        const ext = disassemble(c);
        for (let i = 0; i < ext.length; i++) {
          result = `${result}${ext[i]}`;
        }
      } else {
        result = `${result}${c.value}`;
      }
    }

    return result;
  }

  return {
    assemble,
    disassemble,
    make,
    isHangul,
  };
})();

export default Hangul;
