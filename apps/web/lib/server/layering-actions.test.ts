import {expect,it,vi} from "vitest";
const get=vi.hoisted(()=>vi.fn().mockResolvedValue([]));
vi.mock("@/lib/server/api-client",()=>({apiClient:{get}}));
vi.mock("next/cache",()=>({revalidatePath:vi.fn()}));
import {getDiscoveryIntelligence} from "./layering-actions";
it("gives source-backed discovery a bounded deadline that accommodates measured cold requests",async()=>{
  await getDiscoveryIntelligence({mode:"explore",season:"fall"});
  expect(get).toHaveBeenCalledWith("/api/v1/discover?mode=explore&season=fall",{timeoutMs:60000});
});
