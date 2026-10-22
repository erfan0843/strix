// test-jsdom-interceptor.mjs
//
// Compatibility shim for Nora UI test suites running on jsdom >= 24.
// jsdom >= 24 removed:
//   - `jsdom.requestInterceptor` helper
//   - plain-object `resources: { interceptors: [...] }` option
//   - Response body handling that accepts a WHATWG Response directly
//
// This shim:
//   1. Re-exposes `jsdom.requestInterceptor(handler)` as an identity wrapper.
//   2. Provides InterceptingResourceLoader, a ResourceLoader subclass whose
//      fetch() runs interceptor handlers before falling back to the network.
//      Interceptors may return a WHATWG Response; it is converted to the
//      { data, type } shape jsdom 24's ResourceLoader.fetch expects.
//   3. Wraps JSDOM (constructor + JSDOM.fromFile/fromURL) so that
//      `resources: { interceptors: [...] }` is normalized into an
//      InterceptingResourceLoader before jsdom validates it.
//
// Usage (from the nora-ui directory):
//
//   NODE_OPTIONS=--import ./test-jsdom-interceptor.mjs \
//     node tools/run-unit-tests.cjs
//
// This file is part of the repository (test infrastructure). node_modules
// and any npm metadata are intentionally NOT committed.

import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

const jsdomModule = require("jsdom");

// ── 1. Re-expose requestInterceptor ──────────────────────────────────
if (typeof jsdomModule.requestInterceptor !== "function") {
  // Interceptors are (request) => Response | undefined, used directly.
  jsdomModule.requestInterceptor = (handler) => handler;
}

// ── 2. InterceptingResourceLoader ────────────────────────────────────
const { ResourceLoader, JSDOM: OriginalJSDOM } = jsdomModule;

async function responseToDataType(response) {
  const type = response.headers.get("content-type") || "text/html";
  const data = await response.text();
  return { data, type };
}

class InterceptingResourceLoader extends ResourceLoader {
  constructor(options = {}) {
    super(options);
    this._interceptors = Array.isArray(options.interceptors)
      ? options.interceptors
      : [];
  }

  // jsdom 24's RequestManager calls .abort() on in-flight requests when a
  // window is closed. Provide a no-op stub so suites can teardown cleanly.
  abort() {
    // Nothing to cancel — interceptors resolve immediately or fall through.
  }

  async fetch(urlString, init = {}) {
    const request = { url: urlString, ...init };
    for (const interceptor of this._interceptors) {
      try {
        const result = await interceptor(request);
        if (!result) continue;
        // A WHATWG Response — convert to jsdom's { data, type } shape.
        if (typeof Response !== "undefined" && result instanceof Response) {
          return responseToDataType(result);
        }
        // Already in { data, type } shape.
        if (result && typeof result === "object" && "data" in result) {
          return result;
        }
        // A string/Buffer — treat as data with default type.
        return { data: result, type: "text/html" };
      } catch (_) {
        // Interceptor threw — keep trying the rest.
      }
    }
    return super.fetch(urlString, init);
  }
}

// ── 3. Normalize resources option ────────────────────────────────────
function normalizeResources(options) {
  if (!options || typeof options !== "object") return options;
  const res = options.resources;
  if (
    res &&
    !(res instanceof ResourceLoader) &&
    Array.isArray(res.interceptors)
  ) {
    return {
      ...options,
      resources: new InterceptingResourceLoader({ interceptors: res.interceptors }),
    };
  }
  return options;
}

// ── 4. Wrap JSDOM constructor and static methods ─────────────────────
class InterceptingJSDOM extends OriginalJSDOM {
  constructor(html, options) {
    super(html, normalizeResources(options));
  }

  static fromFile(file, options) {
    return OriginalJSDOM.fromFile(file, normalizeResources(options));
  }

  static fromURL(url, options) {
    return OriginalJSDOM.fromURL(url, normalizeResources(options));
  }
}

jsdomModule.JSDOM = InterceptingJSDOM;
