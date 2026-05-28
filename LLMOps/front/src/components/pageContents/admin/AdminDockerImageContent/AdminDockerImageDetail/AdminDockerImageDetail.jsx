// Components
import { Button } from '@jonathan/ui-react';

import { useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import Table from '@src/components/molecules/Table';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
// CSS module
import style from './AdminDockerImageDetail.module.scss';

const cx = classNames.bind(style);

const detailColumns = [
  {
    name: 'ID',
    selector: 'Image ID',
    sortable: false,
    maxWidth: '160px',
  },
  {
    name: 'Comment',
    selector: 'Comment',
    sortable: false,
    minWidth: '300px',
  },
  {
    name: 'Author',
    selector: 'author',
    sortable: false,
    maxWidth: '130px',
  },
  {
    name: 'Committed Date',
    selector: 'CreatedAt',
    sortable: false,
    maxWidth: '230px',
  },
  {
    name: 'Added Size',
    selector: 'size',
    sortable: false,
    maxWidth: '160px',
  },
];

const AdminDockerImageDetail = ({ data }) => {
  const { t } = useTranslation();
  const [detailTableData, setDetailTableData] = useState([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [commentIsOpen, setCommentIsOpen] = useState(false);
  const {
    id,
    image_name: imageName,
    description,
    library,
    repository,
    tag,
    iid: imageId,
  } = data;

  // 라이브러리 버전 데이터 포맷 변경
  let newLibrary = {};
  if (library) {
    library.map(({ name, version }) => {
      return (newLibrary[name] = version);
    });
  }

  /**
   * 상세 데이터 Comments 테이블 데이터 받기
   */
  const getComments = async () => {
    if (!commentIsOpen) {
      setDetailLoading(true);
      const response = await callApi({
        url: `images/history?image_id=${id}`,
        method: 'get',
      });
      const { result, status, message, error } = response;
      if (status === STATUS_SUCCESS) {
        setDetailTableData(result);
        setCommentIsOpen(true);
      } else {
        errorToastMessage(error, message);
      }
      setDetailLoading(false);
    } else {
      setCommentIsOpen(false);
    }
  };

  return (
    <div className={cx('detail')}>
      <div className={cx('header')}>
        <div className={cx('title')}>
          {/* {t('detailsOf.label', { name: imageName })} */}
          <span>{imageName}</span>
          <span>{t('detailsOf')}</span>
        </div>
        <p className={cx('desc')}>{description}</p>
      </div>
      <ul className={cx('horizon-box')}>
        <li className={cx('box')}>
          <span className={cx('label')}>{t('cudaVersion.label')}</span>
          <span className={cx('value')}>{newLibrary?.cuda ?? '-'}</span>
        </li>
        <li className={cx('box')}>
          <span className={cx('label')}>{t('tensorflowVersion.label')}</span>
          <span className={cx('value')}>{newLibrary?.tensorflow ?? '-'}</span>
        </li>
        <li className={cx('box')}>
          <span className={cx('label')}>{t('mpiVersion.label')}</span>
          <span className={cx('value')}>{newLibrary?.mpi ?? '-'}</span>
        </li>
        <li className={cx('box')}>
          <span className={cx('label')}>{t('pytorchVersion.label')}</span>
          <span className={cx('value')}>{newLibrary?.torch ?? '-'}</span>
        </li>
      </ul>
      <div className={cx('block')}>
        <div className={cx('block-title')}>
          <span className={cx('name')}>{imageName}</span>
          <span>on the System</span>
        </div>
        <div className={cx('border')}></div>
        <div className={cx('info-list')}>
          <div className={cx('list-item')}>
            <label className={cx('label')}>{t('tag.label')}</label>
            <div className={cx('value')}>{tag ?? '-'}</div>
          </div>
          <div className={cx('list-item')}>
            <label className={cx('label')}>{t('image.label')} ID</label>
            <div className={cx('value')}>{imageId ?? '-'}</div>
          </div>
          <div className={cx('list-item')}>
            <label className={cx('label')}>{t('repository.label')}</label>
            <div className={cx('value')}>{repository ?? '-'}</div>
          </div>
        </div>
      </div>
      <div className={cx('table-box')}>
        <span className={cx(data.status !== 2 ? 'disabled' : '')}>
          <Button
            type='none-border'
            size='medium'
            onClick={getComments}
            iconAlign='right'
            icon={
              detailLoading
                ? '/images/icon/spinner-1s-58.svg'
                : commentIsOpen
                ? '/images/icon/00-ic-basic-arrow-02-up-blue.svg'
                : '/images/icon/00-ic-basic-arrow-02-down-blue.svg'
            }
            customStyle={{
              backgroundColor: '#F9FAFB',
              color: data.status !== 2 ? '#dbdbdb' : '#2D76F8',
              margin: '10px -20px',
              cursor: data.status !== 2 && 'not-allowed',
            }}
            disabled={data.status !== 2}
          >
            {t('dockerImage.label')} Comments
          </Button>
        </span>
        {commentIsOpen && (
          <Table
            data={detailTableData}
            columns={detailColumns}
            selectableRows={false}
            highlightOnHover={false}
            totalRows={detailTableData.length}
            hideSearchBox={true}
            loading={detailLoading}
            fixedHeader={true}
            fixedHeaderScrollHeight='235px'
          />
        )}
      </div>
    </div>
  );
};

export default AdminDockerImageDetail;
