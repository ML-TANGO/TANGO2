// Components
import { Button, Checkbox, InputText } from '@tango/ui-react';

import { useEffect, useRef, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import Loading from '@src/components/atoms/loading/Loading';

// CSS module
import classNames from 'classnames/bind';
import style from './DatasetMoveCopy.module.scss';

const cx = classNames.bind(style);

function DatasetMoveCopy({
  datasetName,
  tree,
  newFolder,
  targetPath,
  destinationPath,
  pathSelectHandler,
  pathInputHandler,
  isCopy,
  isCopyCheckHandler,
  confirmHandler,
  cancelHandler,
  disabled,
  tempFolderName,
  btnCustomStyle,
}) {
  const { t } = useTranslation();
  const popup = useRef(null);
  const [mount, setMount] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [isNewFolderOpen, setIsNewFolderOpen] = useState(false);
  const [selectedPath, setSelectedPath] = useState('');

  /**
   * 선택 위치 설정
   */
  useEffect(() => {
    let path = targetPath.join('/') || '/';
    if (destinationPath !== '') {
      path = destinationPath;
    }
    if (newFolder !== '') {
      path =
        destinationPath !== '/'
          ? `${destinationPath}/${newFolder}`
          : `/${newFolder}`;
    }
    setSelectedPath(path);
  }, [destinationPath, newFolder, targetPath, isNewFolderOpen]);

  /**
   * 첫 선택 위치를 현재 위치로 설정
   */
  useEffect(() => {
    if (mount === false) {
      setMount(true);
      let path = targetPath.join('/') || '/';
      if (path === `/${tempFolderName}`) {
        // 임시 폴더일 경우
        path = '/';
      }

      setSelectedPath(path);
      pathSelectHandler(path);
    }
  }, [targetPath, tempFolderName, pathSelectHandler, mount]);

  return (
    <>
      <div className={cx('wrapper')} ref={popup}>
        <div className={cx('btn')}>
          <Button
            type='gray-light'
            onClick={() => {
              setIsOpen(!isOpen);
            }}
            disabled={disabled}
            customStyle={btnCustomStyle}
          >
            {t('moveCopy.label')}
          </Button>
        </div>
        {isOpen && (
          <>
            <div className={cx('popup')}>
              <div className={cx('header')}>
                <img
                  src='/images/icon/ic-data-folder-dataset-gray.svg'
                  alt='dataset'
                  width={26}
                  height={26}
                />
                <span className={cx('dataset-name')}>{datasetName}</span>
              </div>
              <div className={cx('body')}>
                <div className={cx('path-box')}>
                  <label className={cx('label')}>{t('selectPath.label')}</label>
                  <InputText
                    size='small'
                    value={selectedPath}
                    isReadOnly
                    disableLeftIcon
                    disableClearBtn
                    customStyle={{ width: '100%' }}
                  />
                  <Button
                    type='none-border'
                    size='small'
                    customStyle={{ width: '40px', padding: '4px' }}
                    onClick={() => {
                      if (newFolder === '') {
                        setIsNewFolderOpen(!isNewFolderOpen);
                      }
                    }}
                    title={t('newFolder.label')}
                  >
                    <img
                      src='/images/icon/ic-data-folder-add-gray.svg'
                      alt='new folder'
                    />
                  </Button>
                </div>
                {isNewFolderOpen && (
                  <div className={cx('new-folder-box')}>
                    <label className={cx('label')}>
                      {t('newFolder.label')}
                    </label>
                    <InputText
                      size='small'
                      leftIcon={'/images/icon/ic-data-folder-add-gray.svg'}
                      closeIcon={'/images/icon/close-c.svg'}
                      onChange={pathInputHandler}
                      placeholder={t('folderName.placeholder')}
                      value={newFolder}
                      customStyle={{ width: '100%' }}
                      disableLeftIcon={false}
                      disableClearBtn
                    />
                  </div>
                )}
                {tree.length > 0 ? (
                  <ul
                    className={cx(
                      'select-list',
                      isNewFolderOpen ? 'shrink' : '',
                    )}
                  >
                    {tree.map((value, idx) => {
                      return (
                        <li
                          key={idx}
                          className={cx(
                            value === destinationPath || value === selectedPath
                              ? 'selected'
                              : '',
                          )}
                          title={value}
                          onClick={() => pathSelectHandler(value)}
                        >
                          {value}
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <div className={cx('select-list', 'loading')}>
                    <Loading />
                  </div>
                )}
              </div>
              <div className={cx('footer')}>
                <Checkbox
                  label={t('makeCopy.label')}
                  checked={isCopy}
                  onChange={isCopyCheckHandler}
                />
                <div className={cx('btn-box')}>
                  <Button
                    type='none-border'
                    size='small'
                    onClick={() => {
                      cancelHandler();
                      setIsNewFolderOpen(false);
                      setIsOpen(false);
                      setSelectedPath(targetPath.join('/') || '/');
                    }}
                  >
                    {t('cancel.label')}
                  </Button>
                  <Button
                    type='primary'
                    size='small'
                    disabled={!destinationPath}
                    onClick={() => {
                      confirmHandler();
                      setIsNewFolderOpen(false);
                      setIsOpen(false);
                      setSelectedPath(targetPath.join('/') || '/');
                    }}
                  >
                    {t('confirm.label')}
                  </Button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
      {isOpen && <div className={cx('shadow')}></div>}
    </>
  );
}

export default DatasetMoveCopy;
