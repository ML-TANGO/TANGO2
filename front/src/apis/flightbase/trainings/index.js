import { callApi } from '@src/network';

export const getDatasetList = async (workspace_id) => {
  const res = await callApi({
    url: 'options/preprocessing/dataset',
    method: 'get',
    params: {
      workspace_id,
    },
  });
  return res;
};

// 데이터셋 안의 파일 목록.
//
// SDS 레시피의 `data_path` 선택기에서 쓴다: 데이터셋마다 파일명이 달라
// (`sds_train_ko.json` / `sds_train_ko_9k.json` / `sds_valid_ko_1k.json`) 경로를
// 접두사 치환으로 맞출 수 없기 때문에, 실제 존재하는 파일을 골라야 한다.
//
// `extension` 을 주면 BE 가 평면 목록으로 돌려준다 — 계층 응답은 디렉터리당 500개 cap 이
// 정렬 전에 걸려서, 최상위 항목이 많은 데이터셋(sds_eval 등)에선 정작 찾는 json 이 cap
// 밖으로 밀려 안 나온다. 그래서 이 선택기는 항상 확장자를 지정해 부른다.
export const getDatasetDataList = async (
  dataset_id,
  { search, extension } = {},
) => {
  const res = await callApi({
    url: 'options/preprocessing/data',
    method: 'get',
    params: {
      dataset_id,
      ...(search ? { search } : {}),
      ...(extension ? { extension } : {}),
    },
  });
  return res;
};
