// i18n
import { useTranslation } from 'react-i18next';
import { Redirect, Route } from 'react-router-dom';

import PageTitle from '@src/components/atoms/PageTitle';

import InstanceTab from './InstanceTab';
// Components
import SummaryTab from './SummaryTab';
import WorkspacesTab from './WorkspcaesTab';

import classNames from 'classnames/bind';
// CSS module
import style from './AdminRecordContent.module.scss';

const cx = classNames.bind(style);

const navList = [
  { label: 'summary.label', path: '/admin/records/summary' },
  { label: 'workspaces.label', path: '/admin/records/workspaces' },
  { label: 'resources.label', path: '/admin/records/instance' },
];

function AdminRecordContent() {
  const { t } = useTranslation();

  return (
    <div id='AdminRecordContent'>
      <PageTitle>{t('records.label')}</PageTitle>
      <div className={cx('content')}>
        {/* 피그마 내보내기 버튼으로 인해 페이지 내부에서 사용 */}
        {/* <RecordsNav navList={navList} /> */}
        <Route exact path='/admin/records'>
          <Redirect to='/admin/records/summary' />
        </Route>
        <Route path='/admin/records/summary'>
          <SummaryTab navList={navList} />
        </Route>
        <Route path='/admin/records/workspaces'>
          <WorkspacesTab navList={navList} />
        </Route>
        <Route path='/admin/records/instance'>
          <InstanceTab navList={navList} />
        </Route>
      </div>
    </div>
  );
}

export default AdminRecordContent;
