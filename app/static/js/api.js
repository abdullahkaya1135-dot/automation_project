export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export async function apiJson(path, options = {}) {
  const fetchOptions = {
    method: options.method || "GET",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(options.headers || {}),
    },
  };

  if (options.body !== undefined) {
    fetchOptions.headers["Content-Type"] = "application/json";
    fetchOptions.body = JSON.stringify(options.body);
  }

  const response = await fetch(path, fetchOptions);
  const payload = await readJsonResponse(response);

  if (response.status === 401) {
    if (options.redirectOnAuth !== false) {
      window.location.assign("/login");
    }
    throw new ApiError("Oturum açmanız gerekiyor.", response.status, payload);
  }

  if (!response.ok) {
    throw new ApiError(
      errorMessageFromPayload(payload, response.statusText),
      response.status,
      payload,
    );
  }

  return payload;
}

async function readJsonResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return response.json();
}

function errorMessageFromPayload(payload, fallback) {
  if (!payload || payload.detail === undefined) {
    return fallback || "İstek başarısız.";
  }

  if (typeof payload.detail === "string") {
    return payload.detail;
  }

  if (Array.isArray(payload.detail)) {
    return payload.detail
      .map((item) => {
        if (item && typeof item === "object" && item.msg) {
          return item.msg;
        }
        return String(item);
      })
      .join(" ");
  }

  return JSON.stringify(payload.detail);
}
