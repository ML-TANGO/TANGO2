// Component
import { Button, InputText } from '@jonathan/ui-react';

// Icons
import PlusIcon from '@src/static/images/icon/00-ic-basic-plus-blue.svg';
import SearchIcon from '@src/static/images/icon/ic-search.svg';
import { useEffect, useRef, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';

import { toast } from '@src/components/Toast';

// Actions
import { closeModal, openModal } from '@src/store/modules/modal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import { errorToastMessage } from '@src/utils';

import List from './List/List';

// CSS Module
import classNames from 'classnames/bind';
import style from './Template.module.scss';

const cx = classNames.bind(style);

function Template({
  groupData,
  getGroupData,
  clickedGroupId,
  templateData,
  setClickedGroupId,
  getTemplateData,
  defaultGroupName,
  onClickNoGroup,
  noGroupSelectedStatus,
  selectedGroupData,
  onClickGroupList,
}) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const match = useRouteMatch();
  const scrollRef = useRef();
  const { id: workspaceId } = match.params;

  const [groupSearchData, setGroupSearchData] = useState(null);
  const [templateSearchData, setTemplateSearchData] = useState(null);
  const [groupSearch, setGroupSearch] = useState('');
  const [templateSearch, setTemplateSearch] = useState('');
  const [scrollY, setScrollY] = useState();

  // 툴팁 위치 계산용 - 템플릿 리스트 scrollTop 측정
  const getScrollY = () => {
    const top = scrollRef.current.scrollTop;
    setScrollY(top);
  };

  const onDeleteGroup = async (clickedGroupData) => {
    dispatch(closeModal('SERVING_DELETE'));
    const response = await callApi({
      url: `deployments/template-group/${clickedGroupData.id}`,
      method: 'delete',
    });
    const { status, error, message } = response;
    if (status === STATUS_SUCCESS) {
      getGroupData();
      // toast.success(t('template.groupDelete.message'));
    } else {
      errorToastMessage(error, message);
    }
  };

  const onDeleteTemplate = async (clickedTemplateData) => {
    dispatch(closeModal('SERVING_DELETE'));
    const response = await callApi({
      url: `deployments/template/${clickedTemplateData.id}`,
      method: 'delete',
    });
    const { status, error, message } = response;
    if (status === STATUS_SUCCESS) {
      getTemplateData();
      // toast.success(t('template.templateDelete.message'));
    } else {
      errorToastMessage(error, message);
    }
  };

  const onCreate = async (groupName, description) => {
    dispatch(closeModal('SERVING_CREATE_GROUP'));
    let body = {
      workspace_id: workspaceId,
      deployment_template_group_name: groupName,
    };
    if (description) {
      body.deployment_template_group_description = description;
    }
    const response = await callApi({
      url: 'deployments/template-group',
      method: 'post',
      body,
    });
    const { status, error, message } = response;
    if (status === STATUS_SUCCESS) {
      getGroupData();
      // toast.success(t('template.groupCreate.message'));
    } else {
      errorToastMessage(error, message);
    }
  };

  const onEdit = async (groupId, groupName, description) => {
    dispatch(closeModal('SERVING_CREATE_GROUP'));

    let body = {
      workspace_id: workspaceId,
      deployment_template_group_id: groupId,
      deployment_template_group_name: groupName,
    };
    if (description) {
      body.deployment_template_group_description = description;
    }
    const response = await callApi({
      url: 'deployments/template-group',
      method: 'put',
      body,
    });
    const { status, error, message } = response;
    if (status === STATUS_SUCCESS) {
      getGroupData();
      // toast.success(t('template.groupEdit.message'));
    } else {
      errorToastMessage(error, message);
    }
  };

  const onclickNewGroup = () => {
    dispatch(
      openModal({
        modalType: 'SERVING_CREATE_GROUP',
        modalData: {
          submit: {
            text: t('create.label'),
            func: (groupName, description) => {
              onCreate(groupName, description);
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
          data: { workspaceId },
          status: 'create',
        },
      }),
    );
  };

  const onclickEditGroup = (groupData) => {
    dispatch(
      openModal({
        modalType: 'SERVING_CREATE_GROUP',
        modalData: {
          submit: {
            text: t('edit.label'),
            func: (groupName, description) => {
              onEdit(groupData.id, groupName, description);
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
          data: { workspaceId, groupData },
          status: 'edit',
        },
      }),
    );
  };

  const onclickDeleteGroup = (clickedGroupData) => {
    dispatch(
      openModal({
        modalType: 'SERVING_DELETE',
        modalData: {
          submit: {
            text: t('delete.label'),
            func: () => {
              onDeleteGroup(clickedGroupData);
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
          modalTitle: t('template.groupDeleteTitle.label'),
          modalContents: t('template.groupDeleteInfo.message', {
            name: clickedGroupData.name,
          }),
        },
      }),
    );
  };

  const onClickNewTemplate = () => {
    dispatch(
      openModal({
        modalType: 'TEMPLATE_CREATE',
        modalData: {
          submit: {
            text: t('create.label'),
            func: () => {},
          },
          cancel: {
            text: t('cancel.label'),
          },
          data: { groupData, defaultGroupName },
          workspaceId,
          selectedGroupData,
          getTemplateData: () => {
            getTemplateData();
          },
          getGroupData: () => {
            getGroupData();
          },
        },
      }),
    );
  };

  const onClickEditTemplate = (data) => {
    dispatch(
      openModal({
        modalType: 'TEMPLATE_EDIT',
        modalData: {
          submit: {
            text: t('edit.label'),
            func: () => {},
          },
          cancel: {
            text: t('cancel.label'),
          },
          data: { groupData, defaultGroupName },
          workspaceId,
          selectedGroupData,
          editData: data,
          getTemplateData: () => {
            getTemplateData();
          },
          getGroupData: () => {
            getGroupData();
          },
        },
      }),
    );
  };

  const onclickDeleteTemplate = (clickedTemplateData) => {
    dispatch(
      openModal({
        modalType: 'SERVING_DELETE',
        modalData: {
          submit: {
            text: t('delete.label'),
            func: () => {
              onDeleteTemplate(clickedTemplateData);
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
          modalTitle: t('template.deleteTitle.label'),
          modalContents: t('template.deleteContents.label', {
            name: clickedTemplateData.name,
          }),
        },
      }),
    );
  };

  const HeaderTitle = () => {
    if (clickedGroupId) {
      return (
        <div className={cx('grouped-title-sub')}>
          <p className={cx('group-name')}>{selectedGroupData?.name}</p>
          <p className={cx('template-label')}>
            {t('template.templateHeaderSelectedTitle.label')}
          </p>
        </div>
      );
    } else if (!noGroupSelectedStatus) {
      return (
        <div className={cx('grouped-title-sub')}>
          <p className={cx('group-name')}>
            {t('template.totalGroupTemplate.label')}
          </p>
        </div>
      );
    }
    if (!clickedGroupId && noGroupSelectedStatus) {
      return (
        <p className={cx('ungrouped-title-sub')}>
          {t('template.templateHeaderTitle.label')}
        </p>
      );
    }
  };

  const searchLogic = (searchData, value) => {
    let filteredData = searchData.filter((data) => {
      return (
        data.descriptionAssemble?.indexOf(value) >= 0 ||
        data.name?.indexOf(value) >= 0 ||
        data.user_name?.indexOf(value) >= 0 ||
        (data.description?.indexOf(value) >= 0 && data)
      );
    });
    return filteredData;
  };

  const onChangeGroupInput = (e) => {
    const value = e.target.value;
    setGroupSearch(value);
    setGroupSearchData(searchLogic(groupData, value));
  };

  const onChangeTemplateInput = (e) => {
    const value = e.target.value;
    setTemplateSearch(value);
    setTemplateSearchData(searchLogic(templateData, value));
  };

  useEffect(() => {
    getTemplateData();
    getGroupData();
    getScrollY();
    scrollRef.current.addEventListener('scroll', getScrollY);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={cx('container')}>
      <div className={cx('group-container')}>
        <div className={cx('header')}>
          <p className={cx('title')}>{t('template.tempLHeader.label')}</p>
          <InputText
            value={groupSearch}
            onChange={(e) => onChangeGroupInput(e)}
            leftIcon={SearchIcon}
            disableLeftIcon={false}
            placeholder={`${t('template.searchPlaceholderName.label')}, ${t(
              'template.searchPlaceholderDescription.label',
            )}, ${t('template.searchPlaceholderCreator.label')}`}
          />
        </div>
        <div className={cx('group-list')}>
          <Button
            type='primary-reverse'
            icon={PlusIcon}
            onClick={() => onclickNewGroup()}
            customStyle={{
              paddingLeft: '12px',
              width: '100%',
              justifyContent: 'inherit',
              marginBottom: '8px',
              fontFamily: 'SpoqaB',
            }}
            iconStyle={{ width: '16px' }}
          >
            {t('template.TempBodyGroupButton.label')}
          </Button>
          <List
            clickedGroupId={clickedGroupId}
            setClickedGroupId={setClickedGroupId}
            groupList={groupSearchData || groupData}
            deleteGroupHandler={onclickDeleteGroup}
            editGroupHandler={onclickEditGroup}
            onClickGroupList={onClickGroupList}
            onClickNoGroup={onClickNoGroup}
            noGroupSelectedStatus={noGroupSelectedStatus}
            t={t}
          />
        </div>
      </div>
      <div className={cx('template-container')}>
        <div className={cx('header')}>
          <div className={cx(clickedGroupId === null && 'ungrouped-title')}>
            <HeaderTitle />
          </div>
          <InputText
            value={templateSearch}
            onChange={(e) => onChangeTemplateInput(e)}
            leftIcon={SearchIcon}
            disableLeftIcon={false}
            placeholder={`${t('template.searchPlaceholderName.label')}, ${t(
              'template.searchPlaceholderDescription.label',
            )}, ${t('template.searchPlaceholderCreator.label')}`}
          />
        </div>
        <div className={cx('template-list')} ref={scrollRef}>
          <Button
            type='primary-reverse'
            icon={PlusIcon}
            onClick={() => onClickNewTemplate()}
            customStyle={{
              paddingLeft: '12px',
              width: '100%',
              justifyContent: 'inherit',
              marginBottom: '8px',
              fontFamily: 'SpoqaB',
            }}
            iconStyle={{ width: '16px' }}
          >
            {t('template.newTemplate.label')}
          </Button>
          <List
            scrollY={scrollY}
            templateData={templateSearchData || templateData}
            deleteTemplateHandler={onclickDeleteTemplate}
            onClickEditTemplate={onClickEditTemplate}
            t={t}
          />
        </div>
      </div>
    </div>
  );
}
export default Template;
