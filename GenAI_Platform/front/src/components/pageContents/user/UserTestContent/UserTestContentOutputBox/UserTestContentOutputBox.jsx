import { useTranslation } from 'react-i18next';

import UserTestContentOutputHeader from './UserTestContentOutputHeader/UserTestContentOutputHeader';
import OutputColumnChart from './OutputColumnChart/OutputColumnChart';
import OutputObject from './OutputObject/OutputObject';
import OutputPieChart from './OutputPieChart/OutputPieChart';
import OutputNerTable from './OutputNerTable/OutputNerTable';
import OutputTable from './OutputTable/OutputTable';
import OutputVideo from './OutputVideo/OutputVideo';
import OutputAudio from './OutputAudio/OutputAudio';
import OutputImage from './OutputImage/OutputImage';
import OutputText from './OutputText/OutputText';

import classNames from 'classnames/bind';
import style from './UserTestContentOutputBox.module.scss';
const cx = classNames.bind(style);

const UserTestContentOutputBox = ({
  outputObj,
  outputTypeList,
  outputStatus,
}) => {
  const { t } = useTranslation();
  return (
    <>
      {outputObj && outputTypeList.length > 0 && (
        <div className={cx('output-box')}>
          <UserTestContentOutputHeader
            outputStatus={outputStatus}
            outputObj={outputObj}
          />
          <div className={cx('result-container')}>
            {outputTypeList.map((outputType, k) => {
              try {
                switch (outputType) {
                  case 'text':
                    return outputObj.text.map((output, idx) => {
                      return Object.keys(output).map((key, i) => (
                        <OutputText
                          key={`${outputType}_${idx}_${i}`}
                          output={output}
                          objectKey={key}
                        />
                      ));
                    });
                  case 'image':
                    return outputObj.image.map((output, idx) => {
                      return Object.keys(output).map((key, i) => (
                        <OutputImage
                          key={`${outputType}_${idx}_${i}`}
                          output={output}
                          objectKey={key}
                        />
                      ));
                    });
                  case 'audio':
                    return outputObj.audio.map((output, idx) => {
                      return Object.keys(output).map((key, i) => (
                        <OutputAudio
                          key={`${outputType}_${idx}_${i}`}
                          output={output}
                          objectKey={key}
                        />
                      ));
                    });
                  case 'video':
                    return outputObj.video.map((output, idx) => {
                      return Object.keys(output).map((key, i) => (
                        <OutputVideo
                          key={`${outputType}_${idx}_${i}`}
                          outputType={outputType}
                          output={output}
                          objectKey={key}
                        />
                      ));
                    });
                  case 'table':
                    return outputObj.table.map((output, idx) => (
                      <OutputTable
                        key={`${outputType}_${idx}`}
                        idx={idx}
                        output={output}
                      />
                    ));
                  case 'ner-table':
                    return outputObj['ner-table'].map((output, idx) => (
                      <OutputNerTable
                        key={`${outputType}_${idx}`}
                        output={output}
                        idx={idx}
                      />
                    ));
                  case 'piechart':
                    return outputObj.piechart.map((output, idx) => (
                      <OutputPieChart
                        key={`${outputType}_${idx}`}
                        idx={idx}
                        output={output}
                      />
                    ));
                  case 'columnchart':
                    return outputObj.columnchart.map((output, idx) => (
                      <OutputColumnChart
                        key={`${outputType}_${idx}`}
                        idx={idx}
                        output={output}
                      />
                    ));
                  case 'obj':
                    return outputObj.obj.map((output, idx) => {
                      return Object.keys(output).map((key, i) => {
                        const file = new Blob([output[key].obj], {
                          type: 'text/plain',
                        });
                        const objectURL = URL.createObjectURL(file);
                        return (
                          <OutputObject
                            key={`${idx}-${i}`}
                            objectURL={objectURL}
                            objectKey={key}
                          />
                        );
                      });
                    });
                  default:
                    throw new Error(`Output type format Error.`);
                }
              } catch (error) {
                return (
                  <p className={cx('error-text')} key={k}>
                    {t('serviceResult.error.message', {
                      key: outputType,
                    })}
                  </p>
                );
              }
            })}
          </div>
        </div>
      )}
    </>
  );
};

export default UserTestContentOutputBox;
