import { useRef, useState } from 'react';
import { toast } from 'react-toastify';

import { Badge, ButtonV2 } from '@jonathan/ui-react';

import EmptyBox from '@src/components/molecules/EmptyBox';
import PlaygroundRangeBar from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundRangeBar';
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

const MAX_TOKENS_MIN = 64;
const MAX_TOKENS_MAX = 2048;
const MAX_TOKENS_STEP = 32;

// SDS(외부 VLM) 단독 배포 추론 — 이중모델 화면(DualDirectInference)과 같은 조나단 구조:
//   섹션=카드(padding 24/radius 16), 버튼=ButtonV2, 단계/유형 표기=Badge, 빈 상태=EmptyBox.
//   결과는 채팅 버블 대신 결과 카드로 쌓되(최신 먼저) 실행 이력은 그대로 보존한다.
//   max_new_tokens 는 플랫폼 PlaygroundRangeBar(슬라이더+숫자입력, min/max 클램프) 재사용.
export default function ExternalTestCom({ playgroundId }) {
  const [imageB64, setImageB64] = useState('');
  const [aisRows, setAisRows] = useState([{ ...MY_SHIP_DEFAULT }]);
  const [outputType, setOutputType] = useState('한글 해상상황묘사');
  const [maxNewTokens, setMaxNewTokens] = useState(256);
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState([]); // [{ id, text, outputType, maxNewTokens, meta }]
  const resultIdRef = useRef(0); // 안정 key 용 증가 id(index-key 재정렬 버그 방지)

  // PlaygroundRangeBar 는 슬라이더/숫자입력 둘 다 e.target.value 로 값을 준다(플랫폼 규약).
  //   GPU 추론 파라미터라 범위를 벗어난 값이 나가지 않게 여기서도 클램프.
  const handleMaxNewTokens = (e) => {
    const next = Number(e.target.value);
    if (Number.isNaN(next)) return;
    setMaxNewTokens(Math.min(Math.max(next, MAX_TOKENS_MIN), MAX_TOKENS_MAX));
  };

  // 이중 화면과 동일한 실행 가능 조건 — 필수 입력이 없으면 버튼 자체를 잠근다.
  const hasMyShip = aisRows.some((r) => Number(r.my_ship) === 1);
  const canRun = !!imageB64 && aisRows.length > 0 && hasMyShip && !isLoading;

  const handleSubmit = async () => {
    if (!imageB64) {
      toast.error('이미지를 업로드해 주세요.');
      return;
    }
    if (!aisRows.length) {
      toast.error('AIS 데이터를 입력해 주세요.');
      return;
    }
    if (!hasMyShip) {
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
        const meta =
          ts != null
            ? `추론 ${Number(ts).toFixed(2)}s${ckpt ? ` · ${ckpt}` : ''}`
            : '';
        // 최신 결과를 위로 — 실행 이력은 계속 쌓아 비교할 수 있게 한다.
        setResults((prev) => [
          {
            id: resultIdRef.current++,
            text,
            outputType,
            maxNewTokens: Number(maxNewTokens),
            meta,
          },
          ...prev,
        ]);
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
    <div className={cx('panel')}>
      <section className={cx('card')}>
        <div className={cx('card-head')}>
          <h3 className={cx('card-title')}>SDS(VLM) 입력</h3>
          <Badge type='gray' size='sm' label='이미지 · AIS · 출력 유형' />
        </div>
        <ImageUploadField value={imageB64} onChange={setImageB64} />
        <OutputTypeSelect value={outputType} onChange={setOutputType} />
        <PlaygroundRangeBar
          label='Max New Tokens'
          value={maxNewTokens}
          min={MAX_TOKENS_MIN}
          max={MAX_TOKENS_MAX}
          step={MAX_TOKENS_STEP}
          onChange={handleMaxNewTokens}
        />
        <AISRowsForm value={aisRows} onChange={setAisRows} />
      </section>

      <div className={cx('run-row')}>
        <ButtonV2
          type='solid'
          colorType='blue'
          size='l'
          label={isLoading ? '추론 중' : '추론 실행'}
          isLoading={isLoading}
          disabled={!canRun}
          onClick={handleSubmit}
        />
      </div>

      {results.length === 0 ? (
        <EmptyBox
          isBox
          customStyle={{ height: '160px' }}
          text='이미지와 AIS 데이터를 입력하고 추론을 실행하세요.'
        />
      ) : (
        <div className={cx('result')}>
          {results.map((r) => (
            <section key={r.id} className={cx('card')}>
              <div className={cx('card-head')}>
                <h3 className={cx('card-title')}>추론 결과</h3>
                <Badge type='blue' size='sm' label={r.outputType} />
                <Badge
                  type='gray'
                  size='sm'
                  label={`max_new_tokens ${r.maxNewTokens}`}
                />
                {r.meta && <span className={cx('result-meta')}>{r.meta}</span>}
              </div>
              <div className={cx('result-body')}>{r.text}</div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
