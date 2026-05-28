export const TRAINING_TOOL_TYPE = {
  0: {
    label: 'Quick Editor',
    type: 'quick-editor',
    explanation: {
      en: 'Use the CPU to make Jupyter launch faster.',
      ko: 'CPU를 사용하여Jupyter Notebook을 더 빠르게 사용할 수 있습니다.',
    },
  },
  1: {
    label: 'Jupyter Lab',
    type: 'jupyter',
    explanation: {
      en: 'Run Jupyter Lab based on the Docker image.',
      ko: '도커 이미지를 기반으로 Jupyter Lab을 실행합니다.​',
    },
  },
  2: {
    label: 'JOB',
    type: 'job',
    explanation: {
      en: 'Train the model by registering a number of parameters in the queue.',
      ko: '여러 개의 파라미터 실험을 대기열에 등록하여 순차적으로 모델을 학습합니다.',
    },
  },
  3: {
    label: 'HPS',
    type: 'hps',
    explanation: {
      en: 'Search for hyperparameters through Bayesian probabilities, randoms, and grid methodologies.',
      ko: 'Bayesian probabilities, randoms, and grid 방법론을 사용하여 최적화된 하이퍼파라미터를 찾습니다.',
    },
  },
  4: {
    label: 'Shell',
    type: 'ssh',
    explanation: {
      en: 'Run Shell based on the Docker image.',
      ko: '도커 이미지를 기반으로 ​Shell을 실행합니다.​',
    },
  },
  5: {
    label: 'RStudio',
    type: 'rstudio',
    explanation: {
      en: 'RStudio.',
      ko: 'R스튜디오',
    },
  },
  6: {
    label: 'File Browser',
    type: 'filebrowser',
    explanation: {
      en: 'File Browser.',
      ko: '파일브라우저',
    },
  },
  7: {
    label: 'VSCode',
    type: 'vscode',
    explanation: {
      en: 'Run VSCode based on the docker image.',
      ko: '도커 이미지를 기반으로 VSCode를 실행합니다.',
    },
  },
  9: {
    label: 'Federated-learning',
    type: 'federatedLearning',
    explanation: {
      en: 'It is a technology where multiple local clients collaborate with a central server to train a global model in a decentralized data environment.',
      ko: '다수의 로컬 클라이언트와 하나의 중앙 서버가 협력하여 데이터가 탈중앙화된 상황에서 글로벌 모델을 학습하는 기술입니다.',
    },
  },
};
