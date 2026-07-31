/**
 * 로딩 컴포넌트
 * @param {{ customStyle: { display: 'inline-block' } }} props
 */
function Loading({ customStyle }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <img
        style={customStyle}
        src='/images/icon/spinner-1s-58.svg'
        alt='Loading...'
      />
    </div>
  );
}

export default Loading;
