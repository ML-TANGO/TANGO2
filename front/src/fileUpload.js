const noop = () => {};
const defaultChunkSize = 1024 * 1024 * 20;
function msToHMS(ms) {
  // 1- Convert to seconds:
  let seconds = ms / 1000;
  // 2- Extract hours:
  const hours = parseInt(seconds / 3600, 10); // 3,600 seconds in 1 hour
  seconds %= 3600; // seconds remaining after extracting hours
  // 3- Extract minutes:
  const minutes = parseInt(seconds / 60, 10); // 60 seconds in 1 minute
  // 4- Keep only seconds not extracted to minutes:
  seconds %= 60;
  return `${hours}:${minutes}:${Math.floor(seconds)}`;
}

// convert to MB
const convertMB = (d) => d / (1024 * 1024);

const INIT_UPLOAD_STATUS = {
  fileName: '-',
  fileSize: '-',
  uploadedSize: '-',
  progress: '-',
  speed: '-',
  averageSpeed: '-',
  remainingTime: '-',
  progressTime: '-',
  takenTime: '-',
};

/**
 * 분할 업로드 인스턴스 생성 함수
 * @param {{
 *  uploadRequest: (
 *    s: number,
 *    e: number,
 *    chunk: File,
 *    fileName: string,
 *    fileSize: number,
 *  ) => (
 *    { status: 'STATUS_SUCCESS' | 'STATUS_FAIL', message: string }
 *  ),
 *  chunkSize: number,
 *  currentFileWatch: ({
 *    fileName,
 *    fileSize,
 *    uploadedSize,
 *    progress,
 *    speed,
 *    averageSpeed,
 *    remainingTime,
 *    progressTime,
 *  } : {
 *    fileName: string,
 *    fileSize: number,
 *    uploadedSize: number,
 *    progress: number,
 *    speed: number,
 *    averageSpeed: number,
 *    remainingTime: string,
 *    progressTime: string,
 *  }) => {},
 *  totalFileWatch: ({
 *    currentUploadFileName,
 *    totalUploadedSize,
 *    totalFileSize,
 *    totalProgress,
 *    speed,
 *    averageSpeed,
 *    totalProgressTime,
 *    totalRemainingTime,
 *  } : {
 *    currentUploadFileName: string,
 *    totalUploadedSize: number,
 *    totalFileSize: number,
 *    totalProgress: number,
 *    speed: number,
 *    averageSpeed: number,
 *    totalProgressTime: string,
 *    totalRemainingTime: string,
 *  }) => {},
 * }} param
 * @returns
 */
export const sliceUploader = ({
  uploadGroupName,
  data,
  uploadRequest,
  chunkSize = defaultChunkSize,
  currentFileWatch: _currentFileWatch,
  totalFileWatch: _totalFileWatch,
  successFunc: _successFunc = noop,
  failFunc: _failFunc = noop,
  doneFunc = noop,
  noDataFolderName,
}) => {
  let files = []; // 업로드할 파일
  let fileArr = [];
  let uploadedList = [];
  let totalSize = 0;
  let startTime; // 첫 업로드 시작 시간
  let isUpload = false; // true: 업로드 중, false: 대기 상태
  let totalUploadedSize = 0; // 업로드 사이즈
  let uploadedSize = 0; // 현재 파일의 업로드 사이즈
  let totalFileSize = 0; // 업로드할 전체 파일의 사이즈
  let failMessage = '';
  const fileUploadStatus = { ...INIT_UPLOAD_STATUS };
  let currentFileWatch = _currentFileWatch;
  let totalFileWatch = _totalFileWatch;
  let successFunc = _successFunc;
  let failFunc = _failFunc;

  function setFileWatch(f) {
    currentFileWatch = f;
  }

  function setTotalFileWatch(f) {
    totalFileWatch = f;
  }

  function setSuccessFunc(f) {
    successFunc = f;
  }

  function setFailFunc(f) {
    failFunc = f;
  }

  // 업로드를 위한 변수 초기화
  function init(fs) {
    files = fs;
    fileArr = fs.map((file) => ({ file }));
    totalSize = 0;
    fileArr.forEach(({ file }) => {
      if (file.path === undefined) totalSize += file.size;
    });
    startTime = undefined;
    totalUploadedSize = 0;
    uploadedSize = 0;
    totalFileSize = fs.map((f) => f.size).reduce((acc, cur) => acc + cur);
    uploadedList = [];
  }

  /**
   * 분할 업로드를 위한 함수
   * @param {number} callCount 업로드 중인 파일의 업로드 횟수
   * @param {Object} file 업로드할 파일
   * @returns
   */
  async function chunkUpload(callCount, file, fileIndex, prevResult) {
    const s = chunkSize * callCount;
    const e = chunkSize * (callCount + 1);
    const chunk = file.slice(s, e);
    const fileName = file.name;
    const fileSize = file.size;
    const tmpPath = file.webkitRelativePath.split('/');
    const basePath = tmpPath.slice(0, tmpPath.length - 1).join('/');
    const sliceChunkSize = chunk.size;
    const isEnd = chunkSize * (callCount + 1) > fileSize;
    // 요청 시작 시간
    const sTime = new Date().getTime();
    // upload 요청
    let removeFolderName = '';
    if (noDataFolderName?.length > 0) {
      // removeFolderName = noDataFolderName;
      const remove = noDataFolderName;
      removeFolderName = remove.toString();
    }
    const { status, message, result } = await uploadRequest(
      totalUploadedSize,
      totalUploadedSize + sliceChunkSize,
      chunk,
      fileName,
      totalSize,
      basePath,
      isEnd,
      prevResult,
      removeFolderName,
      file,
    );

    // const { status, message } = await uploadRequest(s, e, chunk, fileName, fileSize, basePath);
    // 업로드 성공
    if (status === 'STATUS_SUCCESS') {
      if (callCount === 0) uploadedSize = sliceChunkSize;
      else uploadedSize += sliceChunkSize;

      totalUploadedSize += sliceChunkSize;

      // 응답 받은 시간
      const eTime = new Date().getTime();
      // 걸린 시간 (초)
      const takenTime = (eTime - sTime) / 1000;

      // 현재 업로드 파일 프로그레스
      const progress = Math.floor((uploadedSize / fileSize) * 100);

      // chunk 업로드 속도 = 업로드 파일 사이즈(MB) / 걸린시간(초) = 초당 업로드 사이즈
      const speed = convertMB(sliceChunkSize) / takenTime;

      // chunk 평균 업로드 속도
      const averageSpeed =
        convertMB(uploadedSize) /
        ((eTime - fileArr[fileIndex].startTime) / 1000);

      // 현재 파일 업로드 남은 시간
      const remainingTime = msToHMS(
        (convertMB(fileSize - uploadedSize) / averageSpeed) * 1000,
      );

      // 업로드 진행 시간
      const progressTime = msToHMS(eTime - fileArr[fileIndex].startTime);

      // 현재 업로드 파일 프로그레스
      const fileProgress = Math.floor((uploadedSize / fileSize) * 100);

      // 전체 파일 업로드 프로그레스
      const totalProgress = Math.floor(
        (totalUploadedSize / totalFileSize) * 100,
      );

      // 전체 파일 업로드 남은 시간
      const totalRemainingTime = msToHMS(
        (convertMB(totalFileSize - uploadedSize) / averageSpeed) * 1000,
      );

      // 전체 업로드 진행 시간
      const totalProgressTime = msToHMS(eTime - startTime);

      const uploadInfo = {
        fileName: `${basePath}/${fileName}`,
        fileSize: convertMB(fileSize),
        uploadedSize: convertMB(uploadedSize),
        progress,
        speed,
        averageSpeed,
        remainingTime,
        progressTime,
        takenTime,
        isUploaded: true,
      };

      fileArr[fileIndex] = { ...fileArr[fileIndex], ...uploadInfo };
      uploadedList = fileArr.filter(({ isUploaded }) => isUploaded).reverse();

      const uploadStatus = {
        uploadGroupName,
        currentUploadFileName: `${basePath}/${fileName}`,
        totalUploadedSize: convertMB(totalUploadedSize),
        totalFileSize: convertMB(totalFileSize),
        totalProgress,
        fileProgress,
        speed,
        averageSpeed,
        totalProgressTime,
        totalRemainingTime,
        fileCount: files.length,
        uploadingFileIndex: fileIndex,
        fileArr,
        uploadedList,
      };

      if (currentFileWatch) currentFileWatch({ uploadInfo });
      if (totalFileWatch) totalFileWatch(uploadStatus);

      if (chunkSize * (callCount + 1) > fileSize) return;
      await chunkUpload(callCount + 1, file, fileIndex, result);
      return true;
    }
    isUpload = false;
    failMessage = message;
    return false;
  }

  async function fileUpload(file, fileIndex) {
    fileArr[fileIndex].startTime = new Date().getTime();
    return await chunkUpload(0, file, fileIndex);
  }

  async function upload() {
    if (isUpload) {
      console.warn('업로드 진행중');
      failFunc('already upload');
      return;
    }
    init(data);
    // 업로드 시작
    startTime = new Date().getTime();
    isUpload = true;
    // eslint-disable-next-line no-restricted-syntax
    for (let i = 0; i < files.length; i += 1) {
      const file = files[i];
      // eslint-disable-next-line no-await-in-loop
      const isSuccess = await fileUpload(file, i);
      if (isSuccess === false) {
        return false;
      }
    }
    // 업로드 종료
    isUpload = false;
    if (failMessage !== '') failFunc(failMessage);
    else successFunc();

    doneFunc();
    return true;
  }

  return {
    upload,
    fileUploadStatus,
    setFileWatch,
    setTotalFileWatch,
    setSuccessFunc,
    setFailFunc,
    fileArr,
  };
};
