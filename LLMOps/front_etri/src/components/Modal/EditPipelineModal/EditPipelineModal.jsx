import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import { InputText, Textarea, Tooltip } from '@tango/ui-react';

import Dropdown from '@src/components/atoms/Dropdown';
import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiSelect from '@src/components/molecules/MultiSelect';

import { getUsers } from '@src/apis/flightbase/options';
import { putPipelines } from '@src/apis/flightbase/pipeline';
import { closeModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import { TooltipContent } from '../AddAIPipeLineModal/AddAIPipeLineModal';
import NewStyleModalFrame from '../NewStyleModalFrame';

const accessTypeOptions = [
  { label: 'public', value: 1 },
  { label: 'Private', value: 0 },
];

export default function EditPipelineModal({ data, type }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const {
    workspaceId: workspace_id,
    handleRefresh,
    title,
    id,
    subTitle,
    constructor,
    isAccess: editIsAccess,
    private_user_list,
  } = data;

  console.log('data : ', data);

  const [addState, setAddState] = useState({
    name: title,
    description: subTitle,
    owner_id: {
      label: null,
      value: null,
    },
    access: editIsAccess,
    user_id: [],
  });
  const { description, access, owner_id } = addState;

  const [initialUserSelect] = useState(private_user_list);
  const [ownerOptions, setOwnerOptions] = useState([]);

  const filterOptions = ownerOptions.filter((item1) => {
    return !private_user_list.some((item2) => item2.value === item1.value);
  });

  const userList = useRef([]);
  const handeUserList = ({ selectedList }) => {
    const shallowList = selectedList.slice();
    const transformList = shallowList.map(({ value }) => value);
    userList.current = transformList;
  };

  const handleInput = (type, setAddState, value) => {
    console.log('value: ', value);
    setAddState((prev) => ({
      ...prev,
      [type]: value,
    }));
  };

  useEffect(() => {
    const getOwnerOptions = async () => {
      const { result, message, status } = await getUsers(workspace_id);
      if (status === STATUS_SUCCESS) {
        const transformUserList = result.map((el) => {
          return {
            label: el.name,
            value: el.id,
          };
        });
        const findMyOwner = transformUserList.find(
          (info) => info.label === constructor,
        );

        if (findMyOwner) {
          setAddState((prev) => ({
            ...prev,
            owner_id: findMyOwner,
          }));
        }
        setOwnerOptions(transformUserList);
      } else {
        toast.error(message);
      }
    };
    getOwnerOptions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <NewStyleModalFrame
      title={'파이프라인 수정'}
      type={type}
      submit={{
        text: t('update.label'),
        func: async () => {
          const { status, message } = await putPipelines({
            pipeline_id: id,
            description,
            access,
            owner_id: owner_id.value,
            users_id: [...userList.current],
          });

          if (status === STATUS_SUCCESS) {
            dispatch(closeModal(type));
            handleRefresh();
          } else {
            toast.error(message);
          }
        },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={true}
      isResize={true}
      isMinimize={true}
      footerMessage={''}
    >
      <InputBoxWithLabel
        labelText={t('projectName.label')}
        labelSize='large'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <InputText
          size='medium'
          onChange={() => {}}
          name='projectName'
          placeholder={t('project.empty.message')}
          value={title}
          isReadOnly
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel
        labelText={t('projectDescription.label')}
        optionalText={t('optional.label')}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <Textarea
          size='large'
          placeholder={t('project.desc.empty.message')}
          value={description}
          name='description'
          onChange={(e) => {
            handleInput('description', setAddState, e.target.value);
          }}
          customStyle={{ fontSize: '14px', height: '160px' }}
          isShowMaxLength
        />
      </InputBoxWithLabel>
      <div
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}
      >
        <InputBoxWithLabel
          labelText={t('accessType.label')}
          optionalText={
            <Tooltip
              icon='/src/static/images/icon/00-ic-alert-info-o.svg'
              iconCustomStyle={{
                width: '16px',
                height: '16px',
                paddingBottom: '2px',
              }}
              contents={<TooltipContent />}
              contentsAlign={{ vertical: 'top' }}
              contentsCustomStyle={{
                width: '300px',
                padding: '24px',
                borderRadius: '10px',
                border: '0.5px solid #DEE9FF',
                background: '#FFF',
                boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
              }}
            />
          }
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <Radio
            name='accesstype-input'
            value={access}
            options={accessTypeOptions}
            onChange={(e) =>
              handleInput('access', setAddState, +e.target.value)
            }
            isLabelColor
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={t('owner.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <Dropdown
            value={owner_id.value}
            list={ownerOptions}
            handleOptionClick={(option) => {
              handleInput('owner_id', setAddState, option);
            }}
            placeholder={t('project.select.label')}
            disabled={userName !== constructor}
            style={{ height: '38px', padding: '16px' }}
          />
        </InputBoxWithLabel>
      </div>
      {access === 0 && (
        <MultiSelect
          label='users.label'
          listLabel='availableUsers.label'
          selectedLabel='chosenUsers.label'
          list={filterOptions} // 초기 목록
          selectedList={initialUserSelect} // 초기 선택된 목록
          onChange={handeUserList} // 변경 이벤트
          exceptItem={owner_id && owner_id.value}
          optional
          style={{ marginTop: '32px' }}
        />
      )}
    </NewStyleModalFrame>
  );
}
