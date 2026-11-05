import React, { useEffect } from 'react';
import { useDispatch } from 'react-redux';
import { useHistory } from 'react-router-dom';

import { ButtonV2, InputText, Selectbox } from '@jonathan/ui-react';

import { openConfirm } from '@src/store/modules/confirm';
import { loadModalComponent } from '@src/modal';

// CSS Module
import classNames from 'classnames/bind';
import style from './DataAnalysisDetailHeader.module.scss';

const cx = classNames.bind(style);

// * [계산] 컬럼 종류
const calIsColumns = (graphData, t) => {
  const seenLabels = new Set();
  const columnsArray = [];

  // 'total.label' 객체를 먼저 추가
  const totalLabel = {
    label: t('total.label'),
    value: 9,
  };
  columnsArray.push(totalLabel);
  seenLabels.add(totalLabel.label);

  // graphData 순회하며 중복되지 않는 column 값 추가
  graphData.forEach((item, index) => {
    const label = item.column;
    const value = index;

    if (!seenLabels.has(label)) {
      columnsArray.push({ label, value });
      seenLabels.add(label);
    }
  });

  // graphData가 비어있을 경우, 'total.label'만 포함
  if (graphData.length === 0) {
    return [totalLabel];
  }

  return columnsArray;
};

export default function DataAnalysisDetailHeader({
  t,
  wId,
  infoData,
  checkedId,
  searchValue,
  originGraphData,
  graphData,
  selectboxHandler,
  onChangeSearchValue,
  onClickAddGraph,
  selectedGraphType,
  selectedColumn,
  onDeleteGraph,
}) {
  const history = useHistory();

  const dispatch = useDispatch();

  const handleHistoryBack = () => {
    history.goBack(-1);
  };

  const readyOnlySelectbox = originGraphData?.length === 0;

  const columnList = calIsColumns(originGraphData, t);

  const selectboxList = [
    { label: t('total.label'), value: 9 },
    { label: 'line', value: 0 },
    { label: 'bar', value: 1 },
    { label: 'pie', value: 2 },
  ];

  // ** 그래프 개별 삭제
  const onDeleteGraphModal = (e, id, title) => {
    e.stopPropagation();

    dispatch(
      openConfirm({
        title: 'graphDelete.label',
        content: 'graphDeletePopup.message',
        testid: 'graph-delete-modal',
        submit: {
          text: 'delete.label',
          func: () => {
            onDeleteGraph('individual');
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        confirmMessage: title,
      }),
    );
  };

  // * 그래프 전체 삭제
  const onDeleteAllGraph = (e, id) => {
    e.stopPropagation();

    dispatch(
      openConfirm({
        title: 'graphAllDelete.label',
        content: 'graphAllDeletePopup.messaeg',
        testid: 'graph-delete-modal',
        submit: {
          text: 'delete.label',
          func: () => {
            // onDelete(trainingId);
            // onDelete(id);
            onDeleteGraph('all');
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        confirmMessage: t('deleteAll.label'),
      }),
    );
  };

  useEffect(() => {
    loadModalComponent('ADD_DATASET_GRAPH');
  }, []);
  return (
    <div className={cx('header-cont')}>
      <button className={cx('back-btn')} onClick={handleHistoryBack}>
        <img
          src='/src/static/images/icon/00-ic-basic-arrow-02-left.svg'
          alt='back-icon'
          loading='lazy'
        />
        <span>{t('dataAnalyze.label')}</span>
      </button>
      <div className={cx('title-wrapper')}>
        <div className={cx('title-cont')}>
          <h1 className={cx('title')}>{infoData ? infoData?.name : '-'}</h1>
          <ButtonV2
            size='l'
            label={t('graphAdd.label')}
            // disabled={onClickAddGraph}
            onClick={onClickAddGraph}
          />
        </div>
      </div>

      <div className={cx('btn-list')}>
        <div className={cx('form')}>
          <Selectbox // 그래프 유형
            isReadOnly={readyOnlySelectbox}
            size='medium'
            list={selectboxList}
            selectedItem={selectedGraphType}
            placeholder={t('graphType.label')}
            // customStyle={{ globalForm: { width: '200px' } }}

            onChange={(value) => {
              // ? selectboxHandler()
              selectboxHandler('type', value);
            }}
            scrollAutoFocus={true}
          />
        </div>
        <div className={cx('form')}>
          <Selectbox // 컬럼 종류
            isReadOnly={readyOnlySelectbox}
            size='medium'
            list={columnList}
            selectedItem={selectedColumn}
            placeholder={t('columnType.label')}
            // customStyle={{ selectboxForm: { height: '36px' } }}
            onChange={(value) => {
              selectboxHandler('column', value);
            }}
            scrollAutoFocus={true}
          />
        </div>
        <div className={cx('bar')} />
        <div className={cx('form')}>
          <InputText // 그래프 이름 입력
            placeholder={t('graphNameInput.label')}
            onChange={(e) => onChangeSearchValue(e.target.value)}
            name='name'
            value={searchValue}
            // status={!validate ? 'error' : 'default'}
            isReadOnly={!originGraphData || originGraphData?.length === 0}
            // options={{ maxLength: 50 }}

            customStyle={{ fontSize: '14px', width: '200px' }}
            disableLeftIcon={false}
          />
        </div>
        <ButtonV2
          colorType='lightRed'
          size='l'
          label={t('deleteAll.label')}
          disabled={!originGraphData || originGraphData?.length === 0}
          onClick={onDeleteAllGraph}
        />

        <ButtonV2
          colorType='red'
          size='l'
          label={t('delete.label')}
          disabled={checkedId.length === 0}
          onClick={onDeleteGraphModal}
        />
      </div>
    </div>
  );
}
