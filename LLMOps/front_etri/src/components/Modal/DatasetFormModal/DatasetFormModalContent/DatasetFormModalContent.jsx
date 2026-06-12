// Components
import { InputText, Radio, Selectbox, Textarea } from '@tango/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './DatasetFormModalContent.module.scss';

const cx = classNames.bind(style);

function DatasetFormModalContent({
  workspaceId,
  type,
  name,
  textInputHandler,
  nameError,
  description,
  workspaceOptions,
  selectedWorkspace,
  selectInputHandler,
  uploadMethodOptions,
  uploadMethod,
  templateFileFolderHandler,
  progressRefs,
  accessTypeOptions,
  accessType,
  radioBtnHandler,
  googleDriveHandler,
  googleAccessTokenHandler,
  descriptionError,
  droneBm,
  droneStartDate,
  droneEndDate,
  timeRangeHandler,
  droneArea,
  droneAreaError,
  droneAccess,
  droneOptionHandler,
  builtInTemplate,
  builtInModelTemplateOptions,
  builtInModelNamesHandler,
  builtInModelIdHandler,
  templateData,
  selectedOption,
  t,
}) {
  return (
    <div className={cx('form')}>
      <div className={cx('input-wrap')}>
        <label className={cx('label')}>{t('datasetName.label')}</label>
        <InputText
          size='large'
          name='name'
          status={nameError ? 'error' : 'default'}
          value={name}
          options={{ maxLength: 50 }}
          placeholder={t('datasetName.placeholder')}
          onChange={textInputHandler}
          onClear={() => {
            textInputHandler({ target: { value: '', name: 'name' } });
          }}
          disableLeftIcon={true}
          disableClearBtn={false}
          autoFocus={type === 'CREATE_DATASET'}
          customStyle={{ fontSize: '14px', fontFamily: 'SpoqaM' }}
        />
        <span className={cx('error')}>{nameError && t(nameError)}</span>
      </div>
      <div className={cx('textarea-wrap')}>
        <label
          className={cx('label')}
          style={{
            lineHeight: '1.5',
          }}
        >
          {t('datasetDescription.label')}
          <span
            className={cx('optional-txt')}
            style={{
              lineHeight: '1.8',
              verticalAlign: 'baseline',
            }}
          >
            {t('optional.label')}
          </span>
        </label>
        <span className={cx('text-length-box')}>
          <span className={cx('text-length-txt')}>{description.length}</span>
          /1000
        </span>
        <Textarea
          placeholder='datasetDescription.placeholder'
          value={description}
          name='description'
          onChange={textInputHandler}
          customStyle={{
            fontFamily: 'SpoqaM',
            fontSize: '14px',
            height: '86px',
          }}
          t={t}
        />
        <span className={cx('error')}>
          {descriptionError && t(descriptionError)}
        </span>
      </div>
      <div className={cx('radio-wrap')}>
        <label className={cx('label')}>
          {t('accessType.label')}
          <div className={cx('label-right-item')}>
            {t('datasetAccessType.tooltip.message')}
          </div>
        </label>
        <Radio
          options={accessTypeOptions}
          onChange={(e) => {
            radioBtnHandler('accessType', e.currentTarget.value);
          }}
          selectedValue={accessType}
          name='accessType'
          t={t}
        />
        <span className={cx('error')}></span>
      </div>
      {!workspaceId && (
        <div className={cx('selectbox-wrap')}>
          <label className={cx('label')}>{t('workspace.label')}</label>
          <Selectbox
            type='search'
            size='large'
            placeholder='workspace.placeholder'
            list={workspaceOptions}
            selectedItem={selectedWorkspace}
            onChange={selectInputHandler}
            customStyle={{
              fontStyle: {
                selectbox: {
                  color: '#121619',
                  textShadow: 'None',
                },
              },
            }}
            t={t}
          />
          <span className={cx('error')}></span>
        </div>
      )}
      {/* {type === 'CREATE_DATASET' && (
        <div className={cx('input-wrap')}>
          <label className={cx('label', 'input-group-title')}>
            {t('uploadData.label')}
            <span className={cx('optional')}> - {t('optional.label')}</span>
          </label>
          <div className={cx('upload-option-box')}>
            <div className={cx('radio-wrap')}>
              <InputBoxWithLabel
                labelText={t('builtInModelTemplate.label')}
                labelSize='large'
                disableErrorMsg
              >
                <Radio
                  options={builtInModelTemplateOptions}
                  onChange={(e) => {
                    radioBtnHandler('builtInTemplate', e.currentTarget.value);
                  }}
                  selectedValue={builtInTemplate}
                  name='builtInTemplate'
                  t={t}
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('radio-wrap')}>
              <InputBoxWithLabel
                labelText={t('uploadType.label')}
                labelSize='large'
                disableErrorMsg
              >
                <Radio
                  options={uploadMethodOptions}
                  onChange={(e) => {
                    radioBtnHandler('uploadMethod', e.currentTarget.value);
                  }}
                  selectedValue={uploadMethod}
                  name='uploadMethod'
                  t={t}
                />
              </InputBoxWithLabel>
            </div>
          </div>
          <UploadFormWithPath datasetName={name} path='/'>
            {Number(uploadMethod) === 0 && Number(builtInTemplate) === 0 && (
              <DatasetUploadForm
                onChange={templateFileFolderHandler}
                progressRefs={progressRefs}
                t={t}
                datasetName={name}
              />
            )}
            {Number(uploadMethod) === 1 && Number(builtInTemplate) === 0 && (
              <GoogleDrive
                onChange={googleDriveHandler}
                t={t}
                datasetName={name}
                text={true}
                googleAccessTokenHandler={googleAccessTokenHandler}
              />
            )}
            {((Number(uploadMethod) === 0 && Number(builtInTemplate) === 1) ||
              (Number(uploadMethod) === 1 &&
                Number(builtInTemplate) === 1)) && (
              <DatasetBuiltInModelForm
                datasetName={name}
                progressRefs={progressRefs}
                onChange={templateFileFolderHandler}
                uploadMethodNumber={uploadMethod}
                googleDriveHandler={googleDriveHandler}
                googleAccessTokenHandler={googleAccessTokenHandler}
                builtInModelNamesHandler={builtInModelNamesHandler}
                builtInModelIdHandler={builtInModelIdHandler}
                templateData={templateData}
                selectedOption={selectedOption}
                t={t}
              />
            )}
            {Number(uploadMethod) === 2 && (
              <DroneWsDatasetSearchBox
                droneBm={droneBm}
                droneStartDate={droneStartDate}
                droneEndDate={droneEndDate}
                timeRangeHandler={timeRangeHandler}
                droneArea={droneArea}
                droneAreaError={droneAreaError}
                selectInputHandler={selectInputHandler}
                droneAccess={droneAccess}
                droneOptionHandler={droneOptionHandler}
              />
            )}
          </UploadFormWithPath>
        </div>
      )} */}
    </div>
  );
}

export default DatasetFormModalContent;
