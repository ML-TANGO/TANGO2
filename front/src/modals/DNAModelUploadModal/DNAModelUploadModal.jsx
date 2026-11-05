import { useState, useEffect, useMemo } from 'react';

// Components
import DNAModelUploadModalContent from '@src/components/modalContents/DNAModelUploadModalContent';
import { toast } from '@src/components/Toast';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

function DNAModelUploadModal({ type, data: modalData }) {
  // BM 옵션
  const bmOptions = useMemo(
    () => [
      { label: 'POL', value: 'POL' },
      { label: 'FRM', value: 'FRM' },
      { label: 'STR', value: 'STR' },
      { label: 'WTR', value: 'WTR' },
      { label: 'COMN', value: 'COMN' },
    ],
    [],
  );

  // Component State
  const [bm, setBm] = useState('POL');
  const [checkpoint, setCheckpoint] = useState();
  const [checkpointOptions, setCheckpointOptions] = useState([
    { label: 'a', value: 'a' },
    { label: 'b', value: 'b' },
    { label: 'c', value: 'c' },
  ]);
  const [desc, setDesc] = useState('');

  // Events

  /**
   * 라디오 버튼 핸들러
   * @param {Object} e Event 객체
   */
  const radioBtnHandler = (e) => {
    const { value } = e.target;
    setBm(value);
  };

  /**
   * 셀렉트 박스 핸들러
   * @param {{ label: string, value: string }} s 선택된 옵션 값
   */
  const selectInputHandler = (s) => {
    setCheckpoint(s);
  };

  /**
   * 텍스트 인풋 핸들러
   * @param {Object} e Event 객체
   */
  const textInputHandler = (e) => {
    const { value } = e.target;
    setDesc(value);
  };

  /**
   * 업로드 버튼 클릭 이벤트
   * @returns {Promise<boolean>} true를 리턴하면 모달 닫기
   */
  const onSubmit = async () => {
    const body = {
      bm,
      checkpoint_id: checkpoint.value,
      checkpoint_description: desc,
    };
    // toast.success('준비중');
    // return true;
    const response = await callApi({
      url: 'dna/checkpoints',
      method: 'post',
      body,
    });
    const { status, message } = response;
    if (status === STATUS_SUCCESS) {
      toast.success('success');
      return true;
    }
    toast.error(message);
    return false;
  };

  useEffect(() => {
    const getModelList = async () => {
      const response = await callApi({
        url: 'options/checkpoints',
        method: 'get',
      });

      const { result, message, status } = response;

      if (status === STATUS_SUCCESS) {
        const { checkpoint_list: checkpointList } = result;
        setCheckpointOptions(
          checkpointList.map((c) => ({
            ...c,
            label: `${c.checkpoint_file_path} - ${c.description}`,
            value: c.id,
          })),
        );
      } else {
        toast.error(message);
      }
    };

    getModelList();
  }, []);

  const isValidate = checkpoint !== undefined;

  return (
    <DNAModelUploadModalContent
      modalData={modalData}
      type={type}
      bmOptions={bmOptions}
      bm={bm}
      desc={desc}
      checkpoint={checkpoint}
      checkpointOptions={checkpointOptions}
      radioBtnHandler={radioBtnHandler}
      selectInputHandler={selectInputHandler}
      textInputHandler={textInputHandler}
      onSubmit={onSubmit}
      isValidate={isValidate}
    />
  );
}

export default DNAModelUploadModal;
