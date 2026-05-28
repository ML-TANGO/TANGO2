import { useState } from 'react';

function useLocalStorage(key, initValue) {
  const [storedValue, setStoredValue] = useState(() => {
    if (typeof window === 'undefined') {
      return initValue;
    }

    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initValue;
    } catch (e) {
      console.error(e);
      return initValue;
    }
  });

  const setValue = (value, del) => {
    try {
      if (del !== undefined && del === true) {
        setStoredValue('');
        window.localStorage.removeItem(key);
        return;
      }

      const valueToStore =
        value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(key, JSON.stringify(valueToStore));
      }
    } catch (e) {
      console.error(e);
    }
  };

  return [storedValue, setValue];
}

export default useLocalStorage;
