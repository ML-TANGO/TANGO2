import IcoJP from '@src/static/images/logo/ICO_Flightbase.svg';
import LogoJP from '@src/static/images/logo/BI_Flightbase_v.svg';
// import WhiteLogoJP from '@src/static/images/logo/BI_Flightbase_white.svg';
import WhiteLogoJP from '@src/static/images/logo/BI_Jonathan_white.svg';
// import FooterLogoJP from '@src/static/images/logo/BI_Flightbase.svg';
import FooterLogoJP from '@src/static/images/logo/BI_Jonathan.svg';
import LogoCBTP from '@src/static/images/custom/cbtp-logo.svg';
import SimpleLogoCBTP from '@src/static/images/custom/cbtp.svg';
import SimpleWhiteLogoCBTP from '@src/static/images/custom/cbtp-white.svg';
import LogoDGTP from '@src/static/images/custom/DGTP-logo.png';
import WhiteLogoDGTP from '@src/static/images/custom/DGTP-logo-white.png';
import SimpleLogoDGTP from '@src/static/images/custom/DGTP-en.png';
import LogoEtri from '@src/static/images/custom/DNA+DRONE.png';
import WhiteLogoEtri from '@src/static/images/custom/DNA+DRONE-white.png';
import LogoWellcare from '@src/static/images/custom/wellcare-logo.png';
import WhiteLogoWellcare from '@src/static/images/custom/wellcare-logo-white.png';
// import BlackLogoWellcare from '@src/static/images/custom/wellcare-logo-black.png';
// import LogoEdge from '@src/static/images/logo/edge-logo.png';
import MarkerLogo from '@src/static/images/logo/BI_Marker.svg';
import federatedLearningLogo from '@src/static/images/logo/federated-learning-footer-logo.png';

export const PARTNER = {
  jp: {
    logo: {
      symbol: IcoJP,
      header: WhiteLogoJP,
      sideNav: LogoJP,
      footer: FooterLogoJP,
      marker: MarkerLogo,
      federatedLearning: federatedLearningLogo,
    },
    siteUrl: 'https://www.acryl.ai/',
  },
  etri: {
    logo: {
      header: WhiteLogoEtri,
      sideNav: LogoEtri,
      footer: LogoEtri,
      marker: LogoEtri,
    },
    siteUrl: 'https://www.etri.re.kr/',
  },
  cbtp: {
    logo: {
      loginHeader: LogoCBTP,
      loginContents: SimpleLogoCBTP,
      header: SimpleWhiteLogoCBTP,
      sideNav: SimpleLogoCBTP,
      footer: FooterLogoJP,
    },
    siteUrl: 'https://www.cbtp.or.kr',
  },
  dgtp: {
    logo: {
      loginHeader: LogoDGTP,
      loginContents: SimpleLogoDGTP,
      header: WhiteLogoDGTP,
      sideNav: LogoDGTP,
      footer: FooterLogoJP,
      federatedLearning: federatedLearningLogo,
    },
    siteUrl: 'https://www.ttp.org/dgtp.do',
  },
  wellcare: {
    logo: {
      loginHeader: LogoWellcare,
      header: WhiteLogoWellcare,
      footer: LogoWellcare,
    },
    siteUrl: 'https://wellcare.or.kr/',
  },
};
