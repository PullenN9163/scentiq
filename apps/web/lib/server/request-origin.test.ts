// @vitest-environment node
import {afterEach,expect,it,vi} from "vitest";
import {hasApplicationOrigin} from "./request-origin";
afterEach(()=>vi.unstubAllEnvs());
it("uses configured public origin and ignores spoofed forwarded headers",()=>{
 vi.stubEnv("PUBLIC_APP_URL","https://app.example");
 expect(hasApplicationOrigin(new Request("http://internal:3000/api",{headers:{origin:"https://app.example"}}))).toBe(true);
 expect(hasApplicationOrigin(new Request("http://internal:3000/api",{headers:{origin:"https://evil.example","x-forwarded-host":"evil.example","x-forwarded-proto":"https"}}))).toBe(false);
 expect(hasApplicationOrigin(new Request("http://internal:3000/api"))).toBe(false);
});
it("fails closed without configuration in production",()=>{
 vi.stubEnv("NODE_ENV","production");vi.stubEnv("PUBLIC_APP_URL","");
 expect(hasApplicationOrigin(new Request("https://app.example/api",{headers:{origin:"https://app.example"}}))).toBe(false);
});
