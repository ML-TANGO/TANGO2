import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useParams } from 'react-router-dom';

import _ from 'lodash';

import {
  deleteAnalyzerGraph,
  getAnalyzerInfo,
} from '@src/apis/flightbase/dataset/analysis';
import { openModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import DataAnalysisDetailHeader from './DataAnalysisDetailHeader';
import DataAnalysisGraph from './DataAnalysisGraph';
import useSSEAnalyzerGaph from './useSSEAnalyzerGaph';

import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './UserDatasetAnalysisDetailContent.module.scss';

const cx = classNames.bind(style);

// * get 정보
const getDetailInfo = async (id, setInfoData) => {
  const response = await getAnalyzerInfo(id);
  const { result, status, error, message } = response;
  if (status === STATUS_SUCCESS) {
    setInfoData(result);
  } else {
    errorToastMessage(error, message);
  }
};

//* delete 그래프
const onDeleteGraph = async (type, analyzerId, idList, getRefresh) => {
  const body = { analyzer_id: analyzerId };

  if (type === 'individual') {
    body.graph_id_list = idList;
  }

  const response = await deleteAnalyzerGraph(body);

  const { status, error, message } = response;

  if (status === STATUS_SUCCESS) {
    defaultSuccessToastMessage('delete');
    // getRefresh();
  } else {
    errorToastMessage(error, message);
  }
};

function UserDatasetAnalysisDetailContent() {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { id: wId, did: aId } = useParams();

  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const [infoData, setInfoData] = useState(null);
  const [searchValue, setSearchValue] = useState('');
  const [graphData, setGraphData] = useState([]);
  const [filteredGraphData, setFilteredGraphData] = useState([]);
  const [selectedGraphType, setSelectedGraphType] = useState(null);
  const [selectedColumn, setSelectedColumn] = useState(null);
  const [checkedId, setCheckedId] = useState([]);
  const [showInfoId, setShowInfoId] = useState([]); // 클릭했을 때 info 정보 보여주기
  const [isLoading, setIsLoading] = useState(true);

  // * selectbox 핸들러 /  type === type, type === column
  const selectboxHandler = (type, selectedItem) => {
    setSearchValue('');
    let newGraphData = _.cloneDeep(graphData);
    if (type === 'type') {
      setSelectedGraphType(selectedItem);

      if (selectedColumn && selectedColumn.value !== 9) {
        newGraphData = newGraphData.filter(
          (item) => item.column === selectedColumn.label,
        );
      }

      // 2차 필터링: type 기준
      if (selectedItem && selectedItem.value !== 9) {
        newGraphData = newGraphData.filter(
          (item) => item.type === selectedItem.label,
        );
      }
    } else if (type === 'column') {
      setSelectedColumn(selectedItem);

      if (selectedGraphType && selectedGraphType.value !== 9) {
        newGraphData = newGraphData.filter(
          (item) => item.type === selectedGraphType.label,
        );
      }

      // 2차 필터링: type 기준
      if (selectedItem && selectedItem.value !== 9) {
        newGraphData = newGraphData.filter(
          (item) => item.column === selectedItem.label,
        );
      }
    }

    setFilteredGraphData(newGraphData);
  };

  // * search 핸들러
  const onChangeSearchValue = (value) => {
    let newGraphData = _.cloneDeep(graphData);
    if (selectedGraphType && selectedGraphType?.value !== 9) {
      newGraphData = newGraphData.filter(
        (item) => item.type === selectedGraphType.label,
      );
    }
    if (selectedColumn && selectedColumn?.value !== 9) {
      newGraphData = newGraphData.filter(
        (item) => item.column === selectedColumn.label,
      );
    }

    if (value === '' || value === undefined) {
      setFilteredGraphData(newGraphData);
    } else {
      newGraphData = newGraphData.filter((item) => item.name.includes(value));
      setFilteredGraphData(newGraphData);
    }
    setSearchValue(value);
  };

  const [tabValue, setTabValue] = useState(0);

  const checkboxHandler = (id) => {
    setCheckedId((prevCheckedId) => {
      if (prevCheckedId.includes(id)) {
        return prevCheckedId.filter((item) => item !== id);
      } else {
        return [...prevCheckedId, id];
      }
    });
  };
  const showInfoHandler = (id) => {
    setShowInfoId((prevId) => {
      if (prevId.includes(id)) {
        return prevId.filter((item) => item !== id);
      } else {
        return [...prevId, id];
      }
    });
  };

  // const isExcuteBtn = tabValue === 1;

  // const handleTab = useCallback((v) => {
  //   setTabValue(v);
  // }, []);

  // ** 그래프 추가 버튼
  const onClickAddGraph = () => {
    dispatch(
      openModal({
        modalType: 'ADD_DATASET_GRAPH',
        modalData: {
          submit: {
            text: 'add.label',
            func: () => {
              // fetchProcessList();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          wId,
          aId,
          getRefresh: () => {},
          // getGraphData(aId, setGraphData, setFilteredGraphData),
        },
      }),
    );
  };

  useSSEAnalyzerGaph(aId, userName, setGraphData, setIsLoading);

  useEffect(() => {
    if (aId) {
      getDetailInfo(aId, setInfoData);
      // getGraphData(aId, setGraphData, setFilteredGraphData);
    }
  }, [aId]);

  useEffect(() => {
    // newGraphData가 들어오면 기존 선택된 검색/타입/컬럼 필터를 그대로 적용
    let newData = _.cloneDeep(graphData);

    // 타입 필터
    if (selectedGraphType && selectedGraphType?.value !== 9) {
      newData = newData.filter(
        (item) => item.type === selectedGraphType?.label,
      );
    }
    // 컬럼 필터
    if (selectedColumn && selectedColumn?.value !== 9) {
      newData = newData.filter((item) => item.column === selectedColumn?.label);
    }
    // 검색어 필터
    if (searchValue) {
      newData = newData.filter((item) => item.name.includes(searchValue));
    }

    setFilteredGraphData(newData);
  }, [graphData, selectedGraphType, selectedColumn, searchValue]);

  // * 탭 형식으로 수정 될 수 있어서 기존 탭방식으로 두겠습니다
  return (
    <div className={cx('data-detail-cont')}>
      <DataAnalysisDetailHeader
        t={t}
        wId={wId}
        aId={aId}
        infoData={infoData}
        checkedId={checkedId}
        originGraphData={graphData}
        graphData={filteredGraphData}
        searchValue={searchValue}
        selectedGraphType={selectedGraphType}
        selectedColumn={selectedColumn}
        onClickAddGraph={onClickAddGraph}
        selectboxHandler={selectboxHandler}
        onChangeSearchValue={(value) => onChangeSearchValue(value)}
        onDeleteGraph={(type) => onDeleteGraph(type, aId, checkedId)}
      />

      {tabValue === 0 && (
        <DataAnalysisGraph
          infoData={infoData}
          originGraphData={graphData}
          graphData={filteredGraphData}
          checkboxHandler={checkboxHandler}
          checkedId={checkedId}
          showInfoHandler={showInfoHandler}
          showInfoId={showInfoId}
          isLoading={isLoading}
        />
      )}
      {/* {tabValue === 1 && < />} */}
    </div>
  );
}

export default UserDatasetAnalysisDetailContent;
