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
      ...rest
    } = options as Record<string, unknown> & {
      headers?: Record<string, string>;
    };

    return axios({
      baseURL:
        process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000",
      url,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...customHeaders,
      },
      ...rest,
    });
  };

  return apiCall;
};
