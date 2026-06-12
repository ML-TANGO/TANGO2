import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';

import { InputText, Selectbox, Textarea } from '@tango/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import NewDatasetSearch from '@src/components/molecules/NewDatasetSearch';

import {
  getOptionsAnalyzerColumn,
  postAnalyzerGraph,
} from '@src/apis/flightbase/dataset/analysis';
// Actions
import { closeModal } from '@src/store/modules/modal';
// Network
import { STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import NewStyleModalFrame from '../NewStyleModalFrame';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './AddDatasetGraphModal.module.scss';

const cx = classNames.bind(style);

const graphTypes = [
  { type: 'line', src: '/images/icon/ic-dataset-graph-line.svg', value: 0 },
  { type: 'bar', src: '/images/icon/ic-dataset-graph-bar.svg', value: 1 },
  { type: 'pie', src: '/images/icon/ic-dataset-graph-pie.svg', value: 2 },
];

// ** [계산]
const calIsFooterMessage = (
  name,
  selectedDataset,
  selectedData,
  selectedGraph,
  selectedColumn,
) => {
  // "graphName.warn.message": "그래프 이름을 입력해 주세요.",
  // "graphType.warn.message": "그래프 유형을 선택해 주세요.",
  // "graphColumn.warn.message": "컬럼을 선택해 주세요.",
  const forbiddenChars = /[\\<>:*?"'|:;`{}()^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

  if (!name || name === '') {
    return 'graphName.warn.message';
  }
  if (name && forbiddenChars.test(name)) {
    return 'newNameRule.message';
  }
  if (!selectedDataset.id || selectedDataset.id === '') {
    return 'datasetSelect.message';
  }
  if (!selectedData.name || selectedData.name === '') {
    return 'dataSelecte.message';
  }
  if (!selectedGraph) {
    return 'graphType.warn.message';
  }
  if (!selectedColumn) {
    return 'visualizationField.placeholder';
  }

  return null;
};

// * get 컬럼
const getColumn = async (path, setColumn, id) => {
  const response = await getOptionsAnalyzerColumn(path, id);

  const { status, result, error, message } = response;
  if (status === STATUS_SUCCESS) {
    const columnList = result.map((v, i) => {
      return { label: v, value: i };
    });
    setColumn(columnList);
  }
};

const AddDatasetGraphModal = ({ data, type }) => {
  const { wId, aId, getRefresh } = data;

  const { auth } = useSelector((state) => ({
    auth: state.auth,
  }));
  const { userName } = auth;
  const dispatch = useDispatch();

  const [loading, setLoading] = useState(false);

  const [columnList, setColumnList] = useState([]);
  const [graphName, setGraphName] = useState('');
  const [graphDesc, setGraphDesc] = useState('');

  const [selectedGraph, setSelectedGraph] = useState(null);
  const [selectedColumn, setSelectedColumn] = useState(null);

  const [selectDataset, setSelectedDataset] = useState({ id: '', name: '' });
  const [selectData, setSelectedData] = useState({ name: '', fullPath: '' });

  const handleSelect = (type) => {
    setSelectedGraph(type);
  };

  const { t } = useTranslation();

  useEffect(() => {
    loadModalComponent('HUGGINGFACE_TOKEN_MODAL');
  }, []);

  const footerMessage = calIsFooterMessage(
    graphName,
    selectDataset,
    selectData,
    selectedGraph,
    selectedColumn,
  );

  return (
    <NewStyleModalFrame
      title={`${t('graph.label')} ${t('add.label')}`}
      type={type}
      submit={{
        text: t('add.label'),
        func: async () => {
          const body = {
            analyzer_id: aId,
            name: graphName,
            description: graphDesc,
            workspace_id: wId,
            data_path: selectData.fullPath,
            graph_type: selectedGraph.value,
            column: selectedColumn.label,
            // file_path: trainingData.selectedModel.name,
            // dataset_id: datasetData.selectedModel.id,
            file_path: selectData.fullPath,
            dataset_id: selectDataset.id,
          };

          const response = await postAnalyzerGraph(body);

          const { status, result, error, message } = response;

          if (status === STATUS_SUCCESS) {
            dispatch(closeModal('ADD_DATASET_GRAPH'));
            getRefresh();
          } else {
            errorToastMessage(error, message);
          }
        },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={!footerMessage}
      isResize={true}
      isLoading={loading}
      isMinimize={true}
      footerMessage={t(footerMessage)}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('graphName.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            placeholder={t('graphSelectName.message')}
            onChange={(e) => setGraphName(e.target.value)}
            name='workspace'
            value={graphName}
            // status={!validate ? 'error' : 'default'}
            isReadOnly={type === 'EDIT_COMMIT'}
            options={{ maxLength: 50 }}
            autoFocus={true}
            customStyle={{ fontSize: '14px' }}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={`${t('graph.label')} ${t('description.label')}`}
          optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <Textarea
            size='large'
            placeholder={t('graphSelectDesc.message')}
            value={graphDesc}
            name='description'
            onChange={(e) => setGraphDesc(e.target.value)}
            // error={descriptionError}
            // status={descriptionError ? 'error' : 'default'}
            customStyle={{ fontSize: '14px' }}
            isShowMaxLength
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('datasetSelect.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <NewDatasetSearch
            workspaceId={wId}
            selectData={selectData}
            setSelectedData={(v) => {
              setSelectedColumn(null);
              getColumn(v.fullPath, setColumnList, selectDataset.id);
              setSelectedData(v);
            }}
            selectDataset={selectDataset}
            setSelectedDataset={(v) => {
              setColumnList([]);
              setSelectedColumn(null);
              setSelectedDataset(v);
              // setSelectedData({ id: '', name: '' });
            }}
          />
          <div className={cx('message')}>{t('analysisData.message')}</div>
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('graphType.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <div className={cx('type-box')}>
            {graphTypes.map((graph) => (
              <img
                key={graph.type}
                className={cx('img', {
                  selected: selectedGraph?.type === graph.type,
                })}
                src={
                  selectedGraph?.type === graph.type
                    ? graph.src.replace('.svg', '-select.svg')
                    : graph.src
                }
                alt={graph.type}
                onClick={() => handleSelect(graph)}
              />
            ))}
          </div>
        </InputBoxWithLabel>
      </div>
      <InputBoxWithLabel
        labelText={t('visualizationField.label')}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
      >
        <Selectbox
          isReadOnly={columnList.length === 0}
          // size='large'
          list={columnList}
          selectedItem={selectedColumn}
          placeholder={t('visualizationField.placeholder')}
          // customStyle={{ selectboxForm: { height: '36px' } }}
          onChange={(value) => {
            setSelectedColumn(value);
          }}
          scrollAutoFocus={true}
        />
      </InputBoxWithLabel>
    </NewStyleModalFrame>
  );
};

export default AddDatasetGraphModal;
