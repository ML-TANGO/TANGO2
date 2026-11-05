// i18n
import { useTranslation } from 'react-i18next';

// Components
import { IconArrowLeft } from '@jonathan/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './PortInfo.module.scss';
const cx = classNames.bind(style);

function PortInfo({ portList }) {
  const { t } = useTranslation();
  if (portList.length === 0) return '-';
  return (
    <ul className={cx('port-list')}>
      {portList.map(
        ({ name, node_port: nodePort, target_port: targetPort }, key) => (
          <li className={cx('port-info')} key={key}>
            <div className={cx('title')}>{name}</div>
            <div className={cx('port')}>
              <span>{targetPort}(pod)</span>
              {nodePort && (
                <>
                  <IconArrowLeft width={20} height={20} viewBox={'0 0 24 24'} />
                  <span>
                    {nodePort}({t('external.label')})
                  </span>
                </>
              )}
            </div>
          </li>
        ),
      )}
    </ul>
  );
}

export default PortInfo;
