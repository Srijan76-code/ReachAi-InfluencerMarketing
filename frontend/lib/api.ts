import axios from "axios";
import { useAuth } from "@clerk/nextjs";

export const useApi = () => {
  const { getToken } = useAuth();

  const apiCall = async (
    url: string,
    options: Record<string, unknown> = {},
  ) => {
    const token = await getToken();
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
