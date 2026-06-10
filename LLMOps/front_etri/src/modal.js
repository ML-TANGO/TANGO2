const modalComponents = {
  DEPLOY_WORKER_MEMO: () =>
    import('@src/containers/ModalContainer/DeployWorkerMemoModalContainer'),
  CREATE_WORKSPACE: () =>
    import('@src/containers/ModalContainer/WorkspaceFormModalContainer'),
  EDIT_WORKSPACE: () =>
    import('@src/containers/ModalContainer/WorkspaceFormModalContainer'),
  CREATE_TRAINING: () =>
    import('@src/containers/ModalContainer/TrainingFormModalContainer'),
  EDIT_TRAINING: () =>
    import('@src/containers/ModalContainer/TrainingFormModalContainer'),
  CREATE_DEPLOYMENT: () =>
    import('@src/containers/ModalContainer/DeploymentFormModalContainer'),
  EDIT_DEPLOYMENT: () =>
    import('@src/containers/ModalContainer/DeploymentFormModalContainer'),
  EDIT_WORKER: () =>
    import('@src/containers/ModalContainer/EditWorkerContainer'),
  SYSTEM_LOG: () =>
    import('@src/containers/ModalContainer/SystemLogModalContainer'),
  CREATE_BUILTIN_MODEL: () =>
    import('@src/containers/ModalContainer/BuiltinModelFormModalContainer'),
  EDIT_BUILTIN_MODEL: () =>
    import('@src/containers/ModalContainer/BuiltinModelFormModalContainer'),
  SETTING_STORAGE: () =>
    import('@src/containers/ModalContainer/StorageSettingModalContainer'),
  ADD_NODE: () => import('@src/modals/NodeFormModal'),
  EDIT_NODE: () => import('@src/modals/NodeFormModal'),
  ADD_STORAGE_NODE: () => import('@src/modals/NodeFormModal'),
  EDIT_STORAGE_NODE: () => import('@src/modals/NodeFormModal'),
  SETTING_VIRTUAL_NODE: () => import('@src/modals/NodeSettingModal'),
  MIG_SETTING_MODAL: () => import('@src/modals/MigSettingModal'),
  CREATE_USER: () =>
    import('@src/containers/ModalContainer/UserFormModalContainer'),
  EDIT_USER: () =>
    import('@src/containers/ModalContainer/UserFormModalContainer'),
  CONFIRM_USER: () => import('@src/components/Modal/UserConfirmModal'),
  HPS_RESULT_MODAL: () => import('@src/components/Modal/HpsResultModal'),
  CREATE_DOCKER_IMAGE: () =>
    import('@src/containers/ModalContainer/DockerImageFormModalContainer'),
  DELETE_DOCKER_IMAGE: () =>
    import('@src/containers/ModalContainer/DockerImageDeleteModalContainer'),
  EDIT_DOCKER_IMAGE: () =>
    import('@src/containers/ModalContainer/DockerImageFormModalContainer'),
  DUPLICATE_DOCKER_IMAGE: () =>
    import('@src/containers/ModalContainer/DockerImageFormModalContainer'),
  CREATE_JOB: () =>
    import('@src/containers/ModalContainer/JobCreateFormModalContainer'),
  CREATE_JOB_HUGGING: () =>
    import('@src/components/Modal/IntelHuggingJobModal'),
  CREATE_HPS_GROUP: () =>
    import('@src/containers/ModalContainer/JobCreateFormModalContainer'),
  ADD_HPS: () =>
    import('@src/containers/ModalContainer/JobCreateFormModalContainer'),
  JOB_LOG: () => import('@src/containers/ModalContainer/JobLogModalContainer'),
  HPS_LOG: () => import('@src/containers/ModalContainer/HpsLogModalContainer'),
  CREATE_DATASET: () =>
    import('@src/containers/ModalContainer/DatasetFormModalContainer'),
  UPLOAD_CHECK: () =>
    import('@src/containers/ModalContainer/UploadCheckModalContainer'),
  EDIT_DATASET: () =>
    import('@src/containers/ModalContainer/DatasetFormModalContainer'),
  UPLOAD_FILE: () =>
    import('@src/containers/ModalContainer/LocalFileFormModalContainer'),
  DATASET_UPLOAD: () =>
    import('@src/containers/ModalContainer/DatasetFileUploadModalContainer'),
  CREATE_FOLDER: () =>
    import('@src/containers/ModalContainer/FolderFormModalContainer'),
  EDIT_FOLDER: () =>
    import('@src/containers/ModalContainer/FolderFormModalContainer'),
  EDIT_FILE: () =>
    import('@src/containers/ModalContainer/FileFormModalContainer'),
  CLONE_GITHUB: () => import('@src/modals/GitHubFormModal'),
  UPLOAD_GOOGLE_DRIVE: () => import('@src/modals/GoogleDriveFormModal'),
  UPLOAD_HANLIM: () =>
    import('@src/containers/ModalContainer/HanlimUploadModalContainer'),
  SHOW_JSON: () =>
    import('@src/containers/ModalContainer/JsonViewModalContainer'),
  PREVIEW: () => import('@src/containers/ModalContainer/PreviewModalContainer'),
  CHECKPOINT: () =>
    import('@src/containers/ModalContainer/CheckpointModalContainer'),
  CREATE_WORKSPACE_MODAL: () =>
    import('@src/components/Modal/UserWorkSpaceModal'),
  EDIT_WS_DESC: () =>
    import('@src/containers/ModalContainer/WsDescFormModalContainer'),
  EDIT_GPU_SETTING: () =>
    import('@src/containers/ModalContainer/GPUSettingFormModalContainer'),
  WORKSPACE_CONFIRM_MODAL: () =>
    import('@src/components/Modal/WorkSpaceCheckModal'),
  CREATE_USER_GROUP: () =>
    import('@src/containers/ModalContainer/UserGroupFormModalContainer'),
  EDIT_USER_GROUP: () =>
    import('@src/containers/ModalContainer/UserGroupFormModalContainer'),
  CHANGE_PASSWORD: () =>
    import('@src/containers/ModalContainer/PasswordFormModalContainer'),
  UPLOAD_CHECKPOINT: () => import('@src/modals/UploadCheckpointModal'),
  EDIT_TRAINING_TOOL: () => import('@src/modals/TrainingToolModal'),
  CREATE_TRAINING_TOOL: () => import('@src/modals/TrainingToolModal'),
  CREATE_DEPLOYMENT_API: () => import('@src/modals/DeploymentApiCodeModal'),
  DEPLOYMENT_LOG_DOWNLOAD: () =>
    import('@src/modals/DeploymentLogDownloadModal'),
  DEPLOYMENT_DELETE: () => import('@src/modals/DeploymentDeleteModal'),
  DEPLOYMENT_LOG_DELETE: () => import('@src/modals/DeploymentLogDeleteModal'),
  EDIT_API: () => import('@src/modals/EditApiModal/EditApiModal'),
  BENCHMARK_NODE_RECORD: () => import('@src/modals/BenchmarkNodeRecordModal'),
  BENCHMARK_STORAGE_RECORD: () =>
    import('@src/modals/BenchmarkStorageRecordModal'),
  CREATE_NETWORK_GROUP: () => import('@src/modals/NetworkGroupSettingModal'),
  NETWORK_GROUP_SETTING: () => import('@src/modals/NetworkGroupSettingModal'),
  SERVING_CREATE_GROUP: () => import('@src/modals/ServingGroupModal'),
  SERVING_DELETE: () =>
    import('@src/modals/ServingDeleteModal/ServingDeleteModal'),
  TEMPLATE_CREATE: () =>
    import('@src/containers/ModalContainer/TemplateModalContainer'),
  TEMPLATE_EDIT: () =>
    import('@src/containers/ModalContainer/TemplateModalContainer'),

  TOOL_PASSWORD_CHANGE: () => import('@src/modals/ToolPasswordChangeModal'),
  TOOL_GPU_ALLOCATE: () => import('@src/modals/ToolGpuAllocateModal'),
  ADD_STORAGE: () => import('@src/components/Modal/AddStorageModal'),
  BIG_DATA_UPLOAD: () => import('@src/components/Modal/BigDataUploadModal'),
  SIGNUP_MODAL: () => import('@src/components/Modal/SignupModal'),
  EDIT_WORKSPACE_RESOURCE: () =>
    import('@src/components/Modal/EditWorkspaceResource'),
  VISUALIZATION_GUIDE: () =>
    import('@src/components/Modal/VisualizationGuideModal'),
  SSH_CONNECTION_GUIDE: () =>
    import('@src/components/Modal/SshConnectionGuideModal'),

  // !! LLM !!
  ADD_PLAYGROUND: () => import('@src/components/Modal/AddPlayground'),
  EDIT_PLAYGROUND: () => import('@src/components/Modal/EditPlaygroundModal'),
  ADD_MODEL: () => import('@src/components/Modal/AddModel'),
  // EDIT_MODEL: () => import('@src/components/Modal/EditModel'),
  FINETUNING_DATA_UPLOAD: () =>
    import('@src/components/Modal/FineTuningDataUploadModal'),
  HUGGINGFACE_TOKEN_MODAL: () =>
    import('@src/components/Modal/HuggingFaceTokenModal'),
  CONFIGURATION_DATA_UPLOAD: () =>
    import('@src/components/Modal/ConfigurationDataUploadModal'),
  FINETUNING_SYSTEM_LOG: () =>
    import('@src/components/Modal/FineTuningSystemLogModal'),
  FINETUNING_SETTING: () =>
    import('@src/components/Modal/FineTuningSettingModal'),
  EXTERNAL_TRAINING_START: () =>
    import('@src/components/Modal/ExternalTrainingStartModal'),
  FINETUNING_COMMIT_LOAD: () =>
    import('@src/components/Modal/FineTuningCommitModal'),
  IMPORT_MODEL_PLAYGROUND: () =>
    import('@src/components/Modal/ImportPlaygroundModal'),
  IMPORT_RAG: () => import('@src/components/Modal/ImportRagModal'),
  IMPORT_PROMPT: () => import('@src/components/Modal/ImportPromptModal'),
  EDIT_PROMPT_MODAL: () => import('@src/components/Modal/EditPromptModal'),
  PLAYGROUND_DEPLOY: () =>
    import('@src/components/Modal/LLMPlaygroundDeployModal'),
  PLAYGROUND_TEST_MODAL: () =>
    import('@src/components/Modal/PlaygroundTestModal'),
  ADD_RAG: () => import('@src/components/Modal/AddRag'),
  EDIT_RAG: () => import('@src/components/Modal/EditRag'),
  FINETUNING_COMMIT: () => import('@src/components/Modal/FinetuningCommit'),
  RAG_FILE_UPLOAD: () => import('@src/components/Modal/RagFileUploadModal'),
  RAG_TEST_MODAL: () => import('@src/components/Modal/RagTestModal'),
  RAG_SYSTEM_LOG: () => import('@src/components/Modal/RagSystemLogModal'),
  RAG_EMBEDDING_MODAL: () => import('@src/components/Modal/RagEmbeddingModal'),
  RAG_SETTING_CREATE_MODAL: () =>
    import('@src/components/Modal/RagSettingCreateModal'),
  ADD_DATASET_ANALYSIS: () =>
    import('@src/components/Modal/AddDatasetAnalysisModal'),
  ADD_DATASET_GRAPH: () => import('@src/components/Modal/AddDatasetGraphModal'),
  DATA_RESOURCE_SETTING_MODAL: () =>
    import('@src/components/Modal/DataResourceSettingModal'),
  // ! AI PIPELINE
  AI_PIPELINE_ADD: () => import('@src/components/Modal/AddAIPipeLineModal'),
  AI_DEPLOY_SETTING: () =>
    import('@src/components/Modal/AIPipeLineDeploySettingModal'),
  AI_TRAINING_SETTING: () =>
    import('@src/components/Modal/AIPipeLineTrainingModal'),
  ADD_PREPREOCESS_DATA: () =>
    import('@src/components/Modal/AddAiPipeLinepreprocessModal'),
  ADD_PREPROCESS_BUILT_IN: () =>
    import('@src/components/Modal/AddPreprocessBuiltInModal'),
  ADD_DEPLOY_DATA: () => {
    import('@src/components/Modal/AIPipeLineDeployModal');
  },
  AI_PIPELINE_LOG: () => import('@src/modals/PipelineLogModal'),
  DATA_COLLECT_MODAL: () => import('@src/components/Modal/DataCollectModal'),
  EDIT_DATA_COLLECT_MODAL: () =>
    import('@src/components/Modal/DataCollectModal/EditDataCollectModal'),
  ADD_WEB_CROWLER_MODAL: () => import('@src/components/Modal/AddWebcrowler'),
  ADD_REMOTE_SERVERL: () =>
    import('@src/components/Modal/AddRemoteServerModal'),
  ADD_DEPLOY_PROJECT: () =>
    import('@src/components/Modal/AddDeployProjectModal'),
  ADD_PUBLIC_API_MODAL: () => import('@src/components/Modal/AddPublicApiModal'),
  ADD_CUSTOM_API_MODAL: () => import('@src/components/Modal/AddCustomApiModal'),
  EDIT_PIPELINE_MODAL: () => import('@src/components/Modal/EditPipelineModal'),
};

// ** 기존 모달들 overflow hidden으로 모두 불러오는 방식이었음 (FCP 영향 끼침) **

// ** 모달들 lazy하게 바꾸고 openModal 함수를 통해 모달을 생성하는 페이지에서 **
// ** useEffect []에 초기 마운트 후 load하게 변경함 **
// ** 전체를 다 바꿀 용기가 나지 않으니 v2때 아무나 바꿔주세요. **
export const loadModalComponent = async (modalType) => {
  const importComponent = modalComponents[modalType];
  if (importComponent) {
    return await importComponent();
  } else {
    console.log(`No component found for modal type: ${modalType}`);
  }
};
