"use server";
import { apiClient } from "./api-client";
import type { CollectionItem } from "@/types/api";
export async function searchOwnCollection(query: string): Promise<{ id: string; name: string; brand: string }[]> {
  const items = await apiClient.get<CollectionItem[]>("/api/v1/collection");
  const needle = query.slice(0, 120).trim().toLowerCase();
  return items.filter((item) => `${item.fragrance.name} ${item.fragrance.brand.name}`.toLowerCase().includes(needle)).slice(0, 12).map(({ fragrance }) => ({ id: fragrance.id, name: fragrance.name, brand: fragrance.brand.name }));
}
