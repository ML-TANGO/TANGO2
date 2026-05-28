import { useCallback, useEffect, useRef, useState } from 'react';
import { useDispatch } from 'react-redux';
import { cloneDeep } from 'lodash';

// Utils
import { errorToastMessage } from '@src/utils';
import Hangul from '@src/koreaUtils';

// Actions
import { closeModal } from '@src/store/modules/modal';

// Components
import TemplateModal from '@src/components/Modal/TemplateModal/TemplateModal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

const GROUP = 'group';
const DEPLOY = 'deploy';

function TemplateModalContainer({ type, data: modalData }) {
  const {
    workspaceId,
    selectedGroupData,
    editData,
    getTemplateData,
    getGroupData,
    data,
  } = modalData;
  const dispatch = useDispatch();

  const [groupSelect, setGroupSelect] = useState(false);
  const [clickedGroupDataList, setClickedGroupDataList] = useState(
    selectedGroupData ? selectedGroupData : null,
  );
  const [clickedGroupTemplateLists, setClickedGroupTemplateLists] = useState(
    [],
  );
  const [groupTemplateData, setGroupTemplateData] = useState([]);
  const [clickedDeployDataList, setClickedDeployDataList] = useState(null);
  const [clickedDeployTemplateLists, setClickedDeployTemplateLists] =
    useState(null);
  const [deployTemplateData, setDeployTemplateData] = useState([]);
  const [deploymentType, setDeploymentType] = useState('');
  const [makeNewGroup, setMakeNewGroup] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState(''); // 템플릿 이름
  const [newTemplateDescription, setNewTemplateDescription] = useState(''); // 템플릿 설명
  const [templateNameDuplicate, setTemplateNameDuplicate] = useState(null); // 템플릿 이름 validation
  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupDescription, setNewGroupDescription] = useState('');
  const [groupNameDuplicate, setGroupNameDuplicate] = useState(null);
  const [templateId, setTemplateId] = useState(null);

  // Training State
  const [selectedDeploymentType, setSelectedDeploymentType] = useState(null);
  const [trainingList, setTrainingList] = useState([]);
  const [originTrainingList, setOriginTrainingList] = useState([]);
  const [trainingSelectedType, setTrainingSelectedType] = useState({
    label: 'all.label',
    value: 'all',
  });
  const [trainingSelectedOwner, setTrainingSelectedOwner] = useState({
    label: 'all.label',
    value: 'allOwner',
  });
  const [toolSelectedOwner, setToolSelectedOwner] = useState({
    label: 'all.label',
    value: 'toolAll',
  });
  const [toolSearchValue, setToolSearchValue] = useState('');
  const [trainingInputValue, setTrainingInputValue] = useState('');
  const [trainingSelectTab, setTrainingSelectTab] = useState(0);
  const [jobDetailList, setJobDetailList] = useState(null);
  const [jobList, setJobList] = useState(null);
  const [jobId, setJobId] = useState('');
  const [originJobList, setOriginJobList] = useState(null);
  const [jobDetailOpenList, setJobDetailOpenList] = useState([]);
  const [trainingToolTab, setTrainingToolTab] = useState(0);
  const [hpsList, setHpsList] = useState(null);
  const [originHpsList, setOriginHpsList] = useState(null);
  const [hpsDetailList, setHpsDetailList] = useState(null);
  const [hpsDetailOpenList, setHpsDetailOpenList] = useState([]);
  const [hpsLogTable, setHpsLogTable] = useState([]);
  const [selectedHpsScore, setSelectedHpsScore] = useState('');
  const [selectedHps, setSelectedHps] = useState(null);
  const [customLan, setCustomLan] = useState('python'); // binary
  const [customFile, setCustomFile] = useState(''); // script
  const [customParam, setCustomParam] = useState(''); // arguments
  const [customList, setCustomList] = useState([]);
  const [customSearchValue, setCustomSearchValue] = useState('');
  const [originCustomList, setOriginCustomList] = useState([]);
  const [customRuncode, setCustomRuncode] = useState('');
  const [selectedTool, setSelectedTool] = useState(null);
  const [selectedToolType, setSelectedToolType] = useState(null);
  const [trainingType, setTrainingType] = useState('');
  const [selectedTraining, setSelectedTraining] = useState(null);
  const [createBtnvalidate, setCreateBtnValidate] = useState(false);
  const [modelList, setModelList] = useState([]);
  const [originModelList, setOriginModelList] = useState([]);
  const [modelSelectStatus, setModelSelectStatus] = useState(true);
  const [modelSearchValue, setModelSearchValue] = useState('');
  const [modelCategorySelect, setModelCategorySelect] = useState({
    value: 'all',
  });
  const [selectedModel, setSelectedModel] = useState(null); // 배포유형 - built-in 선택된 모델
  const [jsonData, setJsonData] = useState({}); // 배포유형 - 설정값입력
  const [editStatus, setEditStatus] = useState(false);
  const [showSelectAgain, setShowSelectAgain] = useState(false);
  const [trainingTypeArrow, setTrainingTypeArrow] = useState({
    train: false,
    tool: false,
    model: false,
    variable: false,
    hps: false,
    hpsModel: false,
    jobModel: false,
  });
  const [hpsModelList, setHpsModelList] = useState([]);
  const [jobModelList, setJobModelList] = useState([]);
  const [originHpsModelList, setOriginHpsModelList] = useState([]);
  const [originJobModelList, setOriginJobModelList] = useState([]);
  const [selectedLogId, setSelectedLogId] = useState('');
  const [toolModelSearchValue, setToolModelSearchValue] = useState('');
  const [hpsModelSelectValue, setHpsModelSelectValue] = useState('');
  const [selectedHpsId, setSelectedHpsId] = useState('');
  const [jobModelSelectValue, setJobModelSelectValue] = useState('');
  const [hpsLogList, setHpsLogList] = useState([]);
  const [selectedTrainingData, setSelectedTrainingData] = useState(null); // 배포유형 학습 -> 선택된 학습 정보
  const [customListStatus, setCustomListStatus] = useState(false);
  const [variablesValues, setVariablesValues] = useState([
    { name: '', value: '' },
  ]);
  const [templateEditData, setTemplateEditData] = useState(null);
  const loginUserName = sessionStorage.getItem('user_name'); // 로그인한 유저 네임
  const [readOnly, setReadOnly] = useState(false);
  const [jsonDataError, setJsonDatatError] = useState(false);
  const jsonRef = useRef(null);
  const [deploymentNoGroupSelected, setDeploymentNoGroupSelected] =
    useState(false);
  const [templateNogroupSelected, setTemplateNogroupSelected] = useState(false);

  /**
   * 선택 탭
   * @param {number} idx
   */
  const tabClickHandler = (idx) => {
    setTrainingSelectTab(idx);
  };

  const toolDetailOpenHandler = (idx, type) => {
    const newDetailOpenList = [];
    if (type === 'job') {
      jobDetailOpenList.forEach((v, i) => {
        if (i === idx) {
          newDetailOpenList.push({ arrow: !v.arrow });
        } else {
          newDetailOpenList.push(v);
        }
      });
      setJobDetailOpenList(newDetailOpenList);
    } else if (type === 'hps') {
      hpsDetailOpenList.forEach((v, i) => {
        if (i === idx) {
          newDetailOpenList.push({ arrow: !v.arrow });
        } else {
          newDetailOpenList.push(v);
        }
      });
      setHpsDetailOpenList(newDetailOpenList);
    }
  };

  const trainingToolTabHandler = (tab) => {
    setTrainingToolTab(tab);
    if (tab === 0) {
      setSelectedHpsScore('');
      setHpsLogTable([]);
    }
  };

  const trainingTypeArrowCustomHandler = (type, bool) => {
    let newArrow = {
      ...trainingTypeArrow,
      [type]: bool,
    };
    setTrainingTypeArrow(newArrow);
  };

  const trainingTypeArrowHandler = (type) => {
    let newArrow = {
      ...trainingTypeArrow,
      [type]: !trainingTypeArrow[type],
    };

    setTrainingTypeArrow(newArrow);
  };

  const paramsInputHandler = ({ e = { target: { value: '' } }, type }) => {
    let { value } = e.target;

    if (type === 'file') {
      setCustomFile(value);
    } else if (type === 'param') {
      setCustomParam(value);
    } else if (type === 'lan') {
      setCustomLan(value);
    }
    templateIdReset();
  };

  const variablesDelete = (idx) => {
    const newVariables = [];
    variablesValues.forEach((v, i) => {
      if (i !== idx) {
        newVariables.push(v);
      }
    });

    setVariablesValues(newVariables);
  };

  const variablesAdd = () => {
    let newVariables = [];

    if (variablesValues.length >= 1) {
      variablesValues.forEach((v, i) => {
        newVariables.push(v);
        if (i + 1 === variablesValues.length) {
          newVariables.push({ name: '', value: '' });
        }
      });
    }
    if (newVariables.length === 0) {
      newVariables.push({ name: '', value: '' });
    }

    setVariablesValues(newVariables);
    //this.setState({ variablesValues: newVariables });
  };

  const toolSortHandler = ({
    e = { target: { value: '' } },
    type,
    selectedItem,
  }) => {
    let { value } = e.target;
    let toolType = '';

    if (!type) {
      if (trainingToolTab === 0) {
        toolType = 'job';
      } else {
        toolType = 'hps';
      }
    } else {
      toolType = type;
    }

    setToolSearchValue(value);

    const filteredData = [];

    let selectedOwner = '';

    if (!selectedItem) {
      selectedOwner = toolSelectedOwner;
    } else {
      if (
        selectedItem.value === 'toolOwner' ||
        selectedItem.value === 'toolAll'
      ) {
        selectedOwner = selectedItem;
      }
    }

    if (toolType === 'job') {
      // joblist
      if (value !== '' && value) {
        originJobList.forEach((v) => {
          if (v.job_name.includes(value)) {
            filteredData.push(v);
          }
        });
      } else {
        originJobList.forEach((v) => {
          filteredData.push(v);
        });
      }

      setJobList(filteredData);
    } else if (toolType === 'hps') {
      // hpslist
      if (value !== '' && value) {
        originHpsList.forEach((v) => {
          if (v.hps_name.includes(value)) {
            filteredData.push(v);
          }
        });
      } else {
        originHpsList.forEach((v) => {
          filteredData.push(v);
        });
      }
      setHpsList(filteredData);
    }

    const ownerSortedData = [];

    if (selectedOwner.value === 'toolOwner') {
      setToolSelectedOwner(selectedOwner);
      if (toolType === 'hps') {
        filteredData.forEach((v) => {
          if (loginUserName === v.hps_runner_name) {
            ownerSortedData.push(v);
          }
        });

        setHpsList(ownerSortedData);
      } else if (toolType === 'job') {
        filteredData.forEach((v) => {
          if (loginUserName === v.job_runner_name) {
            ownerSortedData.push(v);
          }
        });

        setJobList(ownerSortedData);
      }
    } else if (selectedOwner.value === 'toolAll') {
      setToolSelectedOwner(selectedOwner);
      filteredData.forEach((v) => {
        ownerSortedData.push(v);
      });

      if (toolType === 'hps') {
        setHpsList(ownerSortedData);
      } else if (toolType === 'job') {
        setJobList(ownerSortedData);
      }
    }
  };

  const toolSelectHandler = ({
    type,
    name,
    jobId,
    detailNumber,
    hpsLogTable,
    jobCheckpoint,
    hpsCheckpoint,
    token,
  }) => {
    if (type === 'JOB') {
      setSelectedToolType('job');
      setJobModelList(jobCheckpoint);
      setOriginJobModelList(jobCheckpoint);
      if (!token) {
        setJobModelSelectValue('');
      }
      setJobId(jobId);
    } else {
      setSelectedToolType('hps');
      setSelectedHpsId(hpsLogTable?.max_item?.hps_id);
      setSelectedHpsScore(hpsLogTable?.max_item?.target);
      setSelectedLogId(hpsLogTable?.max_item?.id);
      setHpsLogTable(hpsLogTable);
      setHpsModelSelectValue('');
      setOriginHpsModelList(hpsCheckpoint);
      setHpsModelList(hpsCheckpoint);
    }
    const selectedTool = `${type} / ${name} / ${detailNumber}`;
    if (!token) {
      templateIdReset();
    }
    trainingTypeArrowCustomHandler('tool', false);
    setSelectedTool(selectedTool);
  };

  const getJobList = async (train, name, token) => {
    const jobDetailLength = [];
    const hpsDetailLength = [];

    setSelectedTool(null);
    setSelectedToolType(null);
    setToolModelSearchValue('');
    setToolSearchValue('');
    setToolSearchValue('');
    setHpsModelSelectValue('');
    setJobModelSelectValue('');
    setJobModelList([]);
    setHpsLogList([]);
    setJobModelList([]);
    setSelectedLogId('');
    setJobList(null);
    setJobDetailList(null);
    setJobDetailOpenList([]);
    setHpsList(null);
    setHpsDetailList(null);
    setHpsDetailOpenList([]);
    setTrainingToolTab(0);
    setCustomLan('python');
    setCustomFile('');
    setCustomParam('');
    setCustomSearchValue('');
    setCustomRuncode('');
    setVariablesValues([{ name: '', value: '' }]);
    setSelectedTrainingData(train);
    trainingSelectHandler(name);

    if (train.training_type) {
      setTrainingType(train.training_type);
    }

    if (train.training_type && !token) {
      templateIdReset();
    }

    const response = await callApi({
      url: `options/deployments/templates/usertrained?training_id=${train?.training_id}`,
      method: 'get',
    });

    const { result, status, error, message } = response;
    const { job_list, hps_list } = result;
    if (status === STATUS_SUCCESS) {
      setJobList(job_list);
      setHpsList(hps_list);
      setOriginJobList(job_list);
      setOriginHpsList(hps_list);

      job_list.forEach((v) => {
        jobDetailLength.push({ arrow: false });
      });
      hps_list.forEach((v) => {
        hpsDetailLength.push({ arrow: false });
      });
    } else {
      errorToastMessage(error, message);
    }

    setJobDetailOpenList(jobDetailLength);
    setHpsDetailOpenList(hpsDetailLength);
    return {
      jobList: job_list,
      hpsList: hps_list,
      jobDetailOpenList: jobDetailLength,
      hpsDetailOpenList: hpsDetailLength,
    };
  };

  const getTrainingTypeData = async (type) => {
    const response = await callApi({
      url: `options/deployments/templates?workspace_id=${workspaceId}&deployment_template_type=${type}`,
      method: 'get',
    });

    const { result, status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      setTrainingList(result);
      setOriginTrainingList(result);
    } else {
      errorToastMessage(error, message);
    }
  };

  const deploymentTypeHandler = (selectedType) => {
    setDeploymentType(selectedType);
    setSelectedDeploymentType(selectedType);

    switch (selectedType) {
      case 'usertrained':
        getTrainingTypeData(selectedType);
        break;
      case 'pretrained':
        getBuiltInModelList(selectedType);
        break;
      default:
        break;
    }
  };

  const trainingSearch = (e) => {
    let { value } = e?.target;
    const { originTrainingList } = this.state;

    const newListData = [];

    if (value === '') {
    } else {
      const trainingSearchData = JSON.parse(
        JSON.stringify(originTrainingList?.usertrained_training_list),
      );

      trainingSearchData.forEach((v) => {
        if (
          v.training_name.indexOf(value) !== -1 ||
          v.training_description.indexOf(value) !== -1
        ) {
          newListData.push(v);
        }
      });
    }
    setTrainingList({
      built_in_model_kind_list: originTrainingList.built_in_model_kind_list,
      built_in_model_thumbnail_image_info:
        originTrainingList.built_in_model_thumbnail_image_info,
      usertrained_training_list: newListData,
    });

    // 이름, 설명, 카테고리
  };

  // 다시 선택
  const backBtnHandler = () => {
    setTrainingTypeArrow({
      train: true,
      tool: true,
      model: true,
      variable: true,
      hps: true,
      hpsModel: true,
      jobModel: true,
    });
    setToolSearchValue('');
    setSelectedTraining('');
    setToolModelSearchValue('');
    setHpsModelSelectValue('');
    setJobModelSelectValue('');
    setTrainingSelectedType({
      label: 'all.label',
      value: 'all',
    });

    setSelectedDeploymentType(null);

    setTrainingSelectedType({
      label: 'all.label',
      value: 'all',
    });
    setTrainingSelectedOwner({
      label: 'all.label',
      value: 'allOwner',
    });

    setSelectedHpsScore('');
    setSelectedHps(null);
    setSelectedTool(null);
    setJobList(null);

    setTrainingToolTab(0);
    setJobDetailList(null);
    setJobDetailOpenList([]);
    setHpsList(null);
    setHpsDetailList(null);
    setHpsDetailOpenList([]);
    setTrainingToolTab(0);
    setCustomLan('python');
    setCustomFile('');
    setCustomParam('');
    setCustomSearchValue('');
    setCustomRuncode('');
    setVariablesValues([{ name: '', value: '' }]);
    setTrainingInputValue('');
    setSelectedModel(null);
    setClickedDeployTemplateLists(null);
    setClickedDeployDataList(null);
    setJsonData({});
    setSelectedTrainingData(null);
    setCreateBtnValidate(false);
    setModelSelectStatus(true);
    getTemplateListHandler({
      type: DEPLOY,
      id: undefined,
    });
    setDeploymentNoGroupSelected(false);
    setTemplateNogroupSelected(false);
  };

  // 학습에서 가져오기 유형, 소유자 Submenu 선택
  const trainingTypeSelectHandler = (type, selectedItem) => {
    const trainingTableData = JSON.parse(
      JSON.stringify(originTrainingList?.usertrained_training_list),
    );
    let copiedTableData = [...trainingTableData];

    const newTrainingList = [];

    if (type === 'type') {
      setTrainingSelectedType(selectedItem);
      const ownerSortedData = [];

      if (trainingSelectedOwner.value === 'owner') {
        copiedTableData.forEach((v) => {
          if (loginUserName === v.training_user_name) {
            ownerSortedData.push(v);
          }
        });
        copiedTableData = [...ownerSortedData];
      }

      if (selectedItem.value === 'custom') {
        copiedTableData.forEach((list) => {
          if (list.training_type === 'advanced') {
            newTrainingList.push(list);
          }
        });
      } else if (selectedItem.value === 'builtIn') {
        copiedTableData.forEach((list) => {
          if (list.training_type === 'built-in') {
            newTrainingList.push(list);
          }
        });
      } else {
        newTrainingList.push(...ownerSortedData);
      }
    } else if (type === 'owner') {
      setTrainingSelectedOwner(selectedItem);
      const typeSortedData = [];
      if (trainingSelectedType.value === 'custom') {
        copiedTableData.forEach((list) => {
          if (list.training_type === 'advanced') {
            typeSortedData.push(list);
          }
        });
      } else if (trainingSelectedType.value === 'all') {
        copiedTableData.forEach((list) => {
          typeSortedData.push(list);
        });
      } else if (trainingSelectedType.value === 'builtIn') {
        copiedTableData.forEach((list) => {
          if (list.training_type === 'advanced') {
            typeSortedData.push(list);
          }
        });
      }
      copiedTableData = [...typeSortedData];
      if (selectedItem.value === 'owner') {
        copiedTableData.forEach((v) => {
          if (loginUserName === v.training_user_name) {
            newTrainingList.push(v);
          }
        });
      } else if (selectedItem.value === 'allOwner') {
        copiedTableData.forEach((v) => newTrainingList.push(v));
      }
    }

    setTrainingList({
      built_in_model_kind_list: originTrainingList.built_in_model_kind_list,
      built_in_model_thumbnail_image_info:
        originTrainingList.built_in_model_thumbnail_image_info,
      usertrained_training_list: newTrainingList,
    });
  };

  const trainingSortHandler = ({
    e = { target: { value: '' } },
    selectedItem,
  }) => {
    let { value } = e.target;

    setTrainingInputValue(value);

    const filteredData = [];
    const typeSortedData = [];
    let selectedType = '';
    let selectedOwner = '';

    if (!selectedItem) {
      selectedType = trainingSelectedType;
      selectedOwner = trainingSelectedOwner;
    } else {
      if (selectedItem.value === 'owner' || selectedItem.value === 'allOwner') {
        selectedOwner = selectedItem;
        selectedType = trainingSelectedType;
      } else {
        selectedType = selectedItem;
        selectedOwner = trainingSelectedOwner;
      }
    }

    if (value !== '' && value) {
      originTrainingList.usertrained_training_list.forEach((v) => {
        if (
          v.training_name.includes(value) ||
          v.training_description.includes(value)
        ) {
          filteredData.push(v);
        }
      });
    } else {
      originTrainingList.usertrained_training_list.forEach((v) => {
        filteredData.push(v);
      });
    }

    const ownerSortedData = [];

    if (selectedOwner.value === 'owner') {
      setTrainingSelectedOwner(selectedOwner);
      filteredData.forEach((v) => {
        if (loginUserName === v.training_user_name) {
          ownerSortedData.push(v);
        }
      });
    } else if (selectedOwner.value === 'allOwner') {
      setTrainingSelectedOwner(selectedOwner);
      filteredData.forEach((v) => {
        ownerSortedData.push(v);
      });
    }
    if (selectedType.value === 'custom') {
      setTrainingSelectedType(selectedType);
      ownerSortedData.forEach((list) => {
        if (list.training_type === 'advanced') {
          typeSortedData.push(list);
        }
      });
    } else if (selectedType.value === 'builtIn') {
      setTrainingSelectedType(selectedType);
      ownerSortedData.forEach((list) => {
        if (list.training_type === 'built-in') {
          typeSortedData.push(list);
        }
      });
    } else if (selectedType.value === 'all') {
      setTrainingSelectedType(selectedType);
      ownerSortedData.forEach((list) => {
        typeSortedData.push(list);
      });
    }

    setTrainingList({
      built_in_model_kind_list: originTrainingList.built_in_model_kind_list,
      built_in_model_thumbnail_image_info:
        originTrainingList.built_in_model_thumbnail_image_info,
      usertrained_training_list: typeSortedData,
    });
  };

  const onClickGroupTemplateList = (data) => {
    if (clickedGroupTemplateLists?.id === data.id) {
      setClickedGroupTemplateLists(null);
    } else {
      setClickedGroupTemplateLists(data);
    }
  };

  const onClickDeployTemplateList = (data) => {
    if (clickedDeployTemplateLists?.id === data.id) {
      setClickedDeployTemplateLists(null);
    } else {
      setClickedDeployTemplateLists(data);
    }
  };

  const getTemplateListHandler = useCallback(
    async ({ type, id, noGroup }) => {
      let url = `deployments/template-list?workspace_id=${workspaceId}`;
      if (id !== undefined) url += `&deployment_template_group_id=${id}`;
      if (!noGroup) url += `&is_ungrouped_template=1`;
      const response = await callApi({
        url,
        method: 'GET',
      });
      const { status, result, error, message } = response;

      if (status === STATUS_SUCCESS) {
        const data = result?.deployment_template_info_list
          ? result.deployment_template_info_list
          : [];
        if (type === GROUP) {
          setGroupTemplateData(data);
        } else if (type === DEPLOY) {
          setDeployTemplateData(data);
        } else {
          setGroupTemplateData(data);
          setDeployTemplateData(data);
        }
      } else {
        errorToastMessage(error, message);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [deploymentNoGroupSelected, workspaceId, templateNogroupSelected],
  );

  const variablesSortHandler = ({ e = { target: { value: '' } } }) => {
    const newCustomList = [];
    let { value } = e.target;

    setCustomSearchValue(value);

    if (value !== '' && value) {
      originCustomList.forEach((runCode) => {
        if (runCode.includes(value)) {
          newCustomList.push(runCode);
        }
      });
      setCustomList(newCustomList);
    } else {
      setCustomList(originCustomList);
    }
  };

  const variableInputHandler = ({
    e = { target: { value: '' } },
    idx,
    key,
  }) => {
    let { value } = e.target;

    const newVariables = [];

    if (key === 'key') {
      variablesValues.forEach((v, i) => {
        if (idx === i) {
          const val = v.value;
          newVariables.push({ name: value, value: val });
        } else {
          newVariables.push(v);
        }
      });
    } else if (key === 'value') {
      variablesValues.forEach((v, i) => {
        if (idx === i) {
          const key = v.name;
          newVariables.push({ name: key, value });
        } else {
          newVariables.push(v);
        }
      });
    }
    templateIdReset();
    setVariablesValues(newVariables);
  };

  const runcodeClickHandler = ({ name }) => {
    setCustomRuncode(name);
    setCustomFile(name);
  };

  const getCustomList = async (training) => {
    setCustomListStatus(true);
    setTimeout(() => {
      setCustomListStatus(false);
    }, 2000);
    const response = await callApi({
      url: `options/deployments/templates/custom?training_id=${training?.training_id}`,
      method: 'get',
    });

    const { result, status, error, message } = response;

    if (status === STATUS_SUCCESS) {
      setCustomList(result.run_code_list);
      setOriginCustomList(result.run_code_list);
    } else {
      errorToastMessage(error, message);
    }
  };

  // 그룹 - 그룹 선택
  const onClickGroupList = (data) => {
    setTemplateNogroupSelected(false);
    if (data.id === clickedGroupDataList?.id) {
      setClickedGroupDataList(null);
      setGroupTemplateData(null);
      getTemplateListHandler({ type: GROUP, id: undefined, noGroup: true });
    } else {
      setClickedGroupDataList(data);
      setClickedGroupTemplateLists([]);
      getTemplateListHandler({ type: GROUP, id: data.id, noGroup: true });
    }
    setMakeNewGroup(false);
  };

  const onClickGroupSelect = () => {
    if (!groupSelect) {
      setClickedGroupTemplateLists([]);
    }
    setGroupSelect((prev) => !prev);
  };

  const logClickHandler = ({ id, target, checkpointList }) => {
    templateIdReset();
    setSelectedLogId(id);
    setSelectedHpsScore(target);
    setHpsModelList(checkpointList);
    setOriginHpsModelList(checkpointList);
    setHpsModelSelectValue('');
    trainingTypeArrowCustomHandler('tool', false);
    trainingTypeArrowCustomHandler('hps', false);
  };

  const hpsLogSortHandler = async ({ title, sortBy, isParam, id }) => {
    const hpsDetailLength = [];
    const url = `options/deployments/templates/usertrained?training_id=${selectedTrainingData?.training_id}&sort_key=${title}&order_by=${sortBy}&is_param=${isParam}`;

    const response = await callApi({
      url,
      method: 'get',
    });

    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const { hps_list } = result;
      hps_list.forEach((v) => {
        hpsDetailLength.push({ arrow: false });
      });
      setHpsList(hps_list);
      setOriginHpsList(hps_list);
      setHpsDetailOpenList(hpsDetailLength);
      hps_list.forEach((v) => {
        if (v?.hps_group_list?.length > 0) {
          v.hps_group_list?.forEach((hps) => {
            if (hps?.hps_id === id) {
              setHpsLogTable(hps?.hps_number_info);
            }
          });
        }
      });
    } else {
      errorToastMessage(error, message);
    }
  };

  //배포 유형 - 그룹 없음
  const onClickNoGroup = () => {
    setDeploymentNoGroupSelected((prev) => !prev);
    setClickedDeployDataList(null);
    getTemplateListHandler({
      type: DEPLOY,
      id: undefined,
      noGroup: deploymentNoGroupSelected,
    });
  };

  // 그룹 - 그룹 없음
  const goupOnClickNoGroup = () => {
    setTemplateNogroupSelected((prev) => !prev);
    setClickedGroupDataList(null);
    getTemplateListHandler({
      type: GROUP,
      id: undefined,
      noGroup: templateNogroupSelected,
    });
  };

  // 배포유형 그룹 리스트 클릭
  const onClickDeployList = (data) => {
    setDeploymentNoGroupSelected(false);
    if (data.id === clickedDeployDataList?.id) {
      setClickedDeployDataList(null);
      setDeployTemplateData(null);
      getTemplateListHandler({ type: DEPLOY, noGroup: true });
    } else {
      setClickedDeployTemplateLists(null);
      setClickedDeployDataList(data);
      getTemplateListHandler({ type: DEPLOY, id: data.id, noGroup: true });
    }
    setMakeNewGroup(false);
  };

  const onClickDeploySelect = () => {
    if (!groupSelect) {
      setClickedGroupTemplateLists([]);
      setClickedGroupDataList(null);
    }
    setGroupSelect((prev) => !prev);
  };

  const onClickNewGroup = () => {
    setClickedGroupDataList(null);
    setNewGroupName('');
    setNewGroupDescription('');
    setMakeNewGroup((prev) => !prev);
    setGroupNameDuplicate(null);
  };

  const trainingSelectHandler = (name) => {
    setSelectedTraining(name);
  };

  const validate = (value) => {
    const forbiddenChars = /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

    const regType = !forbiddenChars.test(value);
    if (value === '') {
      return false;
    }
    if (!regType) {
      return true;
    }
    return null;
  };

  const nameInputHandler = (e) => {
    const validation = validate(e.target.value);
    setNewTemplateName(e.target.value);
    if (validation) {
      setTemplateNameDuplicate('newNameRule.message');
    } else {
      if (!editData || editData.name !== e.target.value) {
        checkTemplateNameDuplicate(e.target.value);
      }
      setTemplateNameDuplicate(false);
    }
  };

  const checkTemplateNameDuplicate = async (value) => {
    const resp = await callApi({
      url: `options/deployments/templates/check-name?deployment_template_name=${value}&workspace_id=${workspaceId}`,
      method: 'GET',
    });
    if (resp.result.is_duplicated) {
      setTemplateNameDuplicate('template.duplicate.name.label');
    }
  };

  const checkGroupNameDuplicate = async (value) => {
    const resp = await callApi({
      url: `options/deployments/templates/check-group-name?deployment_template_group_name=${value}&workspace_id=${workspaceId}`,
      method: 'GET',
    });
    if (resp.result.is_duplicated) {
      setGroupNameDuplicate('template.duplicate.name.label');
    }
  };

  const descriptionInputHandler = (e) => {
    setNewTemplateDescription(e.target.value);
  };

  const groupNameInputHandler = (e) => {
    const validation = validate(e.target.value);
    setNewGroupName(e.target.value);
    if (validation) {
      setGroupNameDuplicate('newNameRule.message');
    } else {
      checkGroupNameDuplicate(e.target.value);
      setGroupNameDuplicate(false);
    }
  };
  const groupDescriptionInputHandler = (e) => {
    setNewGroupDescription(e.target.value);
  };

  const getBuiltInModelList = async (type) => {
    const response = await callApi({
      url: `options/deployments/templates?workspace_id=${workspaceId}&deployment_template_type=${type}`,
      method: 'GET',
    });
    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      result.pretrained_built_in_model_list?.forEach((item) => {
        if (item.built_in_model_name) {
          const dis_name = Hangul.make(item.built_in_model_name);
          Object.assign(item, { dis_name });
        }
        if (item.built_in_model_description) {
          const dis_desc = Hangul.make(item.built_in_model_description);
          Object.assign(item, { dis_desc });
        }
      });
      setModelList(result);
      setOriginModelList(result);
    } else {
      errorToastMessage(error, message);
    }
  };

  const searchModelHandler = (e) => {
    const value = e.target.value;
    setModelSearchValue(value);
    if (value !== '') {
      modelFilterHandler({ searchValue: value.toLowerCase() });
    } else if (modelCategorySelect.value === 'all' && value === '') {
      setModelList(originModelList);
    }
  };

  const categoryHandler = (value) => {
    setModelCategorySelect(value);
    modelFilterHandler({ categoryValue: value });
  };

  const modelFilterHandler = ({
    searchValue = modelSearchValue,
    categoryValue = modelCategorySelect,
  }) => {
    let filteredData;
    const cloneList = cloneDeep(originModelList);
    if (searchValue) {
      filteredData = cloneList.pretrained_built_in_model_list.filter((data) => {
        if (
          data.dis_name?.toLowerCase().includes(searchValue) ||
          data.dis_desc?.toLowerCase().includes(searchValue) ||
          data.built_in_model_description
            ?.toLowerCase()
            .includes(searchValue) ||
          data.built_in_model_name?.toLowerCase().includes(searchValue)
        )
          return data;
        return '';
      });
      cloneList.pretrained_built_in_model_list = filteredData;
    }
    if (categoryValue) {
      if (categoryValue?.value !== 'all') {
        filteredData = cloneList.pretrained_built_in_model_list.filter(
          (data) => {
            if (data.built_in_model_kind === categoryValue.label) return data;
            return '';
          },
        );
        cloneList.pretrained_built_in_model_list = filteredData;
      }
      setModelList(cloneList);
    }
  };

  // 템플릿 id 초기화
  const templateIdReset = () => {
    setTemplateId(null);
  };

  const onClickModelList = (list) => {
    setSelectedModel(list);
    setModelSelectStatus((prev) => !prev);
    setModelCategorySelect({ value: 'all' });
    setModelSearchValue(null);
    setModelList(originModelList);
    templateIdReset();
  };

  const modelSelectStatusHanlder = () => {
    setModelSelectStatus((prev) => !prev);
  };

  const jsonDataHandler = () => (json) => {
    setTimeout(() => {
      if (
        jsonRef.current.jsonEditor.aceEditor.session.getAnnotations().length >
          0 ||
        !json
      ) {
        setJsonDatatError(true);
      } else {
        setJsonDatatError(false);
        setJsonData(json);
      }
      templateIdReset();
    }, [500]);
  };

  // 템플릿 id 초기화

  /**
   * 템플릿 생성
   */
  const onClickTemplateCreate = async () => {
    dispatch(closeModal(type));
    const body = {
      workspace_id: workspaceId,
      deployment_template_name: newTemplateName,
      deployment_template_description: newTemplateDescription,
    };

    if (templateId !== null) {
      body.deployment_template_id = templateId;
    }

    if (deploymentType === 'usertrained') {
      body.deployment_type = selectedTrainingData.deployment_type;
      body.training_id = selectedTrainingData.training_id;
      if (selectedTrainingData.deployment_type === 'built-in') {
        if (trainingToolTab) {
          body.training_type = 'hps';
          body.hps_id = selectedHpsId;
          body.hps_number = selectedLogId;
          body.checkpoint = hpsModelSelectValue;
          body.built_in_model_id = selectedTrainingData.built_in_model_id;
        } else {
          body.job_id = jobId;
          body.training_type = 'job';
          body.checkpoint = jobModelSelectValue;
          body.built_in_model_id = selectedTrainingData.built_in_model_id;
        }
      } else {
        // 커스텀
        body.command = {
          arguments: customParam,
          binary: customLan,
          script: customFile,
        };

        body.environments = variablesValues;
      }
    } else if (deploymentType === 'pretrained') {
      body.deployment_type = 'built-in';
      body.built_in_model_id = selectedModel.built_in_model_id;
      selectedGroupData &&
        !makeNewGroup &&
        (body.deployment_template_group_id = selectedGroupData.id);
    } else if (deploymentType === 'sandbox') {
      body.deployment_type = 'custom';
      body.deployment_template = jsonData;
    } else if (deploymentType === 'template') {
    }
    if (makeNewGroup) {
      body.deployment_template_group_name =
        newGroupName || data.defaultGroupName;
    }
    if (selectedGroupData)
      body.deployment_template_group_id = selectedGroupData.id;
    if (clickedGroupDataList) {
      body.deployment_template_group_id = clickedGroupDataList.id;
    }
    const response = await callApi({
      url: 'deployments/template',
      method: 'post',
      body,
    });

    if (response) {
      getTemplateData();
      if (makeNewGroup) {
        getGroupData();
      }
    } else {
    }
  };

  // tool - 모델 선택 핸들러
  const toolModelSelectHandler = (model, type) => {
    templateIdReset();
    if (type === 'hps') {
      setHpsModelSelectValue(model);
      trainingTypeArrowHandler('hpsModel');
    } else if (type === 'job') {
      setJobModelSelectValue(model);
      trainingTypeArrowHandler('jobModel');
    }
  };

  const toolModelSortHandler = ({ e = { target: { value: '' } }, tool }) => {
    let { value } = e.target;

    setToolModelSearchValue(value);
    const filteredData = [];
    if (tool === 'hps') {
      if (value !== '' && value) {
        originHpsModelList.forEach((v) => {
          if (v.includes(value)) {
            filteredData.push(v);
          }
        });
      } else if (value === '') {
        originHpsModelList.forEach((v) => {
          filteredData.push(v);
        });
      }

      setHpsModelList(filteredData);
    } else if (tool === 'job') {
      if (value !== '' && value) {
        originJobModelList.forEach((v) => {
          if (v.includes(value)) {
            filteredData.push(v);
          }
        });
      } else if (value === '') {
        originJobModelList.forEach((v) => {
          filteredData.push(v);
        });
      }

      setJobModelList(filteredData);
    }
  };

  /**
   * 템플릿 수정
   */
  const onClickTemplateEdit = async () => {
    dispatch(closeModal(type));
    const body = {
      workspace_id: workspaceId,
      deployment_template_id: editData.id,
      deployment_template_name: newTemplateName,
      deployment_template_description: newTemplateDescription,
    };
    if (clickedGroupDataList) {
      body.deployment_template_group_id = clickedGroupDataList.id;
    }
    if (makeNewGroup) {
      body.deployment_template_group_name =
        newGroupName || data.defaultGroupName;
      if (newGroupDescription !== '')
        body.deployment_template_group_description = newGroupDescription;
    }
    const response = await callApi({
      url: 'deployments/template',
      method: 'put',
      body,
    });
    const { status, error, message } = response;
    if (status === STATUS_SUCCESS) {
      getTemplateData();
      if (makeNewGroup) {
        getGroupData();
      }
    } else {
      errorToastMessage(error, message);
    }
  };

  const onClickSubmit = () => {
    if (editData) {
      onClickTemplateEdit();
    } else {
      onClickTemplateCreate();
    }
  };

  const setData = async (data) => {
    const templateData = data.deployment_template;
    const type = data.deployment_template_type;
    if (type === 'usertrained' || type === 'custom') {
      getTrainingTypeData('usertrained');
      if (templateData.deployment_type === 'built-in') {
        setTrainingType('built-in');
        setSelectedDeploymentType('usertrained');
        setSelectedTraining(templateData.training_name);

        const { jobList, hpsList } = await getJobList(
          templateData,
          templateData.training_name,
          true,
        );

        const splitedChekcpoint = templateData.checkpoint.split('/');
        if (templateData.training_type === 'hps') {
          const hpsName = templateData.hps_name;
          const hpsId = templateData.hps_id;
          const hpsIdx = templateData.hps_group_index;
          setTrainingToolTab(1);
          setTrainingType('built-in');

          let hpsLogTable = [];
          hpsList.forEach((v, i) => {
            if (v.hps_name === hpsName) {
              v.hps_group_list.forEach((model) => {
                if (model.hps_id === hpsId) {
                  hpsLogTable = model.hps_number_info;
                }
              });
            }
          });
          toolSelectHandler({
            type: 'HPS',
            name: hpsName,
            jobId: hpsId,
            detailNumber: hpsIdx + 1,
            hpsLogTable: hpsLogTable,
            hpsCheckpoint: hpsLogTable.max_item.checkpoint_list,
            token: true,
          });

          setHpsModelSelectValue(splitedChekcpoint.at(-1));
        } else if (templateData.training_type === 'job') {
          setJobModelSelectValue(splitedChekcpoint.at(-1));
          const jobName = templateData.job_name;
          const jobId = templateData.job_id;
          const jobIdx = templateData.job_group_index;
          let checkpoint = [];
          jobList.forEach((v, i) => {
            if (v.job_name === jobName) {
              v.job_group_list.forEach((model) => {
                if (model.job_id === jobId) {
                  checkpoint = model.checkpoint_list;
                }
              });
            }
          });

          toolSelectHandler({
            type: 'JOB',
            name: jobName,
            jobId: jobId,
            detailNumber: jobIdx + 1,
            jobCheckpoint: checkpoint,
            token: true,
          });
          setTrainingToolTab(0);
          setTrainingType('built-in');
        }
      }
      if (templateData.deployment_type === 'custom') {
        getJobList(templateData, templateData.training_name);

        getCustomList(templateData);
        if (
          templateData?.environments &&
          templateData?.environments.length > 0
        ) {
          setVariablesValues(templateData.environments);
        }

        setSelectedTraining(templateData.training_name);
        setSelectedDeploymentType('usertrained');
        setTrainingType('advanced');
        if (templateData.command) {
          if (templateData.command.arguments) {
            setCustomParam(templateData.command.arguments);
          }
          if (templateData.command.binary) {
            setCustomLan(templateData.command.binary);
          }
          if (templateData.command.script) {
            setCustomFile(templateData.command.script);
          }
        }
      }

      deploymentTypeHandler(type === 'custom' ? 'usertrained' : type);
    } else if (type === 'pretrained') {
      setSelectedModel(data.deployment_template);
    } else if (type === 'sandbox') {
      setJsonData(data.deployment_template);
    }
  };

  /**
   * 배포 유형 -> 템플릿 사용하기 -> 템플릿 적용 버튼
   * clickedDeployDataList - 선택된 그룹 ,
   * clickedDeployTemplateLists - 선택된 템플릿
   */
  const applyButtonClicked = () => {
    setData(clickedDeployTemplateLists);
    setModelSelectStatus(false);
    deploymentTypeHandler(clickedDeployTemplateLists.deployment_template_type);
    setTemplateId(clickedDeployTemplateLists.id);
  };

  const jsonDataErrorHandler = (e) => {
    if (e.length > 0) {
      setJsonDatatError(true);
    }
  };

  useEffect(() => {
    if (!deploymentType) {
      getTemplateListHandler({
        type: GROUP,
        id: clickedGroupDataList?.id || undefined,
        noGroup: true,
      });
    } else {
      getTemplateListHandler({
        type: DEPLOY,
        noGroup: true,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    getTemplateListHandler({
      type: DEPLOY,
      id: undefined,
      noGroup: true,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * edit 일때 데이터 set
   */
  useEffect(() => {
    if (editData) {
      setTemplateEditData(editData);
      setEditStatus(true);
      setShowSelectAgain(true);
      setNewTemplateName(editData.name);
      setNewTemplateDescription(editData.description);
      setDeploymentType(editData.deployment_template_type);
      setSelectedDeploymentType(editData.deployment_template_type);
      setData(editData);
      // 수정 초기 Set State
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editData]);

  useEffect(() => {
    if (type === 'TEMPLATE_EDIT') setReadOnly(true);
    if (type === 'TEMPLATE_EDIT' || clickedDeployTemplateLists) {
      setTrainingTypeArrow({
        train: false,
        tool: false,
        model: false,
        variable: false,
        hps: false,
        hpsModel: false,
        jobModel: false,
      });
    } else {
      setTrainingTypeArrow({
        train: true,
        tool: true,
        model: true,
        variable: true,
        hps: true,
        hpsModel: true,
        jobModel: true,
      });
    }
  }, [type, clickedDeployTemplateLists]);

  /**
   * 생성/수정 버튼 validation check
   */
  useEffect(() => {
    if (
      !templateNameDuplicate &&
      newTemplateName !== '' &&
      deploymentType &&
      !editData &&
      !groupNameDuplicate
    ) {
      if (deploymentType === 'usertrained') {
        if (selectedTrainingData?.deployment_type === 'custom') {
          setCreateBtnValidate(true);
        } else {
          if (selectedHpsId || jobId) {
            if (jobModelSelectValue || hpsModelSelectValue) {
              setCreateBtnValidate(true);
            }
          }
        }
      } else if (deploymentType === 'pretrained' && selectedModel) {
        setCreateBtnValidate(true);
      } else if (
        deploymentType === 'sandbox' &&
        Object.keys(jsonData).length > 0 &&
        !jsonDataError
      ) {
        setCreateBtnValidate(true);
      } else {
        setCreateBtnValidate(false);
      }
    } else if (editData) {
      if (
        (!templateNameDuplicate &&
          newTemplateName !== '' &&
          editData.name !== newTemplateName) ||
        (!templateNameDuplicate &&
          newTemplateName !== '' &&
          clickedGroupDataList &&
          editData) ||
        newTemplateDescription !== editData.description ||
        makeNewGroup
      ) {
        setCreateBtnValidate(true);
      } else {
        setCreateBtnValidate(false);
      }
    } else {
      setCreateBtnValidate(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    newTemplateName,
    newTemplateDescription,
    clickedDeployDataList,
    clickedGroupDataList,
    newGroupName,
    deploymentType,
    selectedModel,
    clickedDeployTemplateLists,
    templateNameDuplicate,
    clickedDeployDataList,
    jsonData,
    hpsModelList,
    trainingType,
    selectedTraining,
    selectedTrainingData,
    jobModelSelectValue,
    selectedLogId,
    jobModelSelectValue,
    hpsModelSelectValue,
    makeNewGroup,
    jsonDataError,
  ]);

  // clickedDeployTemplateLists
  return (
    <TemplateModal
      type={type}
      modalData={modalData}
      workspaceId={workspaceId}
      onClickNewGroup={onClickNewGroup}
      deploymentTypeHandler={deploymentTypeHandler}
      onClickGroupList={onClickGroupList}
      onClickGroupSelect={onClickGroupSelect}
      onClickDeployTemplateList={onClickDeployTemplateList}
      onClickDeploySelect={onClickDeploySelect}
      onClickDeployList={onClickDeployList}
      onClickGroupTemplateList={onClickGroupTemplateList}
      groupTemplateData={groupTemplateData}
      deployTemplateData={deployTemplateData}
      deploymentType={deploymentType}
      makeNewGroup={makeNewGroup}
      clickedGroupDataList={clickedGroupDataList}
      groupSelect={groupSelect}
      clickedGroupTemplateLists={clickedGroupTemplateLists}
      clickedDeployTemplateLists={clickedDeployTemplateLists}
      clickedDeployDataList={clickedDeployDataList}
      setClickedDeployDataList={setClickedDeployDataList}
      setMakeNewGroup={setMakeNewGroup}
      getTemplateListHandler={getTemplateListHandler}
      newTemplateName={newTemplateName}
      nameInputHandler={nameInputHandler}
      newTemplateDescription={newTemplateDescription}
      descriptionInputHandler={descriptionInputHandler}
      templateNameDuplicate={templateNameDuplicate}
      newGroupName={newGroupName}
      newGroupDescription={newGroupDescription}
      groupNameInputHandler={groupNameInputHandler}
      groupDescriptionInputHandler={groupDescriptionInputHandler}
      groupNameDuplicate={groupNameDuplicate}
      trainingTypeSelectHandler={trainingTypeSelectHandler}
      trainingSortHandler={trainingSortHandler}
      toolDetailOpenHandler={toolDetailOpenHandler}
      trainingToolTabHandler={trainingToolTabHandler}
      toolSelectHandler={toolSelectHandler}
      getCustomList={getCustomList}
      paramsInputHandler={paramsInputHandler}
      variablesAdd={variablesAdd}
      variablesDelete={variablesDelete}
      runcodeClickHandler={runcodeClickHandler}
      variablesSortHandler={variablesSortHandler}
      selectedDeploymentType={selectedDeploymentType}
      trainingList={trainingList}
      trainingInputValue={trainingInputValue}
      trainingSelectTab={trainingSelectTab}
      jobDetailList={jobDetailList}
      jobList={jobList}
      originJobList={originJobList}
      trainingToolTab={trainingToolTab}
      hpsList={hpsList}
      originHpsList={originHpsList}
      hpsDetailList={hpsDetailList}
      hpsLogTable={hpsLogTable}
      selectedHpsScore={selectedHpsScore}
      selectedHps={selectedHps}
      customLan={customLan}
      customFile={customFile}
      customParam={customParam}
      customList={customList}
      customSearchValue={customSearchValue}
      customRuncode={customRuncode}
      selectedTool={selectedTool}
      selectedToolType={selectedToolType}
      trainingType={trainingType}
      selectedTraining={selectedTraining}
      hpsDetailOpenList={hpsDetailOpenList}
      jobDetailOpenList={jobDetailOpenList}
      trainingSelectedType={trainingSelectedType}
      trainingSelectedOwner={trainingSelectedOwner}
      variablesValues={variablesValues}
      variableInputHandler={variableInputHandler}
      backBtnHandler={backBtnHandler}
      trainingSearch={trainingSearch}
      getJobList={getJobList}
      tabClickHandler={tabClickHandler}
      toolSortHandler={toolSortHandler}
      toolSearchValue={toolSearchValue}
      toolSelectedOwner={toolSelectedOwner}
      validate={createBtnvalidate}
      modelList={modelList}
      modelSelectStatus={modelSelectStatus}
      searchModelHandler={searchModelHandler}
      modelCategorySelect={modelCategorySelect}
      categoryHandler={categoryHandler}
      onClickModelList={onClickModelList}
      selectedModel={selectedModel}
      modelSelectStatusHanlder={modelSelectStatusHanlder}
      jsonDataHandler={jsonDataHandler}
      editStatus={editStatus}
      jsonData={jsonData}
      onClickSubmit={onClickSubmit}
      applyButtonClicked={applyButtonClicked}
      showSelectAgain={showSelectAgain}
      trainingTypeArrowCustomHandler={trainingTypeArrowCustomHandler}
      trainingTypeArrowHandler={trainingTypeArrowHandler}
      logClickHandler={logClickHandler}
      hpsLogSortHandler={hpsLogSortHandler}
      hpsModelList={hpsModelList}
      jobModelList={jobModelList}
      originHpsModelList={originHpsModelList}
      originJobModelList={originJobModelList}
      selectedLogId={selectedLogId}
      toolModelSearchValue={toolModelSearchValue}
      hpsModelSelectValue={hpsModelSelectValue}
      selectedHpsId={selectedHpsId}
      jobModelSelectValue={jobModelSelectValue}
      trainingTypeArrow={trainingTypeArrow}
      hpsLogList={hpsLogList}
      toolModelSelectHandler={toolModelSelectHandler}
      toolModelSortHandler={toolModelSortHandler}
      customListStatus={customListStatus}
      readOnly={readOnly}
      templateEditData={templateEditData}
      innerRef={jsonRef}
      jsonDataErrorHandler={jsonDataErrorHandler}
      onClickNoGroup={onClickNoGroup}
      deploymentNoGroupSelected={deploymentNoGroupSelected}
      goupOnClickNoGroup={goupOnClickNoGroup}
      templateNogroupSelected={templateNogroupSelected}
    />
  );
}
export default TemplateModalContainer;
