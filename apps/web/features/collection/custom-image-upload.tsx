"use client";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

export function CustomImageUpload({ fragranceId, hasImage }: { fragranceId: string; hasImage: boolean }) {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { if (preview) return () => URL.revokeObjectURL(preview); }, [preview]);
  const mutate = async (method: "PUT" | "DELETE") => {
    setBusy(true);
    try {
      const response = await fetch(`/api/fragrances/${fragranceId}/image`, { method, headers: file && method === "PUT" ? { "Content-Type": file.type } : {}, body: method === "PUT" ? file : undefined });
      if (!response.ok) { const error = await response.json() as { message?: string }; throw new Error(error.message ?? "Image could not be saved."); }
      setFile(null); setPreview(null); if (input.current) input.current.value = ""; toast.success(method === "PUT" ? "Image saved." : "Image removed."); router.refresh();
    } catch (error) { toast.error(error instanceof Error ? error.message : "Image could not be saved."); }
    finally { setBusy(false); }
  };
  return <div className="custom-image-upload stack"><label className="field"><span className="label">Custom fragrance image</span><input ref={input} type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={(event) => { const selected = event.target.files?.[0]; if (!selected) return; if (selected.size > 5 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(selected.type)) { toast.error("Choose a JPEG, PNG, or WebP image up to 5 MB."); event.target.value = ""; return; } setFile(selected); setPreview(URL.createObjectURL(selected)); }} /><span className="field-hint">JPEG, PNG, or WebP · maximum 5 MB</span></label>{preview && <Image src={preview} width={150} height={180} alt="Selected image preview" unoptimized />}<div className="cluster"><Button disabled={!file || busy} onClick={() => void mutate("PUT")}>{busy ? "Saving image…" : hasImage ? "Replace image" : "Upload image"}</Button>{hasImage && <Button variant="ghost" disabled={busy} onClick={() => void mutate("DELETE")}>Remove image</Button>}</div>{busy && <p role="status">Processing your image…</p>}</div>;
}
