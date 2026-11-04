import { FixedSizeList as List } from 'react-window';
import { useResizeDetector } from 'react-resize-detector';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import SkeletonLine from '@src/components/atoms/SkeletonLine/SkeletonLine';

// images
import fileImage from '@src/static/images/icon/file-white.svg';

// CSS Module
import classNames from 'classnames/bind';
import style from './TrainingType.module.scss';
const cx = classNames.bind(style);

function Column({ data, index, style }) {
  const { customList, customFile, runcodeClickHandler } = data;
  const name = customList[index];

  return (
    <div
      className={cx('file', name === customFile && 'selected-file')}
      onClick={() => runcodeClickHandler({ name })}
      key={index}
      style={style}
    >
      <div className={cx('file-contents')}>
        <img src={fileImage} alt='fileImage' className={cx('file-image')} />
        <div className={cx('file-name')}>{name}</div>
      </div>
    </div>
  );
}

function CustomBottom({
  customList,
  customListStatus,
  runcodeClickHandler,
  customFile,
}) {
  const { t } = useTranslation();

  const { width, ref } = useResizeDetector();

  return (
    <div className={cx('custom-bottom')}>
      <div className={cx('list')} ref={ref}>
        {customListStatus && (
          <div
            style={{
              padding: '10px',
            }}
          >
            <SkeletonLine length={3} />
          </div>
        )}
        {!customListStatus && customList.length > 0 ? (
          // customList.map((v, i) => {
          //     return (
          //       <div
          //         className={cx('file', v === customFile && 'selected-file')}
          //         onClick={() => runcodeClickHandler({ name: v })}
          //         key={i}
          //       >
          //         <div className={cx('file-contents')}>
          //           <img
          //             src={fileImage}
          //             alt='fileImage'
          //             className={cx('file-image')}
          //           />
          //           <div className={cx('file-name')}>{v}</div>
          //         </div>
          //       </div>
          //     );
          //   })
          <List
            width={width}
            height={(() => {
              if (customList.length < 3) {
                return 90;
              }
              if (customList.length < 4) {
                return 116;
              }
              if (customList.length < 5) {
                return 156;
              }
              if (customList.length < 6) {
                return 196;
              }
              if (customList.length < 7) {
                return 226;
              }
              return 248;
            })()}
            itemCount={customList.length}
            itemSize={36}
            itemData={{
              customList,
              customFile,
              runcodeClickHandler,
            }}
          >
            {Column}
          </List>
        ) : (
          !customListStatus && (
            <div className={cx('no-data')}>{t('noData.message')}</div>
          )
        )}
      </div>
    </div>
  );
}

export default CustomBottom;
