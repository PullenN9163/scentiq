export type ThemePreference = "system" | "light" | "dark";

// Shared by the server layout and browser fixtures. Keep this module outside
// client boundaries so the layout emits the literal script before paint.
export const themeInitScript = `(function(){try{var m=document.cookie.match(/(?:^|; )scentiq-theme=(light|dark|system)(?:;|$)/);var p=m?m[1]:"system";document.documentElement.dataset.theme=p==="system"?(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"):p;}catch(e){}})();`;
