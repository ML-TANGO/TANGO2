importScripts('/path/to/network.js'); // callApi를 포함한 스크립트 가져오기

self.addEventListener('install', (event) => {
  console.log('Service Worker installing.');
});

self.addEventListener('activate', (event) => {
  console.log('Service Worker activating.');
});

self.addEventListener('message', async (event) => {
  console.log('Received message:', event);
  if (event.data && event.data.type === 'UPLOAD_FILES') {
    console.log('Starting upload process...');
    const { files, uploadDetails } = event.data.payload;

    const uploadFile = async (file, details) => {
      console.log('Uploading file:', file.name);
      const formData = new FormData();
      formData.append('dataset_id', details.datasetId);

      if (details.extractPath(details.loc)) {
        formData.append('path', details.extractPath(details.loc));
      }

      const sanitizeFileName = (name) => {
        const excludeChars = /[?*<>#$%&(),/"|\\\s]/g;
        return name.replace(excludeChars, '_').normalize('NFC');
      };

      const relativePath = file.webkitRelativePath || file.name;
      const pathParts = relativePath.split('/');
      const originFileName = pathParts.pop();
      const sanitizedFileName = sanitizeFileName(originFileName);

      const newFileName = pathParts.join('/')
        ? `${pathParts.join('/')}/${sanitizedFileName}`
        : sanitizedFileName;

      const newFile = new File([file], sanitizedFileName, {
        type: file.type,
        lastModified: file.lastModified,
      });

      formData.append('files', newFile, newFileName);

      if (details.uploadType === 0) {
        formData.append('size', file.size); // 개별 파일의 크기
        formData.append('type', 'file');
      } else {
        formData.append('size', details.totalFolderSize); // 폴더의 총 크기
        formData.append('type', 'dir');
      }

      try {
        const response = await callApi({
          url: 'upload',
          method: 'post',
          isFormData: true,
          body: formData,
        });

        console.log('Upload response:', response);
        return response.status === STATUS_SUCCESS;
      } catch (error) {
        console.error('Upload error:', error);
        return false;
      }
    };

    const allPromises = [];
    let currentBatch = [];

    for (let i = 0; i < files.length; i++) {
      const uploadPromise = uploadFile(files[i], uploadDetails);
      allPromises.push(uploadPromise);
      currentBatch.push(uploadPromise);

      // 5개의 요청마다 getFileForUpload 호출
      if ((i + 1) % 5 === 0 || i === files.length - 1) {
        await Promise.all(currentBatch);
        currentBatch = []; // 현재 배치를 초기화

        // Trigger getFileForUpload
        await callApi({
          url: 'path/to/getFileForUpload',
          method: 'get',
        });
      }
    }

    const successCount = (await Promise.all(allPromises)).filter(
      (result) => result,
    ).length;

    self.clients.matchAll().then((clients) => {
      clients.forEach((client) =>
        client.postMessage({
          type: 'UPLOAD_COMPLETE',
          payload: { successCount },
        }),
      );
    });
  }
});
