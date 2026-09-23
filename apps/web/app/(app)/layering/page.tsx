import { LayeringLab } from "@/features/layering/layering-lab";
export default async function LayeringPage({ searchParams }: { searchParams: Promise<{ a?: string }> }) { const { a } = await searchParams; return <LayeringLab initialA={a} />; }
