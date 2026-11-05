NOTIFICATION_USER_TYPE_ADMIN             = "admin"
NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER = "workspace_manager"
NOTIFICATION_USER_TYPE_USER              = "user"

NOTIFICATION_TYPE_WORKSPACE     = "workspace"
NOTIFICATION_TYPE_USER          = "user"
NOTIFICATION_TYPE_PROJECT       = "projet"
NOTIFICATION_TYPE_SYSTEM        = "system"
NOTIFICATION_TYPE_PREPROCESSING = "preprocessing"
NOTIFICATION_TYPE_FINETUNING    = "fine-tuning"
NOTIFICATION_TYPE_DEPLOYMENT    = "deployment"
NOTIFICATION_TYPE_RESOURCE      = "resource"



# system -> workspace manager
WORKSPACE_CREATE_MESSAGE            = "요청하신 '{workspace_name}' 워크스페이스가 생성되었습니다"
WORKSPACE_CREATE_ACCEP_MESSAGE     = "요청하신 '{workspace_name}' 워크스페이스 생성이 수락 되었습니다."
WORKSPACE_CREATE_REFUSE_MESSAGE     = "요청하신 '{workspace_name}' 워크스페이스 생성이 거절 당했습니다. 관리자에게 문의하세요"
WORKSPACE_UPDATE_ACCEP_MESSAGE     = "요청하신 '{workspace_name}' 워크스페이스 수정이 수락 되었습니다."
WORKSPACE_UPDATE_REFUSE_MESSAGE     = "요청하신 '{workspace_name}' 워크스페이스 수정이 거절 당했습니다. 관리자에게 문의하세요"
WORKSPACE_DELETE_MESSAGE            = "'{workspace_name}' 워크스페이스가 삭제 되었습니다."
WORKSPACE_INSTANCE_RESOURCE_CPU_OVER    = "'{workspace_name}' 워크스페이스의 인스턴스의 cpu 사용률이 80%를 초과하였습니다. 불필요한 작업을 중단하세요."
WORKSPACE_INSTANCE_RESOURCE_RAM_OVER    = "'{workspace_name}' 워크스페이스의 인스턴스의 ram 사용률이 80%를 초과하였습니다. 불필요한 작업을 중단하세요."
WORKSPACE_INSTANCE_RESOURCE_MAIN_STORAGE_OVER    = "'{workspace_name}' 워크스페이스의 '메인 스토리지' 사용률이 80%를 초과하였습니다. 불필요한 데이터를 삭제하세요."
WORKSPACE_INSTANCE_RESOURCE_MAIN_STORAGE_100_OVER    = "'{workspace_name}' 워크스페이스의 '메인 스토리지' 사용률이 90%에 도달하였습니다. 100%에 도달하면 추가 알림 없이 실행중인 학습 툴, 배포, 학습이 강제 종료됩니다. 불필요한 데이터를 삭제하세요."
WORKSPACE_INSTANCE_RESOURCE_DATA_STORAGE_OVER    = "'{workspace_name}' 워크스페이스의 '데이터 스토리지' 사용률이 80%를 초과하였습니다. 불필요한 데이터를 삭제하세요."
WORKSPACE_INSTANCE_RESOURCE_DATA_STORAGE_100_OVER    = "'{workspace_name}' 워크스페이스의 '데이터 스토리지' 사용률이 90%에 도달하였습니다. 100%에 도달하면 업로드기능 및 filebrowser들이 강제 종료됩니다. 불필요한 데이터를 삭제하세요."
# system -> admin
WORKSPACE_CREATE_REQUEST            = "'{user_name}' 사용자가 워크스페이스 생성을 요청하였습니다"
WORKSPACE_UPDATE_REQUEST            = "'{user_name}' 사용자가 워크스페이스 수정을 요청하였습니다"
USER_CREATE_REQUEST                 = "'{user_name}' 사용자 생성을 요청하였습니다."

# TRAINING system -> user
TRAINING_START                      = "'{training_name}' 학습이 시작되었습니다."
TRAINING_COMPLETE                   = "'{training_name}' 학습이 끝났습니다."
TRAINING_TERMINATE                  = "'{training_name}' 학습이 강제 종료 되었습니다."