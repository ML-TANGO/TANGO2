function EditIcon({ className, style, onClick }) {
  return (
    <svg
      width='28'
      height='28'
      viewBox='0 0 28 28'
      style={style}
      onClick={onClick}
      className={className}
    >
      <defs>
        <path
          id='rczgu2e2ja'
          d='M21.77 10.313l1.732-1.732c.182-.182.273-.41.273-.683 0-.274-.09-.502-.273-.684l-2.53-2.506c-.182-.198-.406-.297-.672-.297-.265 0-.497.1-.695.297l-1.709 1.709 3.874 3.896zM8.167 23.917l12.122-12.123-3.896-3.873L4.27 20.02v3.896h3.897z'
        />
      </defs>
      <g fill='none' fillRule='evenodd'>
        <g>
          <g>
            <g>
              <g>
                <g transform='translate(-675 -192) translate(328 188) translate(48) translate(295) translate(4 4)'>
                  <path d='M0 0H28V28H0z' opacity='.2' />
                  <mask id='5mdrig6dgb' fill='#ffffff'>
                    <use xlinkHref='#rczgu2e2ja' />
                  </mask>
                  <path
                    fill='#747474'
                    d='M0 0H28V28H0z'
                    mask='url(#5mdrig6dgb)'
                  />
                </g>
              </g>
            </g>
          </g>
        </g>
      </g>
    </svg>
  );
}

export default EditIcon;
