import { useState, useCallback } from 'react';

// Custom Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';

// Utils
import { scrollToPrevPosition } from '@src/utils';

// Network
import { network } from '@src/network';

// Components
import { InputNumber, Button } from '@jonathan/ui-react';
import { toast } from '@src/components/Toast';

// Test
// import testData from './testImage.json';

// CSS module
import style from './OutputImageRealtime.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

function OutputImageRealtime() {
  const [imgCount, setImgCount] = useState(null);
  const [positiveImgCount, setPositiveImgCount] = useState(null);
  const [negativeImgCount, setNegativeImgCount] = useState(null);
  const [beforeTableData, setBeforeTableData] = useState(null);
  const [afterTableData, setAfterTableData] = useState(null);
  const [isTableShow, setIsTableShow] = useState(false);
  const [inputSrc, setInputSrc] = useState(null);
  const [outputSrc, setOutputSrc] = useState(null);
  const [delay, setDelay] = useState(1000);

  const getModelInfo = useCallback(async () => {
    const response = await network.callServiceApi({
      url: 'http://dev.flightbase.acryl.ai/deployment/h0505e2da062ecdea395c01e57c95ada0/monitor',
      method: 'GET',
    });
    const { data, status } = response;
    if (status === 200) {
      const {
        before_compress: before,
        after_compress: after,
        after_quantization: onnx,
      } = data;
      setBeforeData(before);
      setAfterData(after);
      setOnnxData(onnx);
    }
  }, []);

  const getResult = useCallback(async () => {
    // getModelInfo();
    const response = await network.callServiceApi({
      url: 'https://flightbase.acryl.ai/deployment/hc6e9005490cb6455985eaea3e69873e8/monitor',
      // url: `${url}monitor`,
      method: 'POST',
    });
    const { data, status, message } = response;
    if (status === 200) {
      const imgCount = data?.text?.TOTAL_IMG_COUNT || 0;
      const positiveImgCount = data?.text?.POSITIVE_IMG_COUNT || 0;
      const negativeImgCount = data?.text?.NEGATIVE_IMG_COUNT || 0;
      const input = data?.image?.input || '';
      const output = data?.image?.output || '';
      const beforeTableData = data?.table.before;
      const afterTableData = data?.table.after;
      const isTableShow = data?.table_show === 1;
      setImgCount(imgCount);
      setPositiveImgCount(positiveImgCount);
      setNegativeImgCount(negativeImgCount);
      setInputSrc(input);
      setOutputSrc(output);
      setBeforeTableData(beforeTableData);
      setAfterTableData(afterTableData);
      setIsTableShow(isTableShow);
      return true;
    } else {
      toast.error(message);
    }
    return false;
  }, []);

  // 압축
  const compressModel = async () => {
    await network.callServiceApi({
      url: 'http://dev.flightbase.acryl.ai/deployment/h0505e2da062ecdea395c01e57c95ada0',
      method: 'POST',
    });
  };

  // 압축 결과 리셋
  const resetResult = async () => {
    await network.callServiceApi({
      url: 'http://dev.flightbase.acryl.ai/deployment/h0505e2da062ecdea395c01e57c95ada0/reset',
      method: 'GET',
    });
  };

  // 입력 데이터 리셋
  const resetInputData = async () => {
    await network.callServiceApi({
      // url: `${url}reset`,
      url: 'https://flightbase.acryl.ai/deployment/hc6e9005490cb6455985eaea3e69873e8/reset',
      method: 'POST',
    });
  };

  const onChangeDelay = (data) => {
    const interval = data.value;
    setDelay(interval);
  };

  useIntervalCall(getResult, delay, () => {
    scrollToPrevPosition('root');
  });

  return (
    <div className={cx('wrapper')}>
      <div className={cx('flex-box')}>
        <div className={cx('title')}>Judgement (yolov6)</div>
        <div className={cx('control-box')}>
          <span>ms</span>
          <InputNumber
            size='small'
            min={0}
            step={10}
            value={delay}
            customSize={{ width: '90px' }}
            onChange={onChangeDelay}
          />
          <span>Refresh Interval: </span>
        </div>
      </div>
      <div className={cx('data-info-box')}>
        <div className={cx('left-box')}>
          <Button type='secondary' size='small' onClick={resetInputData}>
            입력 데이터 리셋
          </Button>
          <table className={cx('data-count-table')}>
            <tbody>
              <tr>
                <th>입력 데이터</th>
                <td className={cx('two-column')}>총 {imgCount}개</td>
              </tr>
            </tbody>
          </table>
          <table>
            <tbody>
              <tr>
                <th></th>
                <th>thr {'>'} 0.3</th>
                <th>thr {'<'} 0.3</th>
              </tr>
              <tr>
                <th>분류 데이터</th>
                <td>{positiveImgCount}</td>
                <td>{negativeImgCount}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className={cx('right-box', !isTableShow && 'hide')}>
          {/* <div className={cx('button-box')}>
            <Button type='secondary' size='small' onClick={compressModel}>
              압축
            </Button>
            <img
              className={cx('reset-icon')}
              src='/images/icon/refresh.svg'
              alt='reset'
              onClick={resetResult}
            />
          </div> */}
          <div className={cx('title')}>개선 전 모델</div>
          <table>
            <tbody>
              <tr>
                <th></th>
                <th>압축 전</th>
                <th>압축 후</th>
                <th>INT8 변환 후</th>
              </tr>
              <tr>
                <th>용량</th>
                <td>{beforeTableData ? beforeTableData.big.volume : '-'}</td>
                <td>{beforeTableData ? beforeTableData.compress.volume : '-'}</td>
                <td>{beforeTableData ? beforeTableData.quantize.volume : '-'}</td>
              </tr>
              <tr>
                <th>정확도</th>
                <td>{beforeTableData ? beforeTableData.big.acc : '-'}</td>
                <td>{beforeTableData ? beforeTableData.compress.acc : '-'}</td>
                <td>{beforeTableData ? beforeTableData.quantize.acc : '-'}</td>
              </tr>
            </tbody>
          </table>
          <div className={cx('title')}>개선 후 모델</div>
          <table>
            <tbody>
              <tr>
                <th></th>
                <th>압축 전</th>
                <th>압축 후</th>
                <th>INT8 변환 후</th>
              </tr>
              <tr>
                <th>용량</th>
                <td>{afterTableData ? afterTableData.big.volume : '-'}</td>
                <td>{afterTableData ? afterTableData.compress.volume : '-'}</td>
                <td>{afterTableData ? afterTableData.quantize.volume : '-'}</td>
              </tr>
              <tr>
                <th>정확도</th>
                <td>{afterTableData ? afterTableData.big.acc : '-'}</td>
                <td>{afterTableData ? afterTableData.compress.acc : '-'}</td>
                <td>{afterTableData ? afterTableData.quantize.acc : '-'}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div className={cx('image-box')}>
        <div className={cx('input-box')}>
          <label className={cx('label')}>입력 데이터</label>
          {inputSrc ? (
            <img
              className={cx('image')}
              src={`data:image/jpeg;base64,${inputSrc}`}
              alt='input'
            />
          ) : (
            <div className={cx('empty-box')}>
              <img src='/images/icon/00-ic-basic-img-off.svg' alt='NoImage' />
              <span>No Image</span>
            </div>
          )}
        </div>
        <div className={cx('output-box')}>
          <label className={cx('label')}>추론 데이터</label>
          {outputSrc ? (
            <img
              className={cx('image')}
              src={`data:image/jpeg;base64,${outputSrc}`}
              alt='output'
            />
          ) : (
            <div className={cx('empty-box')}>
              <img src='/images/icon/00-ic-basic-img-off.svg' alt='NoImage' />
              <span>No Image</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
export default OutputImageRealtime;
