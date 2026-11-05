import { useState } from 'react';

const useHposParameter = () => {
  const [fixParam, setFixParam] = useState([]);
  const [fixId, setFixId] = useState(1);

  const handleFixParamInfo = ({ id, info, value }) => {
    setFixParam((prev) =>
      prev.map((v) => (v.id === id ? { ...v, [info]: value } : { ...v })),
    );
  };

  const deleteFixParam = (id) => {
    setFixParam((prev) => prev.filter((v) => v.id !== id));
  };

  const addFixParam = () => {
    setFixParam((prev) => [...prev, { name: '', param: '', id: fixId }]);
    setFixId((prev) => prev + 1);
  };

  const [searchParam, setSearchParam] = useState([]);
  const [searchId, setSearchId] = useState(1);

  const handleParamInfo = ({ id, info, value }) => {
    setSearchParam((prev) =>
      prev.map((v) => (v.id === id ? { ...v, [info]: value } : { ...v })),
    );
  };

  const deleteParamInfo = (id) => {
    setSearchParam((prev) => prev.filter((v) => v.id !== id));
  };

  const addSearchParam = () => {
    setSearchParam((prev) => [
      ...prev,
      { name: '', type: 0, min: '', max: '', count: '', id: searchId },
    ]);
    setSearchId((prev) => prev + 1);
  };

  return {
    fixParam,
    handleFixParamInfo,
    deleteFixParam,
    addFixParam,
    searchParam,
    handleParamInfo,
    deleteParamInfo,
    addSearchParam,
  };
};

export default useHposParameter;
