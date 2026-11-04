import { useState, useMemo } from 'react';

// Components
import DeleteConfirmMessage from '@src/components/molecules/DeleteConfirmMessage';

const useDeleteConfirmMessage = (notice, confirmMessage) => {
  const [inputMessage, setInputMessage] = useState('');

  /**
   * 텍스트 인풋 핸들러
   * @param {Object} e Event 객체
   */
  const textInputHandler = (e) => {
    const { value } = e.target;
    setInputMessage(value);
  };

  const renderDeleteConfirmMessage = () => (
    <DeleteConfirmMessage
      notice={notice}
      confirmMessage={confirmMessage}
      inputMessage={inputMessage}
      textInputHandler={textInputHandler}
    />
  );

  const result = useMemo(
    () => ({
      isValid: confirmMessage ? inputMessage === confirmMessage : true,
    }),
    [inputMessage, confirmMessage],
  );

  return [result, renderDeleteConfirmMessage];
};

export default useDeleteConfirmMessage;
