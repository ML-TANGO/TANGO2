export const DEFAULT_INFO = {
  description: '-',
  name: '-',
  status: '',
  period: '0000-00-00 00:00 ~ 0000-00-00 00:00',
  start_datetime: '0000-00-00 00:00',
  end_datetime: '0000-00-00 00:00',
  owner: '-',
  users: [],
};

export const DEFAULT_HISTORY = [];
export const DEFAULT_TOTAL_COUNT = {
  datasets: '-',
  trainings: '-',
  deployments: '-',
  images: '-',
  models: '-',
  playgrounds: '-',
  prompts: '-',
  rags: '-',
  pricing: '-',
};
export const DEFAULT_USAGE = {
  gpu: {
    total: '-',
    used: '-',
    usage: '-',
  },
  cpu: {
    total: '-',
    used: '-',
    usage: '-',
  },
  ram: {
    total: '-',
    used: '-',
    usage: '-',
  },
  platform_usage: {
    flightbase: {
      cpu: 0,
      ram: 0,
      gpu: 0,
    },
    'a-llm': {
      cpu: 0,
      ram: 0,
      gpu: 0,
    },
  },
};
export const DEFAULT_MAIN_STORAGE = {
  total: '-',
  avail: '-',
  usage: '-',
  used: '-',
  allm_list: [],
  project_list: [],
  allm_usage: 0,
  fb_usage: 0,
};

export const DEFAULT_DATA_STORAGE = {
  total: '-',
  avail: '-',
  usage: '-',
  used: '-',
  dataset_list: [],
};

export const DEFAULT_ISMANAGER = false;
export const DEFAULT_INSTANCE_USED = [];

export const DEAFAULT_DATA = {
  info: DEFAULT_INFO,
  history: DEFAULT_HISTORY,
  total_count: DEFAULT_TOTAL_COUNT,
  usage: DEFAULT_USAGE,
  storage: {
    main_storage: DEFAULT_MAIN_STORAGE,
    data_storage: DEFAULT_DATA_STORAGE,
  },
  instance_used: DEFAULT_INSTANCE_USED,
  manager: DEFAULT_ISMANAGER,
};
