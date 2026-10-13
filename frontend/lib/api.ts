import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api",
});

export async function getHealth(): Promise<{ status: string; message: string }> {
  const res = await api.get("/health");
  return res.data;
}

export default api;
