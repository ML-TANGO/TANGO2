import { Translation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './OutputNerTable.module.scss';
const cx = classNames.bind(style);

const OutputNerTable = ({ output, idx }) => {
  const { t } = Translation();
  return (
    <div className={cx('result-table')}>
      <label className={cx('title')}>{Object.keys(output)[idx]}</label>
      {output[Object.keys(output)[idx]].map(({ sentence, entities }, i) => (
        <table key={i} className={cx('table')}>
          <thead>
            <tr>
              <th>{t('sentence.label')}</th>
              <th>{t('word.label')}</th>
              <th>{t('mainEntity.label')}</th>
              <th>{t('detailEntity.label')}</th>
            </tr>
          </thead>
          <tbody>
            {entities.map(
              (
                { word, main_entity_name: main, detail_entity_name: detail },
                j,
                list,
              ) => (
                <tr key={j}>
                  {j === 0 && (
                    <td rowSpan={list.length} className={cx('rowspan')}>
                      {sentence}
                    </td>
                  )}
                  <td>{word}</td>
                  <td>{main}</td>
                  <td>{detail}</td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      ))}
    </div>
  );
};

export default OutputNerTable;
