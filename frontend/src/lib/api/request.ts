import { ApiRequestError, parseApiErrorBody } from "./errors";
import { getApiBaseUrl } from "./config";

export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  return fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...init.headers,
    },
  });
}

export async function readJsonResponse<T>(
  response: Response,
  validate: (value: unknown) => value is T,
  fallbackMessage: string,
): Promise<T> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const message =
      parseApiErrorBody(body) ??
      (response.status === 404
        ? "We couldn't find that on the server."
        : fallbackMessage);
    throw new ApiRequestError(message, response.status);
  }

  if (!validate(body)) {
    throw new ApiRequestError("Unexpected response from the server.");
  }

  return body;
}

export async function apiJson<T>(
  path: string,
  init: RequestInit,
  validate: (value: unknown) => value is T,
  fallbackMessage: string,
): Promise<T> {
  const response = await apiFetch(path, init);
  return readJsonResponse(response, validate, fallbackMessage);
}
