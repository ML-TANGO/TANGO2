import { InputText } from '@tango/ui-react';

import { getPlaygroundTestLog } from '@src/apis/llm/playground';
import React, { useEffect, useState } from 'react';
import { toast } from 'react-toastify';

import { STATUS_SUCCESS } from '@src/network';

import LogCom from './LogCom';
import SearchCom from './SearchCom';

// CSS module
import classNames from 'classnames/bind';
import style from './SystemLog.module.scss';

const cx = classNames.bind(style);

const getPlaygroundLogData = async (playgroundId, setLogData) => {
  const { status, result, message } = await getPlaygroundTestLog(playgroundId);
  if (status === STATUS_SUCCESS) {
    setLogData(result);
  } else {
    toast.error(message);
  }
};

export default function SystemLog({ playgroundId }) {
  const [logData, setLogData] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);

  const handleSelectedItem = (info) => {
    setSelectedItem(info);
  };

  useEffect(() => {
    getPlaygroundLogData(playgroundId, setLogData);
  }, [playgroundId]);

  return (
    <div className={cx('flex-cont')}>
      <SearchCom
        handleSelectedItem={handleSelectedItem}
        logData={logData}
        selectedItem={selectedItem}
      />
      <LogCom selectedItem={selectedItem} />
    </div>
  );
}
