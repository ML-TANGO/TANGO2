import { useState, useEffect } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button, Selectbox } from '@jonathan/ui-react';
import OptionLabel from '@src/components/atoms/OptionLabel';

// CSS module
import classNames from 'classnames/bind';
import style from './DatasetCheckModalContainer.module.scss';

const cx = classNames.bind(style);

function DatasetCheckModalContainer({ list, closeFunc, submit }) {
  const { t } = useTranslation();
  const [checkPathOpen, setCheckPathOpen] = useState(false);
  const [datasetOptions, setDatasetOptions] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [datasetViewList, setDatasetViewList] = useState([]);
  const [templateData, setTemplateData] = useState([]);
  const [selectedOption, setSelectedOption] = useState(null);
  const [datasetMessage, setDatasetMessage] = useState('');

  /**
   * 클릭한 name 받아와서 해당 데이터 필터 후에 재귀함수 호출
   * @param {Object} datasetName
   */
  const searchSelectHandler = (datasetName) => {
    setSelectedOption(datasetName);
    setDatasetMessage('');
    const newSelectedDataset = {
      label: datasetName?.label,
    };
    setSelectedDataset(newSelectedDataset);

    const selectedItem = list?.filter(
      (datasetList) => datasetList.name === datasetName?.label,
    )[0]?.data_training_form;

    // selectedItem을 이용해서 재귀함수로 넣어준다

    const datasetViewList = datasetViewHandler(selectedItem);
    setDatasetViewList(datasetViewList);
    setTemplateData(selectedItem);
    setCheckPathOpen(true);
  };

  /** 메시지 특정 글자 색 변경 핸들러
   * @param {String} message 전체 메시지
   * @param {String} koText 한글 키워드
   * @param {String} enText 영어 키워드
   * @param {String} color 변경 색상
   * @returns html 태그
   */
  const messageColoringHandler = ({ message, koText, enText, color }) => {
    let messageValid = message.indexOf(koText);
    let newMessage = '';
    let prevMessage = '';
    let currMessage = '';
    let nextMessage = '';
    if (messageValid !== -1) {
      // 한국어
      prevMessage = message.substring(0, messageValid);
      currMessage = message.substring(
        messageValid,
        koText.length + messageValid,
      );
      nextMessage = message.substring(messageValid + koText.length);
    } else {
      // 영어
      messageValid = message.indexOf(enText);
      prevMessage = message.substring(0, messageValid);
      currMessage = message.substring(
        messageValid,
        enText.length + messageValid,
      );
      nextMessage = message.substring(messageValid + enText.length);
    }
    newMessage = (
      <>
        {prevMessage}
        <span style={{ color }}>{currMessage}</span>
        {nextMessage}
      </>
    );
    return newMessage;
  };

  /**
   * 클릭시 적합성 보여주는 재귀 함수
   * @param {Object, Array} list
   * @param {*} bucket
   * @param {*} childPath
   * @returns html tag
   */
  const datasetViewHandler = (list, bucket = '') => {
    if (Array.isArray(list) && list?.length > 0) {
      const childrenBucket = [];

      list.forEach((dataTrainingForm, idx) => {
        childrenBucket.push(
          <div key={idx}>{datasetViewHandler(dataTrainingForm, bucket)}</div>,
        );
      });

      return childrenBucket;
    } else {
      // bucket 생성은 무조건 객체만 받아서 시작
      if (list?.name && list?.name !== '/') {
        let type = list?.type;
        let imageColor = '';

        if (type === 'dir') {
          //file은 type이 애초에 file
          type = 'folder';
        }
        imageColor = `/images/icon/ic-${type}-gray.svg`;
        let textColor = '#3e3e3e';

        if (list.generable && list.argparse) {
          //? blue
          let result = [];
          const firstNewMessage = messageColoringHandler({
            message: t('validDatasetOfSelectedModel.message'),
            koText: '적합',
            enText: 'meets the requirements',
            color: '#439f6e',
          });
          result.push(firstNewMessage);

          const secondNewMessage = messageColoringHandler({
            message: t('parsingDatasetOfSelectedModel.message'),
            koText: 'Parsing 대상',
            enText: 'parsing target',
            color: '#2d76f8',
          });
          result.push(secondNewMessage);
          const newMessage = (
            <>
              {firstNewMessage}
              <br />
              {secondNewMessage}
            </>
          );
          setDatasetMessage(newMessage);
          imageColor = `/images/icon/ic-${type}-blue.svg`;
          textColor = '#2d76f8';
        } else if (list.generable === false) {
          //! red
          const newMessage = messageColoringHandler({
            message: t('invalidDatasetOfSelectedModel.message'),
            koText: '부적합',
            enText: 'not meet the requirements',
            color: '#d91a0c',
          });
          setDatasetMessage(newMessage);
          imageColor = `/images/icon/ic-${type}-red.svg`;
          textColor = '#d91a0c';
        }

        const newBucket = (
          <>
            {bucket}
            <div
              style={{
                paddingLeft: `${list?.depth > 2 ? (list.depth - 2) * 32 : 0}px`,
              }}
              className={cx('dataset-content')}
            >
              <div className={cx('dataset-content-test')}>
                <div className={cx('file-wrap')}>
                  <div className={cx('file-box')}>
                    <div
                      className={cx(
                        list.depth > 1 ? 'dataset-content-border' : '',
                      )}
                    ></div>
                    <img
                      className={cx('icon')}
                      style={{
                        marginLeft: `${list.depth === 1 && 4}px`,
                      }}
                      src={imageColor}
                      alt={type}
                    />
                    <div
                      style={{ color: textColor }}
                      className={cx('folder-name')}
                    >
                      {list.name}
                    </div>
                    <div className={cx(list.category ? 'category' : '')}>
                      {list.category}
                    </div>
                    {list.argparse && submit && (
                      <div className={cx('parse-box')}>parser</div>
                    )}
                  </div>
                  {list?.category_description && (
                    <div
                      className={cx('description')}
                      style={{
                        paddingLeft: `${list?.depth !== 1 ? 30 : 0}px`,
                      }}
                    >
                      {list.category_description}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        );
        if (list.children?.length > 0) {
          //자식이 여러개면 idx === 0 일때 빼고 bukcet을 더하지 않는다
          const testArr = [];
          list.children.forEach((item, idx) =>
            testArr.push(
              <div key={idx}>
                {idx === 0 ? newBucket : ''}
                {datasetViewHandler(item)}
              </div>,
            ),
          );
          return testArr;
        } else {
          //자식이 없으면 끝
          return newBucket;
        }
      }
    }
  };

  useEffect(() => {
    const optionsBucket = [];
    list?.forEach(({ name, generable, id }) => {
      const newOptionObj = {
        label: name,
        generable,
        value: id,
        StatusIcon: () =>
          generable === false && (
            <OptionLabel
              borderColor={'#ff2211'}
              textColor={'#ff2211'}
              width={
                t('inadequate.label').length > 3 &&
                t('inadequate.label').length * 6
              }
            >
              {t('inadequate.label')}
            </OptionLabel>
          ),
      };
      optionsBucket.push(newOptionObj);
    });
    setDatasetOptions([...optionsBucket]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [list]);

  useEffect(() => {
    if (datasetMessage === '' || datasetViewList?.length === 1) {
      const newMessage = messageColoringHandler({
        message: t('validDatasetOfSelectedModel.message'),
        koText: '적합',
        enText: 'meets the requirements',
        color: '#439f6e',
      });
      setDatasetMessage(newMessage);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDataset]);

  return (
    <div className={cx('dataset-box')}>
      <div className={cx('dataset-wrap')}>
        <Selectbox
          type='search'
          list={datasetOptions}
          selectedItem={selectedDataset}
          placeholder={t('builtInDatasetSelect.label')}
          onChange={(e) => searchSelectHandler(e)}
          customStyle={{
            fontStyle: {
              selectbox: {
                color: '#121619',
                textShadow: 'None',
              },
            },
          }}
        />
      </div>
      {checkPathOpen && (
        <div className={cx('dataset-content-wrap')}>
          {datasetViewList}
          <div className={cx('dataset-content-message')}>
            {!submit && (
              <>
                <span
                  className={cx(
                    datasetViewList?.length !== 1
                      ? 'dataset-content-line'
                      : 'dataset-none-line',
                  )}
                ></span>
                <span className={cx('dataset-content-text')}>
                  {datasetMessage}
                </span>
              </>
            )}
          </div>
        </div>
      )}
      <div className={cx('close-btn')}>
        <Button type='none-border' onClick={closeFunc}>
          {t('close.label')}
        </Button>
        {submit && (
          <Button
            type='primary'
            onClick={() => submit.func(templateData, selectedOption)}
          >
            {t(submit.text)}
          </Button>
        )}
      </div>
    </div>
  );
}

export default DatasetCheckModalContainer;
