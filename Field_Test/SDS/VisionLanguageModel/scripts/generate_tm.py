"""
SDS-VLM Technical Memorandum PDF Generator
Requires: fpdf2  (pip install fpdf2)
Fonts   : UnDotum / UnDotumBold  (unfonts-core)
"""
from fpdf import FPDF
import datetime, os

FONT_R = "/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf"
FONT_B = "/usr/share/fonts/truetype/unfonts-core/UnDotumBold.ttf"
OUT    = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                      "SDS-VLM_Technical_Memorandum.pdf")

# ── Color palette ──────────────────────────────────────────────────────────────
C_NAVY   = (21,  47,  86)    # deep navy header
C_BLUE   = (41,  98, 163)    # section title
C_LTBLUE = (210, 225, 245)   # table header fill
C_GRAY   = (240, 242, 245)   # alternating row
C_WHITE  = (255, 255, 255)
C_BLACK  = (30,  30,  30)
C_LINE   = (180, 190, 210)


class TM(FPDF):
    def __init__(self):
        super().__init__("P", "mm", "A4")
        self.add_font("KR",  style="",  fname=FONT_R)
        self.add_font("KR",  style="B", fname=FONT_B)
        self.set_margins(left=15, top=16, right=15)
        self.set_auto_page_break(auto=True, margin=22)
        self._page_no_offset = 0   # title page not numbered

    # ── Header / Footer ────────────────────────────────────────────────────────
    def header(self):
        if self.page == 1:
            return
        self.set_fill_color(*C_NAVY)
        self.rect(0, 0, 210, 10, "F")
        self.set_font("KR", "B", 7)
        self.set_text_color(*C_WHITE)
        self.set_xy(10, 2.5)
        self.cell(0, 5, "SDS-VLM Technical Memorandum  |  ETRI", align="L")
        self.set_xy(0, 2.5)
        self.cell(200, 5, "ETRI", align="R")
        self.set_text_color(*C_BLACK)
        self.set_margins(left=15, top=16, right=15)

    def footer(self):
        if self.page == 1:
            return
        self.set_y(-14)
        self.set_draw_color(*C_LINE)
        self.set_line_width(0.3)
        self.line(15, self.get_y(), 195, self.get_y())
        self.set_font("KR", "", 7)
        self.set_text_color(120, 130, 150)
        self.set_x(15)
        self.cell(0, 8, "본 문서는 ETRI 내부 기술 자료입니다.", align="L")
        self.set_x(0)
        self.cell(195, 8, f"- {self.page - 1} -", align="R")
        self.set_text_color(*C_BLACK)

    # ── Helpers ────────────────────────────────────────────────────────────────
    def h1(self, number, title):
        self.ln(5)
        self.set_fill_color(*C_BLUE)
        self.set_text_color(*C_WHITE)
        self.set_font("KR", "B", 13)
        self.cell(0, 9, f"  {number}.  {title}", ln=True, fill=True)
        self.set_text_color(*C_BLACK)
        self.ln(3)

    def h2(self, title):
        self.ln(2)
        self.set_font("KR", "B", 11)
        self.set_text_color(*C_BLUE)
        self.cell(0, 7, f"▶  {title}", ln=True)
        self.set_text_color(*C_BLACK)
        self.ln(1)

    def body(self, text, size=9.5):
        self.set_font("KR", "", size)
        self.set_x(15)
        self.multi_cell(180, 5.5, text)
        self.ln(1)

    def bullet(self, items, indent=18):
        self.set_font("KR", "", 9.5)
        for item in items:
            self.set_x(indent)
            self.multi_cell(177 - indent, 5.5, f"-  {item}")

    def kv(self, pairs, col1=55, col2=125):
        """Key-value table rows."""
        self.set_font("KR", "", 9)
        for k, v in pairs:
            x = self.get_x()
            y = self.get_y()
            self.set_x(15)
            self.set_fill_color(*C_GRAY)
            self.cell(col1, 6, k, border=1, fill=True)
            self.set_fill_color(*C_WHITE)
            self.cell(col2, 6, v, border=1, fill=False)
            self.ln()

    def table(self, headers, rows, col_widths):
        # header row
        self.set_font("KR", "B", 9)
        self.set_fill_color(*C_LTBLUE)
        self.set_x(15)
        for h, w in zip(headers, col_widths):
            self.cell(w, 7, h, border=1, fill=True, align="C")
        self.ln()
        # data rows
        self.set_font("KR", "", 8.5)
        for i, row in enumerate(rows):
            self.set_x(15)
            fill = (i % 2 == 1)
            self.set_fill_color(*C_GRAY)
            for val, w in zip(row, col_widths):
                self.cell(w, 6.5, str(val), border=1, fill=fill)
            self.ln()
        self.ln(2)

    def code_block(self, text, size=8):
        self.set_fill_color(245, 246, 248)
        self.set_draw_color(*C_LINE)
        self.set_font("KR", "", size)
        self.set_x(15)
        self.multi_cell(180, 4.8, text, border=1, fill=True)
        self.set_font("KR", "", 9.5)
        self.set_draw_color(*C_BLACK)
        self.ln(2)

    def hline(self):
        self.set_draw_color(*C_LINE)
        self.set_line_width(0.3)
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(3)


def make_title_page(pdf):
    pdf.add_page()
    # Navy banner top
    pdf.set_fill_color(*C_NAVY)
    pdf.rect(0, 0, 210, 55, "F")

    # Doc number chip
    pdf.set_font("KR", "", 9)
    pdf.set_text_color(*C_WHITE)
    pdf.set_xy(15, 15)
    pdf.cell(0, 6, "SDS-VLM Technical Memorandum", align="L")

    # Main title
    pdf.set_font("KR", "B", 20)
    pdf.set_xy(15, 26)
    pdf.cell(0, 10, "SDS-VLM 기술 메모", align="L")
    pdf.set_font("KR", "", 13)
    pdf.set_xy(15, 38)
    pdf.cell(0, 7, "Vision-Language Model for Software-Defined Ship", align="L")

    # Reset
    pdf.set_text_color(*C_BLACK)

    # Metadata box
    pdf.set_xy(15, 65)
    pdf.set_font("KR", "", 10)
    today = datetime.date.today().strftime("%Y년 %m월 %d일")
    pdf.kv([
        ("문서 제목",    "SDS-VLM (EVA) 구현 기술 메모"),
        ("작성 기관",    "한국전자통신연구원 (ETRI)"),
        ("작성일",       today),
        ("대상 시스템",  "SDS (Software-Defined Ship) 해상 자율항행 지원 VLM"),
    ], col1=50, col2=130)

    # Abstract box
    pdf.ln(5)
    pdf.set_fill_color(*C_LTBLUE)
    pdf.set_font("KR", "B", 10)
    pdf.set_x(15)
    pdf.cell(180, 7, "  개 요 (Abstract)", ln=True, fill=True)
    pdf.set_fill_color(250, 251, 255)
    pdf.set_font("KR", "", 9.5)
    abs_text = (
        "본 문서는 ETRI SDS(Software-Defined Ship) 프로젝트에서 개발한 "
        "Vision-Language Model(VLM) 시스템 'EVA(ETRI Vessel Agent)'의 "
        "구현 구조와 학습 파이프라인을 기술한 기술 메모(Technical Memorandum)이다. "
        "EVA는 CLIP 비전 인코더와 Llama 3.1-8B-Instruct 언어 모델을 "
        "MLP 프로젝터로 연결하는 LLaVA 계열 아키텍처이며, "
        "해상 카메라 이미지와 AIS 데이터를 융합하여 COLREG 규정에 따른 "
        "항해 조언을 자동 생성한다. "
        "본 문서는 모델 아키텍처, 4단계 학습 파이프라인, "
        "Geometric Attention Alignment(GAA) 보조 손실, "
        "REST API 설계 및 Helm Chart 기반 배포 구조를 포함한다."
    )
    pdf.set_x(15)
    pdf.multi_cell(180, 5.5, abs_text, border=1, fill=True)

    # Footer decoration
    pdf.set_fill_color(*C_NAVY)
    pdf.rect(0, 277, 210, 20, "F")
    pdf.set_font("KR", "", 8)
    pdf.set_text_color(*C_WHITE)
    pdf.set_xy(15, 282)
    pdf.cell(0, 6, "ETRI  |  한국전자통신연구원", align="L")


def make_toc(pdf):
    pdf.add_page()
    pdf.h1("", "목  차")
    sections = [
        ("1", "서론 및 배경", "3"),
        ("2", "시스템 아키텍처 개요", "3"),
        ("3", "모델 구성 요소", "4"),
        ("  3.1", "비전 인코더 (Vision Encoder)", "4"),
        ("  3.2", "MLP 프로젝터 (Projector)", "4"),
        ("  3.3", "언어 모델 (Language Model)", "5"),
        ("  3.4", "VLMConfig 설정 클래스", "5"),
        ("4", "학습 파이프라인", "6"),
        ("  4.1", "Phase 1 — Projector 사전학습", "6"),
        ("  4.2", "Phase 2 — CC3M LoRA 파인튜닝", "6"),
        ("  4.3", "Phase 3 — LLaMarine 텍스트 계속학습", "7"),
        ("  4.4", "Phase 4 — SDS 도메인 파인튜닝", "7"),
        ("5", "GAA (Geometric Attention Alignment)", "8"),
        ("  5.1", "배경 및 동기", "8"),
        ("  5.2", "알고리즘 설계", "8"),
        ("  5.3", "구현 구조", "9"),
        ("6", "REST API 설계", "10"),
        ("7", "배포 아키텍처", "11"),
        ("8", "파라미터 및 시스템 요구사항", "12"),
        ("9", "결론 및 향후 과제", "12"),
    ]
    pdf.set_font("KR", "", 10)
    for num, title, pg in sections:
        pdf.set_x(15)
        dots = "." * max(1, 90 - len(num) - len(title) - len(pg))
        bold = "B" if not num.startswith("  ") else ""
        pdf.set_font("KR", bold, 10)
        pdf.cell(175, 7, f"{num}  {title}  {dots}  {pg}", ln=True)
    pdf.ln(3)


def sec1(pdf):
    pdf.add_page()
    pdf.h1("1", "서론 및 배경")
    pdf.body(
        "소프트웨어 정의 선박(SDS, Software-Defined Ship) 프로젝트는 선박 자율항행 "
        "의사결정 지원을 위한 지능형 시스템 개발을 목표로 한다. 기존 항행 지원 시스템은 "
        "AIS(Automatic Identification System) 수치 데이터만 활용하며, 카메라 영상 "
        "정보와의 융합이 어려웠다. 본 과제에서는 CLIP 비전 인코더와 대형 언어 모델(LLM)을 "
        "연결하여 이미지+AIS 멀티모달 추론이 가능한 VLM 시스템 'EVA(ETRI Vessel Agent)'를 "
        "개발하였다."
    )
    pdf.body(
        "EVA는 LLaVA 1.5 아키텍처를 기반으로 해양 도메인에 특화된 4단계 학습 파이프라인과 "
        "Geometric Attention Alignment(GAA) 보조 손실을 적용하여, COLREG 국제해상충돌예방규칙에 "
        "준거한 항해 조력 메시지를 자동 생성한다."
    )
    pdf.h2("개발 목표")
    pdf.bullet([
        "해상 카메라 이미지와 AIS 데이터를 융합한 다중모달 추론",
        "COLREG 규정(Rule 13~17) 기반 충돌 위험 상황 판단 및 회피 조언 생성",
        "영문/한글 출력을 모두 지원하는 다국어 항해 조력 메시지",
        "REST API 기반 MSA 통합 및 Helm Chart 배포",
        "GAA를 통한 선박 객체 집중 어텐션 학습",
    ])


def sec2(pdf):
    pdf.h1("2", "시스템 아키텍처 개요")
    pdf.body(
        "EVA는 세 개의 주요 모듈로 구성된 end-to-end 멀티모달 파이프라인이다: "
        "(1) 이미지를 패치 토큰 시퀀스로 변환하는 비전 인코더, "
        "(2) 비전 피처 차원을 LLM 임베딩 공간으로 사영하는 MLP 프로젝터, "
        "(3) 통합 토큰 시퀀스로부터 텍스트를 생성하는 언어 모델."
    )
    pdf.code_block(
        "입력 이미지  (1920×1080 PNG)\n"
        "     |\n"
        "     v\n"
        "[Vision Encoder]  CLIP ViT-L/14-336  ->  (B, 576, 1024)\n"
        "     |\n"
        "     v\n"
        "[MLP Projector]   mlp2x_gelu         ->  (B, 576, 4096)\n"
        "     |   576개 시각 토큰을 <image> 위치에 삽입\n"
        "     v\n"
        "[Language Model]  Llama 3.1-8B-Instruct  +  LoRA(r=128)\n"
        "     |\n"
        "     v\n"
        "텍스트 출력  (해상 상황 묘사 + COLREG 항해 조언)"
    )
    pdf.h2("주요 설계 원칙")
    pdf.bullet([
        "단일 <image> 특수 토큰을 576개 시각 패치 벡터로 인라인 대체 (LLaVA 방식)",
        "Flash Attention 2 사용으로 장시퀀스(max 2048) 처리 효율화",
        "PEFT LoRA를 통한 LLM 파인튜닝으로 GPU 메모리 절감",
        "단계별 동결(freeze) 플래그로 학습 단계 분리 관리",
        "HuggingFace Trainer 완전 호환 — DeepSpeed ZeRO-2/3 지원",
    ])
    pdf.h2("지원 모델 조합")
    pdf.table(
        ["구성 요소", "지원 모델", "출력 차원", "패치 수"],
        [
            ["비전 인코더", "CLIP ViT-L/14-336",     "1024-D", "576"],
            ["비전 인코더", "SigLIP-so400m/14-384",  "1152-D", "729"],
            ["비전 인코더", "Video-LanguageBind",    "1024-D", "256×T"],
            ["언어 모델",   "Llama 3.1-8B-Instruct", "4096-D", "—"],
            ["언어 모델",   "Qwen3-8B",              "4096-D", "—"],
            ["프로젝터",    "mlp2x_gelu",            "→4096",  "—"],
        ],
        [45, 65, 35, 35],
    )


def sec3(pdf):
    pdf.add_page()
    pdf.h1("3", "모델 구성 요소")

    pdf.h2("3.1  비전 인코더 (VisionEncoderWrapper)")
    pdf.body(
        "VisionEncoderWrapper는 CLIP, SigLIP, Video-LanguageBind를 통합 인터페이스로 감싸는 "
        "래퍼 클래스이다. 모델 이름 문자열에서 자동으로 인코더 유형을 검출하며, "
        "forward() 출력을 항상 (B, N, D) 형태로 정규화한다."
    )
    pdf.bullet([
        "CLIP: output_hidden_states=True로 feature_layer(-2) 레이어 추출 → CLS 토큰 제거 후 576 패치 반환",
        "SigLIP: CLS 토큰 없음 → 전체 729 패치 직접 반환",
        "Video-LanguageBind: (B,T,C,H,W) 입력을 프레임 단위로 처리 후 (B, T×N, D)로 재조합",
        "feature_layer=-2 (기본값): 마지막 레이어 직전 레이어 사용 — LLaVA 논문 권고값",
    ])

    pdf.h2("3.2  MLP 프로젝터 (VisionProjector)")
    pdf.body(
        "비전 인코더의 출력 차원(예: 1024)을 LLM의 임베딩 차원(4096)으로 변환하는 "
        "MLP이다. Xavier 균등 초기화를 적용하며, 사전학습된 가중치를 projector.bin으로 저장·복원한다."
    )
    pdf.table(
        ["타입", "구조", "파라미터 수"],
        [
            ["linear",     "Linear(1024→4096)",                        "4.2M"],
            ["mlp2x_gelu", "Linear→GELU→Linear  (기본값)",             "20.9M"],
            ["mlp3x_gelu", "Linear→GELU→Linear→GELU→Linear",          "37.7M"],
        ],
        [40, 100, 40],
    )

    pdf.h2("3.3  언어 모델 (Language Model)")
    pdf.body(
        "LlamaForCausalLM 또는 Qwen3-AutoModel을 Flash Attention 2로 로드한다. "
        "<image> 특수 토큰을 어휘에 추가하고(ID: 128256) 임베딩 테이블을 1개 행 확장한다. "
        "LoRA 적용 시 PEFT PeftModel로 래핑되며, _get_embed_layer()가 PeftModel 중첩을 "
        "투명하게 탐색하여 embed_tokens에 접근한다."
    )
    pdf.bullet([
        "LoRA 대상 모듈: q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj",
        "LoRA rank: r=128, alpha=256 (일반), r=16, alpha=32 (소규모 데이터)",
        "Flash Attention 2로 시퀀스 길이 2048 효율 처리",
    ])

    pdf.h2("3.4  VLMConfig 설정 클래스")
    pdf.body("모델 빌드에 필요한 모든 하이퍼파라미터를 dataclass로 관리한다.")
    pdf.table(
        ["필드", "기본값", "설명"],
        [
            ["vision_model_name",             "clip-vit-large-patch14-336", "비전 인코더 HF 이름"],
            ["vision_feature_layer",          "-2",                          "특징 추출 레이어 인덱스"],
            ["vision_feature_select_strategy","patch",                       "patch=CLS 제거, full=포함"],
            ["llm_model_name",                "Llama-3.1-8B-Instruct",      "LLM 경로"],
            ["projector_type",                "mlp2x_gelu",                 "프로젝터 구조"],
            ["freeze_vision",                 "True",                        "비전 인코더 동결 여부"],
            ["freeze_llm",                    "True",                        "LLM 동결 여부"],
            ["max_seq_len",                   "2048",                        "최대 시퀀스 길이"],
        ],
        [55, 55, 70],
    )


def sec4(pdf):
    pdf.add_page()
    pdf.h1("4", "학습 파이프라인")
    pdf.body(
        "EVA는 일반 시각-언어 정렬 → 일반 LoRA 파인튜닝 → 해양 도메인 지식 주입 → "
        "SDS 태스크 특화의 4단계 학습 전략을 사용한다. 각 단계의 학습 대상과 동결 구성을 "
        "명확히 분리하여 catastrophic forgetting을 최소화한다."
    )
    pdf.table(
        ["단계", "데이터", "학습 대상", "동결", "목적"],
        [
            ["Phase 1", "CC3M 595K",         "Projector only",         "CLIP + LLM",    "시각↔언어 정렬"],
            ["Phase 2", "CC3M 595K",         "Projector + LLM(LoRA)",  "CLIP",           "일반 VLM 능력"],
            ["Phase 3", "LLaMarine 54K",     "LLM(LoRA) 계속학습",     "전부(텍스트전용)","해양 지식 주입"],
            ["Phase 4", "SDS 100개",          "Projector + LLM(LoRA)", "CLIP",           "SDS 태스크 특화"],
            ["Phase 4-GAA", "SDS 100개+BBox","CLIP+Projector+LoRA",    "—",              "GAA 어텐션 정렬"],
        ],
        [22, 35, 48, 30, 35],
    )

    pdf.h2("4.1  Phase 1 — Projector 사전학습")
    pdf.bullet([
        "데이터: LLaVA-CC3M-Pretrain-595K (이미지-캡션 쌍)",
        "CLIP과 LLM을 완전 동결, 프로젝터만 학습",
        "lr=1e-3, batch=8, 최대 5,000 steps",
        "결과: projector.bin (약 21M 파라미터)",
    ])

    pdf.h2("4.2  Phase 2 — CC3M LoRA 파인튜닝")
    pdf.bullet([
        "Phase 1 프로젝터 초기화, CLIP 동결",
        "LLM에 LoRA 적용 (r=128, alpha=256, 7개 모듈)",
        "lr=2e-4, batch=4, epoch=3",
        "학습 가능 파라미터: 약 356M / 8.37B (4.25%)",
    ])

    pdf.h2("4.3  Phase 3 — LLaMarine 텍스트 계속학습")
    pdf.bullet([
        "데이터: pentagoniac/llamarine-sft (54,657개 해양 instruction 쌍)",
        "이미지 없음 — 비전 인코더·프로젝터 미로드 (메모리 절감)",
        "기존 LoRA 어댑터 이어받아 계속학습 (lr=5e-5, catastrophic forgetting 방지)",
        "해양 도메인 어휘: AIS, COLREG, 충돌 회피, 선박 유형 등",
        "결과: clip_llama31_lora_marine 체크포인트",
    ])

    pdf.h2("4.4  Phase 4 — SDS 도메인 파인튜닝")
    pdf.bullet([
        "데이터: SDS 시뮬레이션 100개 에피소드 (이미지 + AIS CSV)",
        "3가지 시나리오: 영문 조력(en), 한글 조력(ko), 간결 조력(ko_compact)",
        "lr=2e-4, batch=1, grad_accum=2, epoch=10",
        "CLIP 동결, 프로젝터 + LoRA 학습",
        "결과: clip_llama31_lora_marine_sds_lora_en/ko/ko_compact",
    ])


def sec5(pdf):
    pdf.add_page()
    pdf.h1("5", "GAA — Geometric Attention Alignment")

    pdf.h2("5.1  배경 및 동기")
    pdf.body(
        "LLaVA 계열 VLM에서 CLIP의 CLS 토큰은 배경 텍스처(파도, 하늘)에 과도한 "
        "어텐션을 두어 선박 객체 인식을 방해하는 경향이 있다. "
        "이 현상은 해양 시뮬레이션 이미지처럼 배경이 균일하고 객체가 소형일 때 "
        "더 두드러진다. GAA는 학습 시 바운딩 박스를 특권 정보(privileged information)로 "
        "활용하여 배경 어텐션을 억제한다 (LUPI 패러다임)."
    )

    pdf.h2("5.2  알고리즘 설계")
    pdf.body("GAA는 두 개의 수식으로 정의된다:")

    pdf.set_font("KR", "B", 9.5)
    pdf.set_x(15)
    pdf.cell(0, 6, "■  기하 마스크 (Eq. 4) — 패치가 전경인지 판별", ln=True)
    pdf.code_block(
        "M_i = 1[ coverage(patch_i, bbox) > tau ]\n"
        "\n"
        "coverage = inter_area(patch_i, bbox) / cell_area\n"
        "  * tau = 0.5  (논문 최적값)\n"
        "  * 표준 IoU 대신 coverage 사용: 대형 bbox 내부 패치의 IoU가\n"
        "    항상 tau 미만이 되는 문제를 해결"
    )

    pdf.set_font("KR", "B", 9.5)
    pdf.set_x(15)
    pdf.cell(0, 6, "■  기하 일관성 손실 (Eq. 5)", ln=True)
    pdf.code_block(
        "L_geo = (1/N_B) * sum_k [ (1/||1-M^k||_1) * sum_h ||A_h^k * (1-M^k)||_2^2 ]\n"
        "\n"
        "  A_h^k : k번째 샘플, h번째 헤드의 CLS->patch 어텐션  (B, H, 24, 24)\n"
        "  (1-M) : 배경 마스크 (1=배경, 0=전경)\n"
        "  ||1-M||_1 : 배경 패치 수 (객체 크기 편향 제거용 정규화)"
    )

    pdf.set_font("KR", "B", 9.5)
    pdf.set_x(15)
    pdf.cell(0, 6, "■  최종 손실 (Eq. 6)", ln=True)
    pdf.code_block(
        "L_total = L_SFT + lambda * L_geo        (lambda = 0.5, 논문 최적값)"
    )

    pdf.body(
        "L_geo의 이론적 최솟값: 균등 분포 어텐션 시 ~ 4.83e-05 "
        "(16 heads × 400 bg patches × (1/576)² / 400). "
        "초기 학습에서 L_geo ~ 0.001-0.002이면 CLIP이 배경에 집중 어텐션을 가진 것이며, "
        "이 값이 ~ 4.8e-05로 수렴하면 배경 집중 어텐션이 억제된 상태이다."
    )

    pdf.h2("5.3  구현 구조")
    pdf.body(
        "GAA는 기존 VisionLanguageModel 코드를 변경하지 않고 gaa/ 하위 디렉토리에 "
        "독립적으로 구현된다 (LUPI 원칙: 추론 시 코드 경로 분리)."
    )
    pdf.table(
        ["파일", "역할"],
        [
            ["geometric_loss.py", "Eq.4 compute_geometric_mask / Eq.5 compute_geometric_loss 구현"],
            ["gaa_dataset.py",    "GAADataset — bboxes 필드 추가 / GAADataCollator"],
            ["gaa_trainer.py",    "GAATrainer.compute_loss() — L_SFT + lambda*L_geo 합산"],
            ["train_gaa.py",      "학습 진입점 — freeze_vision=False, CLIP eager attention 재로드"],
            ["sds_reformat.py",   "SDS 에피소드 CSV → GAA chat.json 변환 (bboxes 정규화)"],
            ["compare_models.py", "Baseline vs GAA 순차 로드 비교 (OOM 방지)"],
        ],
        [55, 125],
    )
    pdf.body(
        "GAA 학습의 핵심 기술적 차이: (1) CLIP output_attentions=True는 SDPA 미지원으로 "
        "학습 시작 시 CLIPVisionModel을 eager attention으로 재로드한다. "
        "(2) 매 배치에서 SFT forward 외에 2차 CLIP forward pass를 수행하므로 "
        "GPU 메모리 소비가 약 20% 증가한다 (batch_size=1 권장)."
    )


def sec6(pdf):
    pdf.add_page()
    pdf.h1("6", "REST API 설계")
    pdf.body(
        "EVA는 FastAPI 기반 REST API 서버(eva-vlm, 포트 8000)로 배포되며, "
        "Tango GenAI Platform(조나단) MSA 표준 인터페이스를 준수한다."
    )
    pdf.table(
        ["엔드포인트", "메서드", "조나단 표준", "설명"],
        [
            ["/health",              "GET",  "V 필수", "서비스·모델 상태 확인"],
            ["/info",                "GET",  "V 필수", "서비스 메타 정보"],
            ["/run",                 "POST", "V 필수", "추론 — 이미지+AIS → 텍스트"],
            ["/train",               "POST", "확장",   "비동기 학습 시작, job_id 반환 (HTTP 202)"],
            ["/jobs/{job_id}",       "GET",  "V 표준", "학습 진행 조회 (플랫폼 표준 URL)"],
            ["/jobs/{job_id}/cancel","POST", "V 표준", "학습 중지 (플랫폼 표준 URL)"],
            ["/models",              "GET",  "확장",   "체크포인트 목록 반환"],
            ["/deploy",              "POST", "확장",   "체크포인트 전환 (모델 핫스왑)"],
        ],
        [52, 20, 22, 86],
    )

    pdf.h2("추론 입력 스키마 (/run)")
    pdf.code_block(
        '{\n'
        '  "workspace_id": "ws-abc123",\n'
        '  "project_id":   "proj-def456",\n'
        '  "params": {\n'
        '    "image_base64":      "<base64 PNG/JPG>",\n'
        '    "ais_rows": [\n'
        '      {"ship_id":0, "my_ship":1, "latitude":34.45, "longitude":127.73,\n'
        '       "knot":17.5, "heading":141.0, "length":93, "width":28, "draft":3},\n'
        '      {"ship_id":1, "my_ship":0, "latitude":34.44, "longitude":127.73,\n'
        '       "knot":20.1, "heading":115.0, "length":134, "width":24, "draft":4,\n'
        '       "bbox_x":975, "bbox_y":318, "bbox_width":408, "bbox_height":263}\n'
        '    ],\n'
        '    "output_type":         "간결 항해조력메시지",\n'
        '    "max_new_tokens":      512,\n'
        '    "repetition_penalty":  1.1\n'
        '  }\n'
        '}'
    )

    pdf.h2("output_type 선택지")
    pdf.bullet([
        "영문 해상상황묘사  —  영문 AIS 텍스트 + 영문 묘사 생성",
        "한글 해상상황묘사  —  한글 AIS 텍스트 + 한글 묘사 생성",
        "영문 항해조력메시지  —  영문 AIS + 묘사 + COLREG 기반 조언",
        "한글 항해조력메시지  —  한글 AIS + 묘사 + COLREG 기반 조언",
        "간결 항해조력메시지  —  한글 간결 포맷 COLREG 조언",
    ])

    pdf.h2("에러 코드")
    pdf.table(
        ["코드", "HTTP", "설명"],
        [
            ["INVALID_PARAMS",     "400", "필수 필드 누락 또는 형식 오류"],
            ["NOT_FOUND",          "404", "지정한 체크포인트/job_id 없음"],
            ["RESOURCE_EXHAUSTED", "429", "이미 학습 중 (GPU 1장 환경 제약)"],
            ["SERVICE_UNAVAILABLE","503", "모델 로드 미완료 또는 전환 중"],
            ["INTERNAL_ERROR",     "500", "내부 오류"],
        ],
        [55, 20, 105],
    )


def sec7(pdf):
    pdf.add_page()
    pdf.h1("7", "배포 아키텍처")

    pdf.h2("Docker 컨테이너")
    pdf.bullet([
        "베이스 이미지: nvidia/cuda:12.8.0-devel-ubuntu24.04",
        "서비스명: eva-vlm  |  포트: 8000  |  버전 태그: yvvyee/eva-vlm-backend:1.1.0",
        "Ingress 경로: /msa/eva-vlm  (Tango GenAI Platform 협의 확정)",
    ])

    pdf.h2("NFS 볼륨 구조")
    pdf.code_block(
        "/nfs/eva/\n"
        "├── models/\n"
        "│   ├── llm/\n"
        "│   │   └── Llama-3.1-8B-Instruct/    # LLM 가중치 (~16 GB)\n"
        "│   ├── checkpoints/                   # 학습 결과 체크포인트\n"
        "│   │   ├── sds_lora_ko_compact/       # projector.bin + LoRA\n"
        "│   │   └── ...\n"
        "│   └── hf_cache/                     # CLIP 오프라인 캐시 (선택)\n"
        "└── data/\n"
        "    └── sds/20260227/                  # SDS 학습 데이터셋\n"
        "        ├── 00001/{input_image.png, input_data.csv, output_*.txt}\n"
        "        └── ..."
    )

    pdf.h2("필수 환경 변수")
    pdf.kv([
        ("EVA_LLM_MODEL_PATH",    "/models/llm/Llama-3.1-8B-Instruct"),
        ("EVA_CHECKPOINT_PATH",   "/models/checkpoints/sds_lora_ko_compact"),
        ("EVA_CHECKPOINTS_ROOT",  "/models/checkpoints"),
        ("EVA_VISION_MODEL_NAME", "openai/clip-vit-large-patch14-336"),
        ("EVA_DEVICE",            "cuda:0"),
    ], col1=60, col2=120)

    pdf.h2("Helm Chart 설치")
    pdf.code_block(
        "helm install eva-vlm-1 ./helm_chart/ \\\n"
        "  -n tango-eva --create-namespace \\\n"
        "  --set backend.image=yvvyee/eva-vlm-backend:1.1.0 \\\n"
        "  --set backend.env.EVA_LLM_MODEL_PATH=/models/llm/Llama-3.1-8B-Instruct \\\n"
        "  --set backend.env.EVA_CHECKPOINT_PATH=/models/checkpoints/sds_lora_ko_compact \\\n"
        "  --set backend.volumes[0].nfs.server=<NFS_SERVER_IP> \\\n"
        "  --set backend.volumes[0].nfs.path=/nfs/eva/models \\\n"
        "  --set ingress.enabled=true"
    )

    pdf.h2("Kubernetes 설정 고려사항")
    pdf.bullet([
        "모델 로드 시간 약 2분 → livenessProbe initialDelaySeconds: 120 이상 설정 필요",
        "GPU 1장 환경 제약 — 학습과 추론 동시 실행 불가 (RESOURCE_EXHAUSTED 429 반환)",
        "모델 핫스왑(/deploy) 실행 중 약 2분간 /run 비가용 상태 → 무중단 배포 필요 시 인스턴스 이중화 권장",
    ])


def sec8(pdf):
    pdf.add_page()
    pdf.h1("8", "파라미터 및 시스템 요구사항")

    pdf.h2("모델 파라미터 수 (CLIP + Llama 3.1-8B)")
    pdf.table(
        ["모듈", "전체 파라미터", "학습 가능", "비율"],
        [
            ["CLIP ViT-L/14-336",      "303,507,456",   "0 (동결)",         "0%"],
            ["MLP Projector (2x)",     "20,979,712",    "20,979,712",       "100%"],
            ["Llama 3.1-8B (전체)",    "8,030,269,440", "0 (LoRA 미적용시)","0%"],
            ["Llama 3.1-8B + LoRA r=128","8,365,813,760","335,544,320",     "4.01%"],
            ["GAA (vision 동결 해제)", "8,690,300,928", "660,031,488",      "7.60%"],
        ],
        [55, 48, 48, 29],
    )

    pdf.h2("학습 하이퍼파라미터 (Phase 4 SDS)")
    pdf.kv([
        ("batch_size",      "1 per GPU (GPU 메모리 제약)"),
        ("grad_accum",      "16 steps (effective batch = 16)"),
        ("learning_rate",   "2e-4"),
        ("lr_scheduler",    "cosine"),
        ("warmup_ratio",    "0.03"),
        ("num_epochs",      "1 (소규모 100샘플 기준 권장)"),
        ("LoRA rank/alpha", "16 / 32 (소규모), 128 / 256 (대규모)"),
        ("dtype",           "bfloat16"),
        ("max_seq_len",     "2048 tokens"),
    ], col1=55, col2=125)

    pdf.h2("하드웨어 요구사항")
    pdf.table(
        ["항목", "최소", "권장"],
        [
            ["GPU",    "NVIDIA A100 40GB × 1",    "NVIDIA RTX 5090 32GB × 1 이상"],
            ["CUDA",   "12.0+",                   "12.8"],
            ["RAM",    "64 GB",                   "128 GB"],
            ["NFS",    "200 GB",                  "1 TB+"],
            ["OS",     "Ubuntu 22.04",            "Ubuntu 24.04"],
        ],
        [40, 70, 70],
    )

    pdf.h2("소프트웨어 스택")
    pdf.table(
        ["패키지", "버전", "용도"],
        [
            ["PyTorch",         "2.11.0+cu128", "딥러닝 프레임워크"],
            ["transformers",    "5.3.0",         "모델 로드 / HF Trainer"],
            ["peft",            "0.18.1",        "LoRA 적용"],
            ["accelerate",      "1.13.0",        "멀티 GPU / DeepSpeed 통합"],
            ["deepspeed",       "0.18.8",        "ZeRO-2/3 학습 최적화"],
            ["fastapi",         "최신",           "REST API 서버"],
            ["gradio",          "6.14.0",        "데모 웹 앱"],
        ],
        [40, 40, 100],
    )


def sec9(pdf):
    pdf.add_page()
    pdf.h1("9", "결론 및 향후 과제")

    pdf.h2("구현 요약")
    pdf.body(
        "본 기술 메모에서 기술한 EVA VLM 시스템은 다음을 달성하였다:"
    )
    pdf.bullet([
        "LLaVA 1.5 아키텍처 기반 해양 특화 VLM 완전 구현 (CLIP + Llama 3.1-8B)",
        "4단계 학습 파이프라인: CC3M 정렬 → LoRA 파인튜닝 → 해양 도메인 → SDS 특화",
        "GAA 보조 손실 독립 구현 (기존 코드 무변경, gaa/ 디렉토리 분리)",
        "REST API 서버 — 추론/학습/배포를 단일 서비스로 통합",
        "Helm Chart 기반 Kubernetes 배포 지원",
        "영문 / 한글 / 간결 3가지 출력 유형 지원",
    ])

    pdf.h2("향후 과제")
    pdf.bullet([
        "SDS 학습 데이터 확대 (100개 → 1,000개 이상) — 과적합 없는 GAA 효과 검증",
        "SigLIP 비전 인코더 교체 실험 (729 패치, 1152-D → 풍부한 시각 표현)",
        "Qwen3-8B 언어 모델 비교 실험 (한국어 토크나이저 최적화)",
        "다중 선박 처리: 복수 바운딩 박스 GAA 어텐션 정렬 고도화",
        "실해역 데이터 수집 및 시뮬레이션-실환경 도메인 갭 분석",
        "조나단 플랫폼 연동 — 아크릴 UI 작업 후 E2E 통합 테스트",
        "추론 속도 최적화: TensorRT-LLM / vLLM 적용 검토",
    ])

    pdf.ln(5)
    pdf.hline()
    pdf.set_font("KR", "", 9)
    pdf.set_text_color(100, 110, 130)
    pdf.set_x(15)
    pdf.multi_cell(180, 5.5,
        "본 문서에 포함된 소스코드, 모델 구조, 학습 데이터 및 API 설계는 "
        "ETRI 내부 연구 자산입니다. 외부 배포 및 무단 인용을 금합니다.",
    )
    pdf.set_text_color(*C_BLACK)


# ── Build ──────────────────────────────────────────────────────────────────────

def main():
    pdf = TM()
    pdf.set_title("SDS-VLM Technical Memorandum")
    pdf.set_author("ETRI")

    make_title_page(pdf)
    make_toc(pdf)
    sec1(pdf)
    sec2(pdf)
    sec3(pdf)
    sec4(pdf)
    sec5(pdf)
    sec6(pdf)
    sec7(pdf)
    sec8(pdf)
    sec9(pdf)

    pdf.output(OUT)
    print(f"PDF saved: {OUT}")


if __name__ == "__main__":
    main()
