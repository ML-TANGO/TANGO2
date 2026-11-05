import dayjs from '../../modules/dayjs/dayjs.min.js';
import utc from '../../modules/dayjs/plugin/utc.js';

dayjs.extend(utc);
var DATE_FORM = 'YYYY-MM-DD';
var DATE_TIME_FORM = 'YYYY-MM-DD HH:mm:ss';
var MAXIMAL_TIME = '2099-12-31 23:59:59';
var MINIMAL_TIME = '1900-01-01 00:00:00';
var DATE_PATTERN = /^(19|20)\d{2}-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[0-1])$/;
var nowLocalTime = function (format) {
    return dayjs()
        .local()
        .format(format || DATE_FORM);
};

export { DATE_FORM, DATE_PATTERN, DATE_TIME_FORM, MAXIMAL_TIME, MINIMAL_TIME, nowLocalTime };
//# sourceMappingURL=datetimeUtils.js.map
