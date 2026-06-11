// component
import {
  InputText,
  Radio,
  Selectbox,
  Textarea,
  Tooltip,
} from '@tango/ui-react';

import { Fragment } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import FbRadio from '@src/components/atoms/input/Radio';
import File from '@src/components/molecules/File';
import MultiSelect from '@src/components/molecules/MultiSelect';

import classNames from 'classnames/bind';
import style from './DockerImageFormModalContent.module.scss';

const cx = classNames.bind(style);

function DockerImageFormModalContent({
  type,
  imageName,
  imageNameError,
  imageDesc,
  imageDescError,
  dockerUrl,
  dockerUrlError,
  dockerTag,
  dockerTagError,
  dockerTagOptions,
  dockerNGC,
  dockerNGCError,
  dockerNGCOptions,
  dockerNGCVersion,
  dockerNGCVersionError,
  dockerNGCVersionOptions,
  uploadTypeOptions,
  uploadType,
  files,
  filesError,
  releaseTypeOptions,
  releaseType,
  textInputHandler,
  multiSelectHandler,
  wsList,
  prevSelectedWsList,
  selectedWsListError,
  fileInputHandler,
  selectInputHandler,
  radioBtnHandler,
  progressRef,
  onRemove,
  commitComment,
  commitCommentError,
  isCommit,
  // setRef,
}) {
  const { t } = useTranslation();

  return (
    <>
      <div className={cx('input-wrap', 'mb-32')}>
        <label className={cx('label')}>{t('dockerImageName.label')}</label>
        <InputText
          size='medium'
          name='imageName'
          status={imageNameError ? 'error' : 'default'}
          value={imageName}
          options={{ maxLength: 50 }}
          placeholder={t('dockerImageName.placeholder')}
          isReadOnly={type === 'EDIT_DOCKER_IMAGE'}
          testId='docker-image-name-input'
          onChange={textInputHandler}
          onClear={() => {
            textInputHandler({ target: { value: '', name: 'imageName' } });
          }}
          disableLeftIcon={true}
          disableClearBtn={false}
          customStyle={{ fontSize: '14px' }}
          autoFocus
        />
      </div>
      <div className={cx('textarea-wrap', 'mb-32')}>
        <label className={cx('label')}>
          {t('dockerImageDescription.label')}
          <span>{t('optional.label')}</span>
        </label>
        <span className={cx('text-length-box')}>
          <span className={cx('text-length')}>{imageDesc.length}</span>/1000
        </span>
        <Textarea
          placeholder='dockerImageDescription.placeholder'
          status={
            imageDescError === null
              ? ''
              : imageDescError === ''
              ? 'success'
              : 'error'
          }
          value={imageDesc}
          name='imageDesc'
          testId='docker-image-desc-input'
          customStyle={{
            fontSize: '14px',
            height: '86px',
          }}
          onChange={textInputHandler}
          t={t}
        />
      </div>
      <div
        className={cx(
          'radio-wrap',
          ['DUPLICATE_DOCKER_IMAGE', 'EDIT_DOCKER_IMAGE'].includes(type) &&
            'duplicate',
          'mb-32',
        )}
      >
        <label className={cx('label')}>
          {t('dockerImageCreateType.label')}
        </label>
        <Radio
          options={uploadTypeOptions.map((data, i) => ({
            ...data,
            labelStyle: {
              fontSize: '14px',
              fontFamily: 'SpoqaM',
              textWrap: 'nowrap',
            },
            disabled:
              i === 3 ||
              data.disabled ||
              type === 'DUPLICATE_DOCKER_IMAGE' ||
              data.value === 4 ||
              (!isCommit && data.value === 6) ||
              (isCommit && data.value !== 6),
          }))}
          name='uploadType'
          selectedValue={uploadType}
          onChange={(e) => {
            radioBtnHandler('uploadType', e.currentTarget.value);
          }}
          tooltipValue={new Set([2, 3, 5, 6])}
          onTooltipRender={(value) => {
            if (value === 2) {
              return (
                <Tooltip
                  contents={
                    <div className={cx('tooltip')}>
                      <p className={cx('tooltip-header')}>Tar</p>
                      <p className={cx('tar-highlight')}>
                        {t('image.tar.tooltip.message1')}
                      </p>
                      <p className={cx('tar-normal')}>
                        {t('image.tar.tooltip.message2')}
                      </p>
                    </div>
                  }
                  contentsCustomStyle={{
                    border: '0.5px solid #DEE9FF',
                    borderRadius: '10px',
                    boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
                    padding: '0px',
                    width: '320px',
                  }}
                  contentsAlign={{ vertical: 'bottom', horizontal: 'center' }}
                  iconCustomStyle={{
                    width: '24px',
                    marginLeft: '2px',
                  }}
                />
              );
            }
            if (value === 3) {
              return (
                <Tooltip
                  contentsCustomStyle={{
                    border: '0.5px solid #DEE9FF',
                    borderRadius: '10px',
                    boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
                    padding: '0px',
                    width: '440px',
                  }}
                  contents={
                    <div className={cx('tooltip')}>
                      <p className={cx('tooltip-header')}>Dockerfile build</p>
                      <p className={cx('docker-hightlight')}>
                        {t('image.dockerfileBuild.tooltip.message1')}
                      </p>
                      <p className={cx('docker-normal')}>
                        {t('image.dockerfileBuild.tooltip.message2')}
                      </p>
                      <p className={cx('docker-notice')}>
                        {t('image.dockerfileBuild.tooltip.message3')}
                      </p>
                    </div>
                  }
                  contentsAlign={{ vertical: 'bottom', horizontal: 'center' }}
                  iconCustomStyle={{
                    width: '24px',
                    marginLeft: '2px',
                  }}
                />
              );
            }
            if (value === 5) {
              return (
                <Tooltip
                  contentsCustomStyle={{
                    border: '0.5px solid #DEE9FF',
                    borderRadius: '10px',
                    boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
                    padding: '0px',
                    width: '440px',
                  }}
                  contents={
                    <div className={cx('tooltip')}>
                      <p className={cx('tooltip-header')}>NGC</p>
                      <p className={cx('ngc-hightlight')}>
                        {t('image.ngc.tooltip.message1')}
                      </p>
                    </div>
                  }
                  contentsAlign={{ vertical: 'bottom', horizontal: 'center' }}
                  iconCustomStyle={{
                    width: '24px',
                    marginLeft: '2px',
                  }}
                />
              );
            }
            if (value === 6) {
              return (
                <Tooltip
                  contents={
                    <div className={cx('tooltip')}>
                      <p className={cx('tooltip-header')}>Commit</p>
                      <p className={cx('commit-highlight')}>
                        {t('image.commit.tooltip.message1')}
                      </p>
                      <p className={cx('commit-notice')}>
                        {t('image.commit.tooltip.message2')}
                      </p>
                    </div>
                    // <div>
                    //   <p>{t('image.commit.tooltip.message1')}</p>
                    //   <p className={cx('notice')}>
                    //     {t('image.commit.tooltip.message2')}
                    //   </p>
                    // </div>
                  }
                  contentsAlign={{ vertical: 'bottom', horizontal: 'right' }}
                  iconCustomStyle={{
                    width: '24px',
                    marginLeft: '2px',
                  }}
                  contentsCustomStyle={{
                    border: '0.5px solid #DEE9FF',
                    borderRadius: '10px',
                    boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
                    padding: '0px',
                    width: '320px',
                  }}
                />
              );
            }
          }}
          t={t}
        />
      </div>
      {!['DUPLICATE_DOCKER_IMAGE', 'EDIT_DOCKER_IMAGE'].includes(type) && (
        <div className={cx('input-group')}>
          {uploadType === 1 && (
            <>
              <div className={cx('input-wrap')}>
                <label className={cx('label', 'normal')}>{'Pull URL'}</label>
                <InputText
                  size='medium'
                  name='dockerUrl'
                  status={dockerUrlError ? 'error' : 'default'}
                  value={dockerUrl}
                  placeholder={t('pull.placeholder')}
                  isReadOnly={
                    type === 'EDIT_DOCKER_IMAGE' ||
                    type === 'DUPLICATE_DOCKER_IMAGE'
                  }
                  onChange={textInputHandler}
                  onClear={() => {
                    textInputHandler({
                      target: { value: '', name: 'dockerUrl' },
                    });
                  }}
                  disableLeftIcon={true}
                  disableClearBtn={false}
                  testId='dockerimage-pull-input'
                />
              </div>
            </>
          )}
          {(uploadType === 2 || uploadType === 3) && (
            <File
              label='Docker Image File'
              name='files'
              onChange={fileInputHandler}
              value={files}
              error={filesError}
              btnText='file.select.label'
              onRemove={onRemove}
              progressRef={progressRef}
              single
              disabled={
                type === 'EDIT_DOCKER_IMAGE' ||
                type === 'DUPLICATE_DOCKER_IMAGE'
              }
              labelStyle={{
                marginBottom: '16px',
                fontFamily: 'SpoqaB',
                fontWeight: 'normal',
                fontSize: '14px',
              }}
            />
          )}
          {uploadType === 4 && (
            <div className={cx('selectbox-wrap')}>
              <label className={cx('label', 'mb-16')}>
                Tag Name [ID | Node IP]
              </label>
              {type === 'EDIT_DOCKER_IMAGE' ||
              type === 'DUPLICATE_DOCKER_IMAGE' ? (
                <InputText
                  size='medium'
                  name='dockerTag'
                  value={dockerTag?.label}
                  isReadOnly
                  disableLeftIcon
                />
              ) : (
                <Selectbox
                  type='search'
                  size='medium'
                  selectedItem={dockerTag}
                  list={dockerTagOptions}
                  placeholder={t('dockerTag.placeholder')}
                  onChange={(value) => {
                    selectInputHandler('dockerTag', value);
                  }}
                  customStyle={{
                    fontStyle: {
                      selectbox: {
                        color: '#121619',
                        textShadow: 'None',
                      },
                    },
                  }}
                />
              )}
            </div>
          )}
          {uploadType === 5 && (
            <Fragment>
              {type === 'CREATE_DOCKER_IMAGE' && (
                <Fragment>
                  <div className={cx('selectbox-wrap')}>
                    <div className={cx('order-cont')}>
                      <div className={cx('number-cont')}>
                        <span>1</span>
                      </div>
                      <label className={cx('label')}>
                        NGC [Publisher] Name
                      </label>
                    </div>
                    <div className={cx('line-cont')}>
                      <div className={cx('line')}></div>
                      <div className={cx('selectbox-cont')}>
                        <Selectbox
                          type='search'
                          size='medium'
                          selectedItem={dockerNGC}
                          list={dockerNGCOptions}
                          placeholder={t('dockerNGC.placeholder')}
                          isReadOnly={dockerNGCOptions.length === 0}
                          customStyle={{
                            fontStyle: {
                              selectbox: {
                                color: '#121619',
                                textShadow: 'None',
                              },
                            },
                          }}
                          onChange={(value) => {
                            selectInputHandler('dockerNGC', value);
                          }}
                          scrollAutoFocus={true}
                        />
                        <span className={cx('error')}>{t(dockerNGCError)}</span>
                      </div>
                    </div>
                  </div>
                  <div className={cx('selectbox-wrap')}>
                    <div className={cx('order-cont')}>
                      <div className={cx('number-cont')}>
                        <span>2</span>
                      </div>
                      <label className={cx('label')}>Tag Version</label>
                    </div>
                    <div className={cx('line-cont')}>
                      <div className={cx('line')}></div>
                      <div className={cx('selectbox-cont')}>
                        <Selectbox
                          type='search'
                          size='medium'
                          selectedItem={dockerNGCVersion}
                          list={dockerNGCVersionOptions}
                          placeholder={t('dockerNGCVersion.placeholder')}
                          isReadOnly={
                            !dockerNGC || dockerNGCVersionOptions.length === 0
                          }
                          customStyle={{
                            fontStyle: {
                              selectbox: {
                                color: '#121619',
                                textShadow: 'None',
                              },
                            },
                          }}
                          onChange={(value) => {
                            selectInputHandler('dockerNGCVersion', value);
                          }}
                          scrollAutoFocus={true}
                        />
                        <span className={cx('error')}>
                          {t(dockerNGCVersionError)}
                        </span>
                      </div>
                    </div>
                  </div>
                </Fragment>
              )}

              <div className={cx('order-input-wrap')}>
                <div className={cx('order-cont')}>
                  <div className={cx('number-cont')}>
                    <span>3</span>
                  </div>
                  <label className={cx('label')}>
                    Pull URL
                    {/* {type === 'CREATE_DOCKER_IMAGE' ? 'Pull URL' : 'Pull URL'} */}
                  </label>
                </div>
                <div className={cx('line-cont', 'height-38')}>
                  <div className={cx('line', 'height-52')}></div>
                  <div className={cx('selectbox-cont', 'mb-0')}>
                    <InputText
                      size='medium'
                      placeholder={
                        type === 'CREATE_DOCKER_IMAGE'
                          ? t('dockerNGCUrl.placeholder')
                          : ''
                      }
                      status={dockerUrlError ? 'error' : 'default'}
                      value={dockerUrl}
                      name='dockerUrl'
                      disableLeftIcon
                      isReadOnly={
                        type === 'DUPLICATE_DOCKER_IMAGE' ||
                        type === 'EDIT_DOCKER_IMAGE'
                      }
                      disableClearBtn
                      onChange={textInputHandler}
                    />
                    <span className={cx('error')}>
                      {dockerUrlError && t(dockerUrlError)}
                    </span>
                  </div>
                </div>
              </div>
            </Fragment>
          )}
          {uploadType === 6 && (
            <>
              <div className={cx('input-wrap')}>
                <label className={cx('label', 'normal')}>
                  {t('addDockerImgComment.label')}
                  <span className={cx('optional-txt')}>
                    {t('optional.label')}
                  </span>
                </label>
                <InputText
                  size='medium'
                  name='commitComment'
                  value={commitComment}
                  placeholder={t('commentWrite.label')}
                  isReadOnly={
                    type === 'EDIT_DOCKER_IMAGE' ||
                    type === 'DUPLICATE_DOCKER_IMAGE'
                  }
                  onChange={textInputHandler}
                  onClear={() => {
                    textInputHandler({
                      target: { value: '', name: 'commitComment' },
                    });
                  }}
                  disableLeftIcon={true}
                  disableClearBtn={false}
                />
              </div>
            </>
          )}
        </div>
      )}
      <div className={cx('radio-wrap', 'mb-32')}>
        <label className={cx('label')}>{t('releaseType.label')}</label>
        <FbRadio
          name='releaseType'
          options={releaseTypeOptions}
          value={releaseType}
          onChange={(e) => {
            radioBtnHandler('releaseType', e.currentTarget.value);
          }}
          isLabelColor
        />
      </div>
      {/* workspaceId가 undefined이고 ReleaseType으로 Workspace가 선택된 경우에만 설렉트 박스 제공 */}
      {releaseType === 0 && (
        // {(!workspaceId && releaseType === 0) && (
        <MultiSelect
          // innerRef={setRef}
          label='workspaces.label'
          listLabel='availableWorkspaces.label'
          selectedLabel='chosenWorkspaces.label'
          list={wsList} // 초기 목록
          selectedList={prevSelectedWsList} // 초기 선택된 목록
          onChange={multiSelectHandler} // 변경 이벤트
          placeholder={'inputWorkspace.label'}
        />
      )}
    </>
  );
}

export default DockerImageFormModalContent;
