// i18n
import { useTranslation } from 'react-i18next';

// Components
import InputLabel from '@src/components/atoms/input/InputLabel';
import Loading from '@src/components/atoms/loading/CircleLoading';

// Icons
import RemoveIcon from '@src/static/images/icon/ic-remove-red.svg';
import AddIcon from '@src/static/images/icon/00-ic-basic-plus-blue.svg';

// CSS module
import classNames from 'classnames/bind';
import style from './NetworkGroupNodeInterfaceForm.module.scss';
const cx = classNames.bind(style);

function NetworkGroupNodeInterfaceForm({
  selectedNodeName,
  nodeList,
  interfaceList,
  nodeInterfaceList,
  getInterfaces,
  onAdd,
  onDelete,
  loading,
}) {
  const { t } = useTranslation();

  return (
    <div className={cx('form')}>
      <div className={cx('contents')}>
        <InputLabel
          labelText={`${t('network.nodeInterface.status.label')} ${
            nodeInterfaceList.length > 0 ? `(${nodeInterfaceList.length})` : ''
          }`}
          labelSize='large'
        />
        <div className={cx('list-container')}>
          <div className={cx('list-header')}>
            <label className={cx('name')}>{t('nodeName.label')}</label>
            <label className={cx('name')}>
              {t('network.nodeInterface.label')}
            </label>
            <label className={cx('center')}>
              {t('network.portIndex.label')}
            </label>
            <label className={cx('btn')}>{t('remove.label')}</label>
          </div>
          <div className={cx('list-box')}>
            <ul className={cx('selected-list')}>
              {nodeInterfaceList.length > 0 ? (
                nodeInterfaceList.map(
                  ({ nodeId, nodeName, interfaceName, portIndex }, idx) => {
                    return (
                      <li key={`${nodeName}-${interfaceName}`}>
                        <span className={cx('name')} title={nodeName}>
                          {nodeName}
                        </span>
                        <span className={cx('name')} title={interfaceName}>
                          {interfaceName}
                        </span>
                        <span className={cx('center')}>{portIndex}</span>
                        <span className={cx('btn')}>
                          <img
                            className={cx('icon')}
                            src={RemoveIcon}
                            alt='remove'
                            onClick={() => onDelete(idx, nodeId)}
                          />
                        </span>
                      </li>
                    );
                  },
                )
              ) : (
                <li className={cx('empty-message')}>
                  {t('network.nodeInterface.status.empty.message')}
                </li>
              )}
            </ul>
          </div>
        </div>
      </div>
      <div className={cx('contents')}>
        <InputLabel
          labelText={t('network.nodeInterface.add.label')}
          labelSize='large'
        />
        <div className={cx('status-box')}>
          <span className={cx('status', 'green')}>
            {t('network.nodeInterface.status.green.label')}
          </span>
          <span className={cx('status', 'yellow')}>
            {t('network.nodeInterface.status.yellow.label')}
          </span>
          <span className={cx('status', 'red')}>
            {t('network.nodeInterface.status.red.label')}
          </span>
        </div>
        <div className={cx('list-container')}>
          <div className={cx('list-header')}>
            <div className={cx('left-header')}>
              <label>{t('nodeName.label')}</label>
            </div>
            <div className={cx('right-header')}>
              <label>
                {`${t('network.nodeInterface.label')} [${t('ip.label')} / ${t(
                  'network.category.label',
                )} / SR-IOV]`}
              </label>
              <label className={cx('btn')}>{t('add.label')}</label>
            </div>
          </div>
          <div className={cx('list-box-container')}>
            <div className={cx('list-box', 'left-box')}>
              <ul className={cx('node-list')}>
                {nodeList &&
                  nodeList.map(({ id, node_name: nodeName }) => {
                    return (
                      <li
                        key={id}
                        className={cx(
                          selectedNodeName === nodeName && 'selected',
                        )}
                        onClick={() => getInterfaces(id, nodeName)}
                      >
                        {nodeName}
                      </li>
                    );
                  })}
              </ul>
            </div>
            <div className={cx('list-box', 'right-box')}>
              <ul className={cx('interface-list')}>
                {loading ? (
                  <li className={cx('loading')}>
                    <Loading size='medium' />
                  </li>
                ) : interfaceList.length > 0 ? (
                  interfaceList.map(
                    (
                      {
                        interface: interfaceName,
                        interface_ip: interfaceIp,
                        category,
                        is_virtual: isVirtual,
                        interface_status: status,
                      },
                      idx,
                    ) => {
                      return (
                        <li key={idx}>
                          <span className={cx('item-contents')}>
                            <span
                              className={cx(
                                'name',
                                status === 0
                                  ? 'green'
                                  : status === 1
                                  ? 'yellow'
                                  : 'red',
                              )}
                            >
                              {interfaceName}
                            </span>
                            <span className={cx('info')}>
                              [
                              {`${interfaceIp || '-'} / ${
                                category === 0
                                  ? t('ethernet.label')
                                  : t('infiniBand.label')
                              } / ${isVirtual ? 'VF' : 'PF'}`}
                              ]
                            </span>
                          </span>
                          <span className={cx('btn')}>
                            <img
                              className={cx('icon', 'add')}
                              src={AddIcon}
                              alt='add'
                              onClick={() => onAdd(interfaceName)}
                            />
                          </span>
                        </li>
                      );
                    },
                  )
                ) : (
                  <li className={cx('empty-message')}>
                    {t('network.nodeInterface.list.empty.message')}
                  </li>
                )}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default NetworkGroupNodeInterfaceForm;
