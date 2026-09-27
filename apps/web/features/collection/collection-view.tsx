"use client";

import { Plus, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { AddFragranceDialog } from "@/features/collection/add-fragrance-dialog";
import { CatalogImage } from "@/components/catalog-image";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { CollectionItem, FragranceSummary } from "@/types/api";

/**
 * The collection screen, backed by persisted data.
 *
 * Filtering and sorting stay client-side over the already-fetched collection,
 * which keeps the interaction immediate; the catalog search inside the add
 * dialog queries the service.
 */

const OWNERSHIP_LABELS: Record<string, string> = {
  bottle: "Bottle",
  decant: "Decant",
  sample: "Sample",
};

const STATUS_LABELS: Record<string, string> = {
  owned: "Owned",
  wishlist: "Wishlist",
  finished: "Finished",
  sold: "Sold",
};

export function CollectionView({
  items,
  catalog,
}: {
  items: CollectionItem[];
  catalog: FragranceSummary[];
}) {
  const [query, setQuery] = useState("");
  const [ownership, setOwnership] = useState("all");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState("rating");
  const [addOpen, setAddOpen] = useState(false);

  const counts = useMemo(() => {
    const result: Record<string, number> = {};
    for (const item of items) {
      result[item.ownership_type] = (result[item.ownership_type] ?? 0) + 1;
    }
    return result;
  }, [items]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return items
      .filter((item) => {
        const label = `${item.fragrance.brand.name} ${item.fragrance.name}`.toLowerCase();
        return (
          label.includes(needle) &&
          (ownership === "all" || item.ownership_type === ownership) &&
          (status === "all" || item.status === status)
        );
      })
      .sort((first, second) => {
        if (sort === "name") {
          return first.fragrance.name.localeCompare(second.fragrance.name);
        }
        // Unrated items sort last rather than as zero.
        return (second.user_rating ?? -1) - (first.user_rating ?? -1);
      });
  }, [items, query, ownership, status, sort]);

  const description = items.length
    ? `${items.length} in your collection · ${counts.bottle ?? 0} bottles · ${counts.decant ?? 0} decants · ${counts.sample ?? 0} samples`
    : "Nothing saved yet.";

  return (
    <section className="page">
      <PageHeader
        eyebrow="Your wardrobe"
        title="Collection"
        description={description}
        action={
          <Button onClick={() => setAddOpen(true)}>
            <Plus size={17} />
            Add fragrance
          </Button>
        }
      />

      {items.length > 0 ? (
        <div className="collection-tools">
          <label className="search-field">
            <Search size={18} />
            <span className="sr-only">Search collection</span>
            <input
              type="search"
              aria-label="Search collection"
              placeholder="Search brand or fragrance"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <label>
            <span>Ownership</span>
            <select
              className="select"
              value={ownership}
              onChange={(event) => setOwnership(event.target.value)}
            >
              <option value="all">All</option>
              <option value="bottle">Bottle</option>
              <option value="decant">Decant</option>
              <option value="sample">Sample</option>
            </select>
          </label>
          <label>
            <span>Status</span>
            <select
              className="select"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="all">All</option>
              <option value="owned">Owned</option>
              <option value="wishlist">Wishlist</option>
              <option value="finished">Finished</option>
              <option value="sold">Sold</option>
            </select>
          </label>
          <label>
            <span>Sort</span>
            <select className="select" value={sort} onChange={(event) => setSort(event.target.value)}>
              <option value="rating">Highest rated</option>
              <option value="name">Name</option>
            </select>
          </label>
        </div>
      ) : null}

      {visible.length > 0 ? (
        <div className="fragrance-grid">
          {visible.map((item) => (
            <Card key={item.id} className="fragrance-card" data-testid="fragrance-card">
              <Link
                href={`/collection/${item.fragrance.id}`}
                aria-label={`Open ${item.fragrance.name}`}
              >
                <CatalogImage className="fragrance-card__art" id={item.fragrance.id} name={item.fragrance.name} brand={item.fragrance.brand.name} imageUrl={item.fragrance.image_url} />
                <CardContent>
                  <div className="cluster">
                    <Badge>{OWNERSHIP_LABELS[item.ownership_type] ?? item.ownership_type}</Badge>
                    <span className="rating">
                      {item.user_rating === null ? "Not rated" : `★ ${item.user_rating}`}
                    </span>
                  </div>
                  <h2 className="serif">{item.fragrance.name}</h2>
                  <p>
                    {item.fragrance.brand.name} · {item.fragrance.concentration ?? "Concentration unknown"}
                  </p>
                  <div className="cluster">
                    {item.status !== "owned" ? (
                      <Badge>{STATUS_LABELS[item.status] ?? item.status}</Badge>
                    ) : null}
                    {item.fragrance.is_custom ? <Badge>Custom</Badge> : null}
                  </div>
                  <small>
                    {item.remaining_ml !== null && item.bottle_size_ml !== null
                      ? `${item.remaining_ml}ml of ${item.bottle_size_ml}ml remaining`
                      : "No volume recorded"}
                  </small>
                </CardContent>
              </Link>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          title={items.length ? "No fragrances found" : "Start your fragrance wardrobe"}
          description={
            items.length
              ? "Try a broader search or clear the filters."
              : "Add your first bottle, decant, or sample to start tracking wears and insights."
          }
          action={
            <Button
              variant="secondary"
              onClick={() => {
                if (items.length) {
                  setQuery("");
                  setOwnership("all");
                  setStatus("all");
                } else {
                  setAddOpen(true);
                }
              }}
            >
              {items.length ? "Clear filters" : "Add first fragrance"}
            </Button>
          }
        />
      )}

      <AddFragranceDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        catalog={catalog}
        ownedFragranceIds={items.map((item) => item.fragrance.id)}
      />
    </section>
  );
}
