import { useCallback, useState } from 'react';

export const nameExg = /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

const useNameInput = () => {
  const [name, setName] = useState(undefined);

  const calIsError = useCallback((name, isValidateName) => {
    if (name === undefined) return false;
    return !isValidateName;
  }, []);

  const calIsValidate = useCallback((name) => {
    if (!name) return false;
    if (name.length === '') return false;
    const isNameValidate = nameExg.test(name);
    return !isNameValidate;
  }, []);

  // ** 버튼에 사용하는 유효성 검사 **
  const isValidateName = calIsValidate(name);
  // ** input에 사용하는 Error 검사 **
  const isError = calIsError(name, isValidateName);

  const handleName = useCallback((value) => {
    setName(value);
  }, []);

  return { name, isError, isValidateName, handleName };
};

export default useNameInput;
