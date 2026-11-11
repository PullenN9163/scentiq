import { expect, it } from "vitest";
import DiscoverPage from "./page";

it("renders a query shell without blocking on collection or recommendations", async()=>{
  const element=await DiscoverPage({searchParams:Promise.resolve({q:"  cedar  ".repeat(20),mode:"seasonal",season:"fall",family:"Woody",gender:"unisex",minimum_value:"4"})});
  expect(element.props).toMatchObject({liveMode:true,query:"  cedar  ".repeat(20).slice(0,120),mode:"seasonal",selectedSeason:"fall",selectedFamily:"Woody",selectedGender:"unisex",selectedMinimumValue:"4",results:[]});
});

it("normalizes unsupported modes and preserves the initial search query",async()=>{
  const element=await DiscoverPage({searchParams:Promise.resolve({q:"amber",mode:"legacy"})});
  expect(element.props).toMatchObject({liveMode:true,query:"amber",mode:"balance"});
});
