const DEBUG_QUERY_PARAM = "kwentoDebugImages";
const DEBUG_STORAGE_KEY = "kwentoDebugImages";
const MAX_EVENTS = 500;

const hasWindow = typeof window !== "undefined";

let cachedSessionId = null;

const safeNow = () => {
  if (typeof performance !== "undefined" && typeof performance.now === "function") {
    return performance.now();
  }

  return Date.now();
};

const readSearchParam = () => {
  if (!hasWindow || !window.location?.search) {
    return null;
  }

  try {
    const params = new URLSearchParams(window.location.search);
    return params.get(DEBUG_QUERY_PARAM);
  } catch (error) {
    return null;
  }
};

const readStorageFlag = () => {
  if (!hasWindow || !window.localStorage) {
    return null;
  }

  try {
    return window.localStorage.getItem(DEBUG_STORAGE_KEY);
  } catch (error) {
    return null;
  }
};

export const isImageDebugEnabled = () => {
  const queryValue = readSearchParam();
  if (queryValue === "1" || queryValue === "true") {
    return true;
  }

  const storageValue = readStorageFlag();
  return storageValue === "1" || storageValue === "true";
};

const getSessionId = () => {
  if (cachedSessionId) {
    return cachedSessionId;
  }

  cachedSessionId = `imgdbg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  return cachedSessionId;
};

const ensureStore = () => {
  if (!hasWindow) {
    return null;
  }

  if (!window.__kwentoImageDebug) {
    window.__kwentoImageDebug = {
      sessionId: getSessionId(),
      events: [],
      dump() {
        return [...this.events];
      },
      clear() {
        this.events.length = 0;
      },
    };
  }

  return window.__kwentoImageDebug;
};

const sanitizeValue = (value, depth = 0) => {
  if (depth > 3) {
    return "[depth-limited]";
  }

  if (
    value == null ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return value;
  }

  if (Array.isArray(value)) {
    return value.slice(0, 20).map((entry) => sanitizeValue(entry, depth + 1));
  }

  if (value instanceof Error) {
    return {
      name: value.name,
      message: value.message,
    };
  }

  if (typeof Blob !== "undefined" && value instanceof Blob) {
    return {
      type: "Blob",
      size: value.size,
      mimeType: value.type,
    };
  }

  if (typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .slice(0, 30)
        .map(([key, entryValue]) => [key, sanitizeValue(entryValue, depth + 1)]),
    );
  }

  return String(value);
};

export const logImageEvent = (event, payload = {}) => {
  if (!isImageDebugEnabled()) {
    return;
  }

  const store = ensureStore();
  if (!store) {
    return;
  }

  const record = {
    session_id: store.sessionId,
    ts: Date.now(),
    perf_ts: safeNow(),
    event,
    ...sanitizeValue(payload),
  };

  store.events.push(record);
  if (store.events.length > MAX_EVENTS) {
    store.events.splice(0, store.events.length - MAX_EVENTS);
  }

  if (typeof console !== "undefined" && typeof console.debug === "function") {
    console.debug("[imageDebug]", record);
  }
};

export const getImageDebugPageContext = () => {
  if (!hasWindow) {
    return {};
  }

  const connection = navigator.connection ?? navigator.mozConnection ?? navigator.webkitConnection;
  return {
    href: window.location?.href ?? null,
    visibility_state: document.visibilityState,
    viewport: {
      width: window.innerWidth ?? null,
      height: window.innerHeight ?? null,
      device_pixel_ratio: window.devicePixelRatio ?? null,
    },
    user_agent: navigator.userAgent ?? null,
    network: connection
      ? {
          effective_type: connection.effectiveType ?? null,
          downlink: connection.downlink ?? null,
          rtt: connection.rtt ?? null,
          save_data: connection.saveData ?? null,
        }
      : null,
  };
};
