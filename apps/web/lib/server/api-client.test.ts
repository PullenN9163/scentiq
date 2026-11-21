import {afterEach,expect,it,vi} from "vitest";
vi.mock("server-only",()=>({}));
vi.mock("@clerk/nextjs/server",()=>({auth:async()=>({getToken:async()=>"test-token"})}));
import {apiClient} from "./api-client";
afterEach(()=>{vi.unstubAllGlobals();vi.unstubAllEnvs();vi.restoreAllMocks();});
it("keeps ordinary reads at ten seconds and applies an explicit discovery deadline",async()=>{
  vi.stubEnv("API_INTERNAL_URL","https://api.example.test");
  const timeout=vi.spyOn(AbortSignal,"timeout");
  vi.stubGlobal("fetch",vi.fn().mockImplementation(async()=>new Response("[]")));
  await apiClient.get("/ordinary");
  expect(timeout).toHaveBeenLastCalledWith(10000);
  await apiClient.get("/api/v1/discover",{timeoutMs:60000});
  expect(timeout).toHaveBeenLastCalledWith(60000);
  timeout.mockRestore();
});
it("distinguishes elapsed deadlines from service connectivity failures",async()=>{
  vi.stubEnv("API_INTERNAL_URL","https://api.example.test");
  vi.stubGlobal("fetch",vi.fn().mockRejectedValue(new DOMException("timed out","TimeoutError")));
  await expect(apiClient.get("/timeout")).rejects.toMatchObject({kind:"unavailable",code:"service_timeout"});
  vi.stubGlobal("fetch",vi.fn().mockRejectedValue(new TypeError("network")));
  await expect(apiClient.get("/offline")).rejects.toMatchObject({code:"service_unreachable"});
});
