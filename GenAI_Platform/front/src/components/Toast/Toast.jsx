/* eslint-disable import/no-anonymous-default-export */
import './Toast.scss';
import { toast as _toast } from 'react-toastify';

export default {
  success: (title = '', subtitle = '') => {
    _toast.success(
      <>
        <span className='Toastify__toast-body-title'>{title}</span>{' '}
        <span className='Toastify__toast-body-subtitle'>{subtitle}</span>
      </>,
    );
  },
  info: (title = '', subtitle = '') => {
    _toast.info(
      <>
        <span className='Toastify__toast-body-title'>{title}</span>{' '}
        <span className='Toastify__toast-body-subtitle'>{subtitle}</span>
      </>,
    );
  },
  error: (title = '', subtitle = '') => {
    _toast.error(
      <>
        <span className='Toastify__toast-body-title'>{title}</span>{' '}
        <span className='Toastify__toast-body-subtitle'>{subtitle}</span>
      </>,
    );
  },
  warning: (title = '', subtitle = '') => {
    _toast.warning(
      <>
        <span className='Toastify__toast-body-title'>{title}</span>{' '}
        <span className='Toastify__toast-body-subtitle'>{subtitle}</span>
      </>,
    );
  },
};
