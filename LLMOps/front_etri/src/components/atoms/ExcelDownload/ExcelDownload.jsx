import ReactExport from 'react-export-excel-xlsx-fix';

const { ExcelFile } = ReactExport;
const { ExcelSheet } = ExcelFile;

const ExcelDownload = ({
  children,
  data: { sheetName, sheetData },
  fileName,
}) => {
  return (
    <ExcelFile element={children} filename={fileName}>
      <ExcelSheet dataSet={sheetData} name={sheetName} />
    </ExcelFile>
  );
};

export default ExcelDownload;
