import { ApiStatus } from "@/components/api-status";
import { PageHeader } from "@/components/shared/page-header";
export default function SettingsPage() { return <section className="page"><PageHeader eyebrow="Make it yours" title="Settings" description="Preferences are local demo controls for now." /><div className="settings-status"><h2>System</h2><ApiStatus /></div></section>; }
