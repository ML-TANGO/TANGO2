import classNames from 'classnames/bind';
import style from './OutputImage.module.scss';
const cx = classNames.bind(style);

const OutputImage = ({ output, objectKey }) => {
  // 이미지 클릭시 원본 크기로 팝업 보기
  const viewImage = (img) => {
    const newImage = new Image();
    newImage.src = img;
    if (newImage.width !== 0 && newImage.height !== 0) {
      const W = newImage.width;
      const H = newImage.height;
      const O = `width=${W},height=${H},scrollbars=yes`;
      const imgWindow = window.open('', '', O);
      imgWindow.document.write(
        '<html><head><title>결과 원본보기</title></head>',
      );
      imgWindow.document.write('<body topmargin=0 leftmargin=0>');
      imgWindow.document.write(
        `<img src=${img} onclick='self.close()' style='cursor:pointer;' title ='클릭하시면 창이 닫힙니다.'></body></html>`,
      );
      imgWindow.document.close();
    }
  };
  return (
    <div className={cx('result-image')}>
      <label className={cx('title')}>{objectKey}</label>
      <img
        className={cx('image')}
        src={`data:image/jpeg;base64,${output[objectKey]}`}
        alt='output'
        onClick={() => viewImage(`data:image/jpeg;base64,${output[objectKey]}`)}
      />
    </div>
  );
};

export default OutputImage;
