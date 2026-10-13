export const usePathname = () => new URLSearchParams(location.search).get("view") === "today" ? "/dashboard" : `/${new URLSearchParams(location.search).get("view") ?? "dashboard"}`;
export const useRouter = () => ({refresh:()=>{},push:(href:string)=>location.assign(href),replace:(href:string)=>location.replace(href)});
