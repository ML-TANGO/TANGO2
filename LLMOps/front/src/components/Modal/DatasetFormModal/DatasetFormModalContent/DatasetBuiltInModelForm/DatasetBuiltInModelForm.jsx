import { useCallback, useEffect, useState } from 'react';
import { Selectbox } from '@jonathan/ui-react';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

// Components
import DatasetUploadForm from '../DatasetUploadForm';
import DatasetBuiltInModelFormList from '../DatasetBuiltInModelFormList/DatasetBuiltInModelFormList';
import GoogleDrive from '@src/components/atoms/GoogleDrive';

// Utils
import { errorToastMessage } from '@src/utils';

// CSS module
import style from './DatasetBuiltInModelForm.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const DataSetBuiltInModelForm = ({
  datasetName,
  progressRefs,
  onChange,
  uploadMethodNumber,
  googleDriveHandler,
  googleAccessTokenHandler,
  builtInModelNamesHandler,
  builtInModelIdHandler,
  templateData,
  selectedOption,
  t,
}) => {
  const [selectableOptions, setSelectableOptions] = useState([]); // selector에서 선택 할 수 있는 모델 이름들
  const [selectedOptionsLists, setSelectedOptionsLists] = useState(); // 선택 할 수 있는 모델 데이터들
  const [selectedOptionsDatas, setSelectedOptionsDatas] = useState(); // 선택 된 모델의 폴더, 파일 데이터
  const [selectedItem, setSelectedItem] = useState({
    label: '',
    value: '',
  });

  // 데이터셋 구조 가이드 있을때
  useEffect(() => {
    if (templateData && selectedOption) {
      setSelectedOptionsDatas(templateData);
      setSelectedItem(selectedOption);
      builtInModelIdHandler(selectedOption.value);
    }
  }, [templateData, selectedOption, builtInModelIdHandler]);

  useEffect(() => {
    modelTemplateDataAPI();
  }, []);

  const modelTemplateDataAPI = async () => {
    const response = await callApi({
      url: 'datasets/new_model_template',
      method: 'get',
    });
    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const selectableOptionData = result?.map((data) => {
        return { label: data.name, value: data.id };
      });
      setSelectedOptionsLists(result);
      setSelectableOptions(selectableOptionData);
    } else {
      errorToastMessage(error, message);
    }
  };

  const onChangeSelectBox = (valueObj) => {
    const data = selectedOptionsLists.reduce((acc, cur) => {
      if (cur.id === valueObj.value) return cur;
      else return acc;
    });
    builtInModelIdHandler(data.id);
    setSelectedOptionsDatas(data.data_training_form);
    setSelectedItem(valueObj);
  };

  const RootOrEmptyForm = ({ firstData, uploadMethodNumber }) => {
    return (
      <>
        {firstData && (
          <>
            <p className={cx('form-type')}>
              {`/${datasetName || `{${t('datasetName.label')}}`}/`}
            </p>
            {firstData.category_description !== '' && (
              <div className={cx('root-text')}>{firstData.category}</div>
            )}
            {firstData.category_description !== '' && (
              <div className={cx('root-category-description')}>
                {firstData.category_description}
              </div>
            )}
          </>
        )}
        {uploadMethodNumber === 0 ? (
          <DatasetUploadForm
            onChange={onChange}
            progressRefs={progressRefs}
            t={t}
            datasetName={datasetName}
            defaultText={firstData ? false : true}
          />
        ) : (
          <GoogleDrive
            googleAccessTokenHandler={googleAccessTokenHandler}
            onChange={googleDriveHandler}
            t={t}
          />
        )}
      </>
    );
  };

  const ChildrenForm = ({ firstData, uploadMethodNumber }) => {
    return (
      <>
        {firstData && (
          <>
            <p className={cx('form-type')}>
              {`/${datasetName || `{${t('datasetName.label')}}`}/`}
            </p>
            {firstData.category !== '' &&
            firstData.category_description !== '' ? (
              <>
                <div className={cx('root-text')}>{firstData.category}</div>
                <div className={cx('root-category-description')}>
                  {firstData.category_description}
                </div>
              </>
            ) : (
              <p className={cx('form-desc')}>{t('topLevelPath.message')}</p>
            )}
            <DatasetBuiltInModelFormList
              builtInModelData={selectedOptionsDatas}
              onChange={onChange}
              t={t}
              datasetName={datasetName}
              progressRefs={progressRefs}
              uploadMethodNumber={uploadMethodNumber}
              googleDriveHandler={googleDriveHandler}
              googleAccessTokenHandler={googleAccessTokenHandler}
              builtInModelNamesHandler={builtInModelNamesHandler}
            />
          </>
        )}
      </>
    );
  };

  const BuiltInForm = useCallback(() => {
    return selectedOptionsDatas.length > 1 ? (
      <ChildrenForm
        firstData={selectedOptionsDatas[0]}
        uploadMethodNumber={uploadMethodNumber}
      />
    ) : (
      <RootOrEmptyForm
        firstData={selectedOptionsDatas[0]}
        uploadMethodNumber={uploadMethodNumber}
      />
    );
  }, [selectedOptionsDatas, uploadMethodNumber]);

  return (
    <>
      <div className={cx('select-container')}>
        <Selectbox
          type='search'
          list={selectableOptions}
          placeholder={t('selecteModel.placeholder')}
          selectedItem={selectedItem}
          onChange={onChangeSelectBox}
          customStyle={{
            fontStyle: {
              selectbox: {
                color: '#121619',
                textShadow: 'None',
              },
            },
          }}
        />
        <hr className={cx('divider')} />
      </div>
      {selectedItem.value ? (
        <BuiltInForm />
      ) : (
        <div className={cx('model-lists')}>
          <span className={cx('default-message')}>
            {t('noSelecteModel.label')}
          </span>
        </div>
      )}
    </>
  );
};
export default DataSetBuiltInModelForm;
