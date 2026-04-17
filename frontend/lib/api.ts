import axios from "axios";
import { useAuth } from "@clerk/nextjs";

export const useApi = () => {
  const { getToken } = useAuth();

  const apiCall = async (url: string, options: any = {}) => {
    const token = await getToken();

    const { headers: customHeaders, ...rest } = options;

    return axios({
      baseURL: "http://localhost:8000",
      url,
      headers: {
        Authorization: `Bearer ${token}`,
        ...customHeaders,
      },
      ...rest,
    });
  };

  return apiCall;
};