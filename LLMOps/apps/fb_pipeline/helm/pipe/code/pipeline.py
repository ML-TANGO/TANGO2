import asyncio
import json
import logging
import os
import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
import aiohttp
import redis_con
import db
import settings

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)


def _parse_cfg(raw) -> Dict:
    """built_in_params(JSON str) → dict. None/""/"null"/비-dict 는 {} 로 강제.
    (codex MED: built_in_params=null → "null" 저장 시 json.loads→None→.get 크래시 방지)"""
    if not raw:
        return {}
    try:
        v = json.loads(raw)
    except Exception:
        return {}
    return v if isinstance(v, dict) else {}


@dataclass
class TaskInfo:
    id: int
    task_type: str
    task_item_id: int
    task_item_type: str
    dataset_id: int
    dataset_data_path: str
    gpu_count: int
    built_in_params: str
    run_code: Optional[str] = None
    parameter: Optional[Dict] = None
    image_id: Optional[int] = None
    project_training_type: Optional[str] = None
    pipeline_id: Optional[int] = None
    status: Optional[str] = None
    start_datetime: Optional[str] = None
    end_datetime: Optional[str] = None
    task_item_job_id: Optional[int] = None
    task_item_job_str_id: Optional[str] = None
    x_index: Optional[int] = 0
    y_index: Optional[int] = 0
    x_position: Optional[int] = 0

    def __post_init__(self):
        # 추가 필드 처리를 위한 메서드
        pass

class HTTPClient:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def post(self, url: str, data: Dict) -> Dict:
        if not self.session:
            await self.initialize()
        async with self.session.post(url, json=data) as response:
            response.raise_for_status()
            return await response.json()

    async def get(self, url: str, data: Optional[Dict] = None) -> Dict:
        if not self.session:
            await self.initialize()
        async with self.session.get(url, json=data) as response:
            response.raise_for_status()
            return await response.json()

class TaskExecutor:
    def __init__(self, http_client: HTTPClient, redis_client: Any):
        self.http_client = http_client
        self.redis_client = redis_client

    async def initialize(self):
        await self.http_client.initialize()

    async def close(self):
        await self.http_client.close()

    async def execute_preprocessing(self, task_info: TaskInfo) -> None:
        logger.info(f"Preprocessing {task_info.task_item_id} 실행")
        
        data = self._prepare_preprocessing_data(task_info)
        url = f"http://{settings.PREPROCESSING_DNS}/api/preprocessing/jobs/pipeline/run"
        
        try:
            res = await self.http_client.post(url=url, data=data)
            job_id = res["result"]
            
            if job_id is None:
                raise ValueError("job_id is None")
                
            logger.info(f"전처리기 id: {job_id}")
            db.update_pipeline_task(task_id=task_info.id, task_item_job_id=job_id)
            
            await self._wait_for_preprocessing_completion(job_id, task_info.id)
            
        except Exception as e:
            logger.error(f"Preprocessing error: {str(e)}")
            raise

    async def execute_project(self, task_info: TaskInfo) -> None:
        logger.info(f"Project {task_info.task_item_id} 실행")
        
        data = self._prepare_project_data(task_info)
        url = f"http://{settings.PROJECT_DNS}/api/projects/pipeline/trainings"
        
        try:
            res = await self.http_client.post(url=url, data=data)
            training_id = res["result"]
            
            if training_id is None:
                raise ValueError("training_id is None")
                
            logger.info(f"학습 id: {training_id}")
            db.update_pipeline_task(task_id=task_info.id, task_item_job_id=training_id)
            
            await self._wait_for_training_completion(training_id, task_info.id)
            
        except Exception as e:
            logger.error(f"Project error: {str(e)}")
            raise

    async def execute_deployment(self, task_info: TaskInfo) -> None:
        logger.info(f"Deployment {task_info.task_item_id} 실행")
        
        deployment_workers = db.get_deployment_workers(deployment_id=task_info.task_item_id)
        data = {
            "deployment_id": task_info.task_item_id,
            "create_user_name": settings.OWNER_NAME,
        }
        
        url = f"http://{settings.DEPLOYMENT_DNS}/api/deployments/pipeline/worker"
        
        try:
            res = await self.http_client.post(url=url, data=data)
            worker_id = res["result"]["worker_id"]
            
            if worker_id is None:
                raise ValueError("worker_id is None")
                
            logger.info(f"배포 id: {worker_id}")
            db.update_pipeline_task(task_id=task_info.id, task_item_job_id=worker_id)
            
            await self._wait_for_deployment_completion(worker_id, task_info, deployment_workers)
            
        except Exception as e:
            logger.error(f"Deployment error: {str(e)}")
            raise

    async def execute_generation(self, task_info: TaskInfo) -> None:
        """생성형 데이터 파이프라인 노드 — 고려대 LLM1/LLM2 = external_container
        generate job. fb_external_container 의 POST /api/v1/jobs 로 launch 후
        GET /api/v1/jobs/{id} 폴링. (WBS 1.1 / v0.4 3.3)"""
        logger.info(f"Generation {task_info.task_item_id} 실행")

        data = self._prepare_generation_data(task_info)
        url = f"http://{settings.EXTERNAL_CONTAINER_DNS}/api/v1/jobs"

        try:
            res = await self.http_client.post(url=url, data=data)
            job_id = res.get("job_id")

            if not job_id:
                raise ValueError("job_id is None")

            logger.info(f"생성 job id: {job_id}")
            # external job_id 는 문자열(uuid 계열) — INT 컬럼 대신 str 컬럼에 저장.
            db.update_pipeline_task_str(task_id=task_info.id, task_item_job_str_id=job_id)

            await self._wait_for_external_job(job_id, task_info.id, "Generation")

        except Exception as e:
            logger.error(f"Generation error: {str(e)}")
            raise

    # ── GenAI 통합 파이프라인 신규 task_type (finetuning / quantize / llm_deploy) ──
    async def execute_finetuning(self, task_info: TaskInfo) -> None:
        """LLM 파인튜닝 노드. built_in_params.mode 로 분기.
        - external(기본, SDS 등): fb_external_container train job (generation 과 동형).
        - internal: llm_model `/api/models/fine-tuning/run` (폴링은 모델 FT status — 후속)."""
        logger.info(f"Finetuning {task_info.task_item_id} 실행")
        cfg = _parse_cfg(task_info.built_in_params)
        mode = (cfg.get("mode") or "external").lower()

        if mode == "internal":
            # 내부 FT — llm_model `/api/models/fine-tuning/run` (get_auth 없음 → s2s OK, quantize 동형).
            # running_fine_tuning 은 pod 기동 후 True 반환(job_id 없음)이며, 반환 전
            # update_model_fine_tuning_status(PENDING) 를 동기 호출 → 상태가 즉시 pending 으로
            # 세팅되어 stale("done") 레이스 없음. 진행 상태는 llm_db model.latest_fine_tuning_status 폴링.
            data = self._prepare_finetuning_internal_data(task_info, cfg)
            url = f"http://{settings.LLM_MODEL_DNS}/api/models/fine-tuning/run"
            try:
                res = await self.http_client.post(url=url, data=data)
                # response 엔벨로프: status 1(정상)/0(비정상).
                if not isinstance(res, dict) or res.get("status") != 1:
                    raise ValueError(f"internal finetuning run failed: {res!r}")
                logger.info(f"내부 파인튜닝 시작: model {task_info.task_item_id}")
                # running_fine_tuning 은 job_id 없이 True 반환(Kafka dispatch) → 파이프라인 task 의
                # job 참조로 model_id 저장(운영 가시성 + 모델 FT 페이지 연결, code review HIGH).
                db.update_pipeline_task(task_id=task_info.id, task_item_job_id=task_info.task_item_id)
                await self._wait_for_internal_ft(
                    task_info.task_item_id, task_info.id, "Finetuning(internal)"
                )
            except Exception as e:
                logger.error(f"Internal finetuning error: {str(e)}")
                raise
            return

        # external (SDS 등) — external_container train job. job_type 은 manifest 가 가짐.
        data = self._prepare_finetuning_data(task_info, cfg)
        url = f"http://{settings.EXTERNAL_CONTAINER_DNS}/api/v1/jobs"
        try:
            res = await self.http_client.post(url=url, data=data)
            job_id = res.get("job_id")
            if not job_id:
                raise ValueError("finetuning job_id is None")
            logger.info(f"파인튜닝 job id: {job_id}")
            db.update_pipeline_task_str(task_id=task_info.id, task_item_job_str_id=job_id)
            await self._wait_for_external_job(job_id, task_info.id, "Finetuning")
        except Exception as e:
            logger.error(f"Finetuning error: {str(e)}")
            raise

    def _prepare_finetuning_data(self, task_info: TaskInfo, cfg: Dict) -> Dict:
        # built_in_params 예: {"mode":"external","manifest_name":"eva-vlm-train",
        #  "manifest_version":"1.0.0-acryl-patched-v7","params":{...},"output_subdir":"<선택>"}
        # params 에 _base_model/_dataset 등 예약키 포함 가능(FE 가 해석해 채움).
        body = {
            "manifest_name": cfg.get("manifest_name"),
            "manifest_version": cfg.get("manifest_version"),
            "workspace_id": int(settings.WORKSPACE_ID),
            "params": cfg.get("params", {}),
            "platform_model_id": task_info.task_item_id,
            "output_subdir": cfg.get("output_subdir")
                or f"finetuning/pipeline-{settings.PIPELINE_ID}-{task_info.id}",
        }
        if task_info.gpu_count:
            body["gpu_count"] = task_info.gpu_count
        return body

    def _prepare_finetuning_internal_data(self, task_info: TaskInfo, cfg: Dict) -> Dict:
        # 내부 FT body = PostFineTuningRun(model_id/model_dataset_id/instance_id/
        # instance_count/gpu_count/fine_tuning_config). built_in_params 예:
        # {"mode":"internal","model_dataset_id":N,"instance_id":N,"instance_count":1,
        #  "gpu_count":1,"fine_tuning_config":{...부분 가능, 누락키는 BE 기본값}}
        body = {
            "model_id": task_info.task_item_id,
            "model_dataset_id": cfg.get("model_dataset_id"),
            "instance_id": cfg.get("instance_id"),
            "instance_count": cfg.get("instance_count") or 1,
            "gpu_count": task_info.gpu_count or cfg.get("gpu_count") or 1,
        }
        ft_cfg = cfg.get("fine_tuning_config")
        if isinstance(ft_cfg, dict) and ft_cfg:
            body["fine_tuning_config"] = ft_cfg
        return body

    async def _wait_for_internal_ft(self, model_id: int, task_id: int, label: str = "Finetuning") -> None:
        # 내부 FT 상태 = llm_model `GET /api/models/{id}/fine-tuning/status` (s2s, get_auth 없음).
        # 런타임은 llm_db 직접 접근 불가(utils 미존재) → HTTP 폴링(다른 노드와 동일 설계).
        # status: pending→running→done/stop/error. done=성공 / stop·error=실패.
        # 시작 직후 status=pending 동기 세팅(running_fine_tuning) → stale done 오탐 없음.
        # external job 폴러와 동형(2s 간격, 연속실패 상한 60 ~120s).
        url = f"http://{settings.LLM_MODEL_DNS}/api/models/{model_id}/fine-tuning/status"
        in_progress = ("pending", "running", "installing")
        consecutive_failures = 0
        max_consecutive_failures = 60
        while True:
            await asyncio.sleep(2)
            try:
                res = await self.http_client.get(url=url)
                # 엔벨로프 status==1 일 때만 유효. {status:0,result:null}(서버에러)/None/미지 상태는
                # 카운터 리셋하지 않고 실패로 누적 → 무한 폴 방지(codex MED).
                ok = isinstance(res, dict) and res.get("status") == 1
                ft_status = (res.get("result") or {}).get("status") if ok else None
                if ft_status in ("error", "stop"):
                    raise RuntimeError(f"{label} model {model_id} status={ft_status}")
                if ft_status == "done":
                    db.update_pipeline_task_end(task_id=task_id)
                    break
                if ft_status in in_progress:
                    consecutive_failures = 0  # 유효 진행 상태
                else:
                    consecutive_failures += 1  # bad 엔벨로프/None/미지 상태
                    logger.warning(f"{label} unexpected status poll (status={ft_status!r}, {consecutive_failures}/{max_consecutive_failures})")
                    if consecutive_failures >= max_consecutive_failures:
                        raise RuntimeError(f"{label} model {model_id} status unresolved after {consecutive_failures} attempts")
            except RuntimeError:
                raise
            except Exception as e:
                consecutive_failures += 1
                logger.warning(f"{label} status check failed ({consecutive_failures}/{max_consecutive_failures}): {str(e)}")
                if consecutive_failures >= max_consecutive_failures:
                    raise RuntimeError(f"{label} model {model_id} status unreachable after {consecutive_failures} attempts")

    async def execute_quantize(self, task_info: TaskInfo) -> None:
        """양자화 노드 — llm_model `/api/models/{id}/quantize` 가 convert 외부 job 을
        띄우고 job_id 반환 → external_container `/jobs/{id}` 폴링 (GGUF 포팅, SP-4)."""
        logger.info(f"Quantize {task_info.task_item_id} 실행")
        cfg = _parse_cfg(task_info.built_in_params)
        model_id = task_info.task_item_id
        body = {"target_quant": cfg.get("target_quant", "Q4_K_M")}
        if cfg.get("target_device"):
            body["target_device"] = cfg["target_device"]
        if cfg.get("prune"):
            body["prune"] = bool(cfg["prune"])
        url = f"http://{settings.LLM_MODEL_DNS}/api/models/{model_id}/quantize"
        try:
            res = await self.http_client.post(url=url, data=body)
            job_id = (res.get("result") or {}).get("job_id") or res.get("job_id")
            if not job_id:
                raise ValueError(f"quantize job_id is None: {res!r}")
            logger.info(f"양자화 job id: {job_id}")
            db.update_pipeline_task_str(task_id=task_info.id, task_item_job_str_id=job_id)
            await self._wait_for_external_job(job_id, task_info.id, "Quantize")
        except Exception as e:
            logger.error(f"Quantize error: {str(e)}")
            raise

    async def execute_llm_deploy(self, task_info: TaskInfo) -> None:
        """LLM 배포 노드 — built_in_params.deploy_target 로 분기.
        - cluster(=Playground 배포): 🔵 미배선(spec #4, Playground 배포 계약 확정 필요).
        - edge(타겟 디바이스, SP-6): fb_resource `/api/edge/workers/{id}/deploy` (admin 게이트 →
          전용 /pipeline s2s 엔드포인트가 정석. P3)."""
        logger.info(f"LLM deploy {task_info.task_item_id} 실행")
        cfg = _parse_cfg(task_info.built_in_params)
        target = (cfg.get("deploy_target") or "cluster").lower()
        if target == "cluster":
            raise NotImplementedError(
                "cluster(Playground) deploy not yet wired (spec #4 — Playground 배포 계약 확정 필요)"
            )
        if target == "edge":
            raise NotImplementedError(
                "edge deploy in pipeline = P3 (admin-gated /workers/{id}/deploy → "
                "needs /pipeline s2s endpoint + quantize 산출 GGUF 전제)"
            )
        raise ValueError(f"unknown deploy_target: {target}")

    def _prepare_generation_data(self, task_info: TaskInfo) -> Dict:
        # built_in_params(JSON) 에 외부 컨테이너 manifest 참조 + 생성 파라미터.
        # 예: {"manifest_name":"mock-generate","manifest_version":"1.0.0",
        #      "params":{<생성/메타프롬프트>},"output_subdir":"<선택>"}
        cfg = _parse_cfg(task_info.built_in_params)
        body = {
            "manifest_name": cfg.get("manifest_name"),
            "manifest_version": cfg.get("manifest_version"),
            "workspace_id": int(settings.WORKSPACE_ID),
            "params": cfg.get("params", {}),
            "output_subdir": cfg.get("output_subdir")
                or f"generation/pipeline-{settings.PIPELINE_ID}-{task_info.id}",
        }
        # gpu_count 0 이면 manifest.resources 기본값 사용(키 생략).
        if task_info.gpu_count:
            body["gpu_count"] = task_info.gpu_count
        return body

    async def _wait_for_external_job(self, job_id: str, task_id: int, label: str = "Job") -> None:
        # fb_external_container 가 GET /api/v1/jobs/{id} 로 상태 노출.
        # result.status = canonical(pending/running/completed/failed/cancelled,
        # normalize/status.py). 폴링 패턴은 training/preprocessing 과 동형.
        # generation/finetuning(external)/quantize 가 공유(전부 external_container job).
        # ⚠️ fb_external_container 의 JobTracker 는 in-memory(SP-Ext.3 전) — 서비스
        # 재시작 시 job 소실 → GET 404. 무한 hang 방지 위해 연속 실패 상한 적용
        # (SP-Ext.4 poll_consecutive_fail 선례). 일시 네트워크 오류는 카운터 리셋으로 흡수.
        url = f"http://{settings.EXTERNAL_CONTAINER_DNS}/api/v1/jobs/{job_id}"
        consecutive_failures = 0
        max_consecutive_failures = 60  # ~120s (2s 간격)
        while True:
            try:
                detail = await self.http_client.get(url=url)
                status = (detail.get("result") or {}).get("status")
                consecutive_failures = 0
                if status in ("failed", "cancelled"):
                    raise RuntimeError(f"{label} job {job_id} status={status}")
                if status == "completed":
                    db.update_pipeline_task_end(task_id=task_id)
                    break
            except RuntimeError:
                raise
            except Exception as e:
                consecutive_failures += 1
                logger.warning(f"{label} status check failed ({consecutive_failures}/{max_consecutive_failures}): {str(e)}")
                if consecutive_failures >= max_consecutive_failures:
                    raise RuntimeError(f"{label} job {job_id} unreachable after {consecutive_failures} attempts")
            await asyncio.sleep(2)

    def _prepare_preprocessing_data(self, task_info: TaskInfo) -> Dict:
        if task_info.task_item_type == "advanced":
            return {
                "preprocessing_id": task_info.task_item_id,
                "dataset_id": task_info.dataset_id,
                "image_id": task_info.image_id,
                "job_name": f"pipeline_data-{settings.PIPELINE_ID}-{task_info.id}",
                "run_code": task_info.run_code,
                "parameter": task_info.parameter,
                "gpu_count": task_info.gpu_count,
                "create_user_name": settings.OWNER_NAME,
                "get_job_id": 1
            }
        else:
            return {
                "preprocessing_id": task_info.task_item_id,
                "job_name": f"pipeline_data-{settings.PIPELINE_ID}-{task_info.id}",
                "dataset_id": task_info.dataset_id,
                "dataset_data_path": task_info.dataset_data_path,
                "built_in_param": json.loads(task_info.built_in_params),
                "create_user_name": settings.OWNER_NAME,
                "get_job_id": 1
            }

    def _prepare_project_data(self, task_info: TaskInfo) -> Dict:
        if task_info.task_item_type == "advanced":
            return {
                "project_id": task_info.task_item_id,
                "dataset_id": task_info.dataset_id,
                "image_id": task_info.image_id,
                "training_name": f"pipeline-{settings.PIPELINE_ID}-{task_info.id}",
                "run_code": task_info.run_code,
                "parameter": task_info.parameter,
                "gpu_count": task_info.gpu_count,
                "create_user_name": settings.OWNER_NAME,
                "get_training_id": True
            }
        else:
            return {
                "project_id": task_info.task_item_id,
                "training_name": f"pipeline-{settings.PIPELINE_ID}-{task_info.id}",
                "dataset_id": task_info.dataset_id,
                "dataset_data_path": task_info.dataset_data_path,
                "gpu_count": task_info.gpu_count,
                "gpu_cluster_auto": task_info.gpu_count > 1,
                "gpu_auto_select": {},
                "gpu_cluster_case_old": [],
                "built_in_param": json.loads(task_info.built_in_params),
                "create_user_name": settings.OWNER_NAME,
                "get_training_id": True
            }

    async def _wait_for_preprocessing_completion(self, job_id: int, task_id: int) -> None:
        while True:
            job_info = db.get_preprocessing_job_id(job_id=job_id)
            if job_info["end_status"] == "error":
                raise RuntimeError("Preprocessing pod error")
            if job_info["end_status"] == "done":
                db.update_pipeline_task_end(task_id=task_id)
                break
            await asyncio.sleep(1)

    async def _wait_for_training_completion(self, training_id: int, task_id: int) -> None:
        while True:
            try:
                training_info = db.get_training(training_id=training_id)
                if training_info["end_status"] == "error":
                    raise RuntimeError(f"Training pod error {training_id}")
                if training_info["end_status"] == "done":
                    db.update_pipeline_task_end(task_id=task_id)
                    break
            except Exception as e:
                logger.warning(f"Training status check failed: {str(e)}")
            await asyncio.sleep(1)

    async def _wait_for_deployment_completion(self, worker_id: int, task_info: TaskInfo, deployment_workers: List[Dict]) -> None:
        while True:
            workspace_pod_status = self.redis_client.hget("pod:workspace:status", settings.WORKSPACE_ID)
            if workspace_pod_status is None:
                workspace_pod_status = {}
            else:
                workspace_pod_status = json.loads(workspace_pod_status)
                
            worker_pod_status = workspace_pod_status.get("deployment", {}).get(str(task_info.task_item_id), {}).get(str(worker_id), {})
            
            if worker_pod_status.get("status") == "running":
                await self._cleanup_old_workers(deployment_workers)
                db.update_pipeline_task_end(task_id=task_info.id)
                break
                
            await asyncio.sleep(1)

    async def _cleanup_old_workers(self, deployment_workers: List[Dict]) -> None:
        for worker in deployment_workers:
            worker_id = worker["id"]
            url = f"http://{settings.DEPLOYMENT_DNS}/api/deployments/worker/stop?deployment_worker_id={worker_id}"
            try:
                await self.http_client.get(url=url)
            except Exception as e:
                logger.warning(f"Failed to stop worker {worker_id}: {str(e)}")

class Graph:
    def __init__(self):
        self.graph: Dict[str, Dict] = {}
        self.in_degree: Dict[str, int] = defaultdict(int)

    def add_task(self, task_name: str, func: callable, predecessor: Optional[str] = None, **kwargs) -> str:
        if task_name not in self.graph:
            self.graph[task_name] = {'func': lambda: func(**kwargs), 'successors': []}
        else:
            self.graph[task_name]['func'] = lambda: func(**kwargs)
            
        if predecessor:
            if predecessor in self.graph and task_name not in self.graph[predecessor]['successors']:
                self.graph[predecessor]['successors'].append(task_name)
                self.in_degree[task_name] += 1
                logger.info(f"Task {task_name}의 in_degree 증가: {self.in_degree[task_name]} (predecessor: {predecessor})")
            elif predecessor not in self.graph:
                self.graph[predecessor] = {'func': None, 'successors': [task_name]}
                self.in_degree[task_name] += 1
                logger.info(f"Task {task_name}의 in_degree 증가: {self.in_degree[task_name]} (predecessor: {predecessor})")
        else:
            # predecessor가 없는 경우 in_degree를 0으로 설정
            self.in_degree[task_name] = 0
            logger.info(f"Task {task_name}의 in_degree 초기화: 0 (predecessor 없음)")
            
        return task_name

    async def execute_task(self, task_name: str) -> str:
        func = self.graph[task_name]['func']
        if func:
            logger.info(f"Task {task_name} 실행 시작")
            await func()
            logger.info(f"Task {task_name} 실행 완료")
            for successor in self.graph[task_name]['successors']:
                self.in_degree[successor] -= 1
                logger.info(f"Task {successor}의 in_degree 감소: {self.in_degree[successor]} (predecessor {task_name} 완료)")
        return task_name

    async def execute_graph(self) -> None:
        visited: Set[str] = set()
        running_tasks: Set[str] = set()
        completed_tasks: Set[str] = set()
        
        logger.info("그래프 실행 시작")
        logger.info(f"초기 in_degree 상태: {dict(self.in_degree)}")
        
        while True:
            # 실행 가능한 태스크 찾기
            available_tasks = [
                task for task in self.graph 
                if self.in_degree[task] == 0 
                and task not in visited 
                and task not in running_tasks
            ]
            
            logger.info(f"현재 상태 - 방문: {visited}, 실행 중: {running_tasks}, 완료: {completed_tasks}")
            logger.info(f"실행 가능한 태스크: {available_tasks}")
            logger.info(f"현재 in_degree 상태: {dict(self.in_degree)}")
            
            if not available_tasks:
                # 실행 중인 태스크가 없고, 모든 태스크가 완료되었다면 종료
                if not running_tasks and len(completed_tasks) == len(self.in_degree.keys()):
                    logger.info("모든 태스크 실행 완료")
                    break
                # 실행 중인 태스크가 있으면 잠시 대기
                logger.info("실행 가능한 태스크 없음, 대기 중...")
                await asyncio.sleep(1)
                continue
            
            # 실행 가능한 태스크들을 병렬로 실행
            tasks = []
            for task in available_tasks:
                visited.add(task)
                running_tasks.add(task)
                tasks.append(self.execute_task(task))
            
            if tasks:
                logger.info(f"병렬 실행 시작: {available_tasks}")
                # 태스크 실행 완료 대기
                for task in asyncio.as_completed(tasks):
                    completed_task = await task
                    # 실행 완료된 태스크 제거 및 완료 목록에 추가
                    running_tasks.remove(completed_task)
                    completed_tasks.add(completed_task)
                    logger.info(f"태스크 {completed_task} 완료")
                    
                    # 새로운 실행 가능한 태스크가 있는지 즉시 확인
                    new_available_tasks = [
                        task for task in self.graph 
                        if self.in_degree[task] == 0 
                        and task not in visited 
                        and task not in running_tasks
                    ]
                    
                    if new_available_tasks:
                        logger.info(f"새로운 실행 가능한 태스크 발견: {new_available_tasks}")
                        # 새로운 태스크들을 즉시 실행
                        new_tasks = []
                        for task in new_available_tasks:
                            visited.add(task)
                            running_tasks.add(task)
                            new_tasks.append(self.execute_task(task))
                        
                        if new_tasks:
                            logger.info(f"새로운 태스크 병렬 실행 시작: {new_available_tasks}")
                            await asyncio.gather(*new_tasks)
                            # 실행 완료된 태스크 제거 및 완료 목록에 추가
                            for task in new_available_tasks:
                                running_tasks.remove(task)
                                completed_tasks.add(task)
                            logger.info(f"새로운 태스크 병렬 실행 완료: {new_available_tasks}")
                
                logger.info(f"병렬 실행 완료: {available_tasks}")
                
                # 태스크 완료 후 in_degree 상태 로깅
                logger.info(f"태스크 완료 후 in_degree 상태: {dict(self.in_degree)}")

class Pipeline:
    def __init__(self):
        self.redis_client = redis_con.get_redis_client()
        self.http_client = HTTPClient()
        self.task_executor = TaskExecutor(self.http_client, self.redis_client)

    async def initialize(self):
        await self.task_executor.initialize()

    async def close(self):
        await self.task_executor.close()

    async def execute_task(self, task_id: int, task_type: str) -> None:
        logger.info(f"Task {task_id} 실행")
        logger.info(f"{task_type} 실행")
        
        task_info = db.get_pipeline_task(task_id=task_id)
        task_info_obj = TaskInfo(**task_info)
        
        if task_type == "project":
            await self.task_executor.execute_project(task_info_obj)
        elif task_type == "preprocessing":
            await self.task_executor.execute_preprocessing(task_info_obj)
        elif task_type == "deployment":
            await self.task_executor.execute_deployment(task_info_obj)
        elif task_type == "generation":
            await self.task_executor.execute_generation(task_info_obj)
        elif task_type == "finetuning":
            await self.task_executor.execute_finetuning(task_info_obj)
        elif task_type == "quantize":
            await self.task_executor.execute_quantize(task_info_obj)
        elif task_type == "llm_deploy":
            await self.task_executor.execute_llm_deploy(task_info_obj)
        else:
            # 알 수 없는 task_type 이 조용히 no-op→"완료" 처리되어 후속 노드가
            # 진행되는 silent skip 방지(code-review C-1). DTO Literal 게이트가
            # 1차 방어이나, DB graph 손상/오타/미배선 타입을 런타임에서도 차단.
            raise ValueError(f"Unknown task_type: {task_type!r}")

    async def run(self) -> None:
        try:
            await self.initialize()
            pipeline_id = settings.PIPELINE_ID
            while True:
                before_total_size = self._get_total_size("/dataset")
                logger.info(f"파이프라인 시작 전 총 크기: {before_total_size} 바이트")
                
                db.update_pipeline_start(pipeline_id=pipeline_id, dataset_size=before_total_size)
                db.update_pipeline_task_reset(pipeline_id)
                
                pipeline_info = db.get_pipeline(pipeline_id)
                pipe_graph = json.loads(pipeline_info.get("graph", "{}"))
                logger.info(f"pipe_graph : {pipe_graph}")
                G = Graph()
                for key, values in pipe_graph.items():
                    if not values["predecessors"]:
                        G.add_task(
                            task_name=key,
                            func=self.execute_task,
                            task_id=int(key),
                            task_type=values["task_type"]
                        )
                    else:
                        for predecessor in values["predecessors"]:
                            G.add_task(
                                task_name=key,
                                predecessor=predecessor,
                                func=self.execute_task,
                                task_id=int(key),
                                task_type=values["task_type"]
                            )
                logger.info(f"graph : {G.graph}")
                await G.execute_graph()
                
                if not pipeline_info["retraining_type"]:
                    after_total_size = self._get_total_size("/dataset")
                    increase_size = after_total_size - before_total_size
                    
                    db.update_pipeline_history_done(
                        pipeline_history_id=pipeline_info["latest_history_id"],
                        increase_dataset_size=increase_size,
                        retraining_count=pipeline_info["retraining_count"]
                    )
                    db.update_pipeline_done(pipeline_id=pipeline_id)
                    logger.info("재학습 설정이 되어 있지 않아 종료합니다.")
                    return
                
                retraining_count = pipeline_info["retraining_count"]
                logger.info(f"End {retraining_count} cycle of pipeline")
                
                db.update_pipeline_retraining(pipeline_id=pipeline_id)
                
                await self._wait_for_retraining(pipeline_info, before_total_size)
                
        except Exception as e:
            logger.error(f"Pipeline error: {str(e)}")
            db.update_pipeline_done(pipeline_id=pipeline_id)
            db.update_pipeline_history_error(
                pipeline_history_id=pipeline_info["latest_history_id"],
                retraining_count=pipeline_info["retraining_count"],
                increase_dataset_size=0
            )
            raise
        finally:
            await self.close()

    def _get_total_size(self, path: str) -> int:
        total_size = 0
        for dirpath, _, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if not os.path.islink(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size

    async def _wait_for_retraining(self, pipeline_info: Dict, before_total_size: int) -> None:
        logger.info("재학습 대기.")
        
        if pipeline_info["retraining_type"] == "data":
            while True:
                after_total_size = self._get_total_size("/dataset")
                increase_size = after_total_size - before_total_size
                logger.info(f"증가한 용량: {increase_size}")
                
                retraining_data_size = self._to_bytes(
                    value=pipeline_info["retraining_value"],
                    unit=pipeline_info["retraining_unit"]
                )
                
                if increase_size >= retraining_data_size:
                    break
                    
                await asyncio.sleep(3)
        else:
            wait_time = self._convert_to_seconds(
                value=pipeline_info["retraining_value"],
                unit=pipeline_info["retraining_unit"]
            )
            logger.info(f"{wait_time} 초 대기.")
            await asyncio.sleep(wait_time)
            logger.info("대기가 완료되었습니다.")

    @staticmethod
    def _to_bytes(value: float, unit: str) -> int:
        unit = unit.upper()
        units_in_bytes = {
            'TB': 1024 ** 4,
            'GB': 1024 ** 3,
            'MB': 1024 ** 2,
            'KB': 1024
        }
        if unit in units_in_bytes:
            return int(value * units_in_bytes[unit])
        elif unit == 'B':
            return int(value)
        else:
            raise ValueError(f"Invalid unit: {unit}")

    @staticmethod
    def _convert_to_seconds(value: float, unit: str) -> float:
        unit = unit.lower()
        if unit == 'minutes':
            return value * 60
        elif unit == 'hours':
            return value * 3600
        elif unit == 'seconds':
            return value
        else:
            raise ValueError(f"Invalid unit: {unit}")

async def main():
    pipeline = Pipeline()
    try:
        await pipeline.run()
    finally:
        await pipeline.close()

if __name__ == "__main__":
    asyncio.run(main())