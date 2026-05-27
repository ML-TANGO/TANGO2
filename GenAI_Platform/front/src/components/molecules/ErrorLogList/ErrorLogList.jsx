import ContentBox from '../ContentBox';

// CSS Module
import classNames from 'classnames/bind';
import style from './ErrorLogList.module.scss';
const cx = classNames.bind(style);

function ErrorLogList({ errorLog }) {
  return (
    <ContentBox title='Error log'>
      <ul className={cx('error-log-list')}>
        {errorLog.map(
          ({ worker, request, status, time_local: timeLocal }, key) => (
            <li className={cx('error-log')} key={key}>
              <span>Worker{worker}</span>
              <span>{request}</span>
              <span>status: {status}</span>
              <span>{timeLocal}</span>
              {/* {`Worker${worker}  ${request}  status:${status}  ${time}`} */}
            </li>
          ),
        )}
      </ul>
    </ContentBox>
  );
}

export default ErrorLogList;
