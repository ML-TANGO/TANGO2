import { useCallback, useMemo, useReducer } from 'react';

type TAction = {
  name: string;
  value: string;
};

const reducer = <T extends Record<string, string>>(
  state: T,
  action: TAction | null,
) => {
  if (!action) {
    const initialState: any = {};
    Object.keys(state).forEach((key) => {
      initialState[key] = '';
    });
    return initialState;
  }

  return {
    ...state,
    [action.name]: action.value,
  };
};

const useInputs = <T extends Record<string, any>>(defaultValues: T) => {
  const memoValues = useMemo(() => defaultValues, [defaultValues]);
  const [inputs, dispatch] = useReducer(reducer, memoValues);

  const handleInputs = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    dispatch({
      name: e.target.name,
      value: e.target.value,
    });
  }, []);

  const onReset = useCallback(() => {
    dispatch(null);
  }, []);

  return { inputs, handleInputs, onReset, dispatch } as {
    inputs: T;
    handleInputs: typeof handleInputs;
    onReset: typeof onReset;
    dispatch: typeof dispatch;
  };
};

export default useInputs;
