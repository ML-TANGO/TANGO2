import {
  _classCallCheck,
  _createClass,
  _defineProperty,
  _typeof
} from "./chunk-JQAXZYAK.js";
import "./chunk-ROME4SDB.js";

// node_modules/i18next-xhr-backend/dist/esm/i18nextXHRBackend.js
var arr = [];
var each = arr.forEach;
var slice = arr.slice;
function defaults(obj) {
  each.call(slice.call(arguments, 1), function(source) {
    if (source) {
      for (var prop in source) {
        if (obj[prop] === void 0)
          obj[prop] = source[prop];
      }
    }
  });
  return obj;
}
function addQueryString(url, params) {
  if (params && _typeof(params) === "object") {
    var queryString = "", e = encodeURIComponent;
    for (var paramName in params) {
      queryString += "&" + e(paramName) + "=" + e(params[paramName]);
    }
    if (!queryString) {
      return url;
    }
    url = url + (url.indexOf("?") !== -1 ? "&" : "?") + queryString.slice(1);
  }
  return url;
}
function ajax(url, options, callback, data, cache) {
  if (data && _typeof(data) === "object") {
    if (!cache) {
      data["_t"] = /* @__PURE__ */ new Date();
    }
    data = addQueryString("", data).slice(1);
  }
  if (options.queryStringParams) {
    url = addQueryString(url, options.queryStringParams);
  }
  try {
    var x;
    if (XMLHttpRequest) {
      x = new XMLHttpRequest();
    } else {
      x = new ActiveXObject("MSXML2.XMLHTTP.3.0");
    }
    x.open(data ? "POST" : "GET", url, 1);
    if (!options.crossDomain) {
      x.setRequestHeader("X-Requested-With", "XMLHttpRequest");
    }
    x.withCredentials = !!options.withCredentials;
    if (data) {
      x.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    }
    if (x.overrideMimeType) {
      x.overrideMimeType("application/json");
    }
    var h = options.customHeaders;
    h = typeof h === "function" ? h() : h;
    if (h) {
      for (var i in h) {
        x.setRequestHeader(i, h[i]);
      }
    }
    x.onreadystatechange = function() {
      x.readyState > 3 && callback && callback(x.responseText, x);
    };
    x.send(data);
  } catch (e) {
    console && console.log(e);
  }
}
function getDefaults() {
  return {
    loadPath: "/locales/{{lng}}/{{ns}}.json",
    addPath: "/locales/add/{{lng}}/{{ns}}",
    allowMultiLoading: false,
    parse: JSON.parse,
    parsePayload: function parsePayload(namespace, key, fallbackValue) {
      return _defineProperty({}, key, fallbackValue || "");
    },
    crossDomain: false,
    ajax
  };
}
var Backend = function() {
  function Backend2(services) {
    var options = arguments.length > 1 && arguments[1] !== void 0 ? arguments[1] : {};
    _classCallCheck(this, Backend2);
    this.init(services, options);
    this.type = "backend";
  }
  _createClass(Backend2, [{
    key: "init",
    value: function init(services) {
      var options = arguments.length > 1 && arguments[1] !== void 0 ? arguments[1] : {};
      this.services = services;
      this.options = defaults(options, this.options || {}, getDefaults());
    }
  }, {
    key: "readMulti",
    value: function readMulti(languages, namespaces, callback) {
      var loadPath = this.options.loadPath;
      if (typeof this.options.loadPath === "function") {
        loadPath = this.options.loadPath(languages, namespaces);
      }
      var url = this.services.interpolator.interpolate(loadPath, {
        lng: languages.join("+"),
        ns: namespaces.join("+")
      });
      this.loadUrl(url, callback);
    }
  }, {
    key: "read",
    value: function read(language, namespace, callback) {
      var loadPath = this.options.loadPath;
      if (typeof this.options.loadPath === "function") {
        loadPath = this.options.loadPath([language], [namespace]);
      }
      var url = this.services.interpolator.interpolate(loadPath, {
        lng: language,
        ns: namespace
      });
      this.loadUrl(url, callback);
    }
  }, {
    key: "loadUrl",
    value: function loadUrl(url, callback) {
      var _this = this;
      this.options.ajax(url, this.options, function(data, xhr) {
        if (xhr.status >= 500 && xhr.status < 600)
          return callback(
            "failed loading " + url,
            true
            /* retry */
          );
        if (xhr.status >= 400 && xhr.status < 500)
          return callback(
            "failed loading " + url,
            false
            /* no retry */
          );
        var ret, err;
        try {
          ret = _this.options.parse(data, url);
        } catch (e) {
          err = "failed parsing " + url + " to json";
        }
        if (err)
          return callback(err, false);
        callback(null, ret);
      });
    }
  }, {
    key: "create",
    value: function create(languages, namespace, key, fallbackValue) {
      var _this2 = this;
      if (typeof languages === "string")
        languages = [languages];
      var payload = this.options.parsePayload(namespace, key, fallbackValue);
      languages.forEach(function(lng) {
        var url = _this2.services.interpolator.interpolate(_this2.options.addPath, {
          lng,
          ns: namespace
        });
        _this2.options.ajax(url, _this2.options, function(data, xhr) {
        }, payload);
      });
    }
  }]);
  return Backend2;
}();
Backend.type = "backend";
var i18nextXHRBackend_default = Backend;
export {
  i18nextXHRBackend_default as default
};
//# sourceMappingURL=i18next-xhr-backend.js.map
