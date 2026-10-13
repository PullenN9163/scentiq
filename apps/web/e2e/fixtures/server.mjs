// Isolated browser fixtures use the shipped React views and styles with deterministic service doubles.
// This server is test-only and never bypasses authentication in the Next.js application.
import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
import react from '@vitejs/plugin-react';
const require=createRequire(import.meta.url);
const viteRequire=createRequire(require.resolve('vitest'));
const {createServer}=await import(pathToFileURL(viteRequire.resolve('vite')).href);
const dir=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(dir,'../..');
const serviceDoubles={
  name:'service-doubles', enforce:'pre',
  resolveId(source) {
    if(source.startsWith('\0')) return;
    if(source.includes('/lib/server/')) {
      let absolute=source.startsWith('@/')?path.join(root,source.slice(2)):source;
      if(!absolute.endsWith('.ts')) absolute+='.ts';
      return '\0service:'+absolute;
    }
  },
  load(id) {
    if(!id.startsWith('\0service:')) return;
    const source=readFileSync(id.slice(9),'utf8');
    const names=[...source.matchAll(/export (?:async )?function (\w+)/g)].map(match=>match[1]);
    return names.map(name=>`export async function ${name}(...args) { ${name==='searchCatalogPage'?'throw new Error("Fixture pagination unavailable");':name==='getWearFeedback'?'return null;':name==='wearRecommendation'?'return {ok:true,data:{id:"fixture-wear"}};':name==='decideRecommendation'?'return {ok:true,data:{}};':name.startsWith('search') || name.startsWith('get')?'return [];':'return {status:"error",message:"Fixture save failed. Your values are preserved.",values:Object.fromEntries(args.find(value=>value instanceof FormData)??[])};'} }`).join('\n');
  },
};
const server=await createServer({
  configFile:false, root:dir, cacheDir:path.join(root,'node_modules/.vite-visual'),
  plugins:[serviceDoubles,react()],
  resolve:{alias:{'@':root,'next/link':path.join(dir,'next-link.tsx'),'next/image':path.join(dir,'next-image.tsx'),'next/navigation':path.join(dir,'next-navigation.ts'),'@clerk/nextjs':path.join(dir,'clerk.tsx')}},
  server:{host:'127.0.0.1',port:3100,strictPort:true,fs:{allow:[root]}},
});
await server.listen();
console.log('ScentIQ browser fixtures: http://127.0.0.1:3100');
