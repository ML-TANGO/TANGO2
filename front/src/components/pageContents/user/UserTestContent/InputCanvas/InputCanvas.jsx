// i18n
import { withTranslation } from 'react-i18next';

// Components
import File from '../File';
import InputLabelBox from '../InputLabelBox';

import classNames from 'classnames/bind';
// CSS module
import style from './InputCanvas.module.scss';

const cx = classNames.bind(style);

const InputCanvas = ({
  idx,
  apiKey,
  description,
  fileInputHandler,
  selectedFile,
  selectedFileSrc,
  canvasRef,
  canvasWidth,
  canvasHeight,
  mouseMoveHandler,
  mouseDownHandler,
  mouseUpHandler,
  t,
}) => {
  return (
    <div className={cx('input-analysis')}>
      <InputLabelBox
        idx={idx}
        apiKey={apiKey}
        description={description}
        type={t('image.label')}
      >
        <div className={cx('file-browse')} title={description}>
          <File
            name='image'
            accept='image/*'
            onChange={(e) => fileInputHandler(e)}
            value={selectedFileSrc}
          />
          <div className={cx('file-name')} title={selectedFile.name}>
            {selectedFile && selectedFile.name}
          </div>
        </div>
      </InputLabelBox>
      <div className={cx('canvas-box', selectedFileSrc && 'input-image')}>
        <canvas
          ref={canvasRef}
          width={canvasWidth}
          height={canvasHeight}
          onMouseMove={mouseMoveHandler}
          onMouseDown={mouseDownHandler}
          onMouseUp={mouseUpHandler}
        />
      </div>
    </div>
  );
};

export default withTranslation()(InputCanvas);
