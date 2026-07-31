import Responsive from 'react-responsive';
export const TabletHorizontal = (props) => (
  <Responsive {...props} maxWidth={1366} minWidth={1025} />
);
export const TabletVertical = (props) => (
  <Responsive {...props} minWidth={1024} />
);
export const Default = (props) => <Responsive {...props} minWidth={1367} />;

export default {
  TabletHorizontal,
  TabletVertical,
  Default,
};
