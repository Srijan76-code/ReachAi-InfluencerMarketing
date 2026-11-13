import { BACKEND_URL } from "@/lib/backend";
import axios from "axios";
import { useAuth } from "@clerk/nextjs";

export const useApi = () => {
  const { getToken } = useAuth();

  const apiCall = async (
    url: string,
    options: Record<string, unknown> = {},
  ) => {
    let token: string | null = null;
    try {
      token = await getToken();
    } catch (error) {
      console.error("Unable to obtain Clerk session token:", error);
      throw new Error(
        "Your Clerk session could not be reached. Refresh the page and sign in again.",
        { cause: error },
      );
    }
    const {
      headers: customHeaders = {},
      data,
      body,
      ...rest
    } = options as Record<string, unknown> & {
      headers?: Record<string, string>;
      data?: unknown;
      body?: unknown;
    };

    let requestData = data;
    if (requestData === undefined && body !== undefined) {
      if (typeof body === "string") {
        try {
          requestData = JSON.parse(body);
        } catch {
          requestData = body;
        }
      } else {
        requestData = body;
      }
    }

    const send = (bearer: string | null) =>
      axios({
        baseURL:
          BACKEND_URL,
        url,
        data: requestData,
        headers: {
          ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}),
          ...customHeaders,
        },
        ...rest,
      });

    try {
      return await send(token);
    } catch (error) {
      // a session token can expire on the way (they last about a minute): get a fresh one and try once more
      const res = (error as { response?: { status?: number; data?: { detail?: unknown } } })?.response;
      if (res?.status === 401 && res.data?.detail === "Token has expired") {
        const fresh = await getToken({ skipCache: true }).catch(() => null);
        if (fresh) return send(fresh);
      }
      throw error;
    }
  };

  return apiCall;
};
