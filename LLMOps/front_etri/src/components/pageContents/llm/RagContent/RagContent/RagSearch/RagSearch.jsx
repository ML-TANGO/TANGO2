import { ButtonV2, Textarea } from '@tango/ui-react';

import {
  getRagRetrievalInstance,
  postRagRetrievalTest,
} from '@src/apis/llm/rag';
import InfoIcon from '@src/static/images/icon/00-gray-tooltip-icon.svg';
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { handleRagReset, handleSetRagState } from '@src/store/modules/llmRag';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import PlaygroundRangeBar from '../../../PlaygroundContent/PlaygroundRangeBar';
import RagInstance from '../RagInstance';
import OutputCom from './OutputCom';

import classNames from 'classnames/bind';
import style from './RagSearch.module.scss';

const cx = classNames.bind(style);

const rangeBarTitle = [
  {
    valueTitle: 'maxChunk',
    min: 1,
    max: 100,
    step: 1,
  },
];

// ** [계산] 검색 중지 버튼
const calIsDisabled = (searchStatus) => {
  if (!searchStatus) return true;
  const { status } = searchStatus;

  if (status === 'stop' || status === 'pending' || status === 'installing')
    return true;
  return false;
};

// ** [계산] 인스턴스 자원 display 유무
const calIsInstance = (searchStatus) => {
  if (!searchStatus) return true;
  const { status } = searchStatus;

  if (status === 'pending' || status === 'installing') return true;
  return false;
};

const RagSearch = memo(function RagSearch({ navList, data, ...rest }) {
  const { t } = useTranslation();

  const match = useRouteMatch();
  const { setting, info, searchStatus, searchOutput } = useSelector(
    (state) => state.llmRag,
    shallowEqual,
  );
  const { id: workspaceId, rid: ragId } = match.params;

  const [textValue, setTextValue] = useState('');

  const [instanceInfo, setInstanceInfo] = useState(null);

  const [loading, setLoading] = useState(false);

  const [chunk, setChunk] = useState(3);

  const getInstance = useCallback(async () => {
    const res = await getRagRetrievalInstance(ragId);

    const { result, status, error, message } = res;

    if (status === STATUS_SUCCESS) {
      setInstanceInfo(result);
    } else {
      errorToastMessage(error, message);
    }
  }, [ragId]);

  const history = useHistory();

  const dispatch = useDispatch();

  const { userName } = useSelector((state) => state.auth, shallowEqual);

  const onChangeTextArea = (value) => {
    setTextValue(value.target.value);
  };

  // const handleRangeBar = ({ setting, value, max }) => {
  //   setRangeBarData((prev) => ({
  //     ...prev,
  //     [setting]: Number(value) >= max ? max : Number(value),
  //   }));
  // };

  const handleRangeBar = (e) => {
    setChunk(+e.target.value);
  };

  // ** UI 비활성화 여부
  const isDisabled = calIsDisabled(searchStatus);
  const isInstance = calIsInstance(searchStatus);

  const filteredRest = useMemo(() => {
    const { tReady, dispatch, ...remainingProps } = rest;
    return remainingProps;
  }, [rest]);

  const onClickSearch = async () => {
    setLoading(true);
    const res = await postRagRetrievalTest({
      ragId,
      input: textValue,
      chunk: chunk,
    });

    const { result, status, message, error } = res;
    if (status === STATUS_SUCCESS) {
      // creating
      const { data, status } = result;

      dispatch(
        handleSetRagState({
          type: 'searchOutput',
          searchOutput: data,
        }),
      );
    } else {
      errorToastMessage(error, message);
    }
    setLoading(false);
  };

  useEffect(() => {
    getInstance();
  }, [getInstance]);

  return (
    <div className={cx('container')}>
      <div className={cx('left', isDisabled && 'disabled')}>
        <div className={cx('left-top')}>
          <div className={cx('title')}>
            {t('input.label')}
            <ButtonV2 // 삭제
              type='clear'
              size='l'
              colorType='red'
              label={t('initial')}
              disabled={isDisabled || textValue === ''}
              onClick={() => setTextValue('')}
              style={{ width: '66px', height: '30px' }}
            />
          </div>
          <Textarea
            value={textValue}
            onChange={onChangeTextArea}
            placeholder={t('llm.rag.search.text.placeholder')}
            // maxLength={}
            isDisabled={isDisabled}
            autoFocus={true}
            customStyle={{
              height: '442px',
              marginTop: '32px',
            }}
          />
          <div className={cx('chunk')}>
            {/* <div className={cx('sub-title')}>{t('ragChunkCount.label')}</div> */}
            <div className={cx('count')}>
              {rangeBarTitle.map(({ min, max, step }) => {
                return (
                  <PlaygroundRangeBar
                    label={t('llm.rag.searchResult.label')}
                    value={chunk}
                    min={min}
                    max={max}
                    step={step}
                    disabled={isDisabled}
                    onChange={handleRangeBar}
                    // handleRefresh={handleRefreshRangeBar}
                    tooltipContent={t('llm.rag.search.tooltip.message')}
                  />
                );
              })}
            </div>
          </div>
          <ButtonV2 // 추가
            type='outline'
            size='l'
            label={t('search.label')}
            disabled={textValue === ''}
            isLoading={loading}
            onClick={onClickSearch}
            style={{ width: '100%', marginTop: '16px' }}
          />
        </div>
        {isInstance && <RagInstance instanceInfo={instanceInfo} />}
      </div>
      <div className={cx('right', isDisabled && 'disabled')}>
        <div className={cx('title')}>{t('output.label')}</div>
        {searchOutput && (
          <div className={cx('search-content')}>
            <OutputCom data={searchOutput} />
          </div>
        )}
        {!searchOutput && (
          <div className={cx('noData')}>
            {t('llm.rag.search.btnClick.label')}
          </div>
        )}
      </div>
    </div>
  );
});

export default RagSearch;
