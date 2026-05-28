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
