import "./chunk-ROME4SDB.js";

// node_modules/i18next-localstorage-cache/dist/es/utils.js
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
function debounce(func, wait, immediate) {
  var timeout;
  return function() {
    var context = this, args = arguments;
    var later = function later2() {
      timeout = null;
      if (!immediate)
        func.apply(context, args);
    };
    var callNow = immediate && !timeout;
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
    if (callNow)
      func.apply(context, args);
  };
}

// node_modules/i18next-localstorage-cache/dist/es/index.js
var _createClass = function() {
  function defineProperties(target, props) {
    for (var i = 0; i < props.length; i++) {
      var descriptor = props[i];
      descriptor.enumerable = descriptor.enumerable || false;
      descriptor.configurable = true;
      if ("value" in descriptor)
        descriptor.writable = true;
      Object.defineProperty(target, descriptor.key, descriptor);
    }
  }
  return function(Constructor, protoProps, staticProps) {
    if (protoProps)
      defineProperties(Constructor.prototype, protoProps);
    if (staticProps)
      defineProperties(Constructor, staticProps);
    return Constructor;
  };
}();
function _classCallCheck(instance, Constructor) {
  if (!(instance instanceof Constructor)) {
    throw new TypeError("Cannot call a class as a function");
  }
}
var storage = {
  setItem: function setItem(key, value) {
    if (window.localStorage) {
      try {
        window.localStorage.setItem(key, value);
      } catch (e) {
      }
    }
  },
  getItem: function getItem(key, value) {
    if (window.localStorage) {
      try {
        return window.localStorage.getItem(key, value);
      } catch (e) {
      }
    }
    return void 0;
  }
};
function getDefaults() {
  return {
    enabled: false,
    prefix: "i18next_res_",
    expirationTime: 7 * 24 * 60 * 60 * 1e3,
    versions: {}
  };
}
var Cache = function() {
  function Cache2(services) {
    var options = arguments.length > 1 && arguments[1] !== void 0 ? arguments[1] : {};
    _classCallCheck(this, Cache2);
    this.init(services, options);
    this.type = "cache";
    this.debouncedStore = debounce(this.store, 1e4);
  }
  _createClass(Cache2, [{
    key: "init",
    value: function init(services) {
      var options = arguments.length > 1 && arguments[1] !== void 0 ? arguments[1] : {};
      this.services = services;
      this.options = defaults(options, this.options || {}, getDefaults());
    }
  }, {
    key: "load",
    value: function load(lngs, callback) {
      var _this = this;
      var store = {};
      var nowMS = (/* @__PURE__ */ new Date()).getTime();
      if (!window.localStorage || !lngs.length) {
        return callback(null, null);
      }
      var todo = lngs.length;
      lngs.forEach(function(lng) {
        var local = storage.getItem(_this.options.prefix + lng);
        if (local) {
          local = JSON.parse(local);
          if (
            // expiration field is mandatory, and should not be expired
            local.i18nStamp && local.i18nStamp + _this.options.expirationTime > nowMS && // there should be no language version set, or if it is, it should match the one in translation
            _this.options.versions[lng] === local.i18nVersion
          ) {
            delete local.i18nVersion;
            store[lng] = local;
          }
        }
        todo -= 1;
        if (todo === 0) {
          callback(null, store);
        }
      });
      return void 0;
    }
  }, {
    key: "store",
    value: function store(storeParam) {
      var store2 = storeParam;
      if (window.localStorage) {
        for (var m in store2) {
          store2[m].i18nStamp = (/* @__PURE__ */ new Date()).getTime();
          if (this.options.versions[m]) {
            store2[m].i18nVersion = this.options.versions[m];
          }
          storage.setItem(this.options.prefix + m, JSON.stringify(store2[m]));
        }
      }
    }
  }, {
    key: "save",
    value: function save(store) {
      this.debouncedStore(store);
    }
  }]);
  return Cache2;
}();
Cache.type = "cache";
var es_default = Cache;
export {
  es_default as default
};
//# sourceMappingURL=i18next-localstorage-cache.js.map
