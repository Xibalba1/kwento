const API_BASE_URL =
  process.env.REACT_APP_API_BASE_URL || "http://localhost:8000";

const normalizeBaseUrl = (url) => url.replace(/\/+$/, "");

export const buildApiUrl = (path) => {
  const normalizedBaseUrl = normalizeBaseUrl(API_BASE_URL);
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBaseUrl}${normalizedPath}`;
};
