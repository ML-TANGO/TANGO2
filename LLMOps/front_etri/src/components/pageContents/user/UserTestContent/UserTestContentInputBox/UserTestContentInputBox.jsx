import InputAudio from '../InputAudio';
import InputCanvas from '../InputCanvas';
import InputCSV from '../InputCSV';
import InputImage from '../InputImage';
import InputLLM from '../InputLLM/InputLLM';
import InputText from '../InputText';
import InputVideo from '../InputVideo';

import classNames from 'classnames/bind';
import style from './UserTestContentInputBox.module.scss';

const cx = classNames.bind(style);

const UserContentInputBox = ({
  inputFormList,
  textInputHandler,
  inputText,
  fileInputHandler,
  selectedImage,
  selectedImageSrc,
  selectedVideo,
  selectedVideoSrc,
  selectedAudio,
  selectedAudioSrc,
  selectedCSV,
  selectedCSVSrc,
  canvasInputHandler,
  selectedCanvas,
  selectedCanvasSrc,
  canvasRef,
  canvasWidth,
  canvasHeight,
  mouseMoveHandler,
  mouseDownHandler,
  mouseUpHandler,
  apiUrl,
  info,
}) => {
  return (
    <div className={cx('input-box')}>
      <div className={cx('input-form')}>
        {inputFormList &&
          inputFormList
            .filter(({ category }) => category !== 'canvas-coordinate')
            .map(
              (
                {
                  category,
                  category_description: description,
                  api_key: apiKey,
                },
                idx,
              ) => {
                // llm category

                switch (category) {
                  case 'text':
                    return (
                      <InputText
                        key={idx}
                        idx={idx}
                        apiKey={apiKey}
                        description={description}
                        textInputHandler={(e) => textInputHandler(e, idx)}
                        inputText={inputText[idx]}
                      />
                    );
                  case 'image':
                    return (
                      <InputImage
                        key={idx}
                        idx={idx}
                        apiKey={apiKey}
                        description={description}
                        fileInputHandler={fileInputHandler}
                        selectedFile={selectedImage[idx]}
                        selectedFileSrc={selectedImageSrc[idx]}
                      />
                    );
                  case 'video':
                    return (
                      <InputVideo
                        key={idx}
                        idx={idx}
                        apiKey={apiKey}
                        description={description}
                        fileInputHandler={fileInputHandler}
                        selectedFile={selectedVideo[idx]}
                        selectedFileSrc={selectedVideoSrc[idx]}
                      />
                    );
                  case 'audio':
                    return (
                      <InputAudio
                        key={idx}
                        idx={idx}
                        apiKey={apiKey}
                        description={description}
                        fileInputHandler={fileInputHandler}
                        selectedFile={selectedAudio[idx]}
                        selectedFileSrc={selectedAudioSrc[idx]}
                      />
                    );
                  case 'csv':
                    return (
                      <InputCSV
                        key={idx}
                        idx={idx}
                        apiKey={apiKey}
                        description={description}
                        fileInputHandler={fileInputHandler}
                        selectedFile={selectedCSV[idx]}
                        selectedFileSrc={selectedCSVSrc[idx]}
                      />
                    );
                  case 'canvas-image':
                    return (
                      <InputCanvas
                        key={idx}
                        idx={idx}
                        apiKey={apiKey}
                        description={description}
                        fileInputHandler={canvasInputHandler}
                        selectedFile={selectedCanvas}
                        selectedFileSrc={selectedCanvasSrc}
                        canvasWidth={canvasWidth}
                        canvasHeight={canvasHeight}
                        canvasRef={canvasRef}
                        mouseMoveHandler={mouseMoveHandler}
                        mouseDownHandler={mouseDownHandler}
                        mouseUpHandler={mouseUpHandler}
                      />
                    );
                  case 'llm-single':
                  case 'llm-multi':
                    return (
                      <InputLLM
                        key={idx}
                        idx={idx}
                        apiKey={apiKey}
                        apiUrl={apiUrl}
                        info={info}
                      />
                    );
                  default:
                    return false;
                }
              },
            )}
      </div>
    </div>
  );
};

export default UserContentInputBox;
