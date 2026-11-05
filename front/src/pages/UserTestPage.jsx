import { useCallback, useEffect, useRef, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

// Components
import UserTestContent from '@src/components/pageContents/user/UserTestContent';
import { toast } from '@src/components/Toast';

import { startPath } from '@src/store/modules/breadCrumb';
// Actions
import { closeModal, openModal } from '@src/store/modules/modal';
// Network
import { callApi, network, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

// Utils
import { convertBinaryByte, errorToastMessage } from '@src/utils';

function UserTestPage({ trackingEvent }) {
  const { t } = useTranslation();

  // Router Hooks
  const history = useHistory();
  const match = useRouteMatch();
  const { id: wid, sid } = match.params;

  // Redux hooks
  const dispatch = useDispatch();

  // State
  const [serviceData, setServiceData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [inputText, setInputText] = useState([]);
  const [selectedImage, setSelectedImage] = useState([]);
  const [selectedImageSrc, setSelectedImageSrc] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState([]);
  const [selectedVideoSrc, setSelectedVideoSrc] = useState([]);
  const [selectedAudio, setSelectedAudio] = useState([]);
  const [selectedAudioSrc, setSelectedAudioSrc] = useState([]);
  const [selectedCSV, setSelectedCSV] = useState([]);
  const [selectedCSVSrc, setSelectedCSVSrc] = useState([]);
  /* image canvas */
  const [selectedCanvas, setSelectedCanvas] = useState([]);
  const [selectedCanvasSrc, setSelectedCanvasSrc] = useState(null);
  const [imageObj, setImageObj] = useState(null);
  const [rect, setRect] = useState({});
  const [drag, setDrag] = useState(false);
  const [originWidth, setOriginWidth] = useState(0);
  const [originHeight, setOriginHeight] = useState(0);
  const [autoLength, setAutoLength] = useState(null);
  // const [isWidthLongerThanHeight, setIsWidthLongerThanHeight] = useState(true);
  const [ctx, setCtx] = useState(null);
  const [canvasWidth, setCanvasWidth] = useState(1562);
  const [canvasHeight, setCanvasHeight] = useState(480);
  /* canvas end */
  const [outputObj, setOutputObj] = useState(null);
  const [outputStatus, setOutputStatus] = useState('');
  const [validate, setValidate] = useState(false);
  const [fileUpload, setFileUpload] = useState(null);

  const canvasRef = useRef(null);

  /**
   * Action 브래드크럼
   * @param {String} deployName
   */
  const breadCrumbHandler = useCallback(
    (deployName) => {
      dispatch(
        startPath([
          {
            component: {
              name: 'Simulation',
              path: `/user/workspace/${wid}/services`,
              t,
            },
          },
          {
            component: {
              name: deployName,
            },
          },
        ]),
      );
    },
    [dispatch, t, wid],
  );

  /**
   * API 호출 GET
   * 서비스 데이터 가져오기
   */
  const getServiceData = useCallback(async () => {
    setLoading(true);
    const response = await callApi({
      url: `services/${sid}`,
      method: 'GET',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      breadCrumbHandler(result.name);
      setServiceData(result);
    } else {
      errorToastMessage(error, message);
    }
    setLoading(false);
  }, [breadCrumbHandler, sid]);

  /**
   * 파일 업로드
   *
   * @param {object} e 파일 입력 이벤트
   * @param {string} inputType 파일 입력 유형 (Image | Video | Audio)
   * @param {number} index input 인덱스
   */
  const fileInputHandler = (e, inputType, index) => {
    if (e.length > 0) {
      const fReader = new FileReader();
      const selectedFile = e[0];

      fReader.addEventListener(
        'load',
        () => {
          switch (String(inputType)) {
            case 'Video':
              const fileSrcListVideo = { ...selectedVideoSrc };
              const fileListVideo = { ...selectedVideo };
              fileSrcListVideo[index] = fReader.result;
              fileListVideo[index] = selectedFile;
              setSelectedVideoSrc({ ...fileSrcListVideo });
              setSelectedVideo({ ...fileListVideo });
              break;

            case 'Audio':
              const fileSrcListAudio = { ...selectedAudioSrc };
              const fileListAudio = { ...selectedAudio };
              fileSrcListAudio[index] = fReader.result;
              fileListAudio[index] = selectedFile;
              setSelectedAudioSrc({ ...fileSrcListAudio });
              setSelectedAudio({ ...fileListAudio });
              break;

            case 'CSV':
              const fileSrcListCSV = { ...selectedCSVSrc };
              const fileListCSV = { ...selectedCSV };
              fileSrcListCSV[index] = fReader.result;
              fileListCSV[index] = selectedFile;
              setSelectedCSVSrc({ ...fileSrcListCSV });
              setSelectedCSV({ ...fileListCSV });
              break;

            case 'Image':
              const fileSrcListImage = { ...selectedImageSrc }; // 얘가 계속 에러
              const fileListImage = { ...selectedImage };
              fileSrcListImage[index] = fReader.result;
              fileListImage[index] = selectedFile;
              setSelectedImageSrc({ ...fileSrcListImage });
              setSelectedImage({ ...fileListImage });
              break;

            default:
              break;
          }
          setValidate(true);
          setOutputObj(null);
        },
        false,
      );
      fReader.readAsDataURL(selectedFile);
    } else {
      setValidate(false);
    }
  };

  /**
   * 파일 업로드 캔버스용
   *
   * @param {object} e 파일 입력 이벤트
   */
  const canvasInputHandler = (e) => {
    setFileUpload(e[0]);
    if (e.length > 0) {
      const fReader = new FileReader();
      const selectedCanvas = e[0];

      fReader.addEventListener(
        'load',
        () => {
          setSelectedCanvasSrc(fReader.result);
        },
        false,
      );
      fReader.readAsDataURL(selectedCanvas);

      setSelectedCanvas(selectedCanvas);
      setValidate(true);
      setOutputObj(null);

      if (ctx !== null) {
        // 이미 있을 경우 초기화
        ctx.clearRect(0, 0, canvasWidth, canvasHeight);
      }
      drawCanvas(selectedCanvas);
    } else {
      setValidate(false);
    }
  };

  /**
   * canvas 크기에 따른 상태값 변경
   */
  const canvasStateHandler = ({
    imageObj,
    // widthLongerThanHeight,
    autoLen,
    width,
    height,
  }) => {
    setImageObj(imageObj);
    // setIsWidthLongerThanHeight(widthLongerThanHeight);
    setAutoLength(autoLen);
    setCanvasWidth(width);
    setCanvasHeight(height);
  };

  /**
   * 이미지를 캔버스화
   * @param {object} selectedFile 선택된 이미지 파일
   */
  const drawCanvas = useCallback((selectedFile) => {
    const fileURL = URL.createObjectURL(selectedFile);
    const canvas = canvasRef.current;
    const tempCtx = canvas.getContext('2d');
    const imageObj = new Image();

    imageObj.onload = () => {
      // 화면 크기에 맞춰 이미지 크기 조정
      const w = imageObj.width;
      const h = imageObj.height;

      setOriginWidth(w);
      setOriginHeight(h);

      const autoLength = h * (1562 / w);

      // 가로 최대 길이만 제한하는 경우
      if (w > 1562) {
        const params = {
          imageObj,
          autoLen: autoLength,
          width: 1562,
          height: autoLength,
        };
        canvasStateHandler(params);
        tempCtx.drawImage(imageObj, 0, 0, 1562, autoLength);
      } else {
        const params = {
          imageObj,
          autoLen: w,
          width: w,
          height: h,
        };
        canvasStateHandler(params);
        tempCtx.drawImage(imageObj, 0, 0, w, h);
      }
      // // 가로 세로 길이 모두 제한하는 경우
      // if (w > h) {
      //   // 가로가 더 긴 경우
      //   if (autoLength > 1200) {
      //     // 가로가 더 긴데 세로가 1200 초과한 경우
      //     const params = {
      //       imageObj,
      //       widthLongerThanHeight: false,
      //       autoLen: w * (1200 / h),
      //       width: w * (1200 / h),
      //       height: 1200,
      //     };
      //     canvasStateHandler(params);
      //     tempCtx.drawImage(imageObj, 0, 0, w * (1200 / h), 1200);
      //   } else {
      //     // 가로가 더 긴데 세로가 1200 이내인 경우
      //     const params = {
      //       imageObj,
      //       widthLongerThanHeight: true,
      //       autoLen: autoLength,
      //       width: 1562,
      //       height: autoLength,
      //     };
      //     canvasStateHandler(params);
      //     tempCtx.drawImage(imageObj, 0, 0, 1562, autoLength);
      //   }
      // } else {
      //   // 세로가 더 긴 경우
      //   const params = {
      //     imageObj,
      //     widthLongerThanHeight: false,
      //     autoLen: w * (1200 / h),
      //     width: w * (1200 / h),
      //     height: 1200,
      //   };
      //   canvasStateHandler(params);
      //   tempCtx.drawImage(imageObj, 0, 0, w * (1200 / h), 1200);
      // }
    };
    imageObj.src = fileURL;
    setCtx(tempCtx);
    setRect({});
    canvas.style.cursor = 'crosshair'; // 커서 변경
  }, []);

  /**
   * 좌표 생성
   */
  const getCoordinate = () => {
    const sx = rect.startX * (originWidth / canvasWidth) || 0;
    const sy = rect.startY * (originHeight / canvasHeight) || 0;
    const ex = rect.endX * (originWidth / canvasWidth) || originWidth;
    const ey = rect.endY * (originHeight / canvasHeight) || originHeight;
    let coordinate = [];
    // 좌표 그리는 순서에 따라 달라진 좌표 순서를, 왼쪽 위(시작지점) -> 오른쪽 아래(끝지점) 순서로 맞춤
    if (sx < ex) {
      if (sy < ey) {
        coordinate = [sx, sy, ex, ey];
      } else {
        coordinate = [sx, ey, ex, sy];
      }
    } else if (sy < ey) {
      coordinate = [ex, sy, sx, ey];
    } else {
      coordinate = [ex, ey, sx, sy];
    }
    return coordinate;
  };

  /**
   * 분석 시작 버튼 활성화 가능 확인
   * 텍스트 입력시 입력된 글자가 있을 때 활성화
   */
  const submitBtnCheck = useCallback(
    (index) => {
      if (inputText[index]?.length > 0) {
        setValidate(true);
        setOutputObj(null);
      } else {
        setValidate(false);
      }
    },
    [inputText],
  );

  /**
   * Textarea 글자 입력 핸들러
   *
   * @param {object} e 텍스트 입력 이벤트
   * @param {number} index input 인덱스
   */
  const textInputHandler = useCallback(
    (e, index) => {
      const { value } = e.target;
      const textList = inputText;
      textList[index] = value;
      setInputText({ ...textList });
      submitBtnCheck(index);
    },
    [inputText, submitBtnCheck],
  );

  /**
   * API 호출
   * 각각 서비스에 해당하는 포맷, 주소로 API 호출
   * 결과 분석
   *
   * @param {object} info 서비스 API 정보
   * @param {string} url 서비스 API  URL 정보
   */
  const runAnalysis = async (info, apiUrl) => {
    let body = new FormData();
    const json = {};
    let header = { 'Content-Type': 'application/json;charset=UTF-8' };

    // API info
    const inputFormList = info.data_input_form_list;
    inputFormList.forEach(({ api_key: apiKey, category, location }, idx) => {
      if (location === 'file') {
        header = {
          'Content-Type': 'multipart/form-data',
          Accept: 'application/json',
          type: 'formData',
          'Cache-Control': 'no-cache; no-store; must-revalidate;',
          Pragma: 'no-cache',
        };
      }
      switch (category) {
        case 'text':
          if (location === 'body' || location === 'json') {
            if (inputText[idx]) {
              json[`${apiKey}`] = inputText[idx];
            }
          } else {
            if (inputText[idx]) {
              body.append(`${apiKey}`, inputText[idx]);
            }
          }
          break;
        case 'image':
          if (selectedImage[idx]) {
            body.append(`${apiKey}`, selectedImage[idx]);
          }
          break;
        case 'canvas-image':
          if (selectedCanvas) {
            body.append(`${apiKey}`, selectedCanvas);
          }
          break;
        case 'canvas-coordinate':
          const coordinates = getCoordinate();
          if (coordinates) {
            body.append(`${apiKey}`, coordinates);
          }
          break;
        case 'audio':
          if (selectedAudio[idx]) {
            body.append(`${apiKey}`, selectedAudio[idx]);
          }
          break;
        case 'video':
          if (selectedVideo[idx]) {
            body.append(`${apiKey}`, selectedVideo[idx]);
          }
          break;
        case 'csv':
          if (selectedCSV[idx]) {
            body.append(`${apiKey}`, selectedCSV[idx]);
          }
          break;
        default:
          toast.error('No match input category');
          if (location === 'body') {
            json[`${apiKey}`] = '';
          } else {
            body.append(`${apiKey}`, '');
          }
      }
    });
    // location body(json)만 있는 경우
    if (Object.keys(json).length !== 0) {
      body = json;
    }

    setLoading(true);
    const url = apiUrl.replace('http:', window.location.protocol);
    const method = info.api_method;
    const response = await network.callServiceApi({
      url,
      method,
      body,
      header,
    });
    const { status, message } = response;

    if (status === 200) {
      const { data, statusText, time, headers } = response;
      const outputStatus = {
        status: `${status} ${statusText}`,
        time: `${time}ms`,
        size: headers['content-length']
          ? convertBinaryByte(`${headers['content-length']}`)
          : '-',
      };
      setOutputObj(data);
      setOutputStatus(outputStatus);
      setLoading(false);
    } else if (status === -1) {
      window.open(url, '_blank');
      setLoading(false);
    } else {
      setLoading(false);
      toast.error(message);
    }
    trackingEvent({
      category: 'User Test Page',
      action: 'Run Analysis ',
    });
  };

  /**
   * 서비스 목록으로 돌아가기
   */
  const goBack = () => {
    trackingEvent({
      category: 'User Test Page',
      action: 'Move To Prev Page',
    });
    history.goBack();
  };

  /**
   * JSON 파일 보기 (모달)
   */
  const viewJson = () => {
    dispatch(
      openModal({
        modalType: 'SHOW_JSON',
        modalData: {
          submit: {
            text: 'confirm.label',
            func: () => {
              dispatch(closeModal('SHOW_JSON'));
            },
          },
          jsonData: outputObj,
        },
      }),
    );
  };

  /**
   * 캔버스 - 마우스 이동
   * 마우스 움질일 때 좌표 계산
   * @param {object} e mousemove 이벤트
   */
  const mouseMoveHandler = useCallback(
    (e) => {
      if (!drag) return null;

      if (drag) {
        const newRect = JSON.parse(JSON.stringify(rect));
        if (canvasWidth > 1562) {
          ctx.clearRect(0, 0, 1562, autoLength);
          ctx.drawImage(imageObj, 0, 0, 1562, autoLength);
        } else {
          ctx.clearRect(0, 0, canvasWidth, canvasHeight);
          ctx.drawImage(imageObj, 0, 0, canvasWidth, canvasHeight);
        }

        // if (isWidthLongerThanHeight) {
        //   ctx.clearRect(0, 0, 1562, autoLength);
        //   ctx.drawImage(imageObj, 0, 0, 1562, autoLength);
        // } else {
        //   ctx.clearRect(0, 0, autoLength, 1200);
        //   ctx.drawImage(imageObj, 0, 0, autoLength, 1200);
        // }

        newRect.w = e.nativeEvent.offsetX - rect.startX;
        newRect.h = e.nativeEvent.offsetY - rect.startY;

        ctx.strokeStyle = '#0e4bff';
        ctx.lineWidth = 3;

        // 사각형 그리기
        ctx.strokeRect(newRect.startX, newRect.startY, newRect.w, newRect.h);
        setRect({ ...newRect });
      }
    },
    [
      autoLength,
      ctx,
      drag,
      imageObj,
      // isWidthLongerThanHeight,
      rect,
      canvasWidth,
      canvasHeight,
    ],
  );

  /**
   * 캔버스 - 마우스 클릭 Down
   * 마우스 클릭 시 시작 지점 추가, 그리기 모드로 변경
   *
   * @param {object} e mousedown 이벤트
   */
  const mouseDownHandler = useCallback(
    (e) => {
      setDrag(true);
      const newRect = JSON.parse(JSON.stringify(rect));
      newRect.startX = e.nativeEvent.offsetX;
      newRect.startY = e.nativeEvent.offsetY;
      setRect(newRect);
    },
    [rect],
  );

  /**
   * 캔버스 - 마우스 클릭 UP
   * 마우스 클릭 뗐을 때 좌표계산
   *
   */
  const mouseUpHandler = useCallback(() => {
    setDrag(false);
    const newRect = JSON.parse(JSON.stringify(rect));

    newRect.endX = newRect.startX + newRect.w;
    newRect.endY = newRect.startY + newRect.h;

    setRect({ ...newRect });
  }, [rect]);

  const resetFunc = useCallback(() => {
    if (ctx !== null) {
      // 이미 있을 경우 초기화
      ctx.clearRect(0, 0, canvasWidth, canvasHeight);
    }
    drawCanvas(selectedCanvas);
  }, [canvasHeight, canvasWidth, ctx, drawCanvas, selectedCanvas]);

  useEffect(() => {
    loadModalComponent('SHOW_JSON');
  }, []);

  useEffect(() => {
    if (fileUpload) {
      const canvas = canvasRef.current;
      setCtx(canvas.getContext('2d'));
      resetFunc();
    }
    return () => setFileUpload(null);
  }, [fileUpload, resetFunc]);

  useEffect(() => {
    getServiceData();
  }, [getServiceData]);

  useEffect(() => {
    // Text용 btn check
    submitBtnCheck();
  }, [inputText, submitBtnCheck]);

  return (
    <UserTestContent
      inputText={inputText}
      serviceData={serviceData}
      selectedAudio={selectedAudio}
      selectedAudioSrc={selectedAudioSrc}
      selectedCSV={selectedCSV}
      selectedCSVSrc={selectedCSVSrc}
      selectedCanvas={selectedCanvas}
      selectedCanvasSrc={selectedCanvasSrc}
      selectedVideo={selectedVideo}
      selectedVideoSrc={selectedVideoSrc}
      selectedImage={selectedImage}
      selectedImageSrc={selectedImageSrc}
      goBack={goBack}
      textInputHandler={textInputHandler}
      fileInputHandler={fileInputHandler}
      canvasInputHandler={canvasInputHandler}
      canvasRef={canvasRef}
      canvasWidth={canvasWidth}
      canvasHeight={canvasHeight}
      outputObj={outputObj}
      outputStatus={outputStatus}
      runAnalysis={runAnalysis}
      viewJson={viewJson}
      loading={loading}
      validate={validate}
      mouseMoveHandler={mouseMoveHandler}
      mouseDownHandler={mouseDownHandler}
      mouseUpHandler={mouseUpHandler}
    />
  );
}

export default UserTestPage;
