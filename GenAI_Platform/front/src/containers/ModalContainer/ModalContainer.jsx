import React, { Fragment, Suspense, useEffect } from 'react';
import { useSelector } from 'react-redux';

const EditPromptModal = React.lazy(() =>
  import('@src/components/Modal/EditPromptModal'),
);

const AddPublicApiModal = React.lazy(() =>
  import('@src/components/Modal/AddPublicApiModal'),
);

const AddCustomApiModal = React.lazy(() =>
  import('@src/components/Modal/AddCustomApiModal'),
);

const AddDeployProjectModal = React.lazy(() =>
  import('@src/components/Modal/AddDeployProjectModal'),
);

const AddRemoteServerModal = React.lazy(() =>
  import('@src/components/Modal/AddRemoteServerModal'),
);

const RagFileUploadModal = React.lazy(() =>
  import('@src/components/Modal/RagFileUploadModal'),
);

const DataResourceSettingModal = React.lazy(() =>
  import('@src/components/Modal/DataResourceSettingModal'),
);

const RagTestModal = React.lazy(() =>
  import('@src/components/Modal/RagTestModal'),
);
const RagSystemLog = React.lazy(() =>
  import('@src/components/Modal/RagSystemLogModal'),
);
const RagEmbeddingModal = React.lazy(() =>
  import('@src/components/Modal/RagEmbeddingModal'),
);
const RagSettingCreateModal = React.lazy(() =>
  import('@src/components/Modal/RagSettingCreateModal'),
);

const DataCollectModal = React.lazy(() =>
  import('@src/components/Modal/DataCollectModal'),
);

const EditDataCollectModal = React.lazy(() =>
  import('@src/components/Modal/DataCollectModal/EditDataCollectModal'),
);

const AddWebcrowler = React.lazy(() =>
  import('@src/components/Modal/AddWebcrowler'),
);

const ImportCommitModal = React.lazy(() =>
  import('@src/components/Modal/ImportCommitModal'),
);
const AddAiPipeLinepreprocessModal = React.lazy(() =>
  import('@src/components/Modal/AddAiPipeLinepreprocessModal'),
);

const AddPreprocessBuiltInModal = React.lazy(() =>
  import('@src/components/Modal/AddPreprocessBuiltInModal'),
);

const AIPipeLineTrainingModal = React.lazy(() =>
  import('@src/components/Modal/AIPipeLineTrainingModal'),
);

const AddTrainingBuiltInModal = React.lazy(() =>
  import('@src/components/Modal/AddTrainingBuiltInModal'),
);

const AddAIPipeLineModal = React.lazy(() =>
  import('@src/components/Modal/AddAIPipeLineModal'),
);
const EditPipelineModal = React.lazy(() =>
  import('@src/components/Modal/EditPipelineModal'),
);
const AIPipeLineDeploySettingModal = React.lazy(() =>
  import('@src/components/Modal/AIPipeLineDeploySettingModal'),
);
const AIPipeLineDeployModal = React.lazy(() =>
  import('@src/components/Modal/AIPipeLineDeployModal'),
);
const AIPipelineLogModal = React.lazy(() =>
  import('@src/modals/PipelineLogModal'),
);

// 동적 로딩을 위한 lazy 컴포넌트 정의
const BenchmarkNodeRecordModal = React.lazy(() =>
  import('@src/modals/BenchmarkNodeRecordModal'),
);
const BenchmarkStorageRecordModal = React.lazy(() =>
  import('@src/modals/BenchmarkStorageRecordModal'),
);
const DeploymentApiCodeModal = React.lazy(() =>
  import('@src/modals/DeploymentApiCodeModal'),
);
const DeploymentDeleteModal = React.lazy(() =>
  import('@src/modals/DeploymentDeleteModal'),
);
const DeploymentLogDeleteModal = React.lazy(() =>
  import('@src/modals/DeploymentLogDeleteModal'),
);
const DeploymentLogDownloadModal = React.lazy(() =>
  import('@src/modals/DeploymentLogDownloadModal'),
);
const EditApiModal = React.lazy(() =>
  import('@src/modals/EditApiModal/EditApiModal'),
);
const GitHubFormModal = React.lazy(() => import('@src/modals/GitHubFormModal'));
const GoogleDriveFormModal = React.lazy(() =>
  import('@src/modals/GoogleDriveFormModal'),
);
const MigSettingModal = React.lazy(() => import('@src/modals/MigSettingModal'));
const NetworkGroupSettingModal = React.lazy(() =>
  import('@src/modals/NetworkGroupSettingModal'),
);
const NodeFormModal = React.lazy(() => import('@src/modals/NodeFormModal'));
const NodeSettingModal = React.lazy(() =>
  import('@src/modals/NodeSettingModal'),
);
const ServingDeleteModal = React.lazy(() =>
  import('@src/modals/ServingDeleteModal/ServingDeleteModal'),
);
const ServingGroupModal = React.lazy(() =>
  import('@src/modals/ServingGroupModal'),
);
const ToolGpuAllocateModal = React.lazy(() =>
  import('@src/modals/ToolGpuAllocateModal'),
);
const ToolPasswordChangeModal = React.lazy(() =>
  import('@src/modals/ToolPasswordChangeModal'),
);
const TrainingToolModal = React.lazy(() =>
  import('@src/modals/TrainingToolModal'),
);
const UploadCheckpointModal = React.lazy(() =>
  import('@src/modals/UploadCheckpointModal'),
);

const AddStorageModal = React.lazy(() =>
  import('@src/components/Modal/AddStorageModal'),
);
const BigDataUploadModal = React.lazy(() =>
  import('@src/components/Modal/BigDataUploadModal'),
);
const EditWorkspaceResourceModal = React.lazy(() =>
  import('@src/components/Modal/EditWorkspaceResource'),
);
const SignupModal = React.lazy(() =>
  import('@src/components/Modal/SignupModal'),
);
const SshConnectionGuideModal = React.lazy(() =>
  import('@src/components/Modal/SshConnectionGuideModal'),
);
const UserWorkSpaceModal = React.lazy(() =>
  import('@src/components/Modal/UserWorkSpaceModal'),
);
const VisualizationGuideModal = React.lazy(() =>
  import('@src/components/Modal/VisualizationGuideModal'),
);
const WorkSpaceCheckModal = React.lazy(() =>
  import('@src/components/Modal/WorkSpaceCheckModal'),
);

const BuiltinModelFormModalContainer = React.lazy(() =>
  import('./BuiltinModelFormModalContainer'),
);
const CheckpointModalContainer = React.lazy(() =>
  import('./CheckpointModalContainer'),
);
const DatasetFileUploadModalContainer = React.lazy(() =>
  import('./DatasetFileUploadModalContainer'),
);
const DatasetFormModalContainer = React.lazy(() =>
  import('./DatasetFormModalContainer'),
);
const DeploymentFormModalContainer = React.lazy(() =>
  import('./DeploymentFormModalContainer'),
);
const DeployWorkerMemoModalContainer = React.lazy(() =>
  import('./DeployWorkerMemoModalContainer'),
);
const DockerImageDeleteModalContainer = React.lazy(() =>
  import('./DockerImageDeleteModalContainer'),
);
const DockerImageFormModalContainer = React.lazy(() =>
  import('./DockerImageFormModalContainer'),
);
const EditWorkerContainer = React.lazy(() => import('./EditWorkerContainer'));
const FileFormModalContainer = React.lazy(() =>
  import('./FileFormModalContainer'),
);
const FolderFormModalContainer = React.lazy(() =>
  import('./FolderFormModalContainer'),
);
const GPUSettingFormModalContainer = React.lazy(() =>
  import('./GPUSettingFormModalContainer'),
);
const HanlimUploadModalContainer = React.lazy(() =>
  import('./HanlimUploadModalContainer'),
);
// const HpsLogModalContainer = React.lazy(() => import('./HpsLogModalContainer'));
const JobCreateFormModalContainer = React.lazy(() =>
  import('./JobCreateFormModalContainer'),
);
const IntelHuggingJobModal = React.lazy(() =>
  import('@src/components/Modal/IntelHuggingJobModal'),
);

const JobLogModalContainer = React.lazy(() => import('./JobLogModalContainer'));
const JsonViewModalContainer = React.lazy(() =>
  import('./JsonViewModalContainer'),
);
const LocalFileFormModalContainer = React.lazy(() =>
  import('./LocalFileFormModalContainer'),
);
const PasswordFormModalContainer = React.lazy(() =>
  import('./PasswordFormModalContainer'),
);
const PreviewModalContainer = React.lazy(() =>
  import('./PreviewModalContainer'),
);
const StorageSettingModalContainer = React.lazy(() =>
  import('./StorageSettingModalContainer'),
);
const SystemLogModalContainer = React.lazy(() =>
  import('./SystemLogModalContainer'),
);
const TemplateModalContainer = React.lazy(() =>
  import('./TemplateModalContainer'),
);
const TrainingFormModalContainer = React.lazy(() =>
  import('./TrainingFormModalContainer'),
);
const UploadModalContainer = React.lazy(() =>
  import('./UploadCheckModalContainer'),
);
const UserFormModalContainer = React.lazy(() =>
  import('./UserFormModalContainer'),
);
const UserGroupFormModalContainer = React.lazy(() =>
  import('./UserGroupFormModalContainer'),
);
const WorkspaceFormModalContainer = React.lazy(() =>
  import('./WorkspaceFormModalContainer'),
);
const WsDescFormModalContainer = React.lazy(() =>
  import('./WsDescFormModalContainer'),
);

const UserConfirmModal = React.lazy(() =>
  import('@src/components/Modal/UserConfirmModal'),
);

const EditPlaygroundModal = React.lazy(() =>
  import('@src/components/Modal/EditPlaygroundModal'),
);
const AddPlayground = React.lazy(() =>
  import('@src/components/Modal/AddPlayground'),
);
const AddPromptModal = React.lazy(() =>
  import('@src/components/Modal/AddPromptModal'),
);

const PromptCommitModal = React.lazy(() =>
  import('@src/components/Modal/PromptCommitModal'),
);

const AddModel = React.lazy(() => import('@src/components/Modal/AddModel'));
const EditModel = React.lazy(() => import('@src/components/Modal/EditModel'));

const HuggingFaceTokenModal = React.lazy(() =>
  import('@src/components/Modal/HuggingFaceTokenModal'),
);

const AddRag = React.lazy(() => import('@src/components/Modal/AddRag'));
const EditRag = React.lazy(() => import('@src/components/Modal/EditRag'));

const FineTuningDataUploadModal = React.lazy(() =>
  import('@src/components/Modal/FineTuningDataUploadModal'),
);
const ConfigurationDataUploadModal = React.lazy(() =>
  import('@src/components/Modal/ConfigurationDataUploadModal'),
);

const FineTuningSystemLogModal = React.lazy(() =>
  import('@src/components/Modal/FineTuningSystemLogModal'),
);
const FineTuningSettingModal = React.lazy(() =>
  import('@src/components/Modal/FineTuningSettingModal'),
);
const ExternalTrainingStartModal = React.lazy(() =>
  import('@src/components/Modal/ExternalTrainingStartModal'),
);

const ImportRagModal = React.lazy(() =>
  import('@src/components/Modal/ImportRagModal'),
);

const ImportPlaygroundModal = React.lazy(() =>
  import('@src/components/Modal/ImportPlaygroundModal'),
);
const ImportPromptModal = React.lazy(() =>
  import('@src/components/Modal/ImportPromptModal'),
);
const LLMPlaygroundDeployModal = React.lazy(() =>
  import('@src/components/Modal/LLMPlaygroundDeployModal'),
);
const PlaygroundTestModal = React.lazy(() =>
  import('@src/components/Modal/PlaygroundTestModal'),
);

const FineTuningCommitModal = React.lazy(() =>
  import('@src/components/Modal/FineTuningCommitModal'),
);
const FineTuningCommit = React.lazy(() =>
  import('@src/components/Modal/FinetuningCommit'),
);
const BillingPackageModal = React.lazy(() =>
  import('@src/components/Modal/BillingPackageModal'),
);
const BasicFeeOptionModal = React.lazy(() =>
  import('@src/components/Modal/BasicFeeOptionModal'),
);
const BillingStoragePackageModal = React.lazy(() =>
  import('@src/components/Modal/BillingStoragePackageModal'),
);
const AddDatasetPreprocessModal = React.lazy(() =>
  import('@src/components/Modal/AddDatasetPreprocess'),
);
const HpsResultModal = React.lazy(() =>
  import('@src/components/Modal/HpsResultModal'),
);
const AddDatasetAnalysisModal = React.lazy(() =>
  import('@src/components/Modal/AddDatasetAnalysisModal'),
);
const AddDatasetGraphModal = React.lazy(() =>
  import('@src/components/Modal/AddDatasetGraphModal'),
);
const DatasetResourceModal = React.lazy(() =>
  import('@src/components/Modal/DatasetResourceModal'),
);
const DatasetJobCreate = React.lazy(() =>
  import('@src/components/Modal/DatasetJobCreate'),
);
const DatasetAnalyzeCreate = React.lazy(() =>
  import('@src/components/Modal/AddDatasetAnalyze'),
);
const DatasetProcessSystemLog = React.lazy(() =>
  import('@src/components/Modal/DatasetProcessSystemLog'),
);
const PreprocessGuideModal = React.lazy(() =>
  import('@src/components/Modal/PreprocessGuideModal'),
);
const DatasetBuiltinJobCreate = React.lazy(() =>
  import('@src/components/Modal/DatasetBuiltinJobCreate'),
);
const HpsCustomCreateModal = React.lazy(() =>
  import('@src/components/Modal/HpsCustomModal'),
);
const HpsBuiltinCreateModal = React.lazy(() =>
  import('@src/components/Modal/HpsBuiltinModal'),
);
const NewHpsLogModal = React.lazy(() =>
  import('@src/components/Modal/NewHpsLogModal'),
);
function ModalContainer() {
  const modal = useSelector((state) => state.modal);
  const modalKeys = Object.keys(modal);
  console.log(modalKeys);

  useEffect(() => {
    if (Object.keys(modal).length !== 0) {
      document.getElementsByTagName('body')[0].style.overflow = 'hidden';
    } else {
      document.getElementsByTagName('body')[0].style.overflow = 'auto';
    }
  }, [modal]);

  return (
    <Suspense fallback={null}>
      {modalKeys.map((modalType, idx) => (
        <Fragment key={idx}>
          {/* DeployWorker Modal */}
          {modalType === 'DEPLOY_WORKER_MEMO' && (
            <DeployWorkerMemoModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Workspace Modal */}
          {modalType === 'CREATE_WORKSPACE' && (
            <WorkspaceFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'EDIT_WORKSPACE' && (
            <WorkspaceFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Training Modal */}
          {modalType === 'CREATE_TRAINING' && (
            <TrainingFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'EDIT_TRAINING' && (
            <TrainingFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Deployment Modal */}
          {modalType === 'CREATE_DEPLOYMENT' && (
            <DeploymentFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'EDIT_DEPLOYMENT' && (
            <DeploymentFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'EDIT_WORKER' && (
            <EditWorkerContainer data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'SYSTEM_LOG' && (
            <SystemLogModalContainer data={modal[modalType]} type={modalType} />
          )}
          {/* Built-in Model Modal */}
          {modalType === 'CREATE_BUILTIN_MODEL' && (
            <BuiltinModelFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'EDIT_BUILTIN_MODEL' && (
            <BuiltinModelFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Storage Modal */}
          {modalType === 'SETTING_STORAGE' && (
            <StorageSettingModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Node Modal */}
          {modalType === 'ADD_NODE' && (
            <NodeFormModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'EDIT_NODE' && (
            <NodeFormModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'ADD_STORAGE_NODE' && (
            <NodeFormModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'EDIT_STORAGE_NODE' && (
            <NodeFormModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'SETTING_VIRTUAL_NODE' && (
            <NodeSettingModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'MIG_SETTING_MODAL' && (
            <MigSettingModal data={modal[modalType]} type={modalType} />
          )}
          {/* User Modal */}
          {modalType === 'CREATE_USER' && (
            <UserFormModalContainer data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'EDIT_USER' && (
            <UserFormModalContainer data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'CONFIRM_USER' && (
            <UserConfirmModal data={modal[modalType]} type={modalType} />
          )}
          {/* DockerImage Modal */}
          {modalType === 'CREATE_DOCKER_IMAGE' && (
            <DockerImageFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'DELETE_DOCKER_IMAGE' && (
            <DockerImageDeleteModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'EDIT_DOCKER_IMAGE' && (
            <DockerImageFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'DUPLICATE_DOCKER_IMAGE' && (
            <DockerImageFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Job Modal */}
          {modalType === 'CREATE_JOB' && (
            <JobCreateFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'CREATE_JOB_HUGGING' && (
            <IntelHuggingJobModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'CREATE_HPS_GROUP' && (
            <JobCreateFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'ADD_HPS' && (
            <JobCreateFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'JOB_LOG' && (
            <JobLogModalContainer data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'HPS_LOG' && (
            <NewHpsLogModal data={modal[modalType]} type={modalType} />
          )}
          {/* Dataset Modal */}
          {modalType === 'CREATE_DATASET' && (
            <DatasetFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'UPLOAD_CHECK' && (
            <UploadModalContainer data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'EDIT_DATASET' && (
            <DatasetFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Dataset File Upload Modal */}
          {modalType === 'UPLOAD_FILE' && (
            <LocalFileFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'DATASET_UPLOAD' && (
            <DatasetFileUploadModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Dataset Folder Modal */}
          {modalType === 'CREATE_FOLDER' && (
            <FolderFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'EDIT_FOLDER' && (
            <FolderFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Dataset File Update Modal */}
          {modalType === 'EDIT_FILE' && (
            <FileFormModalContainer data={modal[modalType]} type={modalType} />
          )}
          {/* Dataset GitHub Clone Modal */}
          {modalType === 'CLONE_GITHUB' && (
            <GitHubFormModal data={modal[modalType]} type={modalType} />
          )}
          {/* Dataset Google Drive Upload Modal */}
          {modalType === 'UPLOAD_GOOGLE_DRIVE' && (
            <GoogleDriveFormModal data={modal[modalType]} type={modalType} />
          )}
          {/* Dataset Hanlim DB Upload Modal */}
          {modalType === 'UPLOAD_HANLIM' && (
            <HanlimUploadModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Json View Modal */}
          {modalType === 'SHOW_JSON' && (
            <JsonViewModalContainer data={modal[modalType]} type={modalType} />
          )}
          {/* Preview Modal */}
          {modalType === 'PREVIEW' && (
            <PreviewModalContainer data={modal[modalType]} type={modalType} />
          )}
          {/* Checkpoint Modal */}
          {modalType === 'CHECKPOINT' && (
            <CheckpointModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Create Workspace */}
          {modalType === 'CREATE_WORKSPACE_MODAL' && (
            <UserWorkSpaceModal data={modal[modalType]} type={modalType} />
          )}
          {/* Workspace Edit Desc Modal */}
          {modalType === 'EDIT_WS_DESC' && (
            <WsDescFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Workspace Edit Desc Modal */}
          {modalType === 'EDIT_GPU_SETTING' && (
            <GPUSettingFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Workspace Confirm Modal */}
          {modalType === 'WORKSPACE_CONFIRM_MODAL' && (
            <WorkSpaceCheckModal data={modal[modalType]} type={modalType} />
          )}
          {/* User Group Modal */}
          {modalType === 'CREATE_USER_GROUP' && (
            <UserGroupFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'EDIT_USER_GROUP' && (
            <UserGroupFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* User Password Modal */}
          {modalType === 'CHANGE_PASSWORD' && (
            <PasswordFormModalContainer
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Upload Checkpoint Modal */}
          {modalType === 'UPLOAD_CHECKPOINT' && (
            <UploadCheckpointModal data={modal[modalType]} type={modalType} />
          )}
          {/* DNA Model Upload Modal */}
          {/* {modalType === 'UPLOAD_DNA_MODEL' && (
            <DNAModelUploadModal data={modal[modalType]} type={modalType} />
          )} */}
          {/* DNA+DRONE Challenge Modal */}
          {/* {modalType === 'DRONE_CHALLENGE' && (
            <DroneChallengeModal data={modal[modalType]} type={modalType} />
          )} */}
          {modalType === 'EDIT_TRAINING_TOOL' && (
            <TrainingToolModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'CREATE_TRAINING_TOOL' && (
            <TrainingToolModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'CREATE_DEPLOYMENT_API' && (
            <DeploymentApiCodeModal data={modal[modalType]} type={modalType} />
          )}
          {/* Deployment Log Download Modal */}
          {modalType === 'DEPLOYMENT_LOG_DOWNLOAD' && (
            <DeploymentLogDownloadModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'DEPLOYMENT_DELETE' && (
            <DeploymentDeleteModal data={modal[modalType]} type={modalType} />
          )}
          {/* Deployment Log Delete Modal */}
          {modalType === 'DEPLOYMENT_LOG_DELETE' && (
            <DeploymentLogDeleteModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Edit API Modal */}
          {modalType === 'EDIT_API' && (
            <EditApiModal data={modal[modalType]} type={modalType} />
          )}
          {/* Benchmarking node records Modal */}
          {modalType === 'BENCHMARK_NODE_RECORD' && (
            <BenchmarkNodeRecordModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* Benchmarking storage records Modal */}
          {modalType === 'BENCHMARK_STORAGE_RECORD' && (
            <BenchmarkStorageRecordModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'CREATE_NETWORK_GROUP' && (
            <NetworkGroupSettingModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'NETWORK_GROUP_SETTING' && (
            <NetworkGroupSettingModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'SERVING_CREATE_GROUP' && (
            <ServingGroupModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'SERVING_DELETE' && (
            <ServingDeleteModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'TEMPLATE_CREATE' && (
            <TemplateModalContainer data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'TEMPLATE_EDIT' && (
            <TemplateModalContainer data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'TOOL_PASSWORD_CHANGE' && (
            <ToolPasswordChangeModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'TOOL_GPU_ALLOCATE' && (
            <ToolGpuAllocateModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'ADD_STORAGE' && (
            <AddStorageModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'BIG_DATA_UPLOAD' && (
            <BigDataUploadModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'SIGNUP_MODAL' && (
            <SignupModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'EDIT_WORKSPACE_RESOURCE' && (
            <EditWorkspaceResourceModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'VISUALIZATION_GUIDE' && (
            <VisualizationGuideModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'SSH_CONNECTION_GUIDE' && (
            <SshConnectionGuideModal data={modal[modalType]} type={modalType} />
          )}
          {/* ** LLM ** */}
          {modalType === 'ADD_PLAYGROUND' && (
            <AddPlayground data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'EDIT_PLAYGROUND' && (
            <EditPlaygroundModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'ADD_MODEL' && (
            <AddModel data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'EDIT_MODEL' && (
            <EditModel data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'ADD_RAG' && (
            <AddRag data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'EDIT_RAG' && (
            <EditRag data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'HUGGINGFACE_TOKEN_MODAL' && (
            <HuggingFaceTokenModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'FINETUNING_DATA_UPLOAD' && (
            <FineTuningDataUploadModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'IMPORT_MODEL_PLAYGROUND' && (
            <ImportPlaygroundModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'IMPORT_RAG' && (
            <ImportRagModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'IMPORT_PROMPT' && (
            <ImportPromptModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'PLAYGROUND_DEPLOY' && (
            <LLMPlaygroundDeployModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'CONFIGURATION_DATA_UPLOAD' && (
            <ConfigurationDataUploadModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'FINETUNING_SYSTEM_LOG' && (
            <FineTuningSystemLogModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'RAG_FILE_UPLOAD' && (
            <RagFileUploadModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'RAG_TEST_MODAL' && (
            <RagTestModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'RAG_SYSTEM_LOG' && (
            <RagSystemLog data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'RAG_EMBEDDING_MODAL' && (
            <RagEmbeddingModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'RAG_SETTING_CREATE_MODAL' && (
            <RagSettingCreateModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'FINETUNING_SETTING' && (
            <FineTuningSettingModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'EXTERNAL_TRAINING_START' && (
            <ExternalTrainingStartModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'PLAYGROUND_TEST_MODAL' && (
            <PlaygroundTestModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'PLAYGROUND_PROMPT_COMMIT' && (
            <PromptCommitModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'PROMPT_PROMPT_COMMIT' && (
            <PromptCommitModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'FINETUNING_COMMIT_LOAD' && (
            <FineTuningCommitModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'FINETUNING_COMMIT' && (
            <FineTuningCommit data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'DATA_RESOURCE_SETTING_MODAL' && (
            <DataResourceSettingModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {/* AI 파이프라인 */}
          {modalType === 'AI_PIPELINE_ADD' && (
            <AddAIPipeLineModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'EDIT_PIPELINE_MODAL' && (
            <EditPipelineModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'AI_DEPLOY_SETTING' && (
            <AIPipeLineDeploySettingModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'AI_TRAINING_SETTING' && (
            <AIPipeLineTrainingModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'ADD_TRAINING_BUILT_IN' && (
            <AddTrainingBuiltInModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'ADD_PREPREOCESS_DATA' && (
            <AddAiPipeLinepreprocessModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'ADD_PREPROCESS_BUILT_IN' && (
            <AddPreprocessBuiltInModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'ADD_DEPLOY_DATA' && (
            <AIPipeLineDeployModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'AI_PIPELINE_LOG' && (
            <AIPipelineLogModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'ADD_PROMPT_MODAL' && (
            <AddPromptModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'EDIT_PROMPT_MODAL' && (
            <EditPromptModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'BILLING_PACKAGE' && (
            <BillingPackageModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'IMPORT_COMMIT_MODAL' && (
            <ImportCommitModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'BASIC_FEE_OPTION' && (
            <BasicFeeOptionModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'BILLING_STORAGE_PACKAGE' && (
            <BillingStoragePackageModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'ADD_DATASET_PREPROCESS' && (
            <AddDatasetPreprocessModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'ADD_DATASET_ANALYSIS' && (
            <AddDatasetAnalysisModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'MODIFY_DATASET_ANALYSIS' && (
            <AddDatasetAnalysisModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'ADD_DATASET_GRAPH' && (
            <AddDatasetGraphModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'DATA_COLLECT_MODAL' && (
            <DataCollectModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'EDIT_DATA_COLLECT_MODAL' && (
            <EditDataCollectModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'ADD_PUBLIC_API_MODAL' && (
            <AddPublicApiModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'ADD_CUSTOM_API_MODAL' && (
            <AddCustomApiModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'ADD_WEB_CROWLER_MODAL' && (
            <AddWebcrowler data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'ADD_REMOTE_SERVER' && (
            <AddRemoteServerModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'ADD_DEPLOY_PROJECT' && (
            <AddDeployProjectModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'DATASET_RESOURCE' && (
            <DatasetResourceModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'DATASET_JOB_CREATE' && (
            <DatasetJobCreate data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'DATASET_ANALYZE_CREATE' && (
            <DatasetAnalyzeCreate data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'DATASET_PROCESS_SYSTEM_LOG' && (
            <DatasetProcessSystemLog data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'HPS_RESULT_MODAL' && (
            <HpsResultModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'MODIFY_DATASET_PREPROCESS' && (
            <AddDatasetPreprocessModal
              data={modal[modalType]}
              type={modalType}
            />
          )}
          {modalType === 'PREPROCESS_GUIDE' && (
            <PreprocessGuideModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'DATASET_BUILT_IN_JOB_CREATE' && (
            <DatasetBuiltinJobCreate data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'HPS_CUSTOM_CREATE' && (
            <HpsCustomCreateModal data={modal[modalType]} type={modalType} />
          )}
          {modalType === 'HPS_BUILT_IN_CREATE' && (
            <HpsBuiltinCreateModal data={modal[modalType]} type={modalType} />
          )}
        </Fragment>
      ))}
    </Suspense>
  );
}

export default ModalContainer;
