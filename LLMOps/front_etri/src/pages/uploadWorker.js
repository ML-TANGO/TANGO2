/* eslint-env worker */
/* eslint-disable no-restricted-globals */
// ***  파일 폴더 로직 분리
// **** 중복되는 코드가 발생하더라도 파일과 폴더를 같이 처리하면 새로운 개발자가 코드를 봤을 때 더 복잡할 것임

const STATUS_FAIL = 'STATUS_FAIL';
const STATUS_SUCCESS = 'STATUS_SUCCESS';
const STATUS_INTERNAL_SERVER_ERROR = 'STATUS_INTERNAL_SERVER_ERROR';

const extractPath = (path) => {
  // path 제거 함수

  if (path === '/' || !path) {
    return null;
  }
  if (path.length > 1 && path[0] === '/') {
    return path.slice(1);
  }

  return path;
};

async function callApi({
  url,
  method = 'GET',
  header = {},
  body,
  params,
  isFormData = false,
  userName,
  token,
  loginedSession,
  accessToken,
}) {
  const response = {
    result: {},
    message: '',
    status: STATUS_FAIL,
    error: {},
  };

  if (
    userName === 'demo' &&
    ['PUT', 'POST', 'DELETE'].includes(method.toUpperCase())
  ) {
    response.message = 'Permission denied.';
    return response;
  }

  const headers = isFormData
    ? {}
    : {
        'Content-Type': 'application/json;charset=UTF-8',
      };

  headers['jf-User'] = userName || 'login';
  headers['jf-Token'] = token || 'login';
  headers['jf-Session'] = loginedSession || 'login';

  if (accessToken) {
    headers['Authorization'] = accessToken;
  }

  if (header) {
    Object.assign(headers, header);
  }

  const reqConfig = {
    method,
    headers,
  };

  if (params) {
    const urlParams = new URLSearchParams(params).toString();
    url += `?${urlParams}`;
  }

  if (body) {
    console.log('-------');
    for (let [key, value] of body.entries()) {
      if (value instanceof File) {
        console.log(`${value}:`);
      } else {
        console.log(`${key}: ${value}`);
      }
    }
    console.log('-------');
    reqConfig.body = isFormData ? body : JSON.stringify(body);
  }

  try {
    const res = await fetch(`${url}`, reqConfig);

    if (!res.ok) {
      response.status = STATUS_FAIL;
      response.message = res.statusText;
      console.error(`Fetch error: ${response.message}`);
      return response;
    }

    const data = await res.json();
    const headerToken = res.headers.get('token');
    const {
      expired,
      token: bodyToken,
      result,
      status,
      message,
      locked,
      error,
    } = data;

    if (status === 1) {
      response.status = STATUS_SUCCESS;
    } else {
      response.status = STATUS_FAIL;
      response.error = error;
    }

    if (expired) {
      response.status = STATUS_FAIL;
      response.message = 'Token expired';
      self.postMessage({ type: 'resetSession' });
      return response;
    }
    if (bodyToken || headerToken) {
      const newToken = bodyToken || headerToken;
      self.postMessage({ type: 'refreshToken', token: newToken });
    }

    if (locked) {
      response.status = STATUS_FAIL;
      response.result = { locked };
    } else {
      response.result = result === null || result === undefined ? {} : result;
    }

    response.message = message;

    if (data.length) {
      response.length = data.length;
    }

    return response;
  } catch (error) {
    response.status = STATUS_INTERNAL_SERVER_ERROR;
    response.message = 'Internal Server Error';
    console.error(`Internal Server Error: ${error.message}`);
    return response;
  }
}

self.onmessage = async (event) => {
  const {
    type,
    filesData,
    isFirstFile,
    folderToken,
    overwrite: folderOverwrite,
  } = event.data;

  if (type === 'startUpload') {
    let shouldCancel = false; // 취소 플래그

    let totalUploadedSize = 0;

    let chunkIndex = 1;

    if (filesData[0].uploadType === 0) {
      // 파일 업로드
      const fileData = filesData[0]; // 단일 파일만 처리
      const fileName = fileData.file.name;

      const chunkSize = calculateChunkSize(fileData);
      let start = 0;
      let end = chunkSize;
      let isFirstChunk = true;

      while (start < fileData.file.size && !shouldCancel) {
        const chunk = fileData.file.slice(start, end);
        const formData = prepareFormData(
          fileData,
          chunk,
          isFirstFile,
          isFirstChunk,
          folderToken,
          chunkIndex, // 새로 추가된 청크 아이디
        );

        // overwrite 값이 존재하는 경우에만 FormData에 추가
        if (fileData.hasOwnProperty('overwrite')) {
          formData.append('overwrite', fileData.overwrite);
        }

        const response = await callApi({
          url: fileData.apiUrl,
          method: 'POST',
          body: formData,
          isFormData: true,
          userName: fileData.userName,
          token: fileData.token,
          loginedSession: fileData.loginedSession,
          accessToken: fileData.accessToken,
        });

        if (response.status === STATUS_SUCCESS) {
          self.postMessage({ status: 'success', fileName });
        } else {
          self.postMessage({ status: 'error', error: response.message });
          break;
        }

        start = end;
        end = start + chunkSize;

        isFirstChunk = false;
        chunkIndex++;

        if (event.data.shouldCancel) {
          shouldCancel = true;
        }
      }

      self.postMessage({
        status: shouldCancel ? 'uploadCanceled' : 'complete',
        fileName,
      });
    } else if (filesData[0].uploadType === 1) {
      // 폴더 업로드
      let isFirstChunk = true;
      let size2 = 0;
      let name2 = '';
      for (let i = 0; i < filesData.length && !shouldCancel; i++) {
        const fileData = filesData[i];
        const fileName = fileData.file.name;

        name2 = fileName;
        size2 = fileData.totalFolderSize;
        const chunkSize = calculateChunkSize(fileData);
        let start = 0;
        let end = chunkSize;

        while (start < fileData.file.size && !shouldCancel) {
          const chunk = fileData.file.slice(start, end);
          totalUploadedSize += chunk.size;
          const formData = prepareFormData(
            fileData,
            chunk,
            isFirstFile, // 첫 번째 파일의 첫 청크만 첫 파일로 간주
            isFirstChunk,
            folderToken,
            chunkIndex,
          );
          isFirstChunk = false;
          // overwrite 값이 존재하는 경우에만 FormData에 추가
          if (typeof folderOverwrite === 'boolean') {
            formData.append('overwrite', folderOverwrite);
          }
          const response = await callApi({
            url: fileData.apiUrl,
            method: 'POST',
            body: formData,
            isFormData: true,
            userName: fileData.userName,
            token: fileData.token,
            loginedSession: fileData.loginedSession,
            accessToken: fileData.accessToken,
          });

          if (response.status === STATUS_SUCCESS) {
            self.postMessage({ status: 'success', fileName });
          } else {
            self.postMessage({ status: 'error', error: response.message });
            shouldCancel = true; // 에러 발생 시 업로드 중단
            break;
          }

          start = end;
          end = start + chunkSize;
          chunkIndex++;

          if (event.data.shouldCancel) {
            shouldCancel = true;
          }
        }
      }

      self.postMessage({
        status: shouldCancel ? 'uploadCanceled' : 'complete',
        fileName: folderToken, // 폴더 업로드 시 폴더 이름으로 반환
      });
    }
  } else if (type === 'cancelUpload') {
    self.postMessage({
      status: 'cancelAcknowledged',
      fileName: event.data.fileName,
    });
  }
};

function calculateChunkSize(fileData) {
  // 청크 사이즈 파일 크기별로 다르게
  const size =
    fileData.uploadType === 0 ? fileData.file.size : fileData.totalFolderSize;
  if (size <= 10 * 1024 * 1024) return 1 * 1024 * 1024;
  if (size <= 100 * 1024 * 1024) return 5 * 1024 * 1024;
  return 10 * 1024 * 1024;
}

function prepareFormData(
  fileData,
  chunk,
  isFirstFile,
  isFirstChunk,
  folderToken,
  chunkIndex,
) {
  const formData = new FormData();
  formData.append('dataset_id', fileData.id);
  formData.append('files', chunk, fileData.folderPath);
  const sanitizedPath = extractPath(fileData.loc);
  if (sanitizedPath) formData.append('path', sanitizedPath);
  if (isFirstFile) {
    formData.append('start', true);
  }

  if (isFirstChunk) {
    formData.append('chunk_start', true);
  }

  formData.append(
    'size',
    fileData.uploadType === 0 ? fileData.file.size : fileData.totalFolderSize,
  );

  formData.append('type', fileData.uploadType === 0 ? 'file' : 'dir');
  formData.append('chunk_id', chunkIndex);

  return formData;
}
