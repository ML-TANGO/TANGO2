// CSS Module
import classNames from 'classnames/bind';
import style from './GuideBox.module.scss';
const cx = classNames.bind(style);

function GuideBox({ title, isTitleIcon, subtitle, textList, noticeList }) {
  return (
    <div className={cx('guide-box')}>
      <h3 className={cx('title', isTitleIcon ? 'icon' : 'no-icon')}>{title}</h3>
      <p className={cx('subtitle')}>{subtitle}</p>
      <ol start='1' className={cx('info')}>
        {textList.map((t, idx) => {
          // eslint-disable-next-line react/no-danger
          return <li key={idx} dangerouslySetInnerHTML={{ __html: t }}></li>;
        })}
      </ol>
      {noticeList && (
        <ul className={cx('notice')}>
          {noticeList.map((t, idx) => {
            return (
              // eslint-disable-next-line react/no-danger
              <li key={idx} dangerouslySetInnerHTML={{ __html: t }}></li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default GuideBox;
