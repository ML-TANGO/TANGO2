// Mock Data for Jonathan Flightbase Frontend (Kubernetes-free dummy mode)
import crypto from 'crypto-js';

const ENC_KEY = 'robertirenelico!robertirenelico!';
const IV = 'robertirenelico!';

const decrypt = (encrypted) => {
  if (!encrypted) return '';
  try {
    const wordArray = crypto.enc.Utf8.parse(ENC_KEY);
    const iv = crypto.enc.Utf8.parse(IV);
    const decipher = crypto.AES.decrypt(encrypted, wordArray, {
      iv,
      mode: crypto.mode.CBC,
      keySize: 256,
    });
    return decipher.toString(crypto.enc.Utf8);
  } catch (e) {
    return '';
  }
};

export const mockResponses = {
  'login': {
    status: 1,
    result: {
      logined_session: 'dummy-session-12345',
      user_name: 'admin',
      admin: true,
      token: 'dummy-jwt-token-xyz',
      photo_url: '/images/icon/00-ic-info-user.svg',
      jp_user_name: '관리자',
      logined: false,
    },
    message: 'Success',
  },
  'login/force': {
    status: 1,
    result: {
      logined_session: 'dummy-session-12345',
      user_name: 'admin',
      admin: true,
      token: 'dummy-jwt-token-xyz',
      photo_url: '/images/icon/00-ic-info-user.svg',
      jp_user_name: '관리자',
      logined: false,
    },
    message: 'Success',
  },
  'logout': {
    status: 1,
    result: {},
    message: 'Logout Success',
  },
  'dashboard/admin': {
    status: 1,
    result: {
      totalCount: [
        { variation: 0, total: 10, name: 'Workspaces' },
        { variation: 0, total: 24, name: 'Trainings' },
        { variation: 0, total: 15, name: 'Deployments' },
        { variation: 0, total: 8, name: 'Docker Images' },
        { variation: 0, total: 32, name: 'Datasets' },
        { variation: 0, total: 6, name: 'Nodes' },
      ],
      usage: {
        gpuByType: { total: 16, active: 10, idle: 6, over_limit: 0 },
        gpuByGuarantee: { total: 16, active: 8, idle: 8 },
        hdd: { used: 2500, total: 10000 },
      },
      history: [
        { id: 'h1', action: 'New node added', user: 'system', time: '2026-06-09T08:00:00Z' },
        { id: 'h2', action: 'Workspace billing updated', user: 'admin', time: '2026-06-09T07:30:00Z' }
      ]
    },
    message: 'Success',
  },
  'dashboard/admin/resource-usage': {
    status: 1,
    result: {
      timeline: {
        cpu: [
          { date: '2026-06-09T09:00:00Z', ratio_cpu: 10, total_cpu: 16, used_cpu: 1.6 },
          { date: '2026-06-09T12:00:00Z', ratio_cpu: 20, total_cpu: 16, used_cpu: 3.2 },
          { date: '2026-06-09T15:00:00Z', ratio_cpu: 30, total_cpu: 16, used_cpu: 4.8 }
        ],
        gpu: [
          { date: '2026-06-09T09:00:00Z', ratio_gpu: 5, total_gpu: 4, used_gpu: 0.2 },
          { date: '2026-06-09T12:00:00Z', ratio_gpu: 15, total_gpu: 4, used_gpu: 0.6 },
          { date: '2026-06-09T15:00:00Z', ratio_gpu: 25, total_gpu: 4, used_gpu: 1.0 }
        ],
        ram: [
          { date: '2026-06-09T09:00:00Z', ratio_ram: 20, total_ram: 64, used_ram: 12.8 },
          { date: '2026-06-09T12:00:00Z', ratio_ram: 30, total_ram: 64, used_ram: 19.2 },
          { date: '2026-06-09T15:00:00Z', ratio_ram: 45, total_ram: 64, used_ram: 28.8 }
        ],
        storage_data: [
          { date: '2026-06-09T09:00:00Z', ratio_storage_data: 10, total_storage_data: 5000, used_storage_data: 500 },
          { date: '2026-06-09T12:00:00Z', ratio_storage_data: 12, total_storage_data: 5000, used_storage_data: 600 },
          { date: '2026-06-09T15:00:00Z', ratio_storage_data: 15, total_storage_data: 5000, used_storage_data: 750 }
        ],
        storage_main: [
          { date: '2026-06-09T09:00:00Z', ratio_storage_main: 5, total_storage_main: 1000, used_storage_main: 50 },
          { date: '2026-06-09T12:00:00Z', ratio_storage_main: 6, total_storage_main: 1000, used_storage_main: 60 },
          { date: '2026-06-09T15:00:00Z', ratio_storage_main: 8, total_storage_main: 1000, used_storage_main: 80 }
        ]
      }
    },
    message: 'Success',
  },
  'storage': {
    status: 1,
    result: {
      total: {
        total_size: 10000000000000, // bytes
        total_alloc: 2550000000000,
        total_used: 1900000000000
      },
      list: [
        {
          id: 'stor-1',
          name: 'Primary NFS Storage',
          type: 'NFS',
          path: '/mnt/nfs/primary',
          status: 'Healthy',
          workspaces: {
            detail: []
          },
          usage: {
            size: 5000000000000,
            alloc: 1250000000000,
            used: 1000000000000,
            pcent: 25,
            usage: 20
          }
        },
        {
          id: 'stor-2',
          name: 'Backup GlusterFS',
          type: 'GlusterFS',
          path: '/mnt/gluster/backup',
          status: 'Healthy',
          workspaces: {
            detail: []
          },
          usage: {
            size: 5000000000000,
            alloc: 1300000000000,
            used: 900000000000,
            pcent: 26,
            usage: 18
          }
        }
      ]
    },
    message: 'Success',
  },
  'nodes/node-info': {
    status: 1,
    result: {
      usage: {
        cpu: {
          detail: {
            'node-1': {
              workspace: {
                'workspace-default': { used: 2, total: 4 }
              }
            }
          }
        },
        gpu: {
          detail: {
            'gpu-node-1': {
              workspace: {
                'workspace-default': { used: 1, total: 2 }
              }
            }
          }
        },
        mem: {
          detail: {
            'node-1': {
              workspace: {
                'workspace-default': { used: 8, total: 16 }
              }
            }
          }
        },
        instance: {
          'inst-1': {
            workspace: {
              'workspace-default': { used: 1, total: 1 }
            }
          }
        },
        workspace_instance_usage: {
          'workspace-default': {
            workspace: {}
          }
        }
      }
    },
    message: 'Success',
  },
  'built_in_models/list': {
    status: 1,
    result: {
      list: [
        { id: 'bm-1', name: 'Llama-3-8B-Instruct', kind: 'text-generation', status: 'active', size: '8B' },
        { id: 'bm-2', name: 'Bert-base-uncased', kind: 'text-classification', status: 'inactive', size: '110M' }
      ]
    },
    message: 'Success'
  },
  'options/built_in_models_kind': {
    status: 1,
    result: ['text-generation', 'text-classification', 'question-answering'],
    message: 'Success'
  },
  'deployments/admin': {
    status: 1,
    result: {
      list: [
        { id: 'dep-1', name: 'Llama-3 Service', model_name: 'Llama-3-8B-Instruct', status: 'Active', creator: 'admin', url: 'http://129.254.222.150:8000' }
      ]
    },
    message: 'Success',
  },
  'services': {
    status: 1,
    result: {
      list: [
        { id: 'svc-1', name: 'Llama3-Evaluation-Service', status: 'Running', creator: 'etri', created_at: '2026-06-09T08:00:00Z' }
      ]
    },
    message: 'Success',
  },
  'deployments': {
    status: 1,
    result: {
      list: [
        { id: 'dep-1', name: 'LLama3-8B-Deployment', status: 'Running', creator: 'etri', created_at: '2026-06-09T08:30:00Z', url: 'http://129.254.222.150:8000' }
      ]
    },
    message: 'Success',
  },
  'images': {
    status: 1,
    result: {
      list: [
        { id: 'img-1', name: 'pytorch-2.1-cuda12.1', tag: 'v1.0', creator: 'system', status: 'Active' },
        { id: 'img-2', name: 'tensorflow-2.15-cuda12.1', tag: 'v1.0', creator: 'system', status: 'Active' }
      ]
    },
    message: 'Success',
  },
  'networks/network-group': {
    status: 1,
    result: {
      list: [
        { id: 'net-1', name: 'Default network group', ip_range: '10.244.0.0/16', status: 'Active' }
      ]
    },
    message: 'Success',
  },
  'networks/network-group-view': {
    status: 1,
    result: {
      list: [
        { id: 'net-1', name: 'Default network group', ip_range: '10.244.0.0/16', status: 'Active' }
      ]
    },
    message: 'Success',
  },
  'projects': {
    status: 1,
    result: {
      list: [
        { id: 'proj-1', name: 'Fine-Tuning Project A', status: 'Completed', creator: 'admin', created_at: '2026-06-09T00:00:00Z' }
      ]
    },
    message: 'Success',
  },
  'users/group': {
    status: 1,
    result: {
      list: [
        { id: 'ug-1', name: 'Admin Group', description: 'Administrators' },
        { id: 'ug-2', name: 'User Group', description: 'Regular users' }
      ]
    },
    message: 'Success',
  },
  'users': {
    status: 1,
    result: {
      list: [
        { id: 'u-1', username: 'admin', email: 'admin@tango.com', role: 'ADMIN', status: 'Active' },
        { id: 'u-2', username: 'demo', email: 'demo@tango.com', role: 'USER', status: 'Active' }
      ]
    },
    message: 'Success',
  },
  'cost-management/basic-cost': {
    status: 1,
    result: {
      list: []
    },
    message: 'Success',
  },
  'cost-management/instance-package-active': {
    status: 1,
    result: {
      list: []
    },
    message: 'Success',
  },
  'cost-management/instance-package': {
    status: 1,
    result: {
      list: []
    },
    message: 'Success',
  },
  'cost-management/storage-package-active': {
    status: 1,
    result: {
      list: []
    },
    message: 'Success',
  },
  'cost-management/storage-package': {
    status: 1,
    result: {
      list: []
    },
    message: 'Success',
  },
  'benchmark/basic-node-info': {
    status: 1,
    result: {
      list: []
    },
    message: 'Success',
  },
  'benchmark/node-network-all-latest-info': {
    status: 1,
    result: {
      list: []
    },
    message: 'Success',
  },
  'benchmark/storage-all-info': {
    status: 1,
    result: {
      list: []
    },
    message: 'Success',
  },
  'workspaces': {
    status: 1,
    result: {
      list: [
        {
          id: 'workspace-default',
          name: '기본 워크스페이스',
          description: '쿠버네티스 없이 동작하는 데모용 기본 워크스페이스입니다.',
          created_at: '2026-06-09T00:00:00Z',
          updated_at: '2026-06-09T00:00:00Z',
          favorites: 1,
          status: 'running',
          manager: 'etri',
          user: {
            total: 1,
            list: [{ name: 'etri' }]
          },
          trainings: 2,
          deployments: 1,
          images: 3,
          datasets: 5,
          start_datetime: '2026-06-09T00:00:00Z',
          end_datetime: '2026-12-31T00:00:00Z',
          resource: {
            cpu: { total: 16, used: 4 },
            gpu: { total: 4, used: 1 }
          }
        },
        {
          id: 'workspace-demo',
          name: '데모 워크스페이스',
          description: 'UI 변경 검증용 추가 워크스페이스입니다.',
          created_at: '2026-06-09T00:00:00Z',
          updated_at: '2026-06-09T00:00:00Z',
          favorites: 0,
          status: 'running',
          manager: 'admin',
          user: {
            total: 2,
            list: [{ name: 'admin' }, { name: 'etri' }]
          },
          trainings: 0,
          deployments: 0,
          images: 1,
          datasets: 2,
          start_datetime: '2026-06-09T00:00:00Z',
          end_datetime: '2026-12-31T00:00:00Z',
          resource: {
            cpu: { total: 8, used: 2 },
            gpu: { total: 2, used: 0 }
          }
        }
      ]
    },
    message: 'Success',
  },
  'workspaces/favorites': {
    status: 1,
    result: {
      list: [
        {
          id: 'workspace-default',
          name: '기본 워크스페이스',
          description: '쿠버네티스 없이 동작하는 데모용 기본 워크스페이스입니다.',
          created_at: '2026-06-09T00:00:00Z',
          updated_at: '2026-06-09T00:00:00Z',
          favorites: 1,
          status: 'running',
          manager: 'etri',
          user: {
            total: 1,
            list: [{ name: 'etri' }]
          },
          trainings: 2,
          deployments: 1,
          images: 3,
          datasets: 5,
          start_datetime: '2026-06-09T00:00:00Z',
          end_datetime: '2026-12-31T00:00:00Z',
          resource: {
            cpu: { total: 16, used: 4 },
            gpu: { total: 4, used: 1 }
          }
        }
      ]
    },
    message: 'Success',
  },
  'workspaces/option': {
    status: 1,
    result: {
      gpu_options: ['NVIDIA-A100', 'NVIDIA-T4', 'None'],
      cpu_options: ['2 Cores', '4 Cores', '8 Cores'],
      memory_options: ['8 GB', '16 GB', '32 GB'],
    },
    message: 'Success',
  },
  'dashboard/user': {
    status: 1,
    result: {
      info: {
        id: 'workspace-default',
        name: '기본 워크스페이스',
        description: '데모용 기본 워크스페이스',
      },
      total_count: {
        images: 3,
        datasets: 5,
        trainings: 2,
        deployments: 1,
      },
      usage: {
        gpu: { total: 4, used: 1 },
        cpu: { total: 16, used: 4 },
        memory: { total: 64, used: 16 },
      },
      project_items: [
        { id: 'proj-1', name: 'FineTuning Project 1', status: 'Running', type: 'training' },
        { id: 'proj-2', name: 'LLM Deployment 1', status: 'Active', type: 'deployment' }
      ],
      history: [
        { id: 'hist-1', action: 'Model deployed', user: 'admin', time: '2026-06-09T10:00:00Z' },
        { id: 'hist-2', action: 'Dataset uploaded', user: 'admin', time: '2026-06-09T09:30:00Z' }
      ],
      detailed_timeline: [
        { date: '2026-06-09', cpu: 20, memory: 30, gpu: 25 }
      ],
      manager: true,
      instances_used: [
        { name: 'GPU Instance 1', status: 'Running', allocated_at: '2026-06-09T08:00:00Z' }
      ],
      project_instance_allocate: [
        {
          id: 'alloc-1',
          instance_info: {
            name: 'GPU-Node-A100',
            ip: '192.168.1.100',
            gpu_type: 'NVIDIA-A100',
          }
        }
      ],
      storage: {
        main_storage: { total: 1000, used: 250 },
        data_storage: { total: 5000, used: 1200 },
      },
    },
    message: 'Success',
  },
  'dashboard/user/resource-usage': {
    status: 1,
    result: {
      timeline: {
        cpu: [
          { date: '2026-06-09T09:00:00Z', ratio_cpu: 10, total_cpu: 16, used_cpu: 1.6 },
          { date: '2026-06-09T12:00:00Z', ratio_cpu: 20, total_cpu: 16, used_cpu: 3.2 },
          { date: '2026-06-09T15:00:00Z', ratio_cpu: 30, total_cpu: 16, used_cpu: 4.8 }
        ],
        gpu: [
          { date: '2026-06-09T09:00:00Z', ratio_gpu: 5, total_gpu: 4, used_gpu: 0.2 },
          { date: '2026-06-09T12:00:00Z', ratio_gpu: 15, total_gpu: 4, used_gpu: 0.6 },
          { date: '2026-06-09T15:00:00Z', ratio_gpu: 25, total_gpu: 4, used_gpu: 1.0 }
        ],
        ram: [
          { date: '2026-06-09T09:00:00Z', ratio_ram: 20, total_ram: 64, used_ram: 12.8 },
          { date: '2026-06-09T12:00:00Z', ratio_ram: 30, total_ram: 64, used_ram: 19.2 },
          { date: '2026-06-09T15:00:00Z', ratio_ram: 45, total_ram: 64, used_ram: 28.8 }
        ],
        storage_data: [
          { date: '2026-06-09T09:00:00Z', ratio_storage_data: 10, total_storage_data: 5000, used_storage_data: 500 },
          { date: '2026-06-09T12:00:00Z', ratio_storage_data: 12, total_storage_data: 5000, used_storage_data: 600 },
          { date: '2026-06-09T15:00:00Z', ratio_storage_data: 15, total_storage_data: 5000, used_storage_data: 750 }
        ],
        storage_main: [
          { date: '2026-06-09T09:00:00Z', ratio_storage_main: 5, total_storage_main: 1000, used_storage_main: 50 },
          { date: '2026-06-09T12:00:00Z', ratio_storage_main: 6, total_storage_main: 1000, used_storage_main: 60 },
          { date: '2026-06-09T15:00:00Z', ratio_storage_main: 8, total_storage_main: 1000, used_storage_main: 80 }
        ]
      }
    },
    message: 'Success',
  },
  'models': {
    status: 1,
    result: {
      list: [
        {
          id: 'model-1',
          name: 'Llama-3-8B-Instruct',
          description: 'Llama 3 8B Instruction tuned model',
          type: 'HF',
          status: 'Active',
          created_at: '2026-06-09T01:00:00Z',
          updated_at: '2026-06-09T01:00:00Z',
          size: '8.0B',
          format: 'safetensors',
        },
        {
          id: 'model-2',
          name: 'Qwen2-7B-Instruct',
          description: 'Qwen2 7B Instruction tuned model',
          type: 'HF',
          status: 'Active',
          created_at: '2026-06-09T02:00:00Z',
          updated_at: '2026-06-09T02:00:00Z',
          size: '7.0B',
          format: 'safetensors',
        },
        {
          id: 'model-3',
          name: 'External-Custom-Model',
          description: '외부 협력기관 컨테이너 연동 모델',
          type: 'External',
          status: 'Ready',
          created_at: '2026-06-09T03:00:00Z',
          updated_at: '2026-06-09T03:00:00Z',
          size: '13.0B',
          format: 'custom',
        }
      ]
    },
    message: 'Success',
  },
  'playgrounds': {
    status: 1,
    result: {
      list: [
        {
          id: 'pg-1',
          name: 'Llama-3 Playground',
          description: 'Playground for testing Llama 3',
          model_id: 'model-1',
          status: 'Running',
          created_at: '2026-06-09T05:00:00Z',
        }
      ]
    },
    message: 'Success',
  },
  'datasets': {
    status: 1,
    result: {
      list: [
        {
          id: 'ds-1',
          name: 'IMDB Movie Reviews',
          description: 'Dataset for sentiment analysis',
          size: '25 MB',
          format: 'CSV',
          status: 'Ready',
          created_at: '2026-06-09T04:00:00Z',
        },
        {
          id: 'ds-2',
          name: 'Alpaca Cleaned Korean',
          description: 'Korean translation instruction dataset',
          size: '45 MB',
          format: 'JSONL',
          status: 'Ready',
          created_at: '2026-06-09T04:30:00Z',
        }
      ]
    },
    message: 'Success',
  },
  'pipelines': {
    status: 1,
    result: {
      list: [
        {
          id: 'pipe-1',
          name: 'Standard Fine-Tuning Pipeline',
          description: 'VRAM 24G single-GPU training pipeline',
          status: 'Active',
          created_at: '2026-06-09T02:30:00Z',
        }
      ]
    },
    message: 'Success',
  },
  'trainings': {
    status: 1,
    result: {
      list: [
        {
          id: 'train-1',
          name: 'llama-3-lora-fine-tuning',
          model_id: 'model-1',
          dataset_id: 'ds-2',
          epochs: 3,
          learning_rate: '2e-5',
          status: 'Completed',
          created_at: '2026-06-09T06:00:00Z',
        }
      ]
    },
    message: 'Success',
  },
  'external/manifests': {
    status: 1,
    result: [
      {
        name: 'custom-training-manifest',
        versions: [
          {
            manifest_version: 'v1.0.0',
            default_params: {
              batch_size: 8,
              learning_rate: 0.0001,
              epochs: 5,
              optimizer: 'adamw',
            }
          }
        ]
      }
    ],
    message: 'Success',
  },
  'external/jobs': {
    status: 1,
    result: {
      id: 'job-dummy-123',
      name: 'external-job-run',
      status: 'Running',
      namespace: 'jonathan-system',
      manifest: 'custom-training-manifest',
      params: '{"batch_size": 8, "learning_rate": 0.0001, "epochs": 5}',
      created_at: '2026-06-09T07:00:00Z',
    },
    message: 'Success',
  }
};

export const getMockResponse = (url, method, body, params) => {
  if (!url || typeof url !== 'string') {
    return {
      status: 1,
      result: {},
      message: 'Empty or invalid URL',
    };
  }
  // Strip query parameters to match keys
  const cleanUrl = url.split('?')[0];

  // Intercept login requests to support custom credentials
  if (cleanUrl === 'login' || cleanUrl === 'login/force') {
    if (body) {
      const inputUser = body.user_name;
      const decryptedPw = decrypt(body.password);
      
      if (inputUser === 'etri' && decryptedPw === '1234') {
        return {
          status: 1,
          result: {
            logined_session: 'dummy-session-etri',
            user_name: 'etri',
            admin: false,
            token: 'dummy-jwt-token-etri',
            photo_url: '/images/icon/00-ic-info-user.svg',
            jp_user_name: 'ETRI 사용자',
            logined: false,
          },
          message: 'Success',
        };
      } else if (inputUser === 'admin' && decryptedPw === 'tango1234!') {
        return {
          status: 1,
          result: {
            logined_session: 'dummy-session-12345',
            user_name: 'admin',
            admin: true,
            token: 'dummy-jwt-token-xyz',
            photo_url: '/images/icon/00-ic-info-user.svg',
            jp_user_name: '관리자',
            logined: false,
          },
          message: 'Success',
        };
      } else {
        // Incorrect password or user
        return {
          status: 0,
          result: {},
          message: 'Please retry login with correct ID and password.',
        };
      }
    }
  }
  
  // Try clean url match
  if (mockResponses[cleanUrl]) {
    return mockResponses[cleanUrl];
  }
  
  if (cleanUrl.startsWith('storage/') && cleanUrl.endsWith('/workspace')) {
    return {
      status: 1,
      result: {
        share: 0,
        workspace: {
          workspace_size: 5000000000000,
          workspace_used: 1000000000000,
          workspace_avail: 4000000000000,
          workspace_pcent: 20
        }
      },
      message: 'Success'
    };
  }

  // Check parameterized matches (e.g. models/commit-models/1, external/manifests/name)
  if (cleanUrl.startsWith('models/commit-models/')) {
    return {
      status: 1,
      result: {
        commits: [
          { id: 'c1', message: 'Initial model weights', date: '2026-06-09' }
        ]
      },
      message: 'Success'
    };
  }
  
  if (cleanUrl.startsWith('external/manifests/')) {
    return {
      status: 1,
      result: {
        name: decodeURIComponent(cleanUrl.split('/').pop()),
        versions: [
          {
            manifest_version: 'v1.0.0',
            default_params: {
              batch_size: 8,
              learning_rate: 0.0001,
              epochs: 5,
              optimizer: 'adamw',
            }
          }
        ]
      },
      message: 'Success'
    };
  }
  
  // Generic list responses for unmapped lists
  if (cleanUrl.endsWith('s') || cleanUrl.includes('list') || cleanUrl.includes('options')) {
    return {
      status: 1,
      result: { list: [] },
      message: 'Success',
    };
  }

  // Default fallback response
  return {
    status: 1,
    result: {},
    message: 'Mock Success fallback',
  };
};
