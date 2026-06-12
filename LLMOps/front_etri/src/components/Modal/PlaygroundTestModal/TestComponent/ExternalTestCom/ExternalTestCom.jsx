import { useState } from 'react';
import { toast } from 'react-toastify';

import { ButtonV2 } from '@tango/ui-react';

import { postPlaygroundTestChat } from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';

import {
  ImageUploadField,
  AISRowsForm,
  OutputTypeSelect,
} from '@src/components/MultiModalInput';

import classNames from 'classnames/bind';
import style from './ExternalTestCom.module.scss';

const cx = classNames.bind(style);

// partner schema (RunParams.AISRow) — ship_id 는 integer. label 만 "자선" 표시.
const MY_SHIP_DEFAULT = {
  ship_id: 1,
  my_ship: 1,
  latitude: 35.1,
  longitude: 129.0,
  knot: 5,
  heading: 90,
  length: 100,
  width: 20,
  draft: 5,
};

export default function ExternalTestCom({ playgroundId }) {
  const [imageB64, setImageB64] = useState('');
  const [aisRows, setAisRows] = useState([{ ...MY_SHIP_DEFAULT }]);
  const [outputType, setOutputType] = useState('한글 해상상황묘사');
  const [maxNewTokens, setMaxNewTokens] = useState(256);
  const [isLoading, setIsLoading] = useState(false);
  const [chatList, setChatList] = useState([]);

  const handleSubmit = async () => {
    if (!imageB64) {
      toast.error('이미지를 업로드해 주세요.');
      return;
    }
    if (!aisRows.length) {
      toast.error('AIS 데이터를 입력해 주세요.');
      return;
    }
    if (!aisRows.some((r) => Number(r.my_ship) === 1)) {
      toast.error('자선(my_ship=1) 행이 필요합니다.');
      return;
    }

    const external_payload = {
      image_base64: imageB64,
      ais_rows: aisRows,
      output_type: outputType,
      max_new_tokens: Number(maxNewTokens),
      repetition_penalty: 1.1,
      do_sample: false,
    };

    setChatList((prev) => [
      ...prev,
      { type: 'input', message: `[${outputType}] 추론 요청 (max_new_tokens=${maxNewTokens})` },
    ]);
    setIsLoading(true);

    try {
      const { result, status, message } = await postPlaygroundTestChat({
        playground_id: playgroundId,
        test_type: 'external',
        external_payload,
      });
      if (status === STATUS_SUCCESS && Array.isArray(result) && result[0]) {
        const item = result[0];
        const inner = item.result || {};
        const text = item.output || inner.text || JSON.stringify(inner);
        const ts = inner.inference_time_sec;
        const ckpt = inner.active_checkpoint;
        const meta = ts != null ? ` (추론 ${Number(ts).toFixed(2)}s${ckpt ? ` · ${ckpt}` : ''})` : '';
        setChatList((prev) => [...prev, { type: 'output', message: text + meta }]);
      } else {
        toast.error(message || '추론 실패');
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={cx('container')}>
      <div className={cx('form-area')}>
        <ImageUploadField value={imageB64} onChange={setImageB64} />
        <OutputTypeSelect value={outputType} onChange={setOutputType} />
        <label
          style={{
            display: 'block',
            marginBottom: 12,
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          Max New Tokens: {maxNewTokens}
          <input
            type='range'
            min={64}
            max={2048}
            step={32}
            value={maxNewTokens}
            onChange={(e) => setMaxNewTokens(+e.target.value)}
            style={{ display: 'block', width: '100%', marginTop: 4 }}
          />
        </label>
        <AISRowsForm value={aisRows} onChange={setAisRows} />
        <ButtonV2
          size='l'
          colorType='skyblue'
          label='추론 실행'
          isLoading={isLoading}
          onClick={handleSubmit}
        />
      </div>
      <div className={cx('chat-area')}>
        {chatList.length === 0 && (
          <p className={cx('empty')}>이미지 + AIS 데이터를 입력하고 추론을 실행하세요.</p>
        )}
        {chatList.map((el, i) => (
          <div key={i} className={cx('bubble', el.type)}>
            <p>{el.message}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
