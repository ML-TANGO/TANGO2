import { useEffect, useState } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button, InputText, Textarea } from '@jonathan/ui-react';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// CSS module
import classNames from 'classnames/bind';
import style from './InputDataForm.module.scss';
const cx = classNames.bind(style);

const InputDataForm = ({
  idx,
  data,
  addInputForm,
  removeInputForm,
  inputHandler, // 입력 이벤트 핸들러
  allOpen,
  allClose,
}) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const { depth, type, name, error, category, categoryDesc, argparse } = data;

  useEffect(() => {
    setIsOpen(true);
  }, [allOpen]);

  useEffect(() => {
    setIsOpen(false);
  }, [allClose]);

  return (
    <>
      <div className={cx('input-item-container', isOpen && 'open')}>
        <div
          className={cx('float-box', isOpen && 'open')}
          onClick={(e) => {
            if (!isOpen) {
              if (
                !e.target.closest('button') &&
                !e.target.closest('.event-block')
              ) {
                setIsOpen(!isOpen);
              }
            }
          }}
        >
          <div
            className={cx('depth', isOpen && 'open')}
            style={{
              paddingLeft: `${depth * 32}px`,
            }}
            onClick={() => {
              isOpen && setIsOpen(false);
            }}
          >
            <img
              src={`/images/icon/ic-arrow-${
                isOpen ? 'down-darkgray' : 'right-gray'
              }.svg`}
              alt='fold/unfold'
            />
          </div>
          <div className={cx('type')}>
            {type === 'dir' ? (
              <img
                src={`/images/icon/ic-folder-${
                  error !== '' ? 'red' : 'gray'
                }.svg`}
                alt='folder'
              />
            ) : (
              <img
                src={`/images/icon/ic-file-${
                  error !== '' ? 'red' : 'gray'
                }.svg`}
                alt='file'
              />
            )}
          </div>
          {isOpen ? (
            <div className={`${cx('text-wrap')} event-block`}>
              <InputText
                placeholder={
                  type === 'dir'
                    ? t('folderName.placeholder')
                    : t('fileName.placeholder')
                }
                name='name'
                value={name}
                size='medium'
                status={error !== '' ? 'error' : 'default'}
                onChange={(e) => {
                  inputHandler(e, idx);
                }}
                isReadOnly={depth === 0}
                disableLeftIcon
                disableClearBtn
              />
              {error !== '' && (
                <div className={cx('error-message')}>{t(error)}</div>
              )}
            </div>
          ) : (
            <>
              <div className={cx('name', error !== '' && 'error')}>{name}</div>
              <div className={cx('chip-box', depth === 0 && 'root')}>
                {argparse && (
                  <div className={cx('chip', 'argparse')} title={argparse}>
                    {argparse}
                  </div>
                )}
                {category && (
                  <div className={cx('chip', 'category')} title={category}>
                    {category}
                  </div>
                )}
              </div>
            </>
          )}
          {depth > 0 && (
            <Button
              type='none-border'
              size='small'
              icon='/images/icon/ic-delete-gray.svg'
              iconStyle={{
                width: '24px',
                height: '24px',
                marginRight: '0',
              }}
              customStyle={{
                width: '24px',
                padding: '6px',
                marginLeft: '10px',
              }}
              onClick={() => {
                removeInputForm(type, Number(depth), idx);
              }}
            ></Button>
          )}
        </div>
        {isOpen && (
          <div className={cx('input-item-box')}>
            <div className={cx('input-item')}>
              <InputBoxWithLabel
                labelText={t('category.label')}
                optionalText={t('optional.label')}
                disableErrorMsg
              >
                <InputText
                  placeholder='ex) Text, Image, Audio, Video, CSV'
                  size='medium'
                  name='category'
                  value={category || ''}
                  onChange={(e) => {
                    inputHandler(e, idx);
                  }}
                  disableLeftIcon
                  disableClearBtn
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('input-item')}>
              <InputBoxWithLabel
                labelText={t('categoryDescription.label')}
                optionalText={t('optional.label')}
                disableErrorMsg
              >
                <Textarea
                  size='medium'
                  placeholder={t('categoryDescription.placeholder')}
                  name='categoryDesc'
                  value={categoryDesc}
                  onChange={(e) => {
                    inputHandler(e, idx);
                  }}
                  maxLength={1000}
                  isShowMaxLength
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('input-item')}>
              <InputBoxWithLabel
                labelText={t('argparse.label')}
                optionalText={t('optional.label')}
                disableErrorMsg
              >
                <InputText
                  placeholder='image_dir'
                  size='medium'
                  name='argparse'
                  value={argparse}
                  onChange={(e) => {
                    inputHandler(e, idx);
                  }}
                  leftIcon='/images/icon/ic-parser.svg'
                  disableLeftIcon={false}
                  disableClearBtn
                />
              </InputBoxWithLabel>
            </div>
            {type === 'dir' && (
              <div className={cx('add-btn-box')}>
                <Button
                  type='primary-reverse'
                  icon='/images/icon/ic-add-sub-folder.svg'
                  iconStyle={{ width: '31px', height: '20px' }}
                  customStyle={{
                    background: 'transparent',
                    border: 'none',
                  }}
                  disabled={depth > 7 || error !== ''}
                  onClick={() => {
                    addInputForm('dir', Number(depth) + 1, idx);
                  }}
                >
                  {t('addSubFolder.label')}
                </Button>
                <Button
                  type='primary-reverse'
                  icon='/images/icon/ic-add-sub-file.svg'
                  iconStyle={{ width: '32px', height: '20px' }}
                  customStyle={{
                    background: 'transparent',
                    border: 'none',
                  }}
                  disabled={depth > 7 || error !== ''}
                  onClick={() => {
                    addInputForm('file', Number(depth) + 1, idx);
                  }}
                >
                  {t('addSubFile.label')}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
};

export default InputDataForm;
