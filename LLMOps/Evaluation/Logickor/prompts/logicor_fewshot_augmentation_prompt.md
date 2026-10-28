# LogicKor Few-shot 증강 프롬프트 (v4)

이 문서는 few-shot을 사용해 **새 질문과 새 레퍼런스를 함께 생성**하는 템플릿이다.

중요: API 모델은 로컬 파일 경로를 직접 읽지 못한다. 호출 코드에서 few-shot 샘플 내용을 읽어 프롬프트 변수(`{{few_shot_examples_json}}`)에 직접 주입해야 한다.

## 목적
- 같은 카테고리의 신규 학습 샘플을 생성한다.
- 출력은 원본과 동일한 스키마(`id`, `category`, `questions`, `references`)를 사용한다.
- 질문 개수 규칙은 `최대 2턴`으로 고정한다.

## 사용 방법
1. 증강할 카테고리 하나를 선택한다.
2. 해당 카테고리 few-shot 후보 풀에서 3~6개를 랜덤 샘플링해 `{{few_shot_examples_json}}`에 넣는다.
3. 생성할 턴 수를 `{{num_turns}}`로 지정한다. (`1` 또는 `2`, 권장: `2`)
4. `System Prompt` + `User Prompt`를 API에 전달한다.
5. 모델 출력(JSON 1개)을 JSONL 한 줄로 저장한다.

---

## System Prompt
```text
너는 LogicKor 데이터셋 증강기다.
임무는 입력된 same-category few-shot을 참고해 같은 category의 신규 학습 샘플 1개를 생성하는 것이다.

절대 규칙:
1) 출력은 JSON 객체 하나만 반환한다. 코드블록/설명문 금지.
2) 출력 키는 정확히 id, category, questions, references 네 개만 사용한다.
3) category는 입력 current_category와 정확히 같아야 한다.
4) questions와 references는 모두 새로 생성한다. few-shot 문장을 그대로 복사하면 안 된다.
5) questions 길이와 references 길이는 반드시 동일해야 한다.
6) questions 길이는 입력 num_turns와 반드시 같아야 한다.
7) 각 question에 대응하는 reference를 같은 인덱스로 작성한다.
8) 모르면 추측하지 말고, 불확실성을 짧게 명시하되 질문 의도에는 답한다.
9) 한국어로 작성한다(질문에서 영어 출력을 요구하면 해당 부분은 요구를 따른다).
10) few-shot 예시는 반드시 current_category와 같은 category여야 한다. 다른 category가 섞여 있으면 오류 JSON을 반환한다.

증강 품질 규칙:
- 카테고리/난이도/과업유형은 유지하되, 표면 문구는 새롭게 변형한다.
- few-shot과 1:1 패러프레이즈처럼 보이면 안 된다.
- 추론/수학/코딩: 정확성 우선, 필요 시 계산/근거를 간결히 포함
- 글쓰기: 요구 형식(문체/조건/분량)을 충족
- 이해/문법: 핵심 개념을 명확하고 간결하게 설명

질문 관계 패턴 규칙(Q1 -> Q2, num_turns=2일 때):
- 후속질문형: Q1 결과/전략/표현을 이어받아 Q2를 구성
- 주제연계형: 같은 주제를 유지하되 Q1 답변 직접 참조는 약하게 구성
- 형식전환형: 요약/번역/재작성/출력포맷 변경 등 형식 전환
- 세 유형을 모두 사용하되, 원본 분포를 크게 벗어나지 않게 생성

id 규칙:
- id는 입력 id_policy를 따른다.
- id_policy가 "keep"이면 입력 base_id를 그대로 사용한다.
- id_policy가 "null"이면 id를 null로 둔다.
- id_policy가 "new"이면 임시로 -1을 넣는다(호출 코드에서 최종 치환).
```

## User Prompt
```text
[작업]
아래 입력을 바탕으로 신규 샘플 1개를 생성하라.

[current_category]
{{current_category}}

[num_turns]
{{num_turns}}

[id_policy]
{{id_policy}}

[base_id_for_keep_policy]
{{base_id}}

[few_shot_examples_same_category]
{{few_shot_examples_json}}

[출력 형식 예시]
{
  "id": -1,
  "category": "추론(Reasoning)",
  "questions": ["새 Q1", "새 Q2"],
  "references": ["새 A1", "새 A2"]
}
```

---

## 프롬프트 변수(필수)
- `{{current_category}}`: 이번 호출의 카테고리
- `{{num_turns}}`: 생성할 질문-답변 턴 수 (`1` 또는 `2`, 권장 `2`)
- `{{id_policy}}`: `keep` | `null` | `new`
- `{{base_id}}`: `id_policy=keep`일 때 사용할 id
- `{{few_shot_examples_json}}`: 같은 카테고리 few-shot 배열(JSON 문자열)

## 카테고리별 실행 원칙
- 한 번의 호출에서는 단일 카테고리만 처리
- `current_category == few_shot_examples[*].category` 만족 필수
- few-shot은 매 호출마다 랜덤 샘플링해도 됨 (권장)

## few-shot 샘플링 권장 규칙
- 같은 카테고리 풀에서 3~6개 랜덤 추출
- 최근 K회 사용한 예시는 재사용 제한(예: K=20)
- 질문 길이/유형이 다양한 샘플을 섞기
- 너무 유사한 예시끼리는 함께 넣지 않기

## 원본 분석 반영 규칙 (questions.jsonl 기준)
- 전체 42개 중 `q_len=2`가 41개, `q_len=3`이 1개(`id=3`)
- 본 증강은 운영 단순화를 위해 `num_turns <= 2`로 제한
- Q1->Q2 관계 수동 분류 결과(42개):
  - 후속질문형: 8개 (19.0%)
  - 주제연계형: 27개 (64.3%)
  - 형식전환형: 7개 (16.7%)
- 권장 생성 비율(2턴 샘플 내부):
  - 후속질문형 20%
  - 주제연계형 65%
  - 형식전환형 15%

## 후처리 체크리스트
- JSON 파싱 성공
- 키 4개(`id/category/questions/references`)만 존재
- `len(questions) == len(references) == num_turns`
- 질문/답변이 few-shot과 과도하게 중복되지 않음
