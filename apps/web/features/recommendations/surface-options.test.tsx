import {cleanup, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, it, vi} from "vitest";
import {discoveryResult} from "@/test/catalog-fixtures";
import {SurfaceOptions} from "./surface-options";
const choose=vi.hoisted(()=>vi.fn());
vi.mock("@/lib/server/surface-choice-actions",()=>({surfaceChoice:choose}));
afterEach(cleanup);
it("restores the saved option and advances with the server cursor",async()=>{
 const onChoice=vi.fn(); const result=discoveryResult();
 choose.mockResolvedValueOnce({ok:true,data:{batch_id:"batch",selected:result,candidate_id:result.fragrance.id,remaining_options:1,options_exhausted:false}});
 render(<SurfaceOptions surface="discovery" parameters={{mode:"taste"}} onChoice={onChoice}/>);
 await waitFor(()=>expect(onChoice).toHaveBeenCalledWith(result));
 choose.mockResolvedValueOnce({ok:true,data:{batch_id:"batch",selected:result,candidate_id:"next",remaining_options:0,options_exhausted:true}});
 await userEvent.setup().click(screen.getByRole("button",{name:"Another discovery"}));
 await waitFor(()=>expect(screen.getByRole("button",{name:"Start over"})).toBeVisible());
 expect(choose).toHaveBeenLastCalledWith("discovery",expect.objectContaining({batch_id:"batch",expected_candidate_id:result.fragrance.id,advance:true}));
});

it("refreshes an invalidated batch after preferences change",async()=>{
 const onChoice=vi.fn(); const result=discoveryResult();
 choose.mockResolvedValueOnce({ok:true,data:{batch_id:"old",selected:result,candidate_id:result.fragrance.id,remaining_options:1,options_exhausted:false}});
 render(<SurfaceOptions surface="discovery" parameters={{mode:"taste"}} onChoice={onChoice}/>);
 await waitFor(()=>expect(onChoice).toHaveBeenCalled());
 choose.mockResolvedValueOnce({ok:false,error:"Preferences changed",code:"batch_changed"});
 await userEvent.setup().click(screen.getByRole("button",{name:"Another discovery"}));
 expect(await screen.findByRole("alert")).toHaveTextContent("Preferences changed");
 choose.mockResolvedValueOnce({ok:true,data:{batch_id:"new",selected:result,candidate_id:result.fragrance.id,remaining_options:1,options_exhausted:false}});
 await userEvent.setup().click(screen.getByRole("button",{name:"Another discovery"}));
 await waitFor(()=>expect(choose).toHaveBeenLastCalledWith("discovery",expect.objectContaining({batch_id:undefined})));
});
