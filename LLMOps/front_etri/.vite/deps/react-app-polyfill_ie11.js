import {
  require_es_array_concat,
  require_es_array_from,
  require_es_json_to_string_tag,
  require_es_math_to_string_tag,
  require_es_object_to_string,
  require_es_reflect_to_string_tag,
  require_es_string_iterator,
  require_es_symbol,
  require_es_symbol_async_iterator,
  require_es_symbol_description,
  require_es_symbol_has_instance,
  require_es_symbol_is_concat_spreadable,
  require_es_symbol_iterator,
  require_es_symbol_match,
  require_es_symbol_match_all,
  require_es_symbol_replace,
  require_es_symbol_search,
  require_es_symbol_species,
  require_es_symbol_split,
  require_es_symbol_to_primitive,
  require_es_symbol_to_string_tag,
  require_es_symbol_unscopables,
  require_export,
  require_function_uncurry_this,
  require_get_built_in,
  require_global_this,
  require_is_symbol,
  require_object_define_property,
  require_object_get_own_property_descriptor,
  require_path,
  require_shared,
  require_web_dom_collections_iterator,
  require_well_known_symbol,
  require_well_known_symbol_define
} from "./chunk-32TVRLJU.js";
import {
  require_object_assign
} from "./chunk-NYQDER2B.js";
import {
  __commonJS,
  __esm,
  __export,
  __toCommonJS
} from "./chunk-ROME4SDB.js";

// node_modules/asap/browser-raw.js
var require_browser_raw = __commonJS({
  "node_modules/asap/browser-raw.js"(exports, module) {
    "use strict";
    module.exports = rawAsap;
    function rawAsap(task) {
      if (!queue.length) {
        requestFlush();
        flushing = true;
      }
      queue[queue.length] = task;
    }
    var queue = [];
    var flushing = false;
    var requestFlush;
    var index = 0;
    var capacity = 1024;
    function flush() {
      while (index < queue.length) {
        var currentIndex = index;
        index = index + 1;
        queue[currentIndex].call();
        if (index > capacity) {
          for (var scan = 0, newLength = queue.length - index; scan < newLength; scan++) {
            queue[scan] = queue[scan + index];
          }
          queue.length -= index;
          index = 0;
        }
      }
      queue.length = 0;
      index = 0;
      flushing = false;
    }
    var scope = typeof global !== "undefined" ? global : self;
    var BrowserMutationObserver = scope.MutationObserver || scope.WebKitMutationObserver;
    if (typeof BrowserMutationObserver === "function") {
      requestFlush = makeRequestCallFromMutationObserver(flush);
    } else {
      requestFlush = makeRequestCallFromTimer(flush);
    }
    rawAsap.requestFlush = requestFlush;
    function makeRequestCallFromMutationObserver(callback) {
      var toggle = 1;
      var observer = new BrowserMutationObserver(callback);
      var node = document.createTextNode("");
      observer.observe(node, { characterData: true });
      return function requestCall() {
        toggle = -toggle;
        node.data = toggle;
      };
    }
    function makeRequestCallFromTimer(callback) {
      return function requestCall() {
        var timeoutHandle = setTimeout(handleTimer, 0);
        var intervalHandle = setInterval(handleTimer, 50);
        function handleTimer() {
          clearTimeout(timeoutHandle);
          clearInterval(intervalHandle);
          callback();
        }
      };
    }
    rawAsap.makeRequestCallFromTimer = makeRequestCallFromTimer;
  }
});

// node_modules/promise/lib/core.js
var require_core = __commonJS({
  "node_modules/promise/lib/core.js"(exports, module) {
    "use strict";
    var asap = require_browser_raw();
    function noop() {
    }
    var LAST_ERROR = null;
    var IS_ERROR = {};
    function getThen(obj) {
      try {
        return obj.then;
      } catch (ex) {
        LAST_ERROR = ex;
        return IS_ERROR;
      }
    }
    function tryCallOne(fn, a) {
      try {
        return fn(a);
      } catch (ex) {
        LAST_ERROR = ex;
        return IS_ERROR;
      }
    }
    function tryCallTwo(fn, a, b) {
      try {
        fn(a, b);
      } catch (ex) {
        LAST_ERROR = ex;
        return IS_ERROR;
      }
    }
    module.exports = Promise2;
    function Promise2(fn) {
      if (typeof this !== "object") {
        throw new TypeError("Promises must be constructed via new");
      }
      if (typeof fn !== "function") {
        throw new TypeError("Promise constructor's argument is not a function");
      }
      this._x = 0;
      this._y = 0;
      this._z = null;
      this._A = null;
      if (fn === noop)
        return;
      doResolve(fn, this);
    }
    Promise2._B = null;
    Promise2._C = null;
    Promise2._D = noop;
    Promise2.prototype.then = function(onFulfilled, onRejected) {
      if (this.constructor !== Promise2) {
        return safeThen(this, onFulfilled, onRejected);
      }
      var res = new Promise2(noop);
      handle(this, new Handler(onFulfilled, onRejected, res));
      return res;
    };
    function safeThen(self2, onFulfilled, onRejected) {
      return new self2.constructor(function(resolve2, reject2) {
        var res = new Promise2(noop);
        res.then(resolve2, reject2);
        handle(self2, new Handler(onFulfilled, onRejected, res));
      });
    }
    function handle(self2, deferred) {
      while (self2._y === 3) {
        self2 = self2._z;
      }
      if (Promise2._B) {
        Promise2._B(self2);
      }
      if (self2._y === 0) {
        if (self2._x === 0) {
          self2._x = 1;
          self2._A = deferred;
          return;
        }
        if (self2._x === 1) {
          self2._x = 2;
          self2._A = [self2._A, deferred];
          return;
        }
        self2._A.push(deferred);
        return;
      }
      handleResolved(self2, deferred);
    }
    function handleResolved(self2, deferred) {
      asap(function() {
        var cb = self2._y === 1 ? deferred.onFulfilled : deferred.onRejected;
        if (cb === null) {
          if (self2._y === 1) {
            resolve(deferred.promise, self2._z);
          } else {
            reject(deferred.promise, self2._z);
          }
          return;
        }
        var ret = tryCallOne(cb, self2._z);
        if (ret === IS_ERROR) {
          reject(deferred.promise, LAST_ERROR);
        } else {
          resolve(deferred.promise, ret);
        }
      });
    }
    function resolve(self2, newValue) {
      if (newValue === self2) {
        return reject(
          self2,
          new TypeError("A promise cannot be resolved with itself.")
        );
      }
      if (newValue && (typeof newValue === "object" || typeof newValue === "function")) {
        var then = getThen(newValue);
        if (then === IS_ERROR) {
          return reject(self2, LAST_ERROR);
        }
        if (then === self2.then && newValue instanceof Promise2) {
          self2._y = 3;
          self2._z = newValue;
          finale(self2);
          return;
        } else if (typeof then === "function") {
          doResolve(then.bind(newValue), self2);
          return;
        }
      }
      self2._y = 1;
      self2._z = newValue;
      finale(self2);
    }
    function reject(self2, newValue) {
      self2._y = 2;
      self2._z = newValue;
      if (Promise2._C) {
        Promise2._C(self2, newValue);
      }
      finale(self2);
    }
    function finale(self2) {
      if (self2._x === 1) {
        handle(self2, self2._A);
        self2._A = null;
      }
      if (self2._x === 2) {
        for (var i = 0; i < self2._A.length; i++) {
          handle(self2, self2._A[i]);
        }
        self2._A = null;
      }
    }
    function Handler(onFulfilled, onRejected, promise) {
      this.onFulfilled = typeof onFulfilled === "function" ? onFulfilled : null;
      this.onRejected = typeof onRejected === "function" ? onRejected : null;
      this.promise = promise;
    }
    function doResolve(fn, promise) {
      var done = false;
      var res = tryCallTwo(fn, function(value) {
        if (done)
          return;
        done = true;
        resolve(promise, value);
      }, function(reason) {
        if (done)
          return;
        done = true;
        reject(promise, reason);
      });
      if (!done && res === IS_ERROR) {
        done = true;
        reject(promise, LAST_ERROR);
      }
    }
  }
});

// node_modules/promise/lib/rejection-tracking.js
var require_rejection_tracking = __commonJS({
  "node_modules/promise/lib/rejection-tracking.js"(exports) {
    "use strict";
    var Promise2 = require_core();
    var DEFAULT_WHITELIST = [
      ReferenceError,
      TypeError,
      RangeError
    ];
    var enabled = false;
    exports.disable = disable;
    function disable() {
      enabled = false;
      Promise2._B = null;
      Promise2._C = null;
    }
    exports.enable = enable;
    function enable(options) {
      options = options || {};
      if (enabled)
        disable();
      enabled = true;
      var id = 0;
      var displayId = 0;
      var rejections = {};
      Promise2._B = function(promise) {
        if (promise._y === 2 && // IS REJECTED
        rejections[promise._E]) {
          if (rejections[promise._E].logged) {
            onHandled(promise._E);
          } else {
            clearTimeout(rejections[promise._E].timeout);
          }
          delete rejections[promise._E];
        }
      };
      Promise2._C = function(promise, err) {
        if (promise._x === 0) {
          promise._E = id++;
          rejections[promise._E] = {
            displayId: null,
            error: err,
            timeout: setTimeout(
              onUnhandled.bind(null, promise._E),
              // For reference errors and type errors, this almost always
              // means the programmer made a mistake, so log them after just
              // 100ms
              // otherwise, wait 2 seconds to see if they get handled
              matchWhitelist(err, DEFAULT_WHITELIST) ? 100 : 2e3
            ),
            logged: false
          };
        }
      };
      function onUnhandled(id2) {
        if (options.allRejections || matchWhitelist(
          rejections[id2].error,
          options.whitelist || DEFAULT_WHITELIST
        )) {
          rejections[id2].displayId = displayId++;
          if (options.onUnhandled) {
            rejections[id2].logged = true;
            options.onUnhandled(
              rejections[id2].displayId,
              rejections[id2].error
            );
          } else {
            rejections[id2].logged = true;
            logError(
              rejections[id2].displayId,
              rejections[id2].error
            );
          }
        }
      }
      function onHandled(id2) {
        if (rejections[id2].logged) {
          if (options.onHandled) {
            options.onHandled(rejections[id2].displayId, rejections[id2].error);
          } else if (!rejections[id2].onUnhandled) {
            console.warn(
              "Promise Rejection Handled (id: " + rejections[id2].displayId + "):"
            );
            console.warn(
              '  This means you can ignore any previous messages of the form "Possible Unhandled Promise Rejection" with id ' + rejections[id2].displayId + "."
            );
          }
        }
      }
    }
    function logError(id, error) {
      console.warn("Possible Unhandled Promise Rejection (id: " + id + "):");
      var errStr = (error && (error.stack || error)) + "";
      errStr.split("\n").forEach(function(line) {
        console.warn("  " + line);
      });
    }
    function matchWhitelist(error, list) {
      return list.some(function(cls) {
        return error instanceof cls;
      });
    }
  }
});

// node_modules/promise/lib/es6-extensions.js
var require_es6_extensions = __commonJS({
  "node_modules/promise/lib/es6-extensions.js"(exports, module) {
    "use strict";
    var Promise2 = require_core();
    module.exports = Promise2;
    var TRUE = valuePromise(true);
    var FALSE = valuePromise(false);
    var NULL = valuePromise(null);
    var UNDEFINED = valuePromise(void 0);
    var ZERO = valuePromise(0);
    var EMPTYSTRING = valuePromise("");
    function valuePromise(value) {
      var p = new Promise2(Promise2._D);
      p._y = 1;
      p._z = value;
      return p;
    }
    Promise2.resolve = function(value) {
      if (value instanceof Promise2)
        return value;
      if (value === null)
        return NULL;
      if (value === void 0)
        return UNDEFINED;
      if (value === true)
        return TRUE;
      if (value === false)
        return FALSE;
      if (value === 0)
        return ZERO;
      if (value === "")
        return EMPTYSTRING;
      if (typeof value === "object" || typeof value === "function") {
        try {
          var then = value.then;
          if (typeof then === "function") {
            return new Promise2(then.bind(value));
          }
        } catch (ex) {
          return new Promise2(function(resolve, reject) {
            reject(ex);
          });
        }
      }
      return valuePromise(value);
    };
    var iterableToArray = function(iterable) {
      if (typeof Array.from === "function") {
        iterableToArray = Array.from;
        return Array.from(iterable);
      }
      iterableToArray = function(x) {
        return Array.prototype.slice.call(x);
      };
      return Array.prototype.slice.call(iterable);
    };
    Promise2.all = function(arr) {
      var args = iterableToArray(arr);
      return new Promise2(function(resolve, reject) {
        if (args.length === 0)
          return resolve([]);
        var remaining = args.length;
        function res(i2, val) {
          if (val && (typeof val === "object" || typeof val === "function")) {
            if (val instanceof Promise2 && val.then === Promise2.prototype.then) {
              while (val._y === 3) {
                val = val._z;
              }
              if (val._y === 1)
                return res(i2, val._z);
              if (val._y === 2)
                reject(val._z);
              val.then(function(val2) {
                res(i2, val2);
              }, reject);
              return;
            } else {
              var then = val.then;
              if (typeof then === "function") {
                var p = new Promise2(then.bind(val));
                p.then(function(val2) {
                  res(i2, val2);
                }, reject);
                return;
              }
            }
          }
          args[i2] = val;
          if (--remaining === 0) {
            resolve(args);
          }
        }
        for (var i = 0; i < args.length; i++) {
          res(i, args[i]);
        }
      });
    };
    function onSettledFulfill(value) {
      return { status: "fulfilled", value };
    }
    function onSettledReject(reason) {
      return { status: "rejected", reason };
    }
    function mapAllSettled(item) {
      if (item && (typeof item === "object" || typeof item === "function")) {
        if (item instanceof Promise2 && item.then === Promise2.prototype.then) {
          return item.then(onSettledFulfill, onSettledReject);
        }
        var then = item.then;
        if (typeof then === "function") {
          return new Promise2(then.bind(item)).then(onSettledFulfill, onSettledReject);
        }
      }
      return onSettledFulfill(item);
    }
    Promise2.allSettled = function(iterable) {
      return Promise2.all(iterableToArray(iterable).map(mapAllSettled));
    };
    Promise2.reject = function(value) {
      return new Promise2(function(resolve, reject) {
        reject(value);
      });
    };
    Promise2.race = function(values) {
      return new Promise2(function(resolve, reject) {
        iterableToArray(values).forEach(function(value) {
          Promise2.resolve(value).then(resolve, reject);
        });
      });
    };
    Promise2.prototype["catch"] = function(onRejected) {
      return this.then(null, onRejected);
    };
    function getAggregateError(errors) {
      if (typeof AggregateError === "function") {
        return new AggregateError(errors, "All promises were rejected");
      }
      var error = new Error("All promises were rejected");
      error.name = "AggregateError";
      error.errors = errors;
      return error;
    }
    Promise2.any = function promiseAny(values) {
      return new Promise2(function(resolve, reject) {
        var promises = iterableToArray(values);
        var hasResolved = false;
        var rejectionReasons = [];
        function resolveOnce(value) {
          if (!hasResolved) {
            hasResolved = true;
            resolve(value);
          }
        }
        function rejectionCheck(reason) {
          rejectionReasons.push(reason);
          if (rejectionReasons.length === promises.length) {
            reject(getAggregateError(rejectionReasons));
          }
        }
        if (promises.length === 0) {
          reject(getAggregateError(rejectionReasons));
        } else {
          promises.forEach(function(value) {
            Promise2.resolve(value).then(resolveOnce, rejectionCheck);
          });
        }
      });
    };
  }
});

// node_modules/whatwg-fetch/fetch.js
var fetch_exports = {};
__export(fetch_exports, {
  DOMException: () => DOMException,
  Headers: () => Headers,
  Request: () => Request,
  Response: () => Response,
  fetch: () => fetch
});
function isDataView(obj) {
  return obj && DataView.prototype.isPrototypeOf(obj);
}
function normalizeName(name) {
  if (typeof name !== "string") {
    name = String(name);
  }
  if (/[^a-z0-9\-#$%&'*+.^_`|~!]/i.test(name) || name === "") {
    throw new TypeError('Invalid character in header field name: "' + name + '"');
  }
  return name.toLowerCase();
}
function normalizeValue(value) {
  if (typeof value !== "string") {
    value = String(value);
  }
  return value;
}
function iteratorFor(items) {
  var iterator = {
    next: function() {
      var value = items.shift();
      return { done: value === void 0, value };
    }
  };
  if (support.iterable) {
    iterator[Symbol.iterator] = function() {
      return iterator;
    };
  }
  return iterator;
}
function Headers(headers) {
  this.map = {};
  if (headers instanceof Headers) {
    headers.forEach(function(value, name) {
      this.append(name, value);
    }, this);
  } else if (Array.isArray(headers)) {
    headers.forEach(function(header) {
      if (header.length != 2) {
        throw new TypeError("Headers constructor: expected name/value pair to be length 2, found" + header.length);
      }
      this.append(header[0], header[1]);
    }, this);
  } else if (headers) {
    Object.getOwnPropertyNames(headers).forEach(function(name) {
      this.append(name, headers[name]);
    }, this);
  }
}
function consumed(body) {
  if (body._noBody)
    return;
  if (body.bodyUsed) {
    return Promise.reject(new TypeError("Already read"));
  }
  body.bodyUsed = true;
}
function fileReaderReady(reader) {
  return new Promise(function(resolve, reject) {
    reader.onload = function() {
      resolve(reader.result);
    };
    reader.onerror = function() {
      reject(reader.error);
    };
  });
}
function readBlobAsArrayBuffer(blob) {
  var reader = new FileReader();
  var promise = fileReaderReady(reader);
  reader.readAsArrayBuffer(blob);
  return promise;
}
function readBlobAsText(blob) {
  var reader = new FileReader();
  var promise = fileReaderReady(reader);
  var match = /charset=([A-Za-z0-9_-]+)/.exec(blob.type);
  var encoding = match ? match[1] : "utf-8";
  reader.readAsText(blob, encoding);
  return promise;
}
function readArrayBufferAsText(buf) {
  var view = new Uint8Array(buf);
  var chars = new Array(view.length);
  for (var i = 0; i < view.length; i++) {
    chars[i] = String.fromCharCode(view[i]);
  }
  return chars.join("");
}
function bufferClone(buf) {
  if (buf.slice) {
    return buf.slice(0);
  } else {
    var view = new Uint8Array(buf.byteLength);
    view.set(new Uint8Array(buf));
    return view.buffer;
  }
}
function Body() {
  this.bodyUsed = false;
  this._initBody = function(body) {
    this.bodyUsed = this.bodyUsed;
    this._bodyInit = body;
    if (!body) {
      this._noBody = true;
      this._bodyText = "";
    } else if (typeof body === "string") {
      this._bodyText = body;
    } else if (support.blob && Blob.prototype.isPrototypeOf(body)) {
      this._bodyBlob = body;
    } else if (support.formData && FormData.prototype.isPrototypeOf(body)) {
      this._bodyFormData = body;
    } else if (support.searchParams && URLSearchParams.prototype.isPrototypeOf(body)) {
      this._bodyText = body.toString();
    } else if (support.arrayBuffer && support.blob && isDataView(body)) {
      this._bodyArrayBuffer = bufferClone(body.buffer);
      this._bodyInit = new Blob([this._bodyArrayBuffer]);
    } else if (support.arrayBuffer && (ArrayBuffer.prototype.isPrototypeOf(body) || isArrayBufferView(body))) {
      this._bodyArrayBuffer = bufferClone(body);
    } else {
      this._bodyText = body = Object.prototype.toString.call(body);
    }
    if (!this.headers.get("content-type")) {
      if (typeof body === "string") {
        this.headers.set("content-type", "text/plain;charset=UTF-8");
      } else if (this._bodyBlob && this._bodyBlob.type) {
        this.headers.set("content-type", this._bodyBlob.type);
      } else if (support.searchParams && URLSearchParams.prototype.isPrototypeOf(body)) {
        this.headers.set("content-type", "application/x-www-form-urlencoded;charset=UTF-8");
      }
    }
  };
  if (support.blob) {
    this.blob = function() {
      var rejected = consumed(this);
      if (rejected) {
        return rejected;
      }
      if (this._bodyBlob) {
        return Promise.resolve(this._bodyBlob);
      } else if (this._bodyArrayBuffer) {
        return Promise.resolve(new Blob([this._bodyArrayBuffer]));
      } else if (this._bodyFormData) {
        throw new Error("could not read FormData body as blob");
      } else {
        return Promise.resolve(new Blob([this._bodyText]));
      }
    };
  }
  this.arrayBuffer = function() {
    if (this._bodyArrayBuffer) {
      var isConsumed = consumed(this);
      if (isConsumed) {
        return isConsumed;
      } else if (ArrayBuffer.isView(this._bodyArrayBuffer)) {
        return Promise.resolve(
          this._bodyArrayBuffer.buffer.slice(
            this._bodyArrayBuffer.byteOffset,
            this._bodyArrayBuffer.byteOffset + this._bodyArrayBuffer.byteLength
          )
        );
      } else {
        return Promise.resolve(this._bodyArrayBuffer);
      }
    } else if (support.blob) {
      return this.blob().then(readBlobAsArrayBuffer);
    } else {
      throw new Error("could not read as ArrayBuffer");
    }
  };
  this.text = function() {
    var rejected = consumed(this);
    if (rejected) {
      return rejected;
    }
    if (this._bodyBlob) {
      return readBlobAsText(this._bodyBlob);
    } else if (this._bodyArrayBuffer) {
      return Promise.resolve(readArrayBufferAsText(this._bodyArrayBuffer));
    } else if (this._bodyFormData) {
      throw new Error("could not read FormData body as text");
    } else {
      return Promise.resolve(this._bodyText);
    }
  };
  if (support.formData) {
    this.formData = function() {
      return this.text().then(decode);
    };
  }
  this.json = function() {
    return this.text().then(JSON.parse);
  };
  return this;
}
function normalizeMethod(method) {
  var upcased = method.toUpperCase();
  return methods.indexOf(upcased) > -1 ? upcased : method;
}
function Request(input, options) {
  if (!(this instanceof Request)) {
    throw new TypeError('Please use the "new" operator, this DOM object constructor cannot be called as a function.');
  }
  options = options || {};
  var body = options.body;
  if (input instanceof Request) {
    if (input.bodyUsed) {
      throw new TypeError("Already read");
    }
    this.url = input.url;
    this.credentials = input.credentials;
    if (!options.headers) {
      this.headers = new Headers(input.headers);
    }
    this.method = input.method;
    this.mode = input.mode;
    this.signal = input.signal;
    if (!body && input._bodyInit != null) {
      body = input._bodyInit;
      input.bodyUsed = true;
    }
  } else {
    this.url = String(input);
  }
  this.credentials = options.credentials || this.credentials || "same-origin";
  if (options.headers || !this.headers) {
    this.headers = new Headers(options.headers);
  }
  this.method = normalizeMethod(options.method || this.method || "GET");
  this.mode = options.mode || this.mode || null;
  this.signal = options.signal || this.signal || function() {
    if ("AbortController" in g) {
      var ctrl = new AbortController();
      return ctrl.signal;
    }
  }();
  this.referrer = null;
  if ((this.method === "GET" || this.method === "HEAD") && body) {
    throw new TypeError("Body not allowed for GET or HEAD requests");
  }
  this._initBody(body);
  if (this.method === "GET" || this.method === "HEAD") {
    if (options.cache === "no-store" || options.cache === "no-cache") {
      var reParamSearch = /([?&])_=[^&]*/;
      if (reParamSearch.test(this.url)) {
        this.url = this.url.replace(reParamSearch, "$1_=" + (/* @__PURE__ */ new Date()).getTime());
      } else {
        var reQueryString = /\?/;
        this.url += (reQueryString.test(this.url) ? "&" : "?") + "_=" + (/* @__PURE__ */ new Date()).getTime();
      }
    }
  }
}
function decode(body) {
  var form = new FormData();
  body.trim().split("&").forEach(function(bytes) {
    if (bytes) {
      var split = bytes.split("=");
      var name = split.shift().replace(/\+/g, " ");
      var value = split.join("=").replace(/\+/g, " ");
      form.append(decodeURIComponent(name), decodeURIComponent(value));
    }
  });
  return form;
}
function parseHeaders(rawHeaders) {
  var headers = new Headers();
  var preProcessedHeaders = rawHeaders.replace(/\r?\n[\t ]+/g, " ");
  preProcessedHeaders.split("\r").map(function(header) {
    return header.indexOf("\n") === 0 ? header.substr(1, header.length) : header;
  }).forEach(function(line) {
    var parts = line.split(":");
    var key = parts.shift().trim();
    if (key) {
      var value = parts.join(":").trim();
      try {
        headers.append(key, value);
      } catch (error) {
        console.warn("Response " + error.message);
      }
    }
  });
  return headers;
}
function Response(bodyInit, options) {
  if (!(this instanceof Response)) {
    throw new TypeError('Please use the "new" operator, this DOM object constructor cannot be called as a function.');
  }
  if (!options) {
    options = {};
  }
  this.type = "default";
  this.status = options.status === void 0 ? 200 : options.status;
  if (this.status < 200 || this.status > 599) {
    throw new RangeError("Failed to construct 'Response': The status provided (0) is outside the range [200, 599].");
  }
  this.ok = this.status >= 200 && this.status < 300;
  this.statusText = options.statusText === void 0 ? "" : "" + options.statusText;
  this.headers = new Headers(options.headers);
  this.url = options.url || "";
  this._initBody(bodyInit);
}
function fetch(input, init) {
  return new Promise(function(resolve, reject) {
    var request = new Request(input, init);
    if (request.signal && request.signal.aborted) {
      return reject(new DOMException("Aborted", "AbortError"));
    }
    var xhr = new XMLHttpRequest();
    function abortXhr() {
      xhr.abort();
    }
    xhr.onload = function() {
      var options = {
        statusText: xhr.statusText,
        headers: parseHeaders(xhr.getAllResponseHeaders() || "")
      };
      if (request.url.indexOf("file://") === 0 && (xhr.status < 200 || xhr.status > 599)) {
        options.status = 200;
      } else {
        options.status = xhr.status;
      }
      options.url = "responseURL" in xhr ? xhr.responseURL : options.headers.get("X-Request-URL");
      var body = "response" in xhr ? xhr.response : xhr.responseText;
      setTimeout(function() {
        resolve(new Response(body, options));
      }, 0);
    };
    xhr.onerror = function() {
      setTimeout(function() {
        reject(new TypeError("Network request failed"));
      }, 0);
    };
    xhr.ontimeout = function() {
      setTimeout(function() {
        reject(new TypeError("Network request timed out"));
      }, 0);
    };
    xhr.onabort = function() {
      setTimeout(function() {
        reject(new DOMException("Aborted", "AbortError"));
      }, 0);
    };
    function fixUrl(url) {
      try {
        return url === "" && g.location.href ? g.location.href : url;
      } catch (e) {
        return url;
      }
    }
    xhr.open(request.method, fixUrl(request.url), true);
    if (request.credentials === "include") {
      xhr.withCredentials = true;
    } else if (request.credentials === "omit") {
      xhr.withCredentials = false;
    }
    if ("responseType" in xhr) {
      if (support.blob) {
        xhr.responseType = "blob";
      } else if (support.arrayBuffer) {
        xhr.responseType = "arraybuffer";
      }
    }
    if (init && typeof init.headers === "object" && !(init.headers instanceof Headers || g.Headers && init.headers instanceof g.Headers)) {
      var names = [];
      Object.getOwnPropertyNames(init.headers).forEach(function(name) {
        names.push(normalizeName(name));
        xhr.setRequestHeader(name, normalizeValue(init.headers[name]));
      });
      request.headers.forEach(function(value, name) {
        if (names.indexOf(name) === -1) {
          xhr.setRequestHeader(name, value);
        }
      });
    } else {
      request.headers.forEach(function(value, name) {
        xhr.setRequestHeader(name, value);
      });
    }
    if (request.signal) {
      request.signal.addEventListener("abort", abortXhr);
      xhr.onreadystatechange = function() {
        if (xhr.readyState === 4) {
          request.signal.removeEventListener("abort", abortXhr);
        }
      };
    }
    xhr.send(typeof request._bodyInit === "undefined" ? null : request._bodyInit);
  });
}
var g, support, viewClasses, isArrayBufferView, methods, redirectStatuses, DOMException;
var init_fetch = __esm({
  "node_modules/whatwg-fetch/fetch.js"() {
    g = typeof globalThis !== "undefined" && globalThis || typeof self !== "undefined" && self || // eslint-disable-next-line no-undef
    typeof global !== "undefined" && global || {};
    support = {
      searchParams: "URLSearchParams" in g,
      iterable: "Symbol" in g && "iterator" in Symbol,
      blob: "FileReader" in g && "Blob" in g && function() {
        try {
          new Blob();
          return true;
        } catch (e) {
          return false;
        }
      }(),
      formData: "FormData" in g,
      arrayBuffer: "ArrayBuffer" in g
    };
    if (support.arrayBuffer) {
      viewClasses = [
        "[object Int8Array]",
        "[object Uint8Array]",
        "[object Uint8ClampedArray]",
        "[object Int16Array]",
        "[object Uint16Array]",
        "[object Int32Array]",
        "[object Uint32Array]",
        "[object Float32Array]",
        "[object Float64Array]"
      ];
      isArrayBufferView = ArrayBuffer.isView || function(obj) {
        return obj && viewClasses.indexOf(Object.prototype.toString.call(obj)) > -1;
      };
    }
    Headers.prototype.append = function(name, value) {
      name = normalizeName(name);
      value = normalizeValue(value);
      var oldValue = this.map[name];
      this.map[name] = oldValue ? oldValue + ", " + value : value;
    };
    Headers.prototype["delete"] = function(name) {
      delete this.map[normalizeName(name)];
    };
    Headers.prototype.get = function(name) {
      name = normalizeName(name);
      return this.has(name) ? this.map[name] : null;
    };
    Headers.prototype.has = function(name) {
      return this.map.hasOwnProperty(normalizeName(name));
    };
    Headers.prototype.set = function(name, value) {
      this.map[normalizeName(name)] = normalizeValue(value);
    };
    Headers.prototype.forEach = function(callback, thisArg) {
      for (var name in this.map) {
        if (this.map.hasOwnProperty(name)) {
          callback.call(thisArg, this.map[name], name, this);
        }
      }
    };
    Headers.prototype.keys = function() {
      var items = [];
      this.forEach(function(value, name) {
        items.push(name);
      });
      return iteratorFor(items);
    };
    Headers.prototype.values = function() {
      var items = [];
      this.forEach(function(value) {
        items.push(value);
      });
      return iteratorFor(items);
    };
    Headers.prototype.entries = function() {
      var items = [];
      this.forEach(function(value, name) {
        items.push([name, value]);
      });
      return iteratorFor(items);
    };
    if (support.iterable) {
      Headers.prototype[Symbol.iterator] = Headers.prototype.entries;
    }
    methods = ["CONNECT", "DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"];
    Request.prototype.clone = function() {
      return new Request(this, { body: this._bodyInit });
    };
    Body.call(Request.prototype);
    Body.call(Response.prototype);
    Response.prototype.clone = function() {
      return new Response(this._bodyInit, {
        status: this.status,
        statusText: this.statusText,
        headers: new Headers(this.headers),
        url: this.url
      });
    };
    Response.error = function() {
      var response = new Response(null, { status: 200, statusText: "" });
      response.ok = false;
      response.status = 0;
      response.type = "error";
      return response;
    };
    redirectStatuses = [301, 302, 303, 307, 308];
    Response.redirect = function(url, status) {
      if (redirectStatuses.indexOf(status) === -1) {
        throw new RangeError("Invalid status code");
      }
      return new Response(null, { status, headers: { location: url } });
    };
    DOMException = g.DOMException;
    try {
      new DOMException();
    } catch (err) {
      DOMException = function(message, name) {
        this.message = message;
        this.name = name;
        var error = Error(message);
        this.stack = error.stack;
      };
      DOMException.prototype = Object.create(Error.prototype);
      DOMException.prototype.constructor = DOMException;
    }
    fetch.polyfill = true;
    if (!g.fetch) {
      g.fetch = fetch;
      g.Headers = Headers;
      g.Request = Request;
      g.Response = Response;
    }
  }
});

// node_modules/core-js/es/symbol/index.js
var require_symbol = __commonJS({
  "node_modules/core-js/es/symbol/index.js"(exports, module) {
    "use strict";
    require_es_array_concat();
    require_es_object_to_string();
    require_es_symbol();
    require_es_symbol_async_iterator();
    require_es_symbol_description();
    require_es_symbol_has_instance();
    require_es_symbol_is_concat_spreadable();
    require_es_symbol_iterator();
    require_es_symbol_match();
    require_es_symbol_match_all();
    require_es_symbol_replace();
    require_es_symbol_search();
    require_es_symbol_species();
    require_es_symbol_split();
    require_es_symbol_to_primitive();
    require_es_symbol_to_string_tag();
    require_es_symbol_unscopables();
    require_es_json_to_string_tag();
    require_es_math_to_string_tag();
    require_es_reflect_to_string_tag();
    var path = require_path();
    module.exports = path.Symbol;
  }
});

// node_modules/core-js/stable/symbol/index.js
var require_symbol2 = __commonJS({
  "node_modules/core-js/stable/symbol/index.js"(exports, module) {
    "use strict";
    var parent = require_symbol();
    require_web_dom_collections_iterator();
    module.exports = parent;
  }
});

// node_modules/core-js/modules/esnext.function.metadata.js
var require_esnext_function_metadata = __commonJS({
  "node_modules/core-js/modules/esnext.function.metadata.js"() {
    "use strict";
    var wellKnownSymbol = require_well_known_symbol();
    var defineProperty = require_object_define_property().f;
    var METADATA = wellKnownSymbol("metadata");
    var FunctionPrototype = Function.prototype;
    if (FunctionPrototype[METADATA] === void 0) {
      defineProperty(FunctionPrototype, METADATA, {
        value: null
      });
    }
  }
});

// node_modules/core-js/modules/esnext.symbol.async-dispose.js
var require_esnext_symbol_async_dispose = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.async-dispose.js"() {
    "use strict";
    var globalThis2 = require_global_this();
    var defineWellKnownSymbol = require_well_known_symbol_define();
    var defineProperty = require_object_define_property().f;
    var getOwnPropertyDescriptor = require_object_get_own_property_descriptor().f;
    var Symbol2 = globalThis2.Symbol;
    defineWellKnownSymbol("asyncDispose");
    if (Symbol2) {
      descriptor = getOwnPropertyDescriptor(Symbol2, "asyncDispose");
      if (descriptor.enumerable && descriptor.configurable && descriptor.writable) {
        defineProperty(Symbol2, "asyncDispose", { value: descriptor.value, enumerable: false, configurable: false, writable: false });
      }
    }
    var descriptor;
  }
});

// node_modules/core-js/modules/esnext.symbol.dispose.js
var require_esnext_symbol_dispose = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.dispose.js"() {
    "use strict";
    var globalThis2 = require_global_this();
    var defineWellKnownSymbol = require_well_known_symbol_define();
    var defineProperty = require_object_define_property().f;
    var getOwnPropertyDescriptor = require_object_get_own_property_descriptor().f;
    var Symbol2 = globalThis2.Symbol;
    defineWellKnownSymbol("dispose");
    if (Symbol2) {
      descriptor = getOwnPropertyDescriptor(Symbol2, "dispose");
      if (descriptor.enumerable && descriptor.configurable && descriptor.writable) {
        defineProperty(Symbol2, "dispose", { value: descriptor.value, enumerable: false, configurable: false, writable: false });
      }
    }
    var descriptor;
  }
});

// node_modules/core-js/modules/esnext.symbol.metadata.js
var require_esnext_symbol_metadata = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.metadata.js"() {
    "use strict";
    var defineWellKnownSymbol = require_well_known_symbol_define();
    defineWellKnownSymbol("metadata");
  }
});

// node_modules/core-js/actual/symbol/index.js
var require_symbol3 = __commonJS({
  "node_modules/core-js/actual/symbol/index.js"(exports, module) {
    "use strict";
    var parent = require_symbol2();
    require_esnext_function_metadata();
    require_esnext_symbol_async_dispose();
    require_esnext_symbol_dispose();
    require_esnext_symbol_metadata();
    module.exports = parent;
  }
});

// node_modules/core-js/internals/symbol-is-registered.js
var require_symbol_is_registered = __commonJS({
  "node_modules/core-js/internals/symbol-is-registered.js"(exports, module) {
    "use strict";
    var getBuiltIn = require_get_built_in();
    var uncurryThis = require_function_uncurry_this();
    var Symbol2 = getBuiltIn("Symbol");
    var keyFor = Symbol2.keyFor;
    var thisSymbolValue = uncurryThis(Symbol2.prototype.valueOf);
    module.exports = Symbol2.isRegisteredSymbol || function isRegisteredSymbol(value) {
      try {
        return keyFor(thisSymbolValue(value)) !== void 0;
      } catch (error) {
        return false;
      }
    };
  }
});

// node_modules/core-js/modules/esnext.symbol.is-registered-symbol.js
var require_esnext_symbol_is_registered_symbol = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.is-registered-symbol.js"() {
    "use strict";
    var $ = require_export();
    var isRegisteredSymbol = require_symbol_is_registered();
    $({ target: "Symbol", stat: true }, {
      isRegisteredSymbol
    });
  }
});

// node_modules/core-js/internals/symbol-is-well-known.js
var require_symbol_is_well_known = __commonJS({
  "node_modules/core-js/internals/symbol-is-well-known.js"(exports, module) {
    "use strict";
    var shared = require_shared();
    var getBuiltIn = require_get_built_in();
    var uncurryThis = require_function_uncurry_this();
    var isSymbol = require_is_symbol();
    var wellKnownSymbol = require_well_known_symbol();
    var Symbol2 = getBuiltIn("Symbol");
    var $isWellKnownSymbol = Symbol2.isWellKnownSymbol;
    var getOwnPropertyNames = getBuiltIn("Object", "getOwnPropertyNames");
    var thisSymbolValue = uncurryThis(Symbol2.prototype.valueOf);
    var WellKnownSymbolsStore = shared("wks");
    for (i = 0, symbolKeys = getOwnPropertyNames(Symbol2), symbolKeysLength = symbolKeys.length; i < symbolKeysLength; i++) {
      try {
        symbolKey = symbolKeys[i];
        if (isSymbol(Symbol2[symbolKey]))
          wellKnownSymbol(symbolKey);
      } catch (error) {
      }
    }
    var symbolKey;
    var i;
    var symbolKeys;
    var symbolKeysLength;
    module.exports = function isWellKnownSymbol(value) {
      if ($isWellKnownSymbol && $isWellKnownSymbol(value))
        return true;
      try {
        var symbol = thisSymbolValue(value);
        for (var j = 0, keys = getOwnPropertyNames(WellKnownSymbolsStore), keysLength = keys.length; j < keysLength; j++) {
          if (WellKnownSymbolsStore[keys[j]] == symbol)
            return true;
        }
      } catch (error) {
      }
      return false;
    };
  }
});

// node_modules/core-js/modules/esnext.symbol.is-well-known-symbol.js
var require_esnext_symbol_is_well_known_symbol = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.is-well-known-symbol.js"() {
    "use strict";
    var $ = require_export();
    var isWellKnownSymbol = require_symbol_is_well_known();
    $({ target: "Symbol", stat: true, forced: true }, {
      isWellKnownSymbol
    });
  }
});

// node_modules/core-js/modules/esnext.symbol.custom-matcher.js
var require_esnext_symbol_custom_matcher = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.custom-matcher.js"() {
    "use strict";
    var defineWellKnownSymbol = require_well_known_symbol_define();
    defineWellKnownSymbol("customMatcher");
  }
});

// node_modules/core-js/modules/esnext.symbol.observable.js
var require_esnext_symbol_observable = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.observable.js"() {
    "use strict";
    var defineWellKnownSymbol = require_well_known_symbol_define();
    defineWellKnownSymbol("observable");
  }
});

// node_modules/core-js/modules/esnext.symbol.is-registered.js
var require_esnext_symbol_is_registered = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.is-registered.js"() {
    "use strict";
    var $ = require_export();
    var isRegisteredSymbol = require_symbol_is_registered();
    $({ target: "Symbol", stat: true, name: "isRegisteredSymbol" }, {
      isRegistered: isRegisteredSymbol
    });
  }
});

// node_modules/core-js/modules/esnext.symbol.is-well-known.js
var require_esnext_symbol_is_well_known = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.is-well-known.js"() {
    "use strict";
    var $ = require_export();
    var isWellKnownSymbol = require_symbol_is_well_known();
    $({ target: "Symbol", stat: true, name: "isWellKnownSymbol", forced: true }, {
      isWellKnown: isWellKnownSymbol
    });
  }
});

// node_modules/core-js/modules/esnext.symbol.matcher.js
var require_esnext_symbol_matcher = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.matcher.js"() {
    "use strict";
    var defineWellKnownSymbol = require_well_known_symbol_define();
    defineWellKnownSymbol("matcher");
  }
});

// node_modules/core-js/modules/esnext.symbol.metadata-key.js
var require_esnext_symbol_metadata_key = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.metadata-key.js"() {
    "use strict";
    var defineWellKnownSymbol = require_well_known_symbol_define();
    defineWellKnownSymbol("metadataKey");
  }
});

// node_modules/core-js/modules/esnext.symbol.pattern-match.js
var require_esnext_symbol_pattern_match = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.pattern-match.js"() {
    "use strict";
    var defineWellKnownSymbol = require_well_known_symbol_define();
    defineWellKnownSymbol("patternMatch");
  }
});

// node_modules/core-js/modules/esnext.symbol.replace-all.js
var require_esnext_symbol_replace_all = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.replace-all.js"() {
    "use strict";
    var defineWellKnownSymbol = require_well_known_symbol_define();
    defineWellKnownSymbol("replaceAll");
  }
});

// node_modules/core-js/full/symbol/index.js
var require_symbol4 = __commonJS({
  "node_modules/core-js/full/symbol/index.js"(exports, module) {
    "use strict";
    var parent = require_symbol3();
    require_esnext_symbol_is_registered_symbol();
    require_esnext_symbol_is_well_known_symbol();
    require_esnext_symbol_custom_matcher();
    require_esnext_symbol_observable();
    require_esnext_symbol_is_registered();
    require_esnext_symbol_is_well_known();
    require_esnext_symbol_matcher();
    require_esnext_symbol_metadata_key();
    require_esnext_symbol_pattern_match();
    require_esnext_symbol_replace_all();
    module.exports = parent;
  }
});

// node_modules/core-js/features/symbol/index.js
var require_symbol5 = __commonJS({
  "node_modules/core-js/features/symbol/index.js"(exports, module) {
    "use strict";
    module.exports = require_symbol4();
  }
});

// node_modules/core-js/es/array/from.js
var require_from = __commonJS({
  "node_modules/core-js/es/array/from.js"(exports, module) {
    "use strict";
    require_es_string_iterator();
    require_es_array_from();
    var path = require_path();
    module.exports = path.Array.from;
  }
});

// node_modules/core-js/stable/array/from.js
var require_from2 = __commonJS({
  "node_modules/core-js/stable/array/from.js"(exports, module) {
    "use strict";
    var parent = require_from();
    module.exports = parent;
  }
});

// node_modules/core-js/actual/array/from.js
var require_from3 = __commonJS({
  "node_modules/core-js/actual/array/from.js"(exports, module) {
    "use strict";
    var parent = require_from2();
    module.exports = parent;
  }
});

// node_modules/core-js/full/array/from.js
var require_from4 = __commonJS({
  "node_modules/core-js/full/array/from.js"(exports, module) {
    "use strict";
    var parent = require_from3();
    module.exports = parent;
  }
});

// node_modules/core-js/features/array/from.js
var require_from5 = __commonJS({
  "node_modules/core-js/features/array/from.js"(exports, module) {
    "use strict";
    module.exports = require_from4();
  }
});

// node_modules/react-app-polyfill/ie11.js
if (typeof Promise === "undefined") {
  require_rejection_tracking().enable();
  self.Promise = require_es6_extensions();
}
if (typeof window !== "undefined") {
  init_fetch();
}
Object.assign = require_object_assign();
require_symbol5();
require_from5();
//# sourceMappingURL=react-app-polyfill_ie11.js.map
