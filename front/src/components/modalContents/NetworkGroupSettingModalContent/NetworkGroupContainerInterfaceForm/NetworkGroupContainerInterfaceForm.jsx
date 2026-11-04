import { Fragment } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import InputLabel from '@src/components/atoms/input/InputLabel';
import { Button } from '@jonathan/ui-react';

// Icons
import RemoveIcon from '@src/static/images/icon/ic-remove-red.svg';
import AddIcon from '@src/static/images/icon/00-ic-basic-plus-blue.svg';
import EditIcon from '@src/static/images/icon/ic-edit.svg';
import ErrorIcon from '@src/static/images/icon/icon-error-c-red.svg';

// CSS module
import classNames from 'classnames/bind';
import style from './NetworkGroupContainerInterfaceForm.module.scss';
const cx = classNames.bind(style);

function NetworkGroupContainerInterfaceForm({
  containerInterfaceList,
  onCreate,
  onEdit,
  onDelete,
  onEditMode,
  nameError,
}) {
  const { t } = useTranslation();

  return (
    <div className={cx('form')}>
      <div className={cx('contents')}>
        <div className={cx('title-div')}>
          <InputLabel
            labelText={`${t('network.containerInterface.status.label')} ${
              containerInterfaceList.length > 0
                ? `(${containerInterfaceList.length})`
                : ''
            }`}
            labelSize='large'
          />
          <Button
            type='primary-light'
            size='small'
            icon={AddIcon}
            onClick={onCreate}
          >
            {t('add.label')}
          </Button>
        </div>
        <div className={cx('list-container')}>
          <div className={cx('list-header')}>
            <label className={cx('center', 'number')}>
              {t('network.portIndex.label')}
            </label>
            <label className={cx('name')}>
              {t('network.containerInterface.label')}
            </label>
            <label className={cx('name')}>
              {t('network.belongingNodes.label')}
            </label>
            <label className={cx('btn')}>{t('remove.label')}</label>
          </div>
          <div className={cx('list-box')}>
            <ul className={cx('selected-list')}>
              {containerInterfaceList.length > 0 ? (
                containerInterfaceList.map(
                  (
                    {
                      id,
                      portIndex,
                      interfaceName,
                      nodeInterfaceList,
                      isDeletable,
                      isEdit,
                    },
                    idx,
                  ) => {
                    return (
                      <Fragment
                        key={`${portIndex}-${interfaceName}-${id}-${idx}`}
                      >
                        <li className={cx(isEdit && 'edit')}>
                          <span className={cx('center', 'number')}>
                            {portIndex}
                          </span>
                          {isEdit ? (
                            <span
                              className={cx('name', 'input', isEdit && 'edit')}
                              title={interfaceName}
                              spellCheck='false'
                              contentEditable='true'
                              suppressContentEditableWarning='true'
                              onFocus={() => {
                                onEditMode(idx);
                              }}
                              onBlur={(e) => {
                                onEdit(idx, e.target.innerText);
                              }}
                              onKeyPress={(e) => {
                                if (e.key === 'Enter') {
                                  e.target.blur();
                                }
                              }}
                            >
                              {interfaceName}
                            </span>
                          ) : (
                            <span
                              className={cx(
                                'name',
                                'read-only',
                                nameError[idx] !== '' ? 'error' : 'success',
                              )}
                            >
                              {interfaceName}
                              <img
                                className={cx('icon')}
                                src={EditIcon}
                                alt='edit'
                                onClick={() => onEditMode(idx)}
                              />
                            </span>
                          )}
                          <span className={cx('name')}>
                            {nodeInterfaceList &&
                              nodeInterfaceList
                                .map(
                                  ({ interface: itf, node_name: nodeName }) => {
                                    return `${itf}(${nodeName})`;
                                  },
                                )
                                .join(', ')}
                          </span>
                          <span className={cx('btn')}>
                            <img
                              className={cx(
                                'icon',
                                isDeletable ? 'active' : 'disabled',
                              )}
                              src={RemoveIcon}
                              alt='remove'
                              onClick={() => {
                                if (isDeletable) {
                                  onDelete(idx);
                                }
                              }}
                            />
                          </span>
                        </li>
                        {nameError[idx] !== '' && (
                          <li className={cx('error-message')}>
                            <img
                              className={cx('icon')}
                              src={ErrorIcon}
                              alt='error'
                            />
                            {nameError[idx] === 'other' &&
                              t(
                                'network.containerInterface.otherGroup.duplicate.message',
                              )}
                            {nameError[idx] === 'inner' &&
                              t('network.containerInterface.duplicate.message')}
                          </li>
                        )}
                      </Fragment>
                    );
                  },
                )
              ) : (
                <li className={cx('empty-message')} key='empty'>
                  {t('network.containerInterface.status.empty.message')}
                </li>
              )}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

export default NetworkGroupContainerInterfaceForm;
