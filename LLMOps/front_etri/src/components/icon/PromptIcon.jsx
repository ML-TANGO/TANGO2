export default function PromptIcon({ width, height, color }) {
  return (
    <svg
      xmlns='http://www.w3.org/2000/svg'
      width={width}
      height={height}
      view-box={`0 0 ${width} ${height}`}
      fill='none'
    >
      <path
        d='M2.5 2H13.5C13.7761 2 14 2.22386 14 2.5V13.5C14 13.7761 13.7761 14 13.5 14H2.5C2.22386 14 2 13.7761 2 13.5V2.5C2 2.22386 2.22386 2 2.5 2Z'
        stroke={color}
      />
      <path
        d='M9 10.8571H4V12H9V10.8571ZM12 6.28571H4V7.42857H12V6.28571ZM4 9.71429H12V8.57143H4V9.71429ZM4 4V5.14286H12V4H4Z'
        fill={color}
      />
    </svg>
  );
}
