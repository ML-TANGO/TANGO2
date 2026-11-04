import React, { createContext, useState } from 'react';

export const TestUrlContext = createContext();

export default function TestComProvider({ children }) {
  const testUrlState = useState('');
  return (
    <TestUrlContext.Provider value={testUrlState}>
      {children}
    </TestUrlContext.Provider>
  );
}
