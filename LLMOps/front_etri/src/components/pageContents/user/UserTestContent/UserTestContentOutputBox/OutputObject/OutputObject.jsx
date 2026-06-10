import { Translation } from 'react-i18next';
import { OBJModel } from 'react-3d-viewer';

import classNames from 'classnames/bind';
import style from './OutputObject.module.scss';
const cx = classNames.bind(style);

const OutputObject = ({ objectKey, objectURL }) => {
  const { t } = Translation();
  return (
    <div className={cx('result-obj')}>
      <label className={cx('title')}>{objectKey}</label>
      <a className={cx('download')} href={objectURL} download={`${objectKey}.obj`}>
        {t('download.label')}
      </a>
      <OBJModel src={objectURL} texPath='' />
    </div>
  );
};

export default OutputObject;
