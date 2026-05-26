function Type({ isFolder, name }) {
  // file folder
  if (isFolder) {
    return (
      <svg
        xmlns='http://www.w3.org/2000/svg'
        xmlnsXlink='http://www.w3.org/1999/xlink'
        width='20'
        height='20'
        viewBox='0 0 20 20'
      >
        <defs>
          <path
            id={`folder_id_folder_a`}
            d='M16.875 16.395c.215 0 .397-.075.546-.224.15-.15.224-.331.224-.546V6.458c0-.215-.075-.397-.224-.546-.15-.149-.331-.224-.546-.224H9.23l-.913-1.217c-.072-.095-.161-.17-.268-.224-.108-.053-.221-.08-.34-.08H3.124c-.215 0-.397.074-.546.223-.15.15-.224.332-.224.547v10.688c0 .215.075.397.224.546.15.15.331.224.546.224h13.75z'
          />
        </defs>
        <g fill='none' fillRule='evenodd'>
          <path fill='#000' fillOpacity='0' d='M0 0H20V20H0z' />
          <mask id={`${`folder_id_folder_b`}`} fill='#ffffff'>
            <use xlinkHref={`#${`folder_id_folder_a`}`} />
          </mask>
          <use
            fill='#ffffff'
            fillRule='nonzero'
            xlinkHref={`#${`folder_id_folder_a`}`}
          />
          <path
            fill='#979899'
            d='M0 0H20V20H0z'
            mask={`url(#${`folder_id_folder_b`})`}
          />
        </g>
      </svg>
    );
  }

  return (
    <svg
      xmlns='http://www.w3.org/2000/svg'
      xmlnsXlink='http://www.w3.org/1999/xlink'
      width='20'
      height='20'
      viewBox='0 0 20 20'
    >
      <defs>
        <path
          id={`file_svg_file_a`}
          d='M15.96 6.331L12.147 2.5v3.831h3.813zm-.752 11.44c.203 0 .38-.074.528-.223.15-.15.224-.331.224-.546V7.083h-4.583V2.5H4.502c-.203 0-.379.075-.528.224-.15.149-.224.325-.224.528v13.75c0 .215.075.397.224.546.149.15.325.224.528.224h10.706z'
        />
      </defs>
      <g fill='none' fillRule='evenodd'>
        <path fill='#000' fillOpacity='0' d='M0 0H20V20H0z' />
        <mask id={`${`file_svg_file_b`}`} fill='#ffffff'>
          <use xlinkHref={`#${`file_svg_file_a`}`} />
        </mask>
        <use
          fill='#ffffff'
          fillRule='nonzero'
          xlinkHref={`#${`file_svg_file_a`}`}
        />
        <path
          fill='#979899'
          d='M0 0H20V20H0z'
          mask={`url(#${`file_svg_file_b`})`}
        />
      </g>
    </svg>
  );
}

export default Type;
