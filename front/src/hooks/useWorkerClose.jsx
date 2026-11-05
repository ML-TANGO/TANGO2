// import { useEffect } from 'react';

// function useWorkerClose(status, activeWorkers) {
//   useEffect(() => {
//     const handleBeforeUnload = (event) => {
//       if (status) {
//         console.log('beforeunload 이벤트 감지됨, status가 true다');
//         event.preventDefault();
//         event.returnValue = ''; // Chrome에서 동작?
//         const confirmLeave = window.confirm(
//           '업로드가 진행 중입니다. 정말 페이지를 떠나시겠습니까?',
//         );

//         console.log('window.confirm 호출됨:', confirmLeave);

//         if (confirmLeave) {
//           console.log(
//             '사용자가 페이지를 떠나기로 확인했습니다. 워커 종료 시작.',
//           );
//           // 워커 종료
//           activeWorkers.current.forEach((worker) => {
//             console.log(`Terminating worker for ${worker}`);
//             worker.terminate();
//           });
//           activeWorkers.current.clear();

//           // 여기에 작성
//         } else {
//           event.returnValue = false;
//         }
//       }
//     };

//     window.addEventListener('beforeunload', handleBeforeUnload);

//     return () => {
//       window.removeEventListener('beforeunload', handleBeforeUnload);
//     };
//   }, [status, activeWorkers]);
// }

// export default useWorkerClose;
import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux'; // 리덕스 상태 접근을 위해 추가

import {
  addWorker,
  clearWorkers,
  removeWorker,
  startDatasetLoading,
  startUploading,
  stopDatasetLoading,
  stopUploading,
} from '@src/store/modules/uploadLoading';

import { callApi, STATUS_SUCCESS } from '@src/network';

// 삭제 API 요청 함수 (비동기)
// const deleteWorkerAPI = async (key) => {
//   try {
//     console.log(`Deleting worker with key: ${key}`);

//     // key를 ':' 기준으로 분리하여 ID, path, 파일명 추출
//     const [dId, path, fileName] = key.split(':');

//     // path가 '/'일 경우 빈 문자열로 설정
//     const formattedPath = path === '/' ? '' : path;

//     // API 요청 데이터 구성
//     const response = await callApi({
//       url: `datasets/${dId}/files`, // dId 사용
//       method: 'post',
//       body: {
//         path: formattedPath, // 루트면 빈 문자열, 아니면 해당 경로
//         data_list: [fileName], // data_list에 파일명 넣기
//       },
//     });

//     const { status, message, error } = response;

//     if (status === STATUS_SUCCESS) {
//       console.log('성공적으로 파일을 삭제했습니다.');
//     } else {
//       console.error('파일 삭제 실패:', message || error);
//     }
//   } catch (error) {
//     console.error('Error deleting worker:', error);
//   }
// };

function useWorkerClose(status) {
  const activeWorkers = useSelector(
    (state) => state.uploadLoading.activeWorkers,
  ); // 리덕스에서 activeWorkers 가져오기
  const dispatch = useDispatch();

  useEffect(() => {
    const handleBeforeUnload = (event) => {
      if (status && activeWorkers && activeWorkers.size > 0) {
        // 새로고침 및 브라우저 종료 방지
        event.preventDefault();
        event.returnValue = ''; // Chrome에서 동작

        // 사용자가 페이지를 떠날 것인지 확인
        const confirmLeave = window.confirm(
          '업로드가 진행 중입니다. 정말 페이지를 떠나시겠습니까?',
        );

        if (confirmLeave) {
          console.log('사용자가 페이지를 떠나기로 확인했습니다.');

          // 워커에 cancelUpload 명령을 보내고 응답 처리
          activeWorkers.forEach((worker, key) => {
            console.log(`Sending cancelUpload to worker for ${key}`);

            // 워커에게 cancelUpload 명령 전송
            worker.postMessage({ type: 'cancelUpload' });

            // 일정 시간 내에 응답이 없을 경우 강제 종료할 타임아웃 설정
            // const timeout = setTimeout(() => {
            //   console.log(`Timeout reached, terminating worker for ${key}`);
            //   worker.terminate(); // 응답이 없으면 강제 종료
            //   dispatch(removeWorker(key)); // 워커 상태에서 제거
            //   // deleteWorkerAPI(key);
            // }, 5000); // 5초 타임아웃

            // 워커가 취소 확인 메시지를 보냈을 때
            worker.onmessage = (event) => {
              if (event.data.status === 'cancelAcknowledged') {
                // clearTimeout(timeout); // 타임아웃 취소
                console.log(
                  `Worker for ${key} acknowledged cancel, terminating.`,
                );
                worker.terminate(); // 워커 종료
                // dispatch(removeWorker(key)); // 워커 상태에서 제거

                // deleteWorkerAPI(key);
              }
            };
          });

          // 모든 워커가 종료된 후 상태 초기화
          dispatch(clearWorkers());
        } else {
          event.returnValue = false; // 사용자가 페이지 나가기를 취소
        }
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [status, activeWorkers, dispatch]);
}

export default useWorkerClose;
