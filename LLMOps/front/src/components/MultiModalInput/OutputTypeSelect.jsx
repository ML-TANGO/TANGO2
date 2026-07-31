// SDS(EVA VLM) 가 선언한 출력 유형.
//   ⚠️ 2026-07-27 클러스터 실측: 배포된 eva-vlm-backend 는 이 값에 반응하지 않았다
//   (custom_prompt 유무와 무관하게 출력이 바이트 단위 동일). 컨테이너가 프롬프트에
//   반응하게 되면 이 선택이 실제 효과를 갖는다.
const OPTIONS = [
  '영문 해상상황묘사',
  '한글 해상상황묘사',
  '영문 항해조력메시지',
  '한글 항해조력메시지',
  '간결 항해조력메시지',
];

export default function OutputTypeSelect({ value, onChange }) {
  return (
    <label
      style={{ display: 'block', marginBottom: 12, fontSize: 13, fontWeight: 600 }}
    >
      출력 유형
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          display: 'block',
          marginTop: 4,
          width: '100%',
          padding: '4px 8px',
          fontSize: 12,
          border: '1px solid #ccc',
          borderRadius: 3,
          background: '#fff',
        }}
      >
        {OPTIONS.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}
