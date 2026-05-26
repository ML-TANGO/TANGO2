import { Fragment } from 'react';

// component
import MultiSelect from '@src/components/molecules/MultiSelect';

// CSS module
import classNames from 'classnames/bind';
import style from '@src/components/Modal/DockerImageDeleteModal/DockerImageDeleteModal.module.scss';
const cx = classNames.bind(style);

function DockerImageDeleteModalContent(contentProps) {
  const { list, selectedList, func, t } = contentProps;
  return (
    <>
      <div className={cx('message')}>
        {t('deleteDockerImagePopup.message')
          .split('\n')
          .map((text, i) => (
            <Fragment key={i}>
              {text} <br />
            </Fragment>
          ))}
      </div>

      <MultiSelect
        listLabel='deleteWorkspaceSelect.title.label'
        selectedLabel='deleteWorkspaceSelectAll.title.label'
        list={list} // 초기 목록
        selectedList={selectedList} // 초기 선택된 목록
        onChange={(listItem) => func(listItem)} // 변경 이벤트
        readOnly={false}
        error={''}
        placeholder={'inputWorkspace.label'}
      />
    </>
  );
}

export default DockerImageDeleteModalContent;
