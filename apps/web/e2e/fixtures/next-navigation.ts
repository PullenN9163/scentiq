// Atelier fixture views name their route with ?path=, since view names such as "today-atelier" are not routes.
const pagePaths: Record<string,string> = {today:"/dashboard","today-atelier":"/dashboard","week-atelier":"/week","collection-atelier":"/collection",blends:"/collection",sheet:"/collection",fragrance:"/collection/fixture","discover-atelier":"/discover","insights-atelier":"/insights","settings-atelier":"/settings",blend:"/layering","agent-atelier":"/agent"};
export const usePathname = () => { const params = new URLSearchParams(location.search); const view = params.get("view") ?? "dashboard"; return params.get("path") ?? pagePaths[view] ?? `/${view}`; };
export const useRouter = () => ({refresh:()=>{},push:(href:string)=>location.assign(href),replace:(href:string)=>location.replace(href),back:()=>history.back()});
export const useSearchParams = () => new URLSearchParams(location.search);
export const notFound = () => { throw new Error("Not found"); };
