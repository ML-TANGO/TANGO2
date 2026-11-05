import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import useParentScrollListeners from './useScrollParent';

const root = document.getElementById('aside-cont');

const calTooltipPosition = (
  direction,
  targetRectValue,
  tooltipContentRectValue,
) => {
  if (direction === 'top') {
    return {
      top: targetRectValue.top - tooltipContentRectValue.height,
      left:
        targetRectValue.left -
        tooltipContentRectValue.width / 2 +
        targetRectValue.width / 2,
    };
  }

  if (direction === 'bottom') {
    return {
      top: targetRectValue.bottom,
      left:
        targetRectValue.left +
        targetRectValue.width / 2 -
        tooltipContentRectValue.width / 2,
    };
  }

  if (direction === 'bottom+6') {
    return {
      top: targetRectValue.bottom + 6,
      left:
        targetRectValue.left +
        targetRectValue.width / 2 -
        tooltipContentRectValue.width / 2,
    };
  }

  if (direction === 'topRight') {
    return {
      top: targetRectValue.top - tooltipContentRectValue.height,
      left: targetRectValue.left,
    };
  }
  return { top: 0, left: 0 };
};

const calTooltipStyle = (tooltipPosition) => {
  const { top, left } = tooltipPosition;
  return {
    position: 'absolute',
    left: `${left}px`,
    top: `${top}px`,
    zIndex: 1000,
  };
};

const handleUpdateTooltipPosition = (
  direction,
  isShowTooltip,
  targetRef,
  tooltipContentRef,
  setTooltipPosition,
) => {
  if (!targetRef.current || !tooltipContentRef.current || !isShowTooltip)
    return;
  const targetRectValue = targetRef.current.getBoundingClientRect();
  const tooltipContentRectValue =
    tooltipContentRef.current.getBoundingClientRect();

  const { top, left } = calTooltipPosition(
    direction,
    targetRectValue,
    tooltipContentRectValue,
  );
  setTooltipPosition({
    top,
    left,
  });
};

const TooltipPortal = ({
  targetRef,
  direction,
  isShowTooltip,
  customTooltipStyle = null,
  children,
}) => {
  const tooltipContentRef = useRef(null);
  const [tooltipPosition, setTooltipPosition] = useState({
    top: -99999999999,
    left: -99999999999,
  });

  const tooltipStyle = calTooltipStyle(tooltipPosition);

  useParentScrollListeners(targetRef, () =>
    handleUpdateTooltipPosition(
      direction,
      isShowTooltip,
      targetRef,
      tooltipContentRef,
      setTooltipPosition,
    ),
  );

  useEffect(() => {
    window.addEventListener('resize', () => {
      handleUpdateTooltipPosition(
        direction,
        isShowTooltip,
        targetRef,
        tooltipContentRef,
        setTooltipPosition,
      );
    });

    if (!targetRef.current || !tooltipContentRef.current || !isShowTooltip)
      return;
    handleUpdateTooltipPosition(
      direction,
      isShowTooltip,
      targetRef,
      tooltipContentRef,
      setTooltipPosition,
    );

    return () =>
      window.removeEventListener('resize', () =>
        handleUpdateTooltipPosition(
          direction,
          isShowTooltip,
          targetRef,
          tooltipContentRef,
          setTooltipPosition,
        ),
      );
  }, [direction, isShowTooltip, targetRef]);

  return (
    <>
      {root &&
        isShowTooltip &&
        createPortal(
          <div
            ref={tooltipContentRef}
            style={customTooltipStyle ? customTooltipStyle : tooltipStyle}
          >
            {children}
          </div>,
          root,
        )}
    </>
  );
};

export default TooltipPortal;
