const EMPTY_SHIP = {
  ship_id: '',
  my_ship: 0,
  latitude: '',
  longitude: '',
  knot: '',
  heading: '',
  length: '',
  width: '',
  draft: '',
};

// partner RunParams.AISRow 의 필드 type. ship_id/length/width/draft 는 integer.
const FIELDS = [
  { key: 'ship_id', label: 'ship_id', type: 'number' },
  { key: 'latitude', label: 'latitude', type: 'number' },
  { key: 'longitude', label: 'longitude', type: 'number' },
  { key: 'knot', label: 'knot', type: 'number' },
  { key: 'heading', label: 'heading', type: 'number' },
  { key: 'length', label: 'length', type: 'number' },
  { key: 'width', label: 'width', type: 'number' },
  { key: 'draft', label: 'draft', type: 'number' },
];

function ShipRow({ ship, idx, isOwn, onChange, onRemove }) {
  const handle = (field, type) => (e) => {
    const raw = e.target.value;
    const val = type === 'number' && raw !== '' ? Number(raw) : raw;
    onChange(idx, { ...ship, [field]: val });
  };

  return (
    <div
      style={{
        border: '1px solid #ddd',
        borderRadius: 6,
        padding: 8,
        marginBottom: 8,
        background: isOwn ? '#f0f7ff' : '#fafafa',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 6,
        }}
      >
        <strong style={{ fontSize: 12 }}>
          {isOwn ? '자선 (my_ship=1)' : `타선 ${idx} (my_ship=0)`}
        </strong>
        {!isOwn && (
          <button
            type='button'
            onClick={() => onRemove(idx)}
            style={{
              color: '#d32f2f',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: 11,
            }}
          >
            삭제
          </button>
        )}
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 6,
        }}
      >
        {FIELDS.map((f) => (
          <label key={f.key} style={{ fontSize: 11 }}>
            {f.label}
            <input
              type={f.type}
              step='any'
              value={ship[f.key] ?? ''}
              onChange={handle(f.key, f.type)}
              style={{
                display: 'block',
                width: '100%',
                marginTop: 2,
                padding: '2px 4px',
                fontSize: 11,
                border: '1px solid #ccc',
                borderRadius: 3,
              }}
            />
          </label>
        ))}
      </div>
    </div>
  );
}

export default function AISRowsForm({ value, onChange }) {
  const ownShip = value[0] ?? { ...EMPTY_SHIP, my_ship: 1, ship_id: 'MY' };
  const others = value.slice(1);

  const update = (idx, ship) => {
    if (idx === 0) {
      onChange([{ ...ship, my_ship: 1 }, ...others]);
    } else {
      const arr = [...others];
      arr[idx - 1] = { ...ship, my_ship: 0 };
      onChange([ownShip, ...arr]);
    }
  };

  const addOther = () =>
    onChange([
      ownShip,
      ...others,
      {
        ...EMPTY_SHIP,
        my_ship: 0,
        // partner schema: ship_id integer. 자선이 1이라 타선은 2 부터.
        ship_id: others.length + 2,
        latitude: 35.1,
        longitude: 129.0,
        knot: 0,
        heading: 0,
        length: 50,
        width: 10,
        draft: 3,
      },
    ]);

  const removeOther = (idx) => {
    const arr = others.filter((_, i) => i !== idx - 1);
    onChange([ownShip, ...arr]);
  };

  return (
    <div style={{ marginBottom: 12 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 6,
        }}
      >
        <label style={{ fontWeight: 600, fontSize: 13 }}>
          AIS 데이터 (선박 정보)
        </label>
        <button
          type='button'
          onClick={addOther}
          style={{
            fontSize: 11,
            padding: '2px 8px',
            cursor: 'pointer',
            border: '1px solid #4CAF50',
            color: '#4CAF50',
            background: '#fff',
            borderRadius: 3,
          }}
        >
          + 타선 추가
        </button>
      </div>
      <ShipRow
        ship={ownShip}
        idx={0}
        isOwn
        onChange={update}
        onRemove={removeOther}
      />
      {others.map((s, i) => (
        <ShipRow
          key={i}
          ship={s}
          idx={i + 1}
          isOwn={false}
          onChange={update}
          onRemove={removeOther}
        />
      ))}
    </div>
  );
}
