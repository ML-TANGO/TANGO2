import { useRef, useState } from 'react';

const MAX_BYTES = 5 * 1024 * 1024;

export default function ImageUploadField({ value, onChange }) {
  const ref = useRef(null);
  const [error, setError] = useState('');
  const [mime, setMime] = useState('image/png');

  const handleFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setError('이미지는 5 MB 이하여야 합니다.');
      return;
    }
    setError('');
    setMime(file.type || 'image/png');
    const reader = new FileReader();
    reader.onload = () => {
      const b64 = String(reader.result).split(',')[1] || '';
      onChange(b64);
    };
    reader.readAsDataURL(file);
  };

  const handleClear = () => {
    setError('');
    if (ref.current) ref.current.value = '';
    onChange('');
  };

  return (
    <div style={{ marginBottom: 12 }}>
      <label
        style={{
          fontWeight: 600,
          display: 'block',
          marginBottom: 4,
          fontSize: 13,
        }}
      >
        선박 이미지 (최대 5 MB)
      </label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <input
          type='file'
          accept='image/*'
          ref={ref}
          onChange={handleFile}
          style={{ flex: 1, fontSize: 12 }}
        />
        {value && (
          <button
            type='button'
            onClick={handleClear}
            style={{
              fontSize: 11,
              padding: '2px 8px',
              border: '1px solid #ccc',
              background: '#fff',
              borderRadius: 3,
              cursor: 'pointer',
            }}
          >
            초기화
          </button>
        )}
      </div>
      {error && (
        <p style={{ color: '#d32f2f', fontSize: 11, margin: '4px 0 0' }}>
          {error}
        </p>
      )}
      {value && (
        <img
          src={`data:${mime};base64,${value}`}
          alt='preview'
          style={{
            maxWidth: 200,
            maxHeight: 120,
            marginTop: 8,
            borderRadius: 4,
            border: '1px solid #eee',
          }}
        />
      )}
    </div>
  );
}
