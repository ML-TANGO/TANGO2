"""llm_evaluation 라우터 (벤치마크 — reference/judge, 전문가, 추론 러너).
플랫폼 envelope response() 준수."""
import traceback

from fastapi import APIRouter, Header
from fastapi.responses import FileResponse, Response

from utils.resource import response

import evaluation.dto as dto
import evaluation.service as svc

evaluations = APIRouter(prefix="/evaluations")

TAG = ["EVALUATION"]


@evaluations.post("/projects", summary="평가 프로젝트 생성(대기)", tags=TAG)
async def create_project(body: dto.EvalProjectCreateBody,
                         jf_user: str = Header(default=None, alias="jf-User")):
    """유형·이름·워크스페이스만 고정(2026-08-24 — 모델·데이터셋은 런이 고른다),
    status='created'(run 0개, P5). creator=jf-User 헤더."""
    try:
        res = await svc.create_project(
            name=body.name, eval_type=body.eval_type,
            workspace_id=body.workspace_id, creator=jf_user,
            description=body.description)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/projects", summary="평가 프로젝트 목록(워크스페이스)", tags=TAG)
async def list_projects(workspace_id: int):
    """목록 프로젝트마다 최근 run 활동 기준 update_datetime 을 additive 로 제공한다."""
    try:
        res = await svc.list_projects(workspace_id=workspace_id)
        # 기존 envelope 는 유지하고 result 내부의 신규 필드 계약만 경계에서 검증한다.
        dto.EvalProjectListResult.model_validate(res)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/projects/{project_id}", summary="평가 프로젝트 상세(+run 목록)", tags=TAG)
async def get_project(project_id: int):
    try:
        res = await svc.get_project(project_id=project_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/projects/{project_id}/compare", summary="프로젝트 내 run 비교", tags=TAG)
async def compare_project_runs(project_id: int):
    try:
        res = await svc.compare_project_runs(project_id=project_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.put("/projects/{project_id}", summary="평가 프로젝트 설명 수정", tags=TAG)
async def update_project(project_id: int, body: dto.EvalProjectUpdateBody):
    """설명만 고친다(이름·유형·워크스페이스는 정체성이라 생성 후 고정).

    PATCH 가 아니라 PUT 인 이유는 의미론이 아니라 **관행**이다 — 이 모노레포의 수정
    엔드포인트는 전부 PUT 이고(배포 설명 수정 playgrounds.put("/description") 포함)
    PATCH 는 한 곳도 없다. 혼자 PATCH 를 쓰면 게이트웨이·클라이언트 레이어에서 이
    경로만 다른 취급을 받게 된다. 경로는 이 라우터의 프로젝트 단건 규약을 따른다
    (GET/DELETE /projects/{project_id} 와 같은 자리).

    없는 프로젝트는 service 가 사유와 함께 올리고 envelope message 로 나간다."""
    try:
        res = await svc.update_project(project_id=project_id, description=body.description)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.delete("/projects/{project_id}", summary="평가 프로젝트 삭제", tags=TAG)
async def delete_project(project_id: int):
    try:
        res = await svc.delete_project(project_id=project_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.post("/benchmark", summary="벤치마크 평가 런 생성(reference/judge 공용)", tags=TAG)
async def run_benchmark(body: dto.BenchmarkRunBody):
    """정답 대조(reference)와 LLM 심사(judge) 두 프로젝트 유형이 이 엔드포인트를 공유한다
    — 런치 경로가 같고 다른 것은 채점 주체뿐이다. 고른 벤치마크가 프로젝트 유형과 같은
    축인지는 service 가 대조해 거절한다."""
    try:
        # 검증된 모델 → 서비스는 순수 문자열 목록으로 받는다(dto 의존 분리, 기존 패턴).
        # 요청은 두 shape("logickor" / {"benchmark": "logickor"})를 다 보낼 수 있고,
        # 옛 요청의 metric 키는 여기서 흡수돼 서비스에 도달하지 않는다.
        benchmarks = ([b if isinstance(b, str) else b.benchmark
                       for b in body.benchmarks] if body.benchmarks else None)
        # 실채점 컨테이너 실행 옵션 — dto 가 이미 타입·범위·문자셋을 강제했다. 미지정
        # 필드는 빼서 넘긴다(컨테이너 기본값을 그대로 쓰게 하고, 우리가 기본값을 두 곳에
        # 복제하지 않는다).
        run_options = {k: v for k, v in (
            ("generate_model_len", body.generate_model_len),
            ("strategy", body.strategy),
            ("judge_model", body.judge_model),
            ("judge_model_len", body.judge_model_len),
            ("judge_max_output_tokens", body.judge_max_output_tokens),
        ) if v is not None}
        res = await svc.run_benchmark(
            project_id=body.project_id,
            model_id=body.model_id, dataset_ids=body.dataset_ids,
            benchmarks=benchmarks,
            inference_playground_id=body.inference_playground_id,
            judge_playground_id=body.judge_playground_id,
            run_options=run_options or None)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.post("/inference", summary="평가 추론 러너(generate) 런 생성", tags=TAG)
async def run_eval_inference(body: dto.EvalInferenceRunBody,
                             jf_user: str = Header(default=None, alias="jf-User")):
    """평가가 대상 모델 인스턴스를 확보(running 배포 재사용 or 전용 할당)해 데이터셋 전량 batch
    추론 → _samples + _gen_system_prompt 영속(채점은 후속). 즉시 job_id 반환. 전용 할당 시
    jf-User(트리거 유저)를 배포 소유자로 사용(없으면 project.creator).
    ⚠️ P1 WIP(잔여 지적 有) — 단, '배포 소유권 검증'은 2026-08-27 해소됐다: 재사용 경로
    (inference_playground_id)의 배포가 런의 워크스페이스 것인지 service 가 대조·거절한다."""
    try:
        res = await svc.run_eval_inference(
            project_id=body.project_id,
            model_id=body.model_id, dataset_ids=body.dataset_ids,
            system_prompt=body.system_prompt,
            inference_playground_id=body.inference_playground_id,
            instance_id=body.instance_id, instance_count=body.instance_count,
            gpu_count=body.gpu_count, commit_id=body.commit_id, user_name=jf_user)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/benchmark/judge-models", summary="LogicKor 심판 후보 목록", tags=TAG)
async def list_benchmark_judge_models():
    # ⚠️ 이 라우트는 아래 "/{model_id}/results" 류보다 **먼저** 등록돼야 한다. 뒤에 두면
    #    'benchmark' 가 {model_id} 로 잡혀 int 파싱 422 가 난다(FastAPI 는 등록 순서로 매칭).
    try:
        res = await svc.list_benchmark_judge_models()
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.post("/expert", summary="전문가 평가 세션 시작", tags=TAG)
async def start_expert(body: dto.ExpertStartBody):
    try:
        res = await svc.start_expert(
            project_id=body.project_id,
            model_id=body.model_id, dataset_ids=body.dataset_ids,
            inference_playground_id=body.inference_playground_id,
            inference_job_id=body.inference_job_id,
            sample_limit=body.sample_limit,
            run_name=body.run_name,
            expert_prompt=body.expert_prompt)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/compare", summary="교차모델 비교(전역 best-per-metric)", tags=TAG)
async def compare_models(model_ids: str = ""):
    """model_ids=1,2,3 (콤마구분). 1 세그먼트라 /{model_id}/... param 경로와 충돌 X 지만
    명시 GET 들 앞에 두어 라우팅 의도를 분명히 한다."""
    try:
        ids = []
        for tok in model_ids.split(","):
            tok = tok.strip()
            if tok:
                ids.append(int(tok))    # 비정수 토큰 → ValueError → 422 대신 envelope 0
        res = await svc.compare_models(model_ids=ids)
        return response(status=1, result=res)
    except ValueError as e:
        return response(status=0, message=str(e), result=None)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/runs", summary="비교 후보 런 목록(워크스페이스)", tags=TAG)
async def list_comparable_runs(workspace_id: int):
    """런 단위 비교 피커의 후보 목록. 채점 런만(생성 런 제외) 최신순 + 런 출처 4필드."""
    try:
        res = await svc.list_comparable_runs(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/compare-runs", summary="런 단위 비교(선택 런 간 best-per-metric)", tags=TAG)
async def compare_runs(workspace_id: int, run_ids: str = ""):
    """run_ids=1,2,3 (콤마구분) — /compare 의 model_ids 와 같은 파싱 규칙.
    ⚠️ workspace_id 는 필수 쿼리 파라미터다(런 id 를 직접 받는 경로의 authZ 경계).
    데이터셋이 섞였는지는 막지 않고 dataset_consistent 로 실어 보낸다(화면이 경고)."""
    try:
        ids = []
        for tok in run_ids.split(","):
            tok = tok.strip()
            if tok:
                ids.append(int(tok))    # 비정수 토큰 → ValueError → 422 대신 envelope 0
        res = await svc.compare_runs(workspace_id=workspace_id, run_ids=ids)
        return response(status=1, result=res)
    except ValueError as e:
        return response(status=0, message=str(e), result=None)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@evaluations.get("/{model_id}/results", summary="평가 이력(비교표)", tags=TAG)
async def list_eval_results(model_id: int):
    try:
        res = await svc.list_eval_results(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/{model_id}/{job_id}/result", summary="단건 평가 metrics(poll)", tags=TAG)
async def get_eval_result(model_id: int, job_id: str):
    try:
        res = await svc.get_eval_result(model_id=model_id, job_id=job_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/{model_id}/{job_id}/expert-samples", summary="전문가 채점 샘플+기존채점", tags=TAG)
async def get_expert_samples(model_id: int, job_id: str):
    try:
        res = await svc.get_expert_samples(model_id=model_id, job_id=job_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.post("/{model_id}/{job_id}/expert-rating", summary="전문가 채점 제출(1~5 별점)", tags=TAG)
async def submit_expert_rating(model_id: int, job_id: str, body: dto.ExpertRatingBody,
                               jf_user: str = Header(default=None, alias="jf-User")):
    try:
        res = await svc.submit_expert_rating(
            model_id=model_id, job_id=job_id, sample_idx=body.sample_idx,
            score=body.score, score_json=body.score_json, comment=body.comment,
            rater_user=jf_user)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/{model_id}/{job_id}/expert-result", summary="전문가 평가 진행/결과", tags=TAG)
async def get_expert_result(model_id: int, job_id: str):
    try:
        res = await svc.get_expert_result(model_id=model_id, job_id=job_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/{model_id}/{job_id}/expert-image/{sample_idx}",
                 summary="전문가 샘플 이미지(멀티모달)", tags=TAG)
async def get_expert_image(model_id: int, job_id: str, sample_idx: int):
    """VLM 샘플 이미지를 바이너리로 서빙(envelope 아님). NFS 상대경로 이미지만 — URL 이미지는
    FE 가 직접 렌더. 없거나 검증 실패 → 404(FE 가 플레이스홀더 표시)."""
    try:
        path, media_type = await svc.get_expert_image(
            model_id=model_id, job_id=job_id, sample_idx=sample_idx)
        return FileResponse(path, media_type=media_type)
    except Exception:
        traceback.print_exc()
        return Response(status_code=404)


@evaluations.post("/{model_id}/{job_id}/expert-infer/{sample_idx}",
                  summary="전문가 샘플 실추론(지연 단위 VLM)", tags=TAG)
async def infer_expert_sample(model_id: int, job_id: str, sample_idx: int):
    """전문가가 여는 샘플 1개를 바인드된 배포 SDS 모델로 실추론해 output 을 실출력으로
    교체·영속. 미바인드/비-VLM/이미 실출력/이미지 없음/추론 실패 → real_output=false(mock 유지)."""
    try:
        res = await svc.infer_expert_sample(
            model_id=model_id, job_id=job_id, sample_idx=sample_idx)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.post("/{model_id}/{job_id}/status", summary="평가 실패/취소 마킹", tags=TAG)
async def update_eval_status(model_id: int, job_id: str, body: dto.EvalStatusBody):
    try:
        res = await svc.mark_eval_status(
            model_id=model_id, job_id=job_id, status=body.status)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.delete("/{model_id}/{job_id}", summary="평가 런 삭제(이력 관리)", tags=TAG)
async def delete_eval_run(model_id: int, job_id: str):
    try:
        res = await svc.delete_eval_run(model_id=model_id, job_id=job_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)
